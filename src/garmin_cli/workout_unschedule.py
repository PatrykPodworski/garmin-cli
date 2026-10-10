import argparse
import sys
from typing import Any

from garminconnect import GarminConnectNotFoundError

from garmin_cli.client import Connect
from garmin_cli.errors import GarminCliError

LISTING = "Run 'garmin workout calendar' to list schedule IDs."


def schedule_id(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        number = 0
    if number < 1:
        raise argparse.ArgumentTypeError(f"Invalid schedule ID '{value}'. {LISTING}")
    return number


def unschedule_workout(args: argparse.Namespace, connect: Connect) -> Any:
    try:
        connect().unschedule_workout(args.schedule_id)
    except GarminConnectNotFoundError:
        raise GarminCliError(
            f"No calendar entry with schedule ID {args.schedule_id}.", LISTING
        ) from None
    print(f"garmin: Removed calendar entry {args.schedule_id}.", file=sys.stderr)
    return {"unscheduled": args.schedule_id}


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    # `main` joins `garmin workout unschedule` into this one command name. Without
    # a `help`, `garmin --help` leaves it out.
    unschedule_parser = subparsers.add_parser(
        "workout unschedule",
        description="Takes one entry off the Garmin Connect calendar. The workout "
        "stays in the workout library.",
    )
    unschedule_parser.add_argument(
        "schedule_id",
        type=schedule_id,
        metavar="SCHEDULE_ID",
        help="schedule_id from 'garmin workout calendar'",
    )
    unschedule_parser.set_defaults(run=unschedule_workout)
