import argparse
import difflib
import math
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from garmin_cli.activities import activity
from garmin_cli.client import Connect
from garmin_cli.dates import local_time_zone, parse_datetime


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
    if args.type not in types:
        problem = f"Unknown activity type '{args.type}'."
        if match := difflib.get_close_matches(args.type, types):
            args.parser.fail(f"{problem} Did you mean '{match[0]}'?")
        args.parser.fail(
            f"{problem} Use a Garmin type key, like running, cycling or "
            "strength_training."
        )
    # The payload of garminconnect's `create_manual_activity`, which cannot send
    # calories: without them Garmin estimates far fewer than its web form does.
    summary: dict[str, Any] = {
        "startTimeLocal": args.start.isoformat(timespec="milliseconds"),
        "distance": args.distance * 1000,
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
        description="Creates a private manual activity on Garmin Connect and "
        "prints it as 'garmin activity ID' does.",
    )
    add_parser.add_argument(
        "--type",
        required=True,
        help="Garmin type key: running, cycling, strength_training, ...",
    )
    add_parser.add_argument(
        "--start",
        required=True,
        type=parse_datetime,
        metavar="'YYYY-MM-DD HH:MM'",
        help="local start time",
    )
    add_parser.add_argument(
        "--duration", required=True, type=minutes, help="whole minutes"
    )
    add_parser.add_argument(
        "--distance", type=kilometers, default=0.0, help="kilometers (default: 0)"
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
