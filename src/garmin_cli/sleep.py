import argparse
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from garmin_cli.dates import add_date_argument, parse_date


def local_time(timestamp_ms: int) -> str:
    # Garmin "Local" timestamps hold the wall-clock time encoded as UTC.
    return datetime.fromtimestamp(timestamp_ms / 1000, UTC).strftime("%H:%M")


def sleep(args: argparse.Namespace, connect: Callable[[], Any]) -> Any:
    day = args.night_of + timedelta(days=1) if args.night_of else args.date
    data: dict[str, Any] = connect().get_sleep_data(day.isoformat())
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


def register(subparsers: Any) -> None:
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
