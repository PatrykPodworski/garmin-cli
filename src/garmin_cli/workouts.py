import argparse
from datetime import date, timedelta
from typing import Any

from garminconnect import GarminConnectNotFoundError

from garmin_cli.activities import positive_int
from garmin_cli.client import Connect, GarminClient
from garmin_cli.dates import parse_date
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


def fetch_workout(client: GarminClient, workout_id: int) -> dict[str, Any]:
    try:
        return client.get_workout_by_id(workout_id)
    except GarminConnectNotFoundError:
        raise GarminCliError(
            f"No workout with ID {workout_id}.", "Run 'garmin workouts' to list IDs."
        ) from None


def describe(raw: dict[str, Any]) -> dict[str, Any]:
    # ponytail: a multisport workout's segments are joined into one step list;
    # add a `segments` key if those workouts need their boundaries.
    steps = [
        summarize_step(step)
        for segment in raw.get("workoutSegments") or []
        for step in segment.get("workoutSteps") or []
    ]
    return {**summarize(raw), "steps": steps}


def workout(args: argparse.Namespace, connect: Connect) -> Any:
    raw = fetch_workout(connect(), args.id)
    return raw if args.raw else describe(raw)


def calendar(args: argparse.Namespace, connect: Connect) -> Any:
    start = args.start
    end = args.end or start + timedelta(weeks=4)
    if end < start:
        args.parser.fail(
            f"--to {end} is before --from {start}. Give a --to on or after --from."
        )
    client = connect()
    first = start.year * 12 + start.month - 1
    last = end.year * 12 + end.month - 1
    found = [
        item
        for month in range(first, last + 1)
        for item in client.get_scheduled_workouts(month // 12, month % 12 + 1).get(
            "calendarItems", []
        )
        if item.get("itemType") == "workout"
        and start.isoformat() <= item["date"] <= end.isoformat()
    ]
    found.sort(key=lambda item: item["date"])
    if args.raw:
        return found
    return [
        {
            "schedule_id": item.get("id"),
            "date": item["date"],
            "workout_id": item.get("workoutId"),
            "name": item.get("title"),
        }
        for item in found
    ]


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
    workout_parser = subparsers.add_parser(
        "workout",
        help="one workout with its steps",
        epilog="'garmin workout add', 'garmin workout edit', 'garmin workout "
        "delete', 'garmin workout schedule', 'garmin workout unschedule' and "
        "'garmin workout calendar' manage the workout library and calendar. Run "
        "'garmin workout <command> --help' for their options.",
    )
    workout_parser.add_argument(
        "id", type=workout_id, help="workout ID from 'garmin workouts'"
    )
    workout_parser.add_argument(
        "--raw", action="store_true", help="print the full Garmin response"
    )
    workout_parser.set_defaults(run=workout)
    # `main` joins `garmin workout calendar` into this one command name. Without a
    # `help`, `garmin --help` leaves it out.
    calendar_parser = subparsers.add_parser(
        "workout calendar",
        description="Workouts on the Garmin Connect calendar, by date. Each entry "
        "has the schedule_id that 'garmin workout unschedule' takes.",
    )
    for flag, dest, default, shown in (
        ("--from", "start", date.today(), "today"),
        ("--to", "end", None, "4 weeks after --from"),
    ):
        calendar_parser.add_argument(
            flag,
            dest=dest,
            metavar="DATE",
            default=default,
            type=parse_date,
            help=f"today | yesterday | tomorrow | YYYY-MM-DD (default: {shown})",
        )
    calendar_parser.add_argument(
        "--raw",
        action="store_true",
        help="print the raw Garmin calendar items instead of the summary",
    )
    calendar_parser.set_defaults(run=calendar, parser=calendar_parser)
