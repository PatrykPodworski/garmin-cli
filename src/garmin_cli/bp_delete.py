import argparse
import sys
from typing import Any

from garmin_cli.client import Connect
from garmin_cli.dates import parse_date
from garmin_cli.errors import GarminCliError


def reading_id(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        number = 0
    if number < 1:
        raise argparse.ArgumentTypeError(
            f"Invalid reading ID '{value}'. "
            "Run 'garmin bp --from DATE --to DATE' to list IDs."
        )
    return number


def delete_bp(args: argparse.Namespace, connect: Connect) -> Any:
    client = connect()
    day = args.date.isoformat()
    data = client.get_blood_pressure(day, day)
    reading = next(
        (
            reading
            for summary in data.get("measurementSummaries", [])
            for reading in summary.get("measurements", [])
            if reading.get("version") == args.id
        ),
        None,
    )
    if reading is None:
        raise GarminCliError(
            f"No blood pressure reading with ID {args.id} on {day}.",
            f"Run 'garmin bp --from {day} --to {day}' to list its IDs.",
        )
    at = reading["measurementTimestampLocal"].split("T")[1][:5]
    what = f"the reading of {day} {at} ({reading['systolic']}/{reading['diastolic']})"
    if args.dry_run:
        print(f"garmin: Would delete {what}.", file=sys.stderr)
        return {"would_delete": args.id}
    client.delete_blood_pressure(str(args.id), day)
    print(f"garmin: Deleted {what}.", file=sys.stderr)
    return {"deleted": args.id}


def register(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    delete_parser = commands.add_parser(
        "delete",
        help="delete a blood pressure reading",
        description="Deletes a blood pressure reading from Garmin Connect without "
        "asking. --dry-run shows what would be deleted.",
    )
    delete_parser.add_argument(
        "id", type=reading_id, help="reading ID from 'garmin bp'"
    )
    delete_parser.add_argument(
        "--date",
        required=True,
        type=parse_date,
        help="date of the reading: today | yesterday | tomorrow | YYYY-MM-DD",
    )
    delete_parser.add_argument(
        "--dry-run", action="store_true", help="show the reading, delete nothing"
    )
    delete_parser.set_defaults(run=delete_bp)
