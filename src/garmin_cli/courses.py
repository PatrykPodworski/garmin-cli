import argparse
from collections.abc import Mapping
from typing import Any

from garminconnect import GarminConnectNotFoundError

from garmin_cli.activities import positive_int
from garmin_cli.client import Connect, GarminClient
from garmin_cli.errors import GarminCliError

# A course's `rulePK`, the same rule IDs as an activity's `accessControlRuleDTO`.
PRIVACY = {"public": 1, "private": 2}
LIST_IDS = "Run 'garmin course list' to list IDs."


def course_id(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        number = 0
    if number < 1:
        raise argparse.ArgumentTypeError(f"Invalid course ID '{value}'. {LIST_IDS}")
    return number


def type_keys(client: GarminClient) -> dict[int, str]:
    """Activity type ID -> type key; a course stores only the ID."""
    return {kind["typeId"]: kind["typeKey"] for kind in client.get_activity_types()}


def summarize(raw: dict[str, Any], types: Mapping[Any, str]) -> dict[str, Any]:
    rules: dict[Any, str] = {rule: name for name, rule in PRIVACY.items()}
    summary = {
        "id": raw.get("courseId"),
        "name": raw.get("courseName"),
        "type": types.get(raw.get("activityTypePk")),
        "distance_m": raw.get("distanceMeter"),
        "elevation_gain_m": raw.get("elevationGainMeter"),
        "elevation_loss_m": raw.get("elevationLossMeter"),
        "privacy": rules.get(raw.get("rulePK")),
    }
    return {name: value for name, value in summary.items() if value is not None}


def course_list(args: argparse.Namespace, connect: Connect) -> Any:
    client = connect()
    found = client.get_courses()[: args.limit]
    if args.raw:
        return found
    types = type_keys(client)
    return [summarize(course, types) for course in found]


def fetch_course(client: GarminClient, course_id: int) -> dict[str, Any]:
    try:
        return client.get_course(course_id)
    except GarminConnectNotFoundError:
        raise GarminCliError(f"No course with ID {course_id}.", LIST_IDS) from None


def course_view(args: argparse.Namespace, connect: Connect) -> Any:
    client = connect()
    raw = fetch_course(client, args.id)
    return raw if args.raw else summarize(raw, type_keys(client))


def register(
    subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> "argparse._SubParsersAction[argparse.ArgumentParser]":
    """Returns the `course` commands, for the write modules to add `create` and
    `send`."""
    course_parser = subparsers.add_parser(
        "course", help="courses: GPX routes the watch can follow"
    )
    # `CliParser.explain` names a missing command by this metavar.
    commands = course_parser.add_subparsers(
        dest="subcommand", required=True, metavar="{list,view,create,send}"
    )
    list_parser = commands.add_parser(
        "list",
        help="saved courses",
        description="The courses saved in Garmin Connect, in Garmin's order.",
    )
    list_parser.add_argument(
        "--limit",
        type=positive_int,
        default=20,
        help="max courses to return (default: 20)",
    )
    list_parser.add_argument(
        "--raw", action="store_true", help="print the full Garmin response"
    )
    list_parser.set_defaults(run=course_list)
    view_parser = commands.add_parser(
        "view",
        help="one saved course",
        description="One saved course by its ID: name, activity type, distance, "
        "elevation and privacy.",
    )
    view_parser.add_argument(
        "id", type=course_id, help="course ID from 'garmin course list'"
    )
    view_parser.add_argument(
        "--raw", action="store_true", help="print the full Garmin response"
    )
    view_parser.set_defaults(run=course_view)
    return commands
