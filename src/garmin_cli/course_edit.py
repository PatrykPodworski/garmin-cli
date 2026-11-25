import argparse
import sys
from typing import Any

from garmin_cli.activities import nonblank_name
from garmin_cli.client import Connect
from garmin_cli.course_create import privacy
from garmin_cli.courses import (
    PRIVACY,
    course_id,
    course_write,
    fetch_course,
    summarize,
    type_keys,
)


def edit_course(args: argparse.Namespace, connect: Connect) -> Any:
    if args.name is None and args.privacy is None:
        args.parser.fail("Nothing to change. Give --name or --privacy.")
    client = connect()
    # Garmin's update takes the full course object, track and elevation included.
    body = fetch_course(client, args.id)
    if args.name is not None:
        body = {**body, "courseName": args.name}
    if args.privacy is not None:
        body = {**body, "rulePK": PRIVACY[args.privacy]}
    saved = course_write(args.id, lambda: client.update_course(args.id, body))
    if saved is None:
        saved = fetch_course(client, args.id)
    name = saved.get("courseName")
    what = (
        f'course "{name}" (ID {args.id})' if name is not None else f"course {args.id}"
    )
    print(f"garmin: Updated {what}.", file=sys.stderr)
    return summarize(saved, type_keys(client))


def register(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    edit_parser = commands.add_parser(
        "edit",
        help="rename a course or change its privacy",
        description="Changes a course's name or privacy in Garmin Connect. Only the "
        "options given change; the track, elevation and other fields stay as they are.",
    )
    edit_parser.add_argument(
        "id", type=course_id, help="course ID from 'garmin course list'"
    )
    edit_parser.add_argument("--name", type=nonblank_name, help="new course name")
    edit_parser.add_argument("--privacy", type=privacy, help="private or public")
    edit_parser.set_defaults(run=edit_course, parser=edit_parser)
