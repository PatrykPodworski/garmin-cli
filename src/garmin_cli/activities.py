import argparse
from datetime import date
from typing import Any

from garminconnect import GarminConnectNotFoundError

from garmin_cli.client import Connect, GarminClient
from garmin_cli.dates import add_range_arguments
from garmin_cli.errors import GarminCliError

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
        epilog="'garmin activity add' creates a manual activity on Garmin Connect "
        "and 'garmin activity delete' deletes one. Run 'garmin activity add --help' "
        "or 'garmin activity delete --help' for their options.",
    )
    activity_parser.add_argument("id")
    activity_parser.add_argument(
        "--raw", action="store_true", help="print the full Garmin response"
    )
    activity_parser.set_defaults(run=activity)
