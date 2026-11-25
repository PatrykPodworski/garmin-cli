import argparse
import sys
from collections.abc import Callable
from datetime import datetime
from typing import Any

from garmin_cli.client import Connect
from garmin_cli.health import bp_record
from garmin_cli.weight_add import local_time


def whole_number(name: str, low: int, high: int) -> Callable[[str], int]:
    """An argument type for a whole number in the range garminconnect accepts."""

    def parse(value: str) -> int:
        try:
            number = int(value)
        except ValueError:
            number = low - 1
        if not low <= number <= high:
            raise argparse.ArgumentTypeError(
                f"Invalid {name} '{value}'. Use a whole number from {low} to {high}."
            )
        return number

    return parse


def create_bp(args: argparse.Namespace, connect: Connect) -> Any:
    at = args.at or datetime.now().replace(second=0, microsecond=0).isoformat()
    client = connect()
    posted = client.set_blood_pressure(
        args.systolic,
        args.diastolic,
        pulse=args.pulse,
        timestamp=at,
        notes=args.notes,
    )
    # The POST answer has no `version`, the reading's ID; the stored reading has.
    day = at[:10]
    data = client.get_blood_pressure(day, day)
    stored = [
        reading
        for summary in data.get("measurementSummaries", [])
        for reading in summary.get("measurements", [])
        if reading["measurementTimestampLocal"].startswith(at[:16])
        and reading.get("systolic") == args.systolic
        and reading.get("diastolic") == args.diastolic
        and reading.get("pulse") == args.pulse
    ]
    reading = max(stored, key=lambda reading: reading["version"], default=posted)
    pulse = "" if args.pulse is None else f", pulse {args.pulse},"
    print(
        f"garmin: Logged blood pressure {args.systolic}/{args.diastolic}{pulse} "
        f"at {at[:16].replace('T', ' ')}.",
        file=sys.stderr,
    )
    return bp_record(reading)


def register(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    create_parser = commands.add_parser("create", help="log a blood pressure reading")
    create_parser.add_argument(
        "systolic", type=whole_number("systolic", 70, 260), help="mmHg, e.g. 121"
    )
    create_parser.add_argument(
        "diastolic", type=whole_number("diastolic", 40, 150), help="mmHg, e.g. 79"
    )
    create_parser.add_argument(
        "--pulse",
        type=whole_number("--pulse", 20, 250),
        metavar="BPM",
        help="heart rate in beats per minute",
    )
    create_parser.add_argument(
        "--at",
        type=local_time,
        metavar="'YYYY-MM-DD HH:MM'",
        help="local time of the reading (default: now)",
    )
    create_parser.add_argument(
        "--notes", default="", metavar="TEXT", help="a note on the reading"
    )
    create_parser.set_defaults(run=create_bp)
