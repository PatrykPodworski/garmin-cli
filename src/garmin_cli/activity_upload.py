import argparse
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn
from xml.etree import ElementTree

from garminconnect import GarminConnectConnectionError

from garmin_cli.activities import activity
from garmin_cli.client import Connect
from garmin_cli.course_create import local_name, source_of
from garmin_cli.errors import GarminCliError

XML_FORMATS = {"gpx": "gpx", "TrainingCenterDatabase": "tcx"}
POLLS = 30


def file_format(data: bytes) -> str | None:
    # A FIT file header holds ".FIT" in bytes 8 to 11.
    if data[8:12] == b".FIT":
        return "fit"
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError:
        return None
    return XML_FORMATS.get(local_name(root.tag))


def read_activity_file(args: argparse.Namespace) -> tuple[bytes, str]:
    """The file's bytes and its format, `fit`, `gpx` or `tcx`."""
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
            f"Cannot read {source} ({error.strerror}). Pass a FIT, GPX or TCX file, "
            "or '-' for stdin."
        )
    kind = file_format(data)
    if kind is None:
        fail(f"{source} is not a FIT, GPX or TCX file.")
    return data, kind


def failures(answer: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = answer.json()["detailedImportResult"]["failures"]
    return found


def first_failure(answer: Any) -> dict[str, Any]:
    return (failures(answer) or [{}])[0]


def rejected(source: str, answer: Any) -> GarminCliError:
    messages = first_failure(answer).get("messages") or [{}]
    reason = messages[0].get("content", "no reason given").rstrip(".")
    return GarminCliError(
        f"Garmin did not accept {source}: {reason}.",
        "Check that the file opens in another app, or upload it in Garmin Connect.",
    )


def duplicate(source: str, answer: Any) -> GarminCliError:
    existing = first_failure(answer).get("internalId")
    if existing is None:
        return GarminCliError(
            f"{source} is already on Garmin Connect.",
            "Run 'garmin activities' to find it.",
        )
    return GarminCliError(
        f"{source} is already on Garmin Connect as activity {existing}.",
        f"Run 'garmin activity {existing}' to see it.",
    )


def upload(args: argparse.Namespace, connect: Connect) -> Any:
    data, kind = read_activity_file(args)
    source = source_of(args)
    stem = "activity" if args.file == "-" else Path(args.file).stem
    name = f"{stem}.{kind}"
    client = connect()
    # garminconnect's `upload_activity` sends this request but returns only the
    # body, and the activity ID is behind the answer's `location` header.
    try:
        answer = client.client.post(
            "connectapi", "/upload-service/upload", files={"file": (name, data)}
        )
    except GarminConnectConnectionError as error:
        if error.response is not None and error.response.status_code == 409:
            raise duplicate(source, error.response) from error
        raise
    if "location" not in answer.headers:
        raise rejected(source, answer)
    # Garmin answers 202 while it processes the file and 201 once the activity
    # exists, about 2 s after the upload in the live test of #166.
    for attempt in range(POLLS):
        if attempt:
            time.sleep(1)
        status = client.client.request("GET", "connectapi", answer.headers["location"])
        if status.status_code != 202:
            break
    else:
        print(
            f"garmin: Uploaded {source}; Garmin is still processing it. "
            "Run 'garmin activities' in a minute to find it.",
            file=sys.stderr,
        )
        return {
            "upload_id": answer.json()["detailedImportResult"]["uploadId"],
            "file": name,
        }
    if "location" not in status.headers or failures(status):
        raise rejected(source, status)
    activity_id = status.headers["location"].rpartition("/")[2]
    shown = activity(argparse.Namespace(id=activity_id, raw=False), lambda: client)
    print(f"garmin: Uploaded {source} as activity {activity_id}.", file=sys.stderr)
    return shown
