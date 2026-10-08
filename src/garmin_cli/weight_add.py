import argparse
import math
from datetime import datetime
from typing import Any

from garmin_cli.client import Connect


def positive_weight(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        number = 0
    if not (math.isfinite(number) and number > 0):
        raise argparse.ArgumentTypeError(
            f"Invalid weight '{value}'. Use a number above 0, like 82.4."
        )
    return number


def weight_unit(value: str) -> str:
    if value not in ("kg", "lbs"):
        raise argparse.ArgumentTypeError(f"Invalid --unit '{value}'. Use kg or lbs.")
    return value


def local_time(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M").isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid --at '{value}'. Use 'YYYY-MM-DD HH:MM' in local time."
        ) from None


def add_weight(args: argparse.Namespace, connect: Connect) -> Any:
    # An empty timestamp makes garminconnect use the current time.
    return connect().add_weigh_in(args.weight, args.unit, args.at or "")


def register(weight_parser: argparse.ArgumentParser) -> None:
    add_parser = weight_parser.add_subparsers(dest="subcommand").add_parser(
        "add", help="log a weigh-in"
    )
    add_parser.add_argument("weight", type=positive_weight, help="e.g. 82.4")
    add_parser.add_argument(
        "--at",
        type=local_time,
        metavar="'YYYY-MM-DD HH:MM'",
        help="local time of the weigh-in (default: now)",
    )
    add_parser.add_argument(
        "--unit", type=weight_unit, default="kg", help="kg or lbs (default: kg)"
    )
    add_parser.set_defaults(run=add_weight)
