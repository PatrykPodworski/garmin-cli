import json
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError
from test_sleep import NIGHT, run_sleep

from garmin_cli import dates
from garmin_cli.cli import main

SET_NIGHT: dict[str, Any] = {
    "dailySleepDTO": {
        **NIGHT["dailySleepDTO"],
        "id": 1783199400000,
        "userProfilePK": 1234,
        "napTimeSeconds": None,
    }
}
SUMMARY_START = "23:10"


def night_ending(day: str, end_local: int, end_gmt: int) -> dict[str, Any]:
    return {
        "dailySleepDTO": {
            **SET_NIGHT["dailySleepDTO"],
            "calendarDate": day,
            "sleepEndTimestampLocal": end_local,
            "sleepEndTimestampGMT": end_gmt,
        }
    }


# Europe/Warsaw nights with a clock change, both waking at 07:00 local.
AUTUMN = night_ending("2026-10-25", 1792911600000, 1792908000000)  # CET, +1
SPRING = night_ending("2026-03-29", 1774767600000, 1774760400000)  # CEST, +2


@pytest.fixture(autouse=True)
def time_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TZ", "Europe/Warsaw")


class FailingHttp:
    def put(self, *_args: Any, **_kwargs: Any) -> Any:
        raise GarminConnectConnectionError("API Error 400 - Bad request")


def sleep_client(night: dict[str, Any] = SET_NIGHT) -> FakeClient:
    client = FakeClient(get_sleep_data=night, put={})
    # garminconnect's HTTP client is `Garmin.client`; the fake records both.
    client.client = client
    return client


def put_call(
    start: int, end: int, nap: int = 0, day: str = "2026-07-05"
) -> tuple[str, Any, Any]:
    return (
        "put",
        ("connectapi", "/sleep-service/sleep/dailySleep/1783199400000"),
        {
            "json": {
                "id": 1783199400000,
                "userProfilePK": 1234,
                "calendarDate": day,
                "sleepStartTimestampGMT": start,
                "sleepEndTimestampGMT": end,
                "sleepTimeSeconds": (end - start) // 1000,
                "napTimeSeconds": nap,
                "sleepWindowConfirmed": True,
            },
            "api": True,
        },
    )


def test_sleep_set_start_before_midnight_is_the_day_before(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = sleep_client()

    assert (
        run_sleep(client, "set", "2026-07-05", "--start", "23:40", "--end", "07:15")
        == 0
    )
    # 2026-07-04 23:40 and 2026-07-05 07:15 local, two hours ahead of GMT.
    assert client.calls == [
        ("get_sleep_data", ("2026-07-05",), {}),
        put_call(1783201200000, 1783228500000),
        ("get_sleep_data", ("2026-07-05",), {}),
    ]
    duration = client.calls[1][2]["json"]["sleepTimeSeconds"]
    assert (duration, type(duration)) == (27300, int)
    assert json.loads(capsys.readouterr().out)["start"] == SUMMARY_START


def test_sleep_set_start_after_midnight_is_the_same_day(
    capsys: pytest.CaptureFixture[str],
) -> None:
    night = {"dailySleepDTO": {**SET_NIGHT["dailySleepDTO"], "napTimeSeconds": 1200}}
    client = sleep_client(night)

    assert (
        run_sleep(client, "set", "2026-07-05", "--start", "00:30", "--end", "07:00")
        == 0
    )
    # 2026-07-05 00:30 and 07:00 local.
    assert client.calls[1] == put_call(1783204200000, 1783227600000, nap=1200)
    assert client.calls[1][2]["json"]["sleepTimeSeconds"] == 23400


def test_sleep_set_night_of_takes_the_lights_out_date(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = sleep_client()

    assert (
        run_sleep(
            client,
            "set",
            "--night-of",
            "2026-07-04",
            "--start",
            "23:40",
            "--end",
            "07:15",
        )
        == 0
    )
    assert client.calls[0] == ("get_sleep_data", ("2026-07-05",), {})
    assert client.calls[1] == put_call(1783201200000, 1783228500000)


def test_sleep_set_after_debug_flag(capsys: pytest.CaptureFixture[str]) -> None:
    client = sleep_client()

    assert (
        main(
            [
                "--debug",
                "sleep",
                "set",
                "2026-07-05",
                "--start",
                "23:40",
                "--end",
                "07:15",
            ],
            connect=lambda: client,
        )
        == 0
    )
    assert client.calls[1] == put_call(1783201200000, 1783228500000)


@pytest.mark.parametrize(
    ("night", "argv", "start", "end"),
    [
        # 2026-10-24 23:00 CEST and 2026-10-25 07:15 CET.
        (AUTUMN, ["--start", "23:00", "--end", "07:15"], 1792875600000, 1792908900000),
        # 2026-03-28 23:00 CET and 2026-03-29 07:00 CEST.
        (SPRING, ["--start", "23:00", "--end", "07:00"], 1774735200000, 1774760400000),
        (
            SET_NIGHT,
            ["--start", "23:40", "--end", "07:15"],
            1783201200000,
            1783228500000,
        ),
    ],
)
def test_sleep_set_in_the_nights_zone_converts_each_time_on_its_own(
    night: dict[str, Any],
    argv: list[str],
    start: int,
    end: int,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    day = night["dailySleepDTO"]["calendarDate"]
    client = sleep_client(night)

    assert run_sleep(client, "set", day, *argv) == 0
    assert client.calls[1] == put_call(start, end, day=day)


def test_sleep_set_converts_with_the_zone_not_the_process_clock(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Only garmin-cli's /etc/localtime moves to New York; the C library keeps the
    # test machine's own zone, so a naive conversion would give other times.
    monkeypatch.delenv("TZ", raising=False)
    localtime = tmp_path / "localtime"
    localtime.symlink_to("/usr/share/zoneinfo/America/New_York")
    monkeypatch.setattr(dates, "LOCALTIME", localtime)
    # Waking at 2026-07-05 07:00 EDT, four hours behind GMT.
    client = sleep_client(night_ending("2026-07-05", 1783234800000, 1783249200000))

    assert (
        run_sleep(client, "set", "2026-07-05", "--start", "23:40", "--end", "07:15")
        == 0
    )
    # 2026-07-04 23:40 and 2026-07-05 07:15 EDT.
    assert client.calls[1] == put_call(1783222800000, 1783250100000)


@pytest.mark.parametrize("zone", ["America/New_York", "Nowhere/Land", None])
def test_sleep_set_outside_the_nights_zone_exits_before_the_put(
    zone: str | None,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    if zone:
        monkeypatch.setenv("TZ", zone)
    else:
        monkeypatch.delenv("TZ")
        monkeypatch.setattr(dates, "LOCALTIME", tmp_path / "localtime")
    client = sleep_client()

    assert (
        run_sleep(client, "set", "2026-07-05", "--start", "23:40", "--end", "07:15")
        == 1
    )
    assert capsys.readouterr().err == (
        "garmin: The night ending 2026-07-05 was not in this machine's time zone, "
        "so garmin-cli cannot convert the times. Adjust the sleep times in the "
        "Garmin Connect app.\n"
    )
    assert [call[0] for call in client.calls] == ["get_sleep_data"]


@pytest.mark.parametrize(
    ("night", "argv", "message"),
    [
        (
            SPRING,
            ["--start", "02:30", "--end", "07:00"],
            "2026-03-29 02:30 does not exist because the clocks change that night. "
            "Give another time.",
        ),
        (
            AUTUMN,
            ["--start", "23:00", "--end", "02:30"],
            "2026-10-25 02:30 happens twice because the clocks change that night. "
            "Give another time.",
        ),
    ],
)
def test_sleep_set_time_in_a_clock_change_exits_before_the_put(
    night: dict[str, Any],
    argv: list[str],
    message: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = sleep_client(night)

    with pytest.raises(SystemExit) as exit:
        run_sleep(client, "set", night["dailySleepDTO"]["calendarDate"], *argv)

    assert exit.value.code == 2
    assert capsys.readouterr().err == f"garmin: {message}\n"
    assert [call[0] for call in client.calls] == ["get_sleep_data"]


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (
            ["--start", "06:45", "--end", "06:45"],
            "--start and --end are both 06:45. Give two different times.",
        ),
        (
            ["--start", "25:00", "--end", "06:45"],
            "Invalid time '25:00'. Use HH:MM, for example 23:10.",
        ),
        (
            ["--start", "11pm", "--end", "06:45"],
            "Invalid time '11pm'. Use HH:MM, for example 23:10.",
        ),
        (
            ["--end", "06:45"],
            "Missing --start for 'garmin sleep set'. Run 'garmin sleep set --help'.",
        ),
        (
            ["--start", "23:10"],
            "Missing --end for 'garmin sleep set'. Run 'garmin sleep set --help'.",
        ),
        (
            ["--night-of", "2026-07-04", "--start", "23:10", "--end", "06:45"],
            "Give either a date or --night-of, not both. Use 'garmin sleep set DATE' "
            "for the wake-up date or 'garmin sleep set --night-of DATE' for the "
            "lights-out date.",
        ),
    ],
)
def test_sleep_set_rejects_bad_arguments_before_any_call(
    argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    client = sleep_client()

    with pytest.raises(SystemExit) as exit:
        run_sleep(client, "set", "2026-07-05", *argv)

    assert exit.value.code == 2
    assert capsys.readouterr().err == f"garmin: {message}\n"
    assert client.calls == []


def test_sleep_set_not_synced_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    client = sleep_client({"dailySleepDTO": {"calendarDate": "2026-07-05"}})

    assert (
        run_sleep(client, "set", "2026-07-05", "--start", "23:10", "--end", "06:45")
        == 1
    )
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err.startswith("garmin: No sleep data for the night ending 2026-07-05")
    assert [call[0] for call in client.calls] == ["get_sleep_data"]


@pytest.mark.parametrize("missing", ["sleepEndTimestampLocal", "sleepEndTimestampGMT"])
def test_sleep_set_without_offset_exits_before_the_put(
    missing: str, capsys: pytest.CaptureFixture[str]
) -> None:
    night = {k: v for k, v in SET_NIGHT["dailySleepDTO"].items() if k != missing}
    client = sleep_client({"dailySleepDTO": night})

    assert (
        run_sleep(client, "set", "2026-07-05", "--start", "23:10", "--end", "06:45")
        == 1
    )
    assert capsys.readouterr().err == (
        "garmin: Garmin Connect sent no time zone for the night ending 2026-07-05, "
        "so garmin-cli cannot convert the times. Adjust the sleep times in the "
        "Garmin Connect app.\n"
    )
    assert [call[0] for call in client.calls] == ["get_sleep_data"]


def test_sleep_set_garmin_error_on_put(capsys: pytest.CaptureFixture[str]) -> None:
    client = sleep_client()
    client.client = FailingHttp()

    assert (
        run_sleep(client, "set", "2026-07-05", "--start", "23:10", "--end", "06:45")
        == 1
    )
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == (
        "garmin: Could not reach Garmin Connect (GarminConnectConnectionError: API "
        "Error 400 - Bad request). Check your internet connection and try again.\n"
    )
    assert [call[0] for call in client.calls] == ["get_sleep_data"]


def test_sleep_set_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["sleep", "set", "--help"])

    help = capsys.readouterr().out
    assert help.startswith("usage: garmin sleep set")
    assert "--start HH:MM" in help
