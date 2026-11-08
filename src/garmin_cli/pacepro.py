import argparse
from typing import Any

from garminconnect import GarminConnectNotFoundError

from garmin_cli.activities import positive_int
from garmin_cli.client import Connect, GarminClient
from garmin_cli.errors import GarminCliError

LIST_IDS = "Run 'garmin pacepro list' to list IDs."
# The `splitType` values seen on a real account. Any other value passes through.
SPLITS: dict[Any, str] = {"DISTANCE_KILOMETER": "km", "ELEVATION": "elevation"}
# garminconnect has a list call only: no create, edit, delete, get or send.
# `fetch_plan` and the create, edit and delete commands call the website's
# endpoints themselves.
UI_ONLY = (
    "Send plans to a watch in Garmin Connect (Training & Planning > PacePro "
    "Pacing Strategies); garminconnect has no call for that."
)


def plan_path(plan_id: int) -> str:
    return f"/course-service/pacebands/{plan_id}"


def plan_id(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        number = 0
    if number < 1:
        raise argparse.ArgumentTypeError(
            f"Invalid PacePro plan ID '{value}'. {LIST_IDS}"
        )
    return number


def pace(speed: float | None) -> int | None:
    """Seconds per km for a speed in m/s."""
    return round(1000 / speed) if speed else None


def summarize(raw: dict[str, Any]) -> dict[str, Any]:
    plan: dict[str, Any] = raw.get("paceBandSummary") or {}
    split = plan.get("splitType")
    summary = {
        "id": raw.get("paceBandPk"),
        "name": plan.get("name"),
        "course_id": plan.get("courseId"),
        "split": SPLITS.get(split, split),
        "distance_m": plan.get("totalDistance"),
        "goal_time_s": plan.get("goalTime"),
        "goal_pace_s_per_km": pace(plan.get("goalSpeed")),
        "pacing_strategy": plan.get("pacingStrategy"),
        "uphill_effort": plan.get("uphillEffort"),
        "splits": len(raw.get("paceBandSplits") or []),
    }
    return {name: value for name, value in summary.items() if value is not None}


def elevation_change(raw: dict[str, Any]) -> float | None:
    start: float | None = (raw.get("startPoint") or {}).get("elevation")
    end: float | None = (raw.get("endPoint") or {}).get("elevation")
    if start is None or end is None:
        return None
    return end - start


def summarize_split(raw: dict[str, Any]) -> dict[str, Any]:
    split = {
        "distance_m": raw.get("splitDistance"),
        "pace_s_per_km": pace(raw.get("splitAvgSpeed")),
        "elevation_change_m": elevation_change(raw),
        "cumulative_distance_m": raw.get("cumulativeDistanceFromStart"),
        "cumulative_time_s": raw.get("cumulativeTimeFromStart"),
    }
    return {name: value for name, value in split.items() if value is not None}


def show(plan: dict[str, Any]) -> dict[str, Any]:
    splits = plan.get("paceBandSplits") or []
    return {**summarize(plan), "splits": [summarize_split(split) for split in splits]}


def pacepro_list(args: argparse.Namespace, connect: Connect) -> Any:
    found = connect().get_pace_bands()[: args.limit]
    return found if args.raw else [summarize(plan) for plan in found]


def fetch_plan(client: GarminClient, plan_id: int) -> dict[str, Any]:
    try:
        plan: dict[str, Any] = client.connectapi(plan_path(plan_id))
    except GarminConnectNotFoundError:
        raise GarminCliError(f"No PacePro plan with ID {plan_id}.", LIST_IDS) from None
    return plan


def pacepro_view(args: argparse.Namespace, connect: Connect) -> Any:
    plan = fetch_plan(connect(), args.id)
    return plan if args.raw else show(plan)


def register(
    subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> "argparse._SubParsersAction[argparse.ArgumentParser]":
    """Returns the `pacepro` commands, for the write modules to add theirs."""
    pacepro_parser = subparsers.add_parser(
        "pacepro", help="PacePro pacing plans: list, view, create, edit and delete"
    )
    # `CliParser.explain` names a missing command by this metavar.
    commands = pacepro_parser.add_subparsers(
        dest="subcommand", required=True, metavar="{list,view,create,edit,delete}"
    )
    list_parser = commands.add_parser(
        "list",
        help="saved PacePro plans",
        description=f"The PacePro plans saved in Garmin Connect, in Garmin's order. "
        f"Read-only. {UI_ONLY}",
    )
    list_parser.add_argument(
        "--limit",
        type=positive_int,
        default=20,
        help="max plans to return (default: 20)",
    )
    list_parser.add_argument(
        "--raw", action="store_true", help="print the full Garmin response"
    )
    list_parser.set_defaults(run=pacepro_list)
    view_parser = commands.add_parser(
        "view",
        help="one PacePro plan with its splits",
        description=f"One PacePro plan by its ID, with the target pace of each split. "
        f"Read-only. {UI_ONLY}",
    )
    view_parser.add_argument(
        "id", type=plan_id, help="plan ID from 'garmin pacepro list'"
    )
    view_parser.add_argument(
        "--raw", action="store_true", help="print the full Garmin response"
    )
    view_parser.set_defaults(run=pacepro_view)
    return commands
