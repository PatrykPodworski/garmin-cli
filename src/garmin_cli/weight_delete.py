import argparse
import sys
from typing import Any

from garmin_cli.client import Connect
from garmin_cli.dates import parse_date, wall_clock
from garmin_cli.errors import GarminCliError


def weigh_in_id(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        number = 0
    if number < 1:
        raise argparse.ArgumentTypeError(
            f"Invalid weigh-in ID '{value}'. "
            "Run 'garmin weight --from DATE --to DATE' to list IDs."
        )
    return number


def delete_weight(args: argparse.Namespace, connect: Connect) -> Any:
    client = connect()
    day = args.date.isoformat()
    data = client.get_weigh_ins(day, day)
    metric = next(
        (
            metric
            for summary in data.get("dailyWeightSummaries", [])
            for metric in summary.get("allWeightMetrics", [])
            if metric.get("samplePk") == args.id
        ),
        None,
    )
    if metric is None:
        raise GarminCliError(
            f"No weigh-in with ID {args.id} on {day}.",
            f"Run 'garmin weight --from {day} --to {day}' to list its IDs.",
        )
    at = wall_clock(metric["date"]).strftime("%H:%M")
    what = f"the weigh-in of {day} {at} ({round(metric['weight'] / 1000, 2)} kg)"
    if args.dry_run:
        print(f"garmin: Would delete {what}.", file=sys.stderr)
        return {"would_delete": args.id}
    client.delete_weigh_in(str(args.id), day)
    print(f"garmin: Deleted {what}.", file=sys.stderr)
    return {"deleted": args.id}


def register(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    delete_parser = commands.add_parser(
        "delete",
        help="delete a weigh-in",
        description="Deletes a weigh-in from Garmin Connect without asking. "
        "--dry-run shows what would be deleted.",
    )
    delete_parser.add_argument(
        "id", type=weigh_in_id, help="weigh-in ID from 'garmin weight'"
    )
    delete_parser.add_argument(
        "--date",
        required=True,
        type=parse_date,
        help="date of the weigh-in: today | yesterday | tomorrow | YYYY-MM-DD",
    )
    delete_parser.add_argument(
        "--dry-run", action="store_true", help="show the weigh-in, delete nothing"
    )
    delete_parser.set_defaults(run=delete_weight)
