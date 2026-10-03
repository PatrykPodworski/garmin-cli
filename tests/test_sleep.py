import json
from typing import Any

import pytest

from garmin_cli.cli import main


class FakeSleepClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.dates: list[str] = []

    def get_sleep_data(self, cdate: str) -> dict[str, Any]:
        self.dates.append(cdate)
        return self.response


NIGHT: dict[str, Any] = {
    "dailySleepDTO": {
        "calendarDate": "2026-07-05",
        "sleepTimeSeconds": 24300,
        "deepSleepSeconds": 5400,
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


def run_sleep(client: FakeSleepClient, *argv: str) -> int:
    return main(["sleep", *argv], connect=lambda: client)


def test_sleep_summarizes_the_night(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeSleepClient(NIGHT)

    assert run_sleep(client, "2026-07-05") == 0
    assert client.dates == ["2026-07-05"]
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


def test_sleep_night_of_queries_the_wake_up_date(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeSleepClient(NIGHT)

    assert run_sleep(client, "--night-of", "2026-07-04") == 0
    assert client.dates == ["2026-07-05"]
    assert json.loads(capsys.readouterr().out)["start"] == "23:10"


def test_sleep_rejects_date_with_night_of(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit:
        run_sleep(FakeSleepClient(NIGHT), "2026-07-05", "--night-of", "2026-07-04")

    assert exit.value.code == 2


def test_sleep_not_synced_exits_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeSleepClient({"dailySleepDTO": {"calendarDate": "2026-07-05"}})

    assert run_sleep(client, "2026-07-05") == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert "no sleep data for 2026-07-05" in out.err


def test_sleep_raw_prints_the_full_response(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_sleep(FakeSleepClient(NIGHT), "2026-07-05", "--raw") == 0
    assert json.loads(capsys.readouterr().out) == NIGHT


def test_sleep_help_documents_both_dates(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["sleep", "--help"])

    help = capsys.readouterr().out
    assert "wake-up" in help
    assert "--night-of" in help
