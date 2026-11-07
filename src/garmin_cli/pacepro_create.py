import argparse
import math
import re
import sys
from collections.abc import Callable
from typing import Any

from garmin_cli.client import Connect
from garmin_cli.courses import course_id, fetch_course
from garmin_cli.errors import GarminCliError
from garmin_cli.pacepro import show
from garmin_cli.pacing import compute_splits

SPLIT_TYPES = {"km": "DISTANCE_KILOMETER", "elevation": "ELEVATION"}
# Settings the Garmin Connect website sends with every plan. The minimum elevation
# split length is the value of the one reference case.
WEBSITE_SETTINGS = {
    "distanceUnit": None,
    "manualPaceEdit": False,
    "elevationSegmentationTolerance": 50.0,
    "paceFactor": 2.0,
    "elevationSegmentMinLength": 1700.0,
}


def split_type(value: str) -> str:
    if value not in SPLIT_TYPES:
        raise argparse.ArgumentTypeError(
            f"Invalid --split '{value}'. Use km or elevation."
        )
    return SPLIT_TYPES[value]


def goal_time(value: str) -> int:
    match = re.fullmatch(r"(\d+):([0-5]\d):([0-5]\d)", value)
    seconds = int(match[1]) * 3600 + int(match[2]) * 60 + int(match[3]) if match else 0
    if seconds < 1:
        raise argparse.ArgumentTypeError(
            f"Invalid --goal-time '{value}'. Use H:MM:SS, like 1:05:00."
        )
    return seconds


def goal_pace(value: str) -> int:
    """Seconds per km."""
    match = re.fullmatch(r"(\d+):([0-5]\d)", value)
    seconds = int(match[1]) * 60 + int(match[2]) if match else 0
    if seconds < 1:
        raise argparse.ArgumentTypeError(
            f"Invalid --goal-pace '{value}'. Use M:SS per km, like 5:30."
        )
    return seconds


def slider(option: str) -> Callable[[str], float]:
    def parse(value: str) -> float:
        try:
            number = float(value)
        except ValueError:
            number = math.nan
        if not math.isfinite(number):
            raise argparse.ArgumentTypeError(
                f"Invalid {option} '{value}'. Use a number, like -0.5."
            )
        return number

    return parse


def elevation_track(course: dict[str, Any], course_id: int) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = course.get("geoPoints") or []
    if len(points) < 2 or any(point.get("elevation") is None for point in points):
        raise GarminCliError(
            f"Course {course_id} has no track with elevation, which PacePro needs.",
            "Pick another course from 'garmin course list'.",
        )
    return points


def create_plan(args: argparse.Namespace, connect: Connect) -> Any:
    client = connect()
    course = fetch_course(client, args.course)
    points = elevation_track(course, args.course)
    distance = course["distanceMeter"]
    seconds = args.goal_time or round(args.goal_pace * distance / 1000)
    summary = {
        "courseId": args.course,
        "name": args.name or course.get("courseName"),
        "goalTime": seconds,
        "goalSpeed": distance / seconds,
        "splitType": args.split,
        "totalDistance": distance,
        "uphillEffort": args.uphill_effort,
        "pacingStrategy": args.pacing_strategy,
        **WEBSITE_SETTINGS,
    }
    plan = {
        "paceBandSummary": summary,
        "paceBandSplits": compute_splits(points, summary),
    }
    if args.dry_run:
        print(
            f"garmin: Would create a PacePro plan from course {args.course}; "
            "nothing saved.",
            file=sys.stderr,
        )
        return show(plan)
    # garminconnect has no call to create a plan. This is the endpoint the Garmin
    # Connect website posts finished plans to.
    saved = client.client.post(
        "connectapi", "/course-service/pacebands", json=plan, api=True
    )
    print(
        f"garmin: Created PacePro plan {saved.get('paceBandPk')} from course "
        f"{args.course}.",
        file=sys.stderr,
    )
    return show(saved)


def register(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    create_parser = commands.add_parser(
        "create",
        help="compute a PacePro plan from a course and save it",
        description="Computes a PacePro plan from a saved course with garmin-cli's "
        "own pacing algorithm and saves it to Garmin Connect. Each run saves a new "
        "plan. --dry-run prints the plan without saving it.",
    )
    create_parser.add_argument(
        "--course",
        type=course_id,
        required=True,
        help="course ID from 'garmin course list'",
    )
    goal = create_parser.add_mutually_exclusive_group(required=True)
    goal.add_argument("--goal-time", type=goal_time, help="finish time, H:MM:SS")
    goal.add_argument("--goal-pace", type=goal_pace, help="average pace per km, M:SS")
    create_parser.add_argument(
        "--split",
        type=split_type,
        metavar="{km,elevation}",
        default="km",
        help="split at every km or where the grade changes (default: km)",
    )
    create_parser.add_argument(
        "--pacing-strategy",
        type=slider("--pacing-strategy"),
        default=0.0,
        help="Garmin's pacing slider; below 0 slows the second half (default: 0)",
    )
    create_parser.add_argument(
        "--uphill-effort",
        type=slider("--uphill-effort"),
        default=0.0,
        help="Garmin's uphill slider; above 0 slows the climbs (default: 0)",
    )
    create_parser.add_argument("--name", help="plan name (default: the course name)")
    create_parser.add_argument(
        "--dry-run", action="store_true", help="print the plan, save nothing"
    )
    create_parser.set_defaults(run=create_plan)
