import argparse
import sys
from typing import Any

from garmin_cli.activities import fetch_activity
from garmin_cli.client import Connect


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


def delete_activity(args: argparse.Namespace, connect: Connect) -> Any:
    if not (args.yes or sys.stdin.isatty()):
        args.parser.fail(
            "Cannot ask to confirm the deletion: stdin is not a terminal. "
            "Pass --yes to delete without asking."
        )
    client = connect()
    summary = fetch_activity(client, args.id)
    name = summary["activityName"]
    start = summary["summaryDTO"]["startTimeLocal"][:16].replace("T", " ")
    if not args.yes:
        type_key = summary["activityTypeDTO"]["typeKey"]
        print(f'Delete "{name}" ({type_key}, {start})? [y/N] ', end="", file=sys.stderr)
        if sys.stdin.readline().strip().lower() not in ("y", "yes"):
            args.parser.exit(1, "garmin: Nothing deleted.\n")
    client.delete_activity(args.id)
    print(f'garmin: Deleted "{name}" ({start}).', file=sys.stderr)
    return {"deleted": int(args.id)}


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    # `main` joins `garmin activity delete` into this one command name. Without a
    # `help`, `garmin --help` leaves it out; `garmin activity --help` names it.
    delete_parser = subparsers.add_parser(
        "activity delete",
        description="Deletes an activity from Garmin Connect. Asks to confirm "
        "first; without a terminal to ask on, pass --yes.",
    )
    delete_parser.add_argument(
        "id", type=activity_id, help="activity ID from 'garmin activities'"
    )
    delete_parser.add_argument(
        "--yes", action="store_true", help="delete without asking to confirm"
    )
    delete_parser.set_defaults(run=delete_activity, parser=delete_parser)
