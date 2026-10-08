import json
from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError

from garmin_cli.cli import main

NIGHT: dict[str, Any] = {
    "dailySleepDTO": {
        "calendarDate": "2026-07-05",
        "sleepTimeSeconds": 24300,
        "deepSleepSeconds": 5430,
        "lightSleepSeconds": 13200,
        "remSleepSeconds": 5700,
        "awakeSleepSeconds": 3600,
        # 2026-07-04 23:10 and 2026-07-05 06:55 as wall-clock time encoded as UTC.
        "sleepStartTimestampLocal": 1783206600000,
        "sleepEndTimestampLocal": 1783234500000,
        "sleepStartTimestampGMT": 1783199400000,
        "sleepEndTimestampGMT": 1783227300000,
        "sleepScores": {
            "overall": {"value": 82, "qualifierKey": "GOOD"},
            "remPercentage": {"value": 23, "qualifierKey": "EXCELLENT"},
            "stress": {"qualifierKey": "FAIR"},
        },
    },
    "sleepMovement": [{"activityLevel": 1.0}],
}


def run_sleep(client: FakeClient, *argv: str) -> int:
    return main(["sleep", *argv], connect=lambda: client)


def test_sleep_summarizes_the_night(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_sleep_data=NIGHT)

    assert run_sleep(client, "2026-07-05") == 0
    assert client.calls == [("get_sleep_data", ("2026-07-05",), {})]
    assert json.loads(capsys.readouterr().out) == {
        "date": "2026-07-05",
        "start": "23:10",
        "end": "06:55",
        "duration_min": 405,
        "deep_min": 90,
        "light_min": 220,
        "rem_min": 95,
        "awake_min": 60,
        "score": 82,
        "scores": {
            "rem_percentage": {"value": 23, "qualifier": "EXCELLENT"},
            "stress": {"value": None, "qualifier": "FAIR"},
        },
    }


@pytest.mark.parametrize(
    ("garmin_key", "output_key"),
    [
        ("deepSleepSeconds", "deep_min"),
        ("lightSleepSeconds", "light_min"),
        ("remSleepSeconds", "rem_min"),
        ("awakeSleepSeconds", "awake_min"),
    ],
)
def test_sleep_missing_stage_is_null(
    garmin_key: str, output_key: str, capsys: pytest.CaptureFixture[str]
) -> None:
    night = {k: v for k, v in NIGHT["dailySleepDTO"].items() if k != garmin_key}
    client = FakeClient(get_sleep_data={"dailySleepDTO": night})

    assert run_sleep(client, "2026-07-05") == 0
    assert json.loads(capsys.readouterr().out)[output_key] is None


def test_sleep_without_overall_score_is_null(
    capsys: pytest.CaptureFixture[str],
) -> None:
    night = {**NIGHT["dailySleepDTO"], "sleepScores": {}}
    client = FakeClient(get_sleep_data={"dailySleepDTO": night})

    assert run_sleep(client, "2026-07-05") == 0
    result = json.loads(capsys.readouterr().out)
    assert (result["score"], result["scores"]) == (None, {})


def test_sleep_night_of_queries_the_wake_up_date(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get_sleep_data=NIGHT)

    assert run_sleep(client, "--night-of", "2026-07-04") == 0
    assert client.calls == [("get_sleep_data", ("2026-07-05",), {})]
    assert json.loads(capsys.readouterr().out)["start"] == "23:10"


def test_sleep_rejects_date_with_night_of(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit:
        run_sleep(
            FakeClient(get_sleep_data=NIGHT), "2026-07-05", "--night-of", "2026-07-04"
        )

    assert exit.value.code == 2


def test_sleep_not_synced_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(
        get_sleep_data={"dailySleepDTO": {"calendarDate": "2026-07-05"}}
    )

    assert run_sleep(client, "2026-07-05") == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == (
        "garmin: No sleep data for the night ending 2026-07-05 yet. Sync your watch "
        "with Garmin Connect, or use --night-of if 2026-07-05 is the night you went "
        "to bed.\n"
    )


def test_sleep_night_of_not_synced_drops_the_hint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get_sleep_data={"dailySleepDTO": {}})

    assert run_sleep(client, "--night-of", "2026-07-04") == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == (
        "garmin: No sleep data for the night of 2026-07-04 yet. Sync your watch "
        "with Garmin Connect, then try again.\n"
    )


def test_sleep_raw_prints_the_full_response(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_sleep(FakeClient(get_sleep_data=NIGHT), "2026-07-05", "--raw") == 0
    assert json.loads(capsys.readouterr().out) == NIGHT


def test_sleep_help_documents_both_dates(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["sleep", "--help"])

    help = capsys.readouterr().out
    assert "wake-up" in help
    assert "--night-of" in help


SET_NIGHT: dict[str, Any] = {
    "dailySleepDTO": {
        **NIGHT["dailySleepDTO"],
        "id": 1783199400000,
        "userProfilePK": 1234,
        "napTimeSeconds": None,
    }
}
SUMMARY_START = "23:10"


class FailingHttp:
    def put(self, *_args: Any, **_kwargs: Any) -> Any:
        raise GarminConnectConnectionError("API Error 400 - Bad request")


def sleep_client(night: dict[str, Any] = SET_NIGHT) -> FakeClient:
    client = FakeClient(get_sleep_data=night, put={})
    # garminconnect's HTTP client is `Garmin.client`; the fake records both.
    client.client = client
    return client


def put_call(start: int, end: int, nap: int = 0) -> tuple[str, Any, Any]:
    return (
        "put",
        ("connectapi", "/sleep-service/sleep/dailySleep/1783199400000"),
        {
            "json": {
                "id": 1783199400000,
                "userProfilePK": 1234,
                "calendarDate": "2026-07-05",
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
