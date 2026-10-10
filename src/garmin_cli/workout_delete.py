import argparse
import sys
from typing import Any

from garmin_cli.client import Connect
from garmin_cli.workouts import fetch_workout, workout_id


def delete_workout(args: argparse.Namespace, connect: Connect) -> Any:
    client = connect()
    name = fetch_workout(client, args.id).get("workoutName")
    what = f'"{name}"' if name is not None else f"workout {args.id}"
    if args.dry_run:
        print(f"garmin: Would delete {what}.", file=sys.stderr)
        return {"would_delete": args.id}
    client.delete_workout(args.id)
    print(f"garmin: Deleted {what}.", file=sys.stderr)
    return {"deleted": args.id}


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    # `main` joins `garmin workout delete` into this one command name. Without a
    # `help`, `garmin --help` leaves it out.
    delete_parser = subparsers.add_parser(
        "workout delete",
        description="Deletes a workout from the Garmin Connect workout library "
        "without asking, with its calendar entries. --dry-run shows what would be "
        "deleted.",
    )
    delete_parser.add_argument(
        "id", type=workout_id, help="workout ID from 'garmin workouts'"
    )
    delete_parser.add_argument(
        "--dry-run", action="store_true", help="show the workout, delete nothing"
    )
    delete_parser.set_defaults(run=delete_workout)
