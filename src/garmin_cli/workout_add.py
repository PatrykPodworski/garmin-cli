import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn, cast

from garmin_cli import strength
from garmin_cli.client import Connect
from garmin_cli.dates import parse_date
from garmin_cli.workout_schedule import schedule

REQUIRED_KEYS = ("workoutName", "sportType", "workoutSegments")


def source_of(args: argparse.Namespace) -> str:
    return "stdin" if args.file == "-" else f"'{args.file}'"


def read_json(args: argparse.Namespace) -> Any:
    try:
        text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text()
    except (OSError, UnicodeDecodeError) as error:
        problem = error.strerror if isinstance(error, OSError) else "not UTF-8 text"
        args.parser.fail(
            f"Cannot read {source_of(args)} ({problem}). Pass a workout JSON file, or "
            "'-' for stdin."
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        args.parser.fail(
            f"Invalid JSON in {source_of(args)} at line {error.lineno}, column "
            f"{error.colno}: {error.msg}. Fix it and try again."
        )


def read_workout(args: argparse.Namespace) -> dict[str, Any]:
    workout = read_json(args)
    source = source_of(args)
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


def read_strength(args: argparse.Namespace) -> dict[str, Any]:
    try:
        return strength.build(read_json(args))
    except strength.InvalidWorkout as error:
        # `args.parser` is untyped; the annotation tells mypy `fail` exits.
        fail: Callable[[str], NoReturn] = args.parser.fail
        fail(f"{error.where} in {source_of(args)} {error.problem}")


def add_workout(args: argparse.Namespace, connect: Connect) -> Any:
    workout = read_strength(args) if args.strength else read_workout(args)
    client = connect()
    created = client.upload_workout(workout)
    workout_id = created["workoutId"]
    what = f'workout "{created.get("workoutName")}" (ID {workout_id})'
    scheduled = args.schedule.isoformat() if args.schedule else None
    if scheduled:
        try:
            schedule(client, created, args.schedule)
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
    stored = created.get("estimatedDurationInSecs")
    # Garmin can answer 0 for a strength workout (#125); show the estimate sent.
    seconds = stored or workout.get("estimatedDurationInSecs", stored)
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
        "Connect workout library and prints its ID. --strength reads a short strength "
        "workout file instead. --schedule also puts the workout on the calendar, and "
        "the watch gets it on its next sync.",
    )
    add_parser.add_argument(
        "--file",
        required=True,
        help="workout JSON file, or - to read stdin",
    )
    add_parser.add_argument(
        "--strength",
        action="store_true",
        help="read --file as a strength workout: name, note, warmup, blocks of "
        "exercise and rest steps, cooldown",
    )
    add_parser.add_argument(
        "--schedule",
        type=parse_date,
        metavar="DATE",
        help="today | yesterday | tomorrow | YYYY-MM-DD: put the workout on the "
        "calendar",
    )
    add_parser.set_defaults(run=add_workout, parser=add_parser)
