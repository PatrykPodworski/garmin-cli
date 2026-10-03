"""`garmin` entry point. A subcommand gets the parsed args and a Garmin client,
returns JSON-serializable data, and `main` prints it to stdout."""

import argparse
import json
import sys
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from garminconnect import Garmin

TOKENSTORE = "~/.garminconnect"


def connect() -> Any:
    client = Garmin()
    client.login(TOKENSTORE)
    return client


def parse_date(value: str) -> date:
    if value == "today":
        return date.today()
    if value == "yesterday":
        return date.today() - timedelta(days=1)
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected today, yesterday or YYYY-MM-DD, got {value!r}"
        ) from None


def add_date_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "date",
        nargs="?",
        default="today",
        type=parse_date,
        help="today | yesterday | YYYY-MM-DD (default: today)",
    )


def main(argv: list[str] | None = None, connect: Callable[[], Any] = connect) -> int:
    parser = argparse.ArgumentParser(
        prog="garmin", description="Read Garmin Connect data as JSON."
    )
    parser.add_subparsers(dest="command", required=True)
    args = parser.parse_args(argv)

    try:
        result = args.run(args, connect())
    except Exception as error:
        print(f"garmin: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0
