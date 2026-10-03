"""`garmin` entry point. A subcommand gets the parsed args and a Garmin client,
returns JSON-serializable data, and `main` prints it to stdout."""

import argparse
import json
import os
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


def add_date_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "date",
        nargs="?",
        default="today",
        type=parse_date,
        help="today | yesterday | YYYY-MM-DD (default: today)",
    )


def add_range_arguments(parser: argparse.ArgumentParser) -> None:
    for flag, dest in (("--from", "start"), ("--to", "end")):
        parser.add_argument(
            flag,
            dest=dest,
            metavar="DATE",
            default="today",
            type=parse_date,
            help="today | yesterday | YYYY-MM-DD (default: today)",
        )


def kilograms(grams: float | None) -> float | None:
    return None if grams is None else grams / 1000


def weight(args: argparse.Namespace, client: Any) -> list[dict[str, Any]]:
    data = client.get_weigh_ins(args.start.isoformat(), args.end.isoformat())
    records = []
    for day in data.get("dailyWeightSummaries", []):
        for metric in day.get("allWeightMetrics", []):
            # Garmin encodes the local wall-clock time as if it were UTC.
            local = datetime.fromtimestamp(metric["date"] / 1000, UTC)
            records.append(
                {
                    "date": metric["calendarDate"],
                    "time": local.strftime("%H:%M:%S"),
                    "weight_kg": kilograms(metric.get("weight")),
                    "body_fat_pct": metric.get("bodyFat"),
                    "muscle_mass_kg": kilograms(metric.get("muscleMass")),
                    "body_water_pct": metric.get("bodyWater"),
                }
            )
    return records


def blood_pressure(args: argparse.Namespace, client: Any) -> list[dict[str, Any]]:
    data = client.get_blood_pressure(args.start.isoformat(), args.end.isoformat())
    records = []
    for day in data.get("measurementSummaries", []):
        for reading in day.get("measurements", []):
            day_part, time_part = reading["measurementTimestampLocal"].split("T")
            records.append(
                {
                    "date": day_part,
                    "time": time_part[:8],
                    "systolic": reading.get("systolic"),
                    "diastolic": reading.get("diastolic"),
                    "pulse": reading.get("pulse"),
                    "notes": reading.get("notes"),
                }
            )
    return records


def main(argv: list[str] | None = None, connect: Callable[[], Any] = connect) -> int:
    parser = argparse.ArgumentParser(
        prog="garmin", description="Read Garmin Connect data as JSON."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "login",
        help="log in as GARMIN_EMAIL with the Keychain password, save tokens",
    )
    weight_parser = subparsers.add_parser("weight", help="weigh-ins in a date range")
    add_range_arguments(weight_parser)
    weight_parser.set_defaults(run=weight)
    bp_parser = subparsers.add_parser("bp", help="blood pressure in a date range")
    add_range_arguments(bp_parser)
    bp_parser.set_defaults(run=blood_pressure)
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
