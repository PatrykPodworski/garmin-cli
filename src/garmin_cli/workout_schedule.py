import argparse
import sys
from datetime import date
from typing import Any

from garmin_cli.client import Connect, GarminClient
from garmin_cli.dates import parse_date
from garmin_cli.workouts import fetch_workout, workout_id


def schedule(
    client: GarminClient, workout: dict[str, Any], day: date
) -> dict[str, Any]:
    """Puts a workout from the library on the calendar and returns the entry as
    `garmin workout calendar` prints it."""
    entry = client.schedule_workout(workout["workoutId"], day.isoformat())
    return {
        "schedule_id": entry.get("workoutScheduleId"),
        "date": day.isoformat(),
        "workout_id": workout["workoutId"],
        "name": workout.get("workoutName"),
    }


def schedule_workout(args: argparse.Namespace, connect: Connect) -> Any:
    client = connect()
    entry = schedule(client, fetch_workout(client, args.id), args.date)
    print(
        f'garmin: Scheduled workout "{entry["name"]}" (ID {entry["workout_id"]}) '
        f"for {entry['date']}.",
        file=sys.stderr,
    )
    return entry


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    # `main` joins `garmin workout schedule` into this one command name. Without a
    # `help`, `garmin --help` leaves it out.
    schedule_parser = subparsers.add_parser(
        "workout schedule",
        description="Puts a workout from the workout library on the Garmin Connect "
        "calendar. The watch gets it on its next sync.",
    )
    schedule_parser.add_argument(
        "id", type=workout_id, help="workout ID from 'garmin workouts'"
    )
    schedule_parser.add_argument(
        "date", type=parse_date, help="today | yesterday | tomorrow | YYYY-MM-DD"
    )
    schedule_parser.set_defaults(run=schedule_workout)
