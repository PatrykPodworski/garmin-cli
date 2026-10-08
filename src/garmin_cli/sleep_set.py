import argparse
from datetime import UTC, date, datetime, timedelta
from typing import Any

from garmin_cli.client import Connect
from garmin_cli.dates import gmt_ms, parse_time
from garmin_cli.errors import GarminCliError
from garmin_cli.sleep import add_night_arguments, fetch, summarize


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
    # The night's own offset gives GMT whatever the machine's time zone is.
    start_ms, end_ms = (gmt_ms(t, local - gmt) for t in (start, end))
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


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    # `main` joins `garmin sleep set` into this one command name. Without a `help`,
    # `garmin --help` leaves it out; `garmin sleep --help` names it.
    set_parser = subparsers.add_parser(
        "sleep set",
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
