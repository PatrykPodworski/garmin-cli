import argparse
from datetime import UTC, date, datetime, time, timedelta

from garmin_cli.dates import add_date_argument, sleep_window


def parse(*argv: str) -> date:
    parser = argparse.ArgumentParser()
    add_date_argument(parser)
    day: date = parser.parse_args(argv).date
    return day


def test_date_defaults_to_today() -> None:
    assert parse() == date.today()


def test_date_today() -> None:
    assert parse("today") == date.today()


def test_date_yesterday() -> None:
    assert parse("yesterday") == date.today() - timedelta(days=1)


def test_date_iso() -> None:
    assert parse("2026-07-05") == date(2026, 7, 5)


def test_date_tomorrow() -> None:
    assert parse("tomorrow") == date.today() + timedelta(days=1)


def test_sleep_window_start_later_than_end_is_the_evening_before() -> None:
    assert sleep_window(date(2026, 7, 5), time(23, 40), time(7, 15)) == (
        datetime(2026, 7, 4, 23, 40, tzinfo=UTC),
        datetime(2026, 7, 5, 7, 15, tzinfo=UTC),
    )


def test_sleep_window_start_earlier_than_end_is_the_wake_up_date() -> None:
    assert sleep_window(date(2026, 7, 5), time(0, 30), time(7, 0)) == (
        datetime(2026, 7, 5, 0, 30, tzinfo=UTC),
        datetime(2026, 7, 5, 7, 0, tzinfo=UTC),
    )


def test_sleep_window_equal_times_are_the_wake_up_date() -> None:
    assert sleep_window(date(2026, 7, 5), time(6, 45), time(6, 45)) == (
        datetime(2026, 7, 5, 6, 45, tzinfo=UTC),
        datetime(2026, 7, 5, 6, 45, tzinfo=UTC),
    )


def test_sleep_window_crosses_month_and_year() -> None:
    assert sleep_window(date(2027, 1, 1), time(22, 0), time(6, 0)) == (
        datetime(2026, 12, 31, 22, 0, tzinfo=UTC),
        datetime(2027, 1, 1, 6, 0, tzinfo=UTC),
    )
