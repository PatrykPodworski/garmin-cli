import argparse
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn
from xml.etree import ElementTree

from garmin_cli.activities import require_type
from garmin_cli.client import Connect
from garmin_cli.courses import PRIVACY, summarize
from garmin_cli.errors import GarminCliError


def course_name(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError(
            f"Invalid --name '{value}'. Give a name that is not blank."
        )
    return value.strip()


def privacy(value: str) -> str:
    if value not in PRIVACY:
        raise argparse.ArgumentTypeError(
            f"Invalid --privacy '{value}'. Use private or public."
        )
    return value


def source_of(args: argparse.Namespace) -> str:
    return "stdin" if args.file == "-" else f"'{args.file}'"


def local_name(tag: str) -> str:
    """`{http://www.topografix.com/GPX/1/1}trkpt` -> `trkpt`."""
    return tag.rpartition("}")[2]


def read_gpx(args: argparse.Namespace) -> bytes:
    """The GPX bytes, after checking they hold a track or route Garmin can import."""
    # `args.parser` is untyped; the annotation tells mypy `fail` exits.
    fail: Callable[[str], NoReturn] = args.parser.fail
    source = source_of(args)
    try:
        data = (
            sys.stdin.buffer.read()
            if args.file == "-"
            else Path(args.file).read_bytes()
        )
    except OSError as error:
        fail(
            f"Cannot read {source} ({error.strerror}). Pass a GPX file, or '-' for "
            "stdin."
        )
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as error:
        fail(f"Invalid XML in {source}: {error}. Pass a GPX file.")
    if (name := local_name(root.tag)) != "gpx":
        fail(
            f"The XML in {source} is <{name}>, not GPX. Pass a GPX file; TCX and FIT "
            "are not supported."
        )
    points = sum(local_name(node.tag) in ("trkpt", "rtept") for node in root.iter())
    if points < 2:
        fail(
            f"The GPX in {source} has {points} track or route points. A course needs "
            "at least 2."
        )
    return data


def create_course(args: argparse.Namespace, connect: Connect) -> Any:
    gpx = read_gpx(args)
    client = connect()
    types = {kind["typeKey"]: kind["typeId"] for kind in client.get_activity_types()}
    require_type(args.type, types, args.parser.fail)
    stem = "Course" if args.file == "-" else Path(args.file).stem
    # The library reads a path and wants a .gpx suffix, which stdin has not.
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / f"{stem}.gpx"
        path.write_bytes(gpx)
        # Garmin parses the file into a course object without saving it.
        imported = client.import_course(str(path))
    if not isinstance(imported, dict) or not imported.get("geoPoints"):
        raise GarminCliError(
            f"Garmin found no track in {source_of(args)}, so no course was saved.",
            "Check that the file imports in Garmin Connect's course import.",
        )
    saved = client.create_course(
        {
            **imported,
            "courseName": args.name or imported.get("courseName") or stem,
            "activityTypePk": types[args.type],
            "rulePK": PRIVACY[args.privacy],
        }
    )
    print(
        f"garmin: Imported {source_of(args)} and saved it as course "
        f'"{saved.get("courseName")}" (ID {saved["courseId"]}).',
        file=sys.stderr,
    )
    return summarize(saved, {type_id: key for key, type_id in types.items()})


def register(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    create_parser = commands.add_parser(
        "create",
        help="save a GPX file as a course",
        description="Imports a GPX file into Garmin Connect and saves it as a "
        "course. The import alone saves nothing and has no ID; the saved course gets "
        "the ID that 'garmin course view' takes.",
    )
    create_parser.add_argument(
        "--file", required=True, help="GPX file, or - to read stdin"
    )
    create_parser.add_argument(
        "--name",
        type=course_name,
        help="course name (default: the name Garmin reads from the GPX, else the "
        "file name)",
    )
    create_parser.add_argument(
        "--type",
        default="running",
        help="Garmin activity type key: running, trail_running, cycling, hiking, ... "
        "(default: running)",
    )
    create_parser.add_argument(
        "--privacy",
        type=privacy,
        default="private",
        help="private or public (default: private)",
    )
    create_parser.set_defaults(run=create_course, parser=create_parser)
