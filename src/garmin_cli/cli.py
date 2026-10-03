"""`garmin` entry point. A subcommand gets the parsed args and a `connect`
function, returns JSON-serializable data, and `main` prints it to stdout."""

import argparse
import json
import sys

from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from garmin_cli import activities, auth, health, sleep, stats
from garmin_cli.client import Connect
from garmin_cli.errors import GarminCliError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="garmin", description="Read Garmin Connect data as JSON."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    auth.register(subparsers)
    health.register(subparsers)
    sleep.register(subparsers)
    activities.register(subparsers)
    stats.register(subparsers)
    return parser


def main(argv: list[str] | None = None, connect: Connect = auth.connect) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = args.run(args, connect)
    # OSError covers network failures: requests exceptions subclass it.
    except (
        GarminCliError,
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
        OSError,
    ) as error:
        print(f"garmin: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0
