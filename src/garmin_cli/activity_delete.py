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
    client = connect()
    summary = fetch_activity(client, args.id)
    name = summary.get("activityName")
    start = (summary.get("summaryDTO") or {}).get("startTimeLocal")
    what = f'"{name}"' if name is not None else f"activity {args.id}"
    if start:
        what += f" ({start[:16].replace('T', ' ')})"
    if args.dry_run:
        print(f"garmin: Would delete {what}.", file=sys.stderr)
        return {"would_delete": int(args.id)}
    client.delete_activity(args.id)
    print(f"garmin: Deleted {what}.", file=sys.stderr)
    return {"deleted": int(args.id)}


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    # `main` joins `garmin activity delete` into this one command name. Without a
    # `help`, `garmin --help` leaves it out; `garmin activity --help` names it.
    delete_parser = subparsers.add_parser(
        "activity delete",
        description="Deletes an activity from Garmin Connect without asking. "
        "--dry-run shows what would be deleted.",
    )
    delete_parser.add_argument(
        "id", type=activity_id, help="activity ID from 'garmin activities'"
    )
    delete_parser.add_argument(
        "--dry-run", action="store_true", help="show the activity, delete nothing"
    )
    delete_parser.set_defaults(run=delete_activity)
