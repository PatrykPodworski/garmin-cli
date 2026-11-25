import argparse
import difflib
import io
import sys
import zipfile
from collections.abc import Callable, Collection
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

from garminconnect import Garmin, GarminConnectNotFoundError

from garmin_cli.client import Connect, GarminClient
from garmin_cli.dates import add_range_arguments
from garmin_cli.errors import ISSUES, GarminCliError
from garmin_cli.output import NO_STDOUT

# Output name -> Garmin key. A list item and a detail `summaryDTO` name the
# aerobic training effect differently, so either key fills `aerobic_te`.
FIELDS = {
    "id": ("activityId",),
    "date": ("startTimeLocal",),
    "name": ("activityName",),
    "duration_s": ("duration",),
    "distance_m": ("distance",),
    "avg_hr": ("averageHR",),
    "max_hr": ("maxHR",),
    "elevation_gain_m": ("elevationGain",),
    "calories": ("calories",),
    "aerobic_te": ("aerobicTrainingEffect", "trainingEffect"),
    "anaerobic_te": ("anaerobicTrainingEffect",),
    "vo2max": ("vO2MaxValue",),
}

# `fit` is Garmin's original upload, a zip that holds one file.
DOWNLOAD_FORMATS = {
    "fit": Garmin.ActivityDownloadFormat.ORIGINAL,
    "gpx": Garmin.ActivityDownloadFormat.GPX,
    "tcx": Garmin.ActivityDownloadFormat.TCX,
    "kml": Garmin.ActivityDownloadFormat.KML,
    "csv": Garmin.ActivityDownloadFormat.CSV,
}


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        number = 0
    if number < 1:
        raise argparse.ArgumentTypeError(
            f"Invalid --limit '{value}'. Use a whole number of 1 or more."
        )
    return number


def nonblank_name(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError(
            f"Invalid --name '{value}'. Give a name that is not blank."
        )
    return value.strip()


def activity_id(value: str) -> str:
    try:
        number = int(value)
    except ValueError:
        number = 0
    if number < 1:
        raise argparse.ArgumentTypeError(
            f"Invalid activity ID '{value}'. Run 'garmin activities' to list IDs."
        )
    return str(number)


def download_format(value: str) -> str:
    if value not in DOWNLOAD_FORMATS:
        raise argparse.ArgumentTypeError(
            f"Invalid --format '{value}'. Use fit, gpx, tcx, kml or csv."
        )
    return value


def require_type(
    key: str, keys: Collection[str], fail: Callable[[str], NoReturn]
) -> None:
    """Fails with exit 2 unless `key` is one of Garmin's activity type `keys`."""
    if key in keys:
        return
    problem = f"Unknown activity type '{key}'."
    if match := difflib.get_close_matches(key, list(keys)):
        fail(f"{problem} Did you mean '{match[0]}'?")
    fail(
        f"{problem} Use a Garmin type key, like running, cycling or strength_training."
    )


def summarize(raw: dict[str, Any], type_key: str | None) -> dict[str, Any]:
    picked = {
        name: next((raw[key] for key in keys if raw.get(key) is not None), None)
        for name, keys in FIELDS.items()
    }
    summary = {name: value for name, value in picked.items() if value is not None}
    if type_key:
        summary["type"] = type_key
    speed = raw.get("averageSpeed")
    if speed:
        if type_key and "running" in type_key:
            summary["avg_pace_s_per_km"] = round(1000 / speed)
        else:
            summary["avg_speed_kmh"] = round(speed * 3.6, 1)
    return summary


def activities(args: argparse.Namespace, connect: Connect) -> Any:
    client = connect()
    if args.start or args.end:
        # Garmin needs a start date; 2000-01-01 predates any Garmin Connect upload.
        # ponytail: --to alone pages through the whole history before the limit
        # applies; page with get_activities and stop at --to if that gets slow.
        start = (args.start or date(2000, 1, 1)).isoformat()
        end = args.end and args.end.isoformat()
        found = client.get_activities_by_date(start, end, args.type)[: args.limit]
    else:
        found = client.get_activities(0, args.limit, activitytype=args.type)
    if args.raw:
        return found
    return [summarize(a, a.get("activityType", {}).get("typeKey")) for a in found]


def fetch_activity(client: GarminClient, activity_id: str) -> dict[str, Any]:
    try:
        return client.get_activity(activity_id)
    except GarminConnectNotFoundError:
        raise GarminCliError(
            f"No activity with ID {activity_id}.",
            "Run 'garmin activities' to list recent IDs.",
        ) from None


def activity(args: argparse.Namespace, connect: Connect) -> Any:
    client = connect()
    summary = fetch_activity(client, args.id)
    splits = client.get_activity_splits(args.id)
    zones = client.get_activity_hr_in_timezones(args.id)
    if args.raw:
        return {"summary": summary, "splits": splits, "hr_zones": zones}
    type_key = summary.get("activityTypeDTO", {}).get("typeKey")
    result = summarize({**summary, **summary.get("summaryDTO", {})}, type_key)
    laps = [summarize(lap, type_key) for lap in splits.get("lapDTOs", [])]
    result["laps"] = [
        {name: value for name, value in lap.items() if name != "type"} for lap in laps
    ]
    result["hr_zones"] = [
        {
            "zone": zone.get("zoneNumber"),
            "seconds": zone.get("secsInZone"),
            "low_bpm": zone.get("zoneLowBoundary"),
        }
        for zone in zones or []
    ]
    return result


def fit_file(original: bytes, activity_id: str) -> bytes:
    """The FIT file inside Garmin's original download."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(original))
        [entry] = archive.infolist()
    except (zipfile.BadZipFile, ValueError):
        raise GarminCliError(
            f"Garmin sent no FIT file for activity {activity_id}.",
            f"Rerun with --debug and report it at {ISSUES}.",
        ) from None
    kind = PurePosixPath(entry.filename).suffix.removeprefix(".").lower()
    if kind != "fit":
        use = kind if kind in DOWNLOAD_FORMATS else "gpx"
        raise GarminCliError(
            f"Activity {activity_id} was uploaded as a {kind.upper()} file, so "
            "Garmin has no FIT file for it.",
            f"Use --format {use}.",
        )
    return archive.read(entry)


def activity_download(args: argparse.Namespace, connect: Connect) -> Any:
    fail: Callable[[str], NoReturn] = args.parser.fail
    if args.output == "-":
        if sys.stdout.isatty():
            fail(
                "--output - writes the file to stdout, which is a terminal. "
                "Pipe it to another command, or give a file name."
            )
    elif not (folder := Path(args.output).parent).is_dir():
        fail(
            f"Cannot write '{args.output}': folder '{folder}' does not exist. "
            "Give a path in an existing folder."
        )
    client = connect()
    summary = fetch_activity(client, args.id)
    if (summary.get("metadataDTO") or {}).get("manualActivity"):
        raise GarminCliError(
            f"Activity {args.id} is a manual entry, so it has no recording to "
            "download.",
            f"Run 'garmin activity {args.id}' to see it.",
        )
    data = client.download_activity(args.id, dl_fmt=DOWNLOAD_FORMATS[args.format])
    if args.format == "fit":
        data = fit_file(data, args.id)
    if args.output == "-":
        sys.stdout.buffer.write(data)
        return NO_STDOUT
    Path(args.output).write_bytes(data)
    name = summary.get("activityName")
    what = f'"{name}"' if name is not None else args.id
    print(
        f"garmin: Saved activity {what} as {args.output} ({len(data)} bytes).",
        file=sys.stderr,
    )
    return {
        "id": int(args.id),
        "format": args.format,
        "file": args.output,
        "bytes": len(data),
    }


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    activities_parser = subparsers.add_parser(
        "activities", help="recent activities, newest first"
    )
    add_range_arguments(activities_parser, None)
    activities_parser.add_argument("--type", help="running, cycling, swimming, ...")
    activities_parser.add_argument(
        "--limit",
        type=positive_int,
        default=20,
        help="max activities to return (default: 20)",
    )
    activities_parser.add_argument(
        "--raw", action="store_true", help="print the full Garmin response"
    )
    activities_parser.set_defaults(run=activities)
    activity_parser = subparsers.add_parser(
        "activity",
        help="one activity with laps and HR zones",
        epilog="'garmin activity add' creates a manual activity on Garmin Connect, "
        "'garmin activity delete' deletes one and 'garmin activity download' saves "
        "its recording as a file. Run 'garmin activity add --help', 'garmin activity "
        "delete --help' or 'garmin activity download --help' for their options.",
    )
    activity_parser.add_argument(
        "id", type=activity_id, help="activity ID from 'garmin activities'"
    )
    activity_parser.add_argument(
        "--raw", action="store_true", help="print the full Garmin response"
    )
    activity_parser.set_defaults(run=activity)
    # `main` joins `garmin activity download` into this one command name. Without a
    # `help`, `garmin --help` leaves it out; `garmin activity --help` names it.
    download_parser = subparsers.add_parser(
        "activity download",
        description="Saves an activity's recording as a FIT, GPX, TCX, KML or CSV "
        "file. --output - writes it to stdout for a pipe.",
    )
    download_parser.add_argument(
        "id", type=activity_id, help="activity ID from 'garmin activities'"
    )
    download_parser.add_argument(
        "--format",
        type=download_format,
        default="fit",
        help="fit (default, the original file), gpx, tcx, kml or csv",
    )
    download_parser.add_argument(
        "--output",
        required=True,
        help="file to write, overwritten if it exists; - for stdout",
    )
    download_parser.set_defaults(run=activity_download, parser=download_parser)
