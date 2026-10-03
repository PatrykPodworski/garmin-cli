"""`garmin` entry point. A subcommand gets the parsed args and a Garmin client,
returns JSON-serializable data, and `main` prints it to stdout."""

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from garminconnect import Garmin, GarminConnectAuthenticationError


def tokenstore() -> str:
    return os.environ.get("GARMINTOKENS", "~/.garminconnect")


def connect() -> Any:
    client = Garmin()
    try:
        client.login(tokenstore())
    except GarminConnectAuthenticationError:
        raise RuntimeError("no valid saved tokens, run 'garmin login'") from None
    return client


def login() -> dict[str, str]:
    email = os.environ.get("GARMIN_EMAIL")
    if not email:
        raise RuntimeError("set GARMIN_EMAIL to your Garmin account email")
    keychain = subprocess.run(
        ["security", "find-generic-password", "-s", "garmin", "-a", email, "-w"],
        capture_output=True,
        text=True,
    )
    if keychain.returncode != 0:
        raise RuntimeError(
            f"no Keychain password for service 'garmin', account {email}"
        )
    password = keychain.stdout.rstrip("\n")
    client = Garmin(email, password, prompt_mfa=lambda: input("MFA code: "))
    path = tokenstore()
    client.login(path)
    return {"tokenstore": path}


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


def add_date_argument(parser: argparse._ActionsContainer) -> None:
    parser.add_argument(
        "date",
        nargs="?",
        default=date.today(),
        type=parse_date,
        help="today | yesterday | YYYY-MM-DD (default: today)",
    )


def local_time(timestamp_ms: int) -> str:
    # Garmin "Local" timestamps hold the wall-clock time encoded as UTC.
    return datetime.fromtimestamp(timestamp_ms / 1000, UTC).strftime("%H:%M")


def sleep(args: argparse.Namespace, client: Any) -> Any:
    day = args.night_of + timedelta(days=1) if args.night_of else args.date
    data: dict[str, Any] = client.get_sleep_data(day.isoformat())
    night = data.get("dailySleepDTO") or {}
    if not night.get("sleepTimeSeconds"):
        raise RuntimeError(f"no sleep data for {day}, not synced yet")
    if args.raw:
        return data
    scores = dict(night.get("sleepScores") or {})
    overall = scores.pop("overall", None) or {}
    return {
        "date": night["calendarDate"],
        "start": local_time(night["sleepStartTimestampLocal"]),
        "end": local_time(night["sleepEndTimestampLocal"]),
        "duration_min": night["sleepTimeSeconds"] // 60,
        "deep_min": night["deepSleepSeconds"] // 60,
        "light_min": night["lightSleepSeconds"] // 60,
        "rem_min": night["remSleepSeconds"] // 60,
        "awake_min": night["awakeSleepSeconds"] // 60,
        "score": overall.get("value"),
        "scores": {
            re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower(): {
                "value": score.get("value"),
                "qualifier": score.get("qualifierKey"),
            }
            for name, score in scores.items()
        },
    }


def main(argv: list[str] | None = None, connect: Callable[[], Any] = connect) -> int:
    parser = argparse.ArgumentParser(
        prog="garmin", description="Read Garmin Connect data as JSON."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "login",
        help="log in as GARMIN_EMAIL with the Keychain password, save tokens",
    )
    sleep_parser = subparsers.add_parser(
        "sleep",
        help="sleep window, sleep score and stages for one night",
        description="Garmin files a night under its wake-up date: `date` is the "
        "morning you woke up. --night-of DATE takes the lights-out date instead "
        "and shows the night that started on DATE.",
    )
    night = sleep_parser.add_mutually_exclusive_group()
    add_date_argument(night)
    night.add_argument(
        "--night-of",
        type=parse_date,
        metavar="DATE",
        help="lights-out date: the night that started on DATE",
    )
    sleep_parser.add_argument(
        "--raw", action="store_true", help="print the full Garmin response"
    )
    sleep_parser.set_defaults(run=sleep)
    args = parser.parse_args(argv)

    try:
        if args.command == "login":
            result: Any = login()
        else:
            result = args.run(args, connect())
    except Exception as error:
        print(f"garmin: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0
