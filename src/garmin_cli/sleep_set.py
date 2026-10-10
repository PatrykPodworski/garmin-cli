import argparse
from datetime import date, datetime, timedelta
from typing import Any

from garmin_cli.client import Connect
from garmin_cli.dates import machine_zone, parse_time, zone_gmt_ms
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
    end = datetime.combine(wake_up, args.end)
    start = datetime.combine(wake_up, args.start)
    if args.start > args.end:
        start -= timedelta(days=1)
    zone = machine_zone()
    if zone is None or datetime.fromtimestamp(gmt / 1000, zone).utcoffset() != (
        timedelta(milliseconds=local - gmt)
    ):
        # ponytail: a night slept in another time zone (travel) is rare enough for
        # the Garmin Connect app; a --tz option can come when someone needs it.
        raise GarminCliError(
            f"The night ending {night['calendarDate']} was not in this machine's "
            "time zone, so garmin-cli cannot convert the times.",
            "Adjust the sleep times in the Garmin Connect app.",
        )
    # Each time gets its own offset, also when the clocks change that night.
    try:
        start_ms, end_ms = zone_gmt_ms(start, zone), zone_gmt_ms(end, zone)
    except ValueError as problem:
        args.parser.fail(
            f"{problem} because the clocks change that night. Give another time."
        )
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
