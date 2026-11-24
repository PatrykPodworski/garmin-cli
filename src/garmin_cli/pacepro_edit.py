import argparse
import sys
from typing import Any

from garmin_cli.client import Connect
from garmin_cli.courses import fetch_course
from garmin_cli.pacepro import fetch_plan, plan_id, plan_path, show
from garmin_cli.pacepro_create import elevation_track, goal_pace, goal_time
from garmin_cli.pacing import km_plan

# Keys Garmin adds to a stored plan; the website leaves them out of an update.
STORED_ONLY = {
    "paceBandPk",
    "userProfilePk",
    "createdDate",
    "lastUpdatedDate",
    "eventDate",
    "paceBandSplitPk",
    "bearing",
}
# The settings a plan from the v1 model always has.
V1_KEYS = ("splitType", "uphillEffort", "pacingStrategy", "manualPaceEdit")


def without_stored_keys(part: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in part.items() if key not in STORED_ONLY}


def edit_plan(args: argparse.Namespace, connect: Connect) -> Any:
    if args.name is None and args.goal_time is None and args.goal_pace is None:
        args.parser.fail("Nothing to change. Give --name, --goal-time or --goal-pace.")
    client = connect()
    stored = fetch_plan(client, args.id)
    summary = stored["paceBandSummary"]
    name = args.name or summary["name"]
    note = ""
    if args.goal_time or args.goal_pace:
        course = fetch_course(client, summary["courseId"])
        points = elevation_track(course, summary["courseId"])
        distance = course["distanceMeter"]
        seconds = args.goal_time or round(args.goal_pace * distance / 1000)
        plan = km_plan(summary["courseId"], name, seconds, distance, points)
        new = plan["paceBandSummary"]
        if any(summary.get(key) != new[key] for key in V1_KEYS):
            note = "; it now has km splits at the default sliders"
    else:
        plan = {
            "paceBandSummary": {**without_stored_keys(summary), "name": name},
            "paceBandSplits": [
                without_stored_keys(split) for split in stored["paceBandSplits"]
            ],
        }
    # garminconnect has no call to update a plan; this is the website's request.
    saved = client.client.put("connectapi", plan_path(args.id), json=plan, api=True)
    print(f'garmin: Updated PacePro plan "{name}"{note}.', file=sys.stderr)
    return show(saved)


def register(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    edit_parser = commands.add_parser(
        "edit",
        help="rename a PacePro plan or change its goal",
        description="Changes a PacePro plan's name or goal in Garmin Connect. A new "
        "goal recomputes the splits with garmin-cli's own pacing algorithm and saves "
        "the plan with a split every km and the website's default pacing, whatever "
        "splits, sliders or hand-edited paces it had. A new name alone keeps the "
        "splits.",
    )
    edit_parser.add_argument(
        "id", type=plan_id, help="plan ID from 'garmin pacepro list'"
    )
    edit_parser.add_argument("--name", help="new plan name")
    goal = edit_parser.add_mutually_exclusive_group()
    goal.add_argument("--goal-time", type=goal_time, help="finish time, H:MM:SS")
    goal.add_argument("--goal-pace", type=goal_pace, help="average pace per km, M:SS")
    edit_parser.set_defaults(run=edit_plan, parser=edit_parser)
