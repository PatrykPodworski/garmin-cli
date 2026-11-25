import argparse
import math
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from garmin_cli import activity_upload
from garmin_cli.activities import activity, require_type
from garmin_cli.client import Connect
from garmin_cli.dates import local_time_zone, parse_datetime

MANUAL = (
    "--type",
    "--start",
    "--duration",
    "--distance",
    "--calories",
    "--name",
    "--tz",
)
REQUIRED = MANUAL[:3]


def minutes(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        number = 0
    if number < 1:
        raise argparse.ArgumentTypeError(
            f"Invalid --duration '{value}'. Use whole minutes, 1 or more."
        )
    return number


def kilometers(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        number = math.nan
    if not (math.isfinite(number) and number >= 0):
        raise argparse.ArgumentTypeError(
            f"Invalid --distance '{value}'. Use kilometers, 0 or more, like 5.2."
        )
    return number


def kilocalories(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        number = math.nan
    if not (math.isfinite(number) and number > 0):
        raise argparse.ArgumentTypeError(
            f"Invalid --calories '{value}'. Use kilocalories, more than 0, like 266.7."
        )
    return number


def add_activity(args: argparse.Namespace, connect: Connect) -> Any:
    given = [option for option in MANUAL if getattr(args, option[2:]) is not None]
    if args.file is not None:
        if given:
            args.parser.error(f"argument {given[0]}: not allowed with argument --file")
        return activity_upload.upload(args, connect)
    if missing := [option for option in REQUIRED if option not in given]:
        args.parser.error(f"the following arguments are required: {', '.join(missing)}")
    time_zone = args.tz or local_time_zone() or ""
    if not time_zone:
        args.parser.fail(
            "Could not find this machine's time zone. "
            "Pass --tz, for example --tz Europe/Warsaw."
        )
    try:
        ZoneInfo(time_zone)
    except (ZoneInfoNotFoundError, ValueError):
        args.parser.fail(
            f"Unknown time zone '{time_zone}'. Pass --tz with an IANA name, "
            "for example --tz Europe/Warsaw."
        )
    client = connect()
    types = [activity_type["typeKey"] for activity_type in client.get_activity_types()]
    require_type(args.type, types, args.parser.fail)
    # The payload of garminconnect's `create_manual_activity`, which cannot send
    # calories: without them Garmin estimates far fewer than its web form does.
    summary: dict[str, Any] = {
        "startTimeLocal": args.start.isoformat(timespec="milliseconds"),
        "distance": (args.distance or 0.0) * 1000,
        "duration": args.duration * 60,
    }
    if args.calories is not None:
        summary["calories"] = args.calories
    created = client.create_manual_activity_from_json(
        {
            "activityTypeDTO": {"typeKey": args.type},
            "accessControlRuleDTO": {"typeId": 2, "typeKey": "private"},
            "timeZoneUnitDTO": {"unitKey": time_zone},
            # ponytail: the type key title-cased, close to Garmin's display names;
            # read the names from Garmin if one turns out wrong.
            "activityName": args.name or args.type.replace("_", " ").title(),
            "metadataDTO": {"autoCalcCalories": args.calories is None},
            "summaryDTO": summary,
        }
    )
    shown = argparse.Namespace(id=str(created["activityId"]), raw=False)
    return activity(shown, lambda: client)


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    # `main` joins `garmin activity add` into this one command name. Without a
    # `help`, `garmin --help` leaves it out; `garmin activity --help` names it.
    add_parser = subparsers.add_parser(
        "activity add",
        description="Creates a private manual activity on Garmin Connect, or "
        "uploads a FIT, GPX or TCX file with --file, and prints the activity as "
        "'garmin activity ID' does.",
    )
    add_parser.add_argument(
        "--file",
        help="FIT, GPX or TCX file to upload, or - for stdin; leave out the other "
        "options",
    )
    add_parser.add_argument(
        "--type",
        help="Garmin type key: running, cycling, strength_training, ...",
    )
    add_parser.add_argument(
        "--start",
        type=parse_datetime,
        metavar="'YYYY-MM-DD HH:MM'",
        help="local start time",
    )
    add_parser.add_argument("--duration", type=minutes, help="whole minutes")
    add_parser.add_argument(
        "--distance", type=kilometers, help="kilometers (default: 0)"
    )
    add_parser.add_argument(
        "--calories",
        type=kilocalories,
        metavar="KCAL",
        help="kilocalories burned (default: Garmin's estimate)",
    )
    add_parser.add_argument(
        "--name", help="activity name (default: the type, like 'Strength Training')"
    )
    add_parser.add_argument(
        "--tz",
        metavar="ZONE",
        help="IANA time zone, like Europe/Warsaw (default: this machine's)",
    )
    add_parser.set_defaults(run=add_activity, parser=add_parser)
