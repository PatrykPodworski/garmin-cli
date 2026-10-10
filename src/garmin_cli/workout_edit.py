import argparse
import sys
from typing import Any

from garmin_cli.client import Connect
from garmin_cli.workout_add import read_workout
from garmin_cli.workouts import describe, fetch_workout, workout_id


def edit_workout(args: argparse.Namespace, connect: Connect) -> Any:
    workout = read_workout(args)
    client = connect()
    fetch_workout(client, args.id)
    client.update_workout(args.id, workout)
    print(
        f'garmin: Updated workout "{workout["workoutName"]}" (ID {args.id}).',
        file=sys.stderr,
    )
    return describe(fetch_workout(client, args.id))


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    # `main` joins `garmin workout edit` into this one command name. Without a
    # `help`, `garmin --help` leaves it out.
    edit_parser = subparsers.add_parser(
        "workout edit",
        description="Replaces a workout in the Garmin Connect workout library with "
        "the workout in Garmin's own JSON format, the shape 'garmin workout ID --raw' "
        "prints. The workout keeps its ID and its calendar entries.",
    )
    edit_parser.add_argument(
        "id", type=workout_id, help="workout ID from 'garmin workouts'"
    )
    edit_parser.add_argument(
        "--file",
        required=True,
        help="workout JSON file, or - to read stdin",
    )
    edit_parser.set_defaults(run=edit_workout, parser=edit_parser)
