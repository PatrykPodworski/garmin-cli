import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

from garmin_cli.client import Connect
from garmin_cli.dates import parse_date

REQUIRED_KEYS = ("workoutName", "sportType", "workoutSegments")


def read_workout(args: argparse.Namespace) -> dict[str, Any]:
    source = "stdin" if args.file == "-" else f"'{args.file}'"
    try:
        text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text()
    except (OSError, UnicodeDecodeError) as error:
        problem = error.strerror if isinstance(error, OSError) else "not UTF-8 text"
        args.parser.fail(
            f"Cannot read {source} ({problem}). Pass a workout JSON file, or '-' "
            "for stdin."
        )
    try:
        workout = json.loads(text)
    except json.JSONDecodeError as error:
        args.parser.fail(
            f"Invalid JSON in {source} at line {error.lineno}, column {error.colno}: "
            f"{error.msg}. Fix it and try again."
        )
    if not isinstance(workout, dict):
        args.parser.fail(
            f"The workout in {source} is not a JSON object. Pass one workout object "
            "with workoutName, sportType and workoutSegments."
        )
    if missing := [key for key in REQUIRED_KEYS if key not in workout]:
        args.parser.fail(
            f"The workout in {source} has no {', '.join(missing)}. A workout needs "
            "workoutName, sportType and workoutSegments."
        )
    # `fail` exits, but `args.parser` is untyped, so mypy cannot narrow `workout`.
    return cast(dict[str, Any], workout)


def add_workout(args: argparse.Namespace, connect: Connect) -> Any:
    workout = read_workout(args)
    client = connect()
    created = client.upload_workout(workout)
    workout_id = created["workoutId"]
    what = f'workout "{created.get("workoutName")}" (ID {workout_id})'
    scheduled = args.schedule.isoformat() if args.schedule else None
    if scheduled:
        try:
            client.schedule_workout(workout_id, scheduled)
        except Exception:
            # `main` reports the cause on the next line.
            print(
                f"garmin: Created {what} but did not schedule it. Schedule it in "
                "Garmin Connect; running this command again creates a second copy.",
                file=sys.stderr,
            )
            raise
        print(
            f"garmin: Created {what} and scheduled it for {scheduled}.", file=sys.stderr
        )
    else:
        print(f"garmin: Created {what}.", file=sys.stderr)
    seconds = created.get("estimatedDurationInSecs")
    return {
        "id": workout_id,
        "name": created.get("workoutName"),
        "estimated_duration_min": seconds / 60 if seconds is not None else None,
        "scheduled": scheduled,
    }


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    # `main` joins `garmin workout add` into this one command name. Without a
    # `help`, `garmin --help` leaves it out.
    add_parser = subparsers.add_parser(
        "workout add",
        description="Saves a workout in Garmin's own JSON format to the Garmin "
        "Connect workout library and prints its ID. --schedule also puts it on the "
        "calendar, and the watch gets it on its next sync.",
    )
    add_parser.add_argument(
        "--file",
        required=True,
        help="workout JSON file, or - to read stdin",
    )
    add_parser.add_argument(
        "--schedule",
        type=parse_date,
        metavar="DATE",
        help="today | yesterday | YYYY-MM-DD: put the workout on the calendar",
    )
    add_parser.set_defaults(run=add_workout, parser=add_parser)
