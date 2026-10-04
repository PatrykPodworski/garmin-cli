import json
from typing import Any

import pytest
from conftest import FakeClient

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
