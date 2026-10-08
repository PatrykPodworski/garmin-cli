import argparse
import re
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from garmin_cli.client import Connect, GarminClient
from garmin_cli.dates import add_date_argument, parse_date, wall_clock
from garmin_cli.errors import GarminCliError


def minutes(seconds: int | None) -> int | None:
    return None if seconds is None else seconds // 60


def parse_time(value: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid time '{value}'. Use HH:MM, for example 23:10."
        ) from None


def fetch(args: argparse.Namespace, client: GarminClient, key: str) -> dict[str, Any]:
    """The night's full Garmin response; an error when its `dailySleepDTO` has no
    `key`."""
    day = args.night_of + timedelta(days=1) if args.night_of else args.date
    data: dict[str, Any] = client.get_sleep_data(day.isoformat())
    night = data.get("dailySleepDTO") or {}
    if not night.get(key):
        if args.night_of:
            raise GarminCliError(
                f"No sleep data for the night of {args.night_of} yet.",
                "Sync your watch with Garmin Connect, then try again.",
            )
        raise GarminCliError(
            f"No sleep data for the night ending {day} yet.",
            f"Sync your watch with Garmin Connect, or use --night-of if {day} is "
            "the night you went to bed.",
        )
    return data


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    night = data["dailySleepDTO"]
    scores = dict(night.get("sleepScores") or {})
    overall = scores.pop("overall", None) or {}
    return {
        "date": night["calendarDate"],
        "start": wall_clock(night["sleepStartTimestampLocal"]).strftime("%H:%M"),
        "end": wall_clock(night["sleepEndTimestampLocal"]).strftime("%H:%M"),
        "duration_min": minutes(night["sleepTimeSeconds"]),
        "deep_min": minutes(night.get("deepSleepSeconds")),
        "light_min": minutes(night.get("lightSleepSeconds")),
        "rem_min": minutes(night.get("remSleepSeconds")),
        "awake_min": minutes(night.get("awakeSleepSeconds")),
        "score": overall.get("value"),
        "scores": {
            re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower(): {
                "value": score.get("value"),
                "qualifier": score.get("qualifierKey"),
            }
            for name, score in scores.items()
        },
    }


def sleep(args: argparse.Namespace, connect: Connect) -> Any:
    data = fetch(args, connect(), "sleepTimeSeconds")
    return data if args.raw else summarize(data)


def set_sleep(args: argparse.Namespace, connect: Connect) -> Any:
    if args.start == args.end:
        args.parser.fail(
            f"--start and --end are both {args.start:%H:%M}. Give two different times."
        )
    client = connect()
    night = fetch(args, client, "id")["dailySleepDTO"]
    local, gmt = night.get("sleepEndTimestampLocal"), night.get("sleepEndTimestampGMT")
    if local is None or gmt is None:
        raise GarminCliError(
            f"Garmin Connect sent no time zone for the night ending "
            f"{night['calendarDate']}, so garmin-cli cannot convert the times.",
            "Adjust the sleep times in the Garmin Connect app.",
        )
    wake_up = date.fromisoformat(night["calendarDate"])
    end = datetime.combine(wake_up, args.end, UTC)
    start = datetime.combine(wake_up, args.start, UTC)
    if args.start > args.end:
        start -= timedelta(days=1)
    # Local timestamps are wall-clock time encoded as UTC, so subtracting the
    # night's own offset gives GMT whatever the machine's time zone is.
    start_ms, end_ms = (int(t.timestamp()) * 1000 - (local - gmt) for t in (start, end))
    client.client.put(
        "connectapi",
        f"/sleep-service/sleep/dailySleep/{night['id']}",
        json={
            "id": night["id"],
            "userProfilePK": night["userProfilePK"],
            "calendarDate": night["calendarDate"],
            "sleepStartTimestampGMT": start_ms,
            "sleepEndTimestampGMT": end_ms,
            "sleepTimeSeconds": (end_ms - start_ms) // 1000,
            "napTimeSeconds": night.get("napTimeSeconds") or 0,
            "sleepWindowConfirmed": True,
        },
        api=True,
    )
    return summarize(fetch(args, client, "sleepTimeSeconds"))


def add_night_arguments(parser: argparse.ArgumentParser) -> None:
    night = parser.add_mutually_exclusive_group()
    add_date_argument(night)
    night.add_argument(
        "--night-of",
        type=parse_date,
        metavar="DATE",
        help="lights-out date: the night that started on DATE",
    )


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    sleep_parser = subparsers.add_parser(
        "sleep",
        help="sleep window, sleep score and stages for one night",
        description="Garmin files a night under its wake-up date: `date` is the "
        "morning you woke up. --night-of DATE takes the lights-out date instead "
        "and shows the night that started on DATE.",
    )
    add_night_arguments(sleep_parser)
    sleep_parser.add_argument(
        "--raw", action="store_true", help="print the full Garmin response"
    )
    sleep_parser.set_defaults(run=sleep)
    # `main` joins `garmin sleep set` into this one command name.
    set_parser = subparsers.add_parser(
        "sleep set",
        help="move one night's sleep start and end on Garmin Connect",
        description="Like 'Adjust sleep times' in the Garmin Connect app. `date` "
        "is the wake-up date, as in 'garmin sleep'. Times are local HH:MM; the end "
        "is on the wake-up date, and a start later than the end is on the evening "
        "before. Prints the updated night; Garmin may update the sleep score later.",
    )
    add_night_arguments(set_parser)
    for flag in ("--start", "--end"):
        set_parser.add_argument(
            flag, required=True, type=parse_time, metavar="HH:MM", help="local time"
        )
    set_parser.set_defaults(run=set_sleep, parser=set_parser)
