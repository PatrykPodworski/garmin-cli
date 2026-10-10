import argparse
from typing import Any

from garminconnect import GarminConnectNotFoundError

from garmin_cli.activities import positive_int
from garmin_cli.client import Connect
from garmin_cli.errors import GarminCliError

# Workouts per `get_workouts` call, the library's default limit.
PAGE = 100


def workout_id(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        number = 0
    if number < 1:
        raise argparse.ArgumentTypeError(
            f"Invalid workout ID '{value}'. Run 'garmin workouts' to list IDs."
        )
    return number


def summarize(raw: dict[str, Any]) -> dict[str, Any]:
    seconds = raw.get("estimatedDurationInSecs")
    summary = {
        "id": raw.get("workoutId"),
        "name": raw.get("workoutName"),
        "sport": (raw.get("sportType") or {}).get("sportTypeKey"),
        "estimated_duration_min": seconds and seconds / 60,
        "created": raw.get("createdDate"),
        "updated": raw.get("updateDate"),
    }
    return {name: value for name, value in summary.items() if value is not None}


def summarize_step(raw: dict[str, Any]) -> dict[str, Any]:
    step = {
        "type": (raw.get("stepType") or {}).get("stepTypeKey"),
        "iterations": raw.get("numberOfIterations"),
        "end": (raw.get("endCondition") or {}).get("conditionTypeKey"),
        "end_value": raw.get("endConditionValue"),
        "target": (raw.get("targetType") or {}).get("workoutTargetTypeKey"),
        "target_low": raw.get("targetValueOne"),
        "target_high": raw.get("targetValueTwo"),
        "description": raw.get("description"),
    }
    if "workoutSteps" in raw:
        step["steps"] = [summarize_step(child) for child in raw["workoutSteps"]]
    return {name: value for name, value in step.items() if value is not None}


def workouts(args: argparse.Namespace, connect: Connect) -> Any:
    client = connect()
    found: list[dict[str, Any]] = []
    while len(found) < args.limit:
        size = min(PAGE, args.limit - len(found))
        page = client.get_workouts(len(found), size)
        found += page
        if len(page) < size:
            break
    if args.raw:
        return found
    return [summarize(w) for w in found]


def workout(args: argparse.Namespace, connect: Connect) -> Any:
    client = connect()
    try:
        raw = client.get_workout_by_id(args.id)
    except GarminConnectNotFoundError:
        raise GarminCliError(
            f"No workout with ID {args.id}.", "Run 'garmin workouts' to list IDs."
        ) from None
    if args.raw:
        return raw
    # ponytail: a multisport workout's segments are joined into one step list;
    # add a `segments` key if those workouts need their boundaries.
    steps = [
        summarize_step(step)
        for segment in raw.get("workoutSegments") or []
        for step in segment.get("workoutSteps") or []
    ]
    return {**summarize(raw), "steps": steps}


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    workouts_parser = subparsers.add_parser(
        "workouts", help="workouts in the workout library, newest first"
    )
    workouts_parser.add_argument(
        "--limit",
        type=positive_int,
        default=20,
        help="max workouts to return (default: 20)",
    )
    workouts_parser.add_argument(
        "--raw", action="store_true", help="print the full Garmin response"
    )
    workouts_parser.set_defaults(run=workouts)
    workout_parser = subparsers.add_parser("workout", help="one workout with its steps")
    workout_parser.add_argument(
        "id", type=workout_id, help="workout ID from 'garmin workouts'"
    )
    workout_parser.add_argument(
        "--raw", action="store_true", help="print the full Garmin response"
    )
    workout_parser.set_defaults(run=workout)
