import argparse
import sys
from typing import Any

from garmin_cli.client import Connect
from garmin_cli.courses import course_id, course_plans, course_write, fetch_course


def plan_label(plan: dict[str, Any]) -> str:
    name = (plan.get("paceBandSummary") or {}).get("name")
    return f'"{name}"' if name is not None else str(plan.get("paceBandPk"))


def delete_course(args: argparse.Namespace, connect: Connect) -> Any:
    client = connect()
    name = fetch_course(client, args.id).get("courseName")
    what = f'course "{name}"' if name is not None else f"course {args.id}"
    labels = [plan_label(plan) for plan in course_plans(client, args.id)]
    if len(labels) == 1:
        what += f" and its PacePro plan {labels[0]}"
    elif labels:
        what += f" and its {len(labels)} PacePro plans {', '.join(labels)}"
    if args.dry_run:
        print(f"garmin: Would delete {what}.", file=sys.stderr)
        return {"would_delete": args.id}
    course_write(args.id, lambda: client.delete_course(args.id))
    print(f"garmin: Deleted {what}.", file=sys.stderr)
    return {"deleted": args.id}


def register(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    delete_parser = commands.add_parser(
        "delete",
        help="delete a course",
        description="Deletes a course from Garmin Connect without asking. Garmin "
        "deletes the course's PacePro plans with it. --dry-run shows what would be "
        "deleted.",
    )
    delete_parser.add_argument(
        "id", type=course_id, help="course ID from 'garmin course list'"
    )
    delete_parser.add_argument(
        "--dry-run", action="store_true", help="show the course, delete nothing"
    )
    delete_parser.set_defaults(run=delete_course)
