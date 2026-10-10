import argparse
import os
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

LOCALTIME = Path("/etc/localtime")


def parse_date(value: str) -> date:
    if value == "today":
        return date.today()
    if value == "yesterday":
        return date.today() - timedelta(days=1)
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'. Use today, yesterday or YYYY-MM-DD."
        ) from None


def wall_clock(timestamp_ms: int) -> datetime:
    # Garmin "Local" timestamps hold the wall-clock time encoded as UTC.
    return datetime.fromtimestamp(timestamp_ms / 1000, UTC)


def zone_gmt_ms(wall: datetime, zone: ZoneInfo) -> int:
    """Epoch ms in GMT of the naive wall-clock time `wall` in `zone`. Raises
    ValueError when a clock change skips the time or shows it twice."""
    first, second = (
        wall.replace(tzinfo=zone, fold=fold).timestamp() for fold in (0, 1)
    )
    if first > second:
        raise ValueError(f"{wall:%Y-%m-%d %H:%M} does not exist")
    if first < second:
        raise ValueError(f"{wall:%Y-%m-%d %H:%M} happens twice")
    return int(first) * 1000


def parse_time(value: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid time '{value}'. Use HH:MM, for example 23:10."
        ) from None


def parse_datetime(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid time '{value}'. Use 'YYYY-MM-DD HH:MM', "
            "for example '2026-07-05 18:30'."
        ) from None


def local_time_zone() -> str | None:
    """The machine's IANA time zone name: `TZ`, else the zoneinfo path that
    /etc/localtime links to."""
    if name := os.environ.get("TZ"):
        return name
    try:
        target = str(LOCALTIME.readlink())
    except OSError:
        return None
    return target.partition("zoneinfo/")[2] or None


def machine_zone() -> ZoneInfo | None:
    name = local_time_zone()
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def add_date_argument(parser: argparse._ActionsContainer) -> None:
    parser.add_argument(
        "date",
        nargs="?",
        default=date.today(),
        type=parse_date,
        help="today | yesterday | YYYY-MM-DD (default: today)",
    )


def add_range_arguments(parser: argparse.ArgumentParser, default: date | None) -> None:
    help = "today | yesterday | YYYY-MM-DD"
    if default:
        help += " (default: today)"
    for flag, dest in (("--from", "start"), ("--to", "end")):
        parser.add_argument(
            flag, dest=dest, metavar="DATE", default=default, type=parse_date, help=help
        )
