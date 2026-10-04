from typing import Any

import pytest
from conftest import FakeClient, run_json
from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from garmin_cli.cli import main, round_floats
from garmin_cli.errors import GarminCliError


class RaisingClient:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def get_stats(self, _day: str) -> Any:
        raise self.error


def test_help_exits_0(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["--help"])

    assert exit.value.code == 0
    assert "usage: garmin" in capsys.readouterr().out


def test_prints_json_indented_by_2(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_stats={"totalSteps": [1]})

    assert main(["stats", "--raw"], connect=lambda: client) == 0
    assert capsys.readouterr().out == '{\n  "totalSteps": [\n    1\n  ]\n}\n'


@pytest.mark.parametrize(
    "command", ["activities", "activity", "sleep", "stats", "weight", "bp"]
)
def test_raw_help_on_every_data_command(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main([command, "--help"])

    help_text = " ".join(capsys.readouterr().out.split())
    assert "--raw print the full Garmin response" in help_text


@pytest.mark.parametrize(
    "error",
    [
        GarminCliError("not synced"),
        GarminConnectAuthenticationError("bad credentials"),
        GarminConnectConnectionError("server error"),
        GarminConnectTooManyRequestsError("rate limited"),
        ConnectionError("connection refused"),
    ],
)
def test_expected_error_exits_1_with_message(
    error: Exception, capsys: pytest.CaptureFixture[str]
) -> None:
    client: Any = RaisingClient(error)

    assert main(["stats"], connect=lambda: client) == 1
    assert capsys.readouterr().err == f"garmin: {error}\n"


def test_bug_propagates_with_traceback() -> None:
    client: Any = RaisingClient(KeyError("totalKilocalories"))

    with pytest.raises(KeyError):
        main(["stats"], connect=lambda: client)


def test_round_floats_walks_dicts_and_lists() -> None:
    value = {
        "a": 0.800000011920929,
        "b": [4056.409912109375, {"c": 124.0}],
        "d": 7,
        "e": "x",
        "f": None,
        "g": True,
    }

    result = round_floats(value)

    assert result == {
        "a": 0.8,
        "b": [4056.41, {"c": 124.0}],
        "d": 7,
        "e": "x",
        "f": None,
        "g": True,
    }
    assert result["g"] is True


@pytest.mark.parametrize(
    ("argv", "key", "expected"),
    [
        (["activities"], "aerobic_te", 0.8),
        (["activities", "--raw"], "aerobicTrainingEffect", 0.800000011920929),
    ],
)
def test_activities_rounds_summary_not_raw(
    argv: list[str], key: str, expected: float, capsys: pytest.CaptureFixture[str]
) -> None:
    activity = {"activityId": 1, "aerobicTrainingEffect": 0.800000011920929}

    result = run_json(argv, FakeClient(get_activities=[activity]), capsys)

    assert result[0][key] == expected


def test_weight_rounds_summary_not_raw(capsys: pytest.CaptureFixture[str]) -> None:
    weigh_ins = {
        "dailyWeightSummaries": [
            {
                "allWeightMetrics": [
                    {
                        "calendarDate": "2026-07-05",
                        "date": 1783236900000,
                        "weight": 70412.3456,
                        "bodyFat": 18.500000476837158,
                    }
                ]
            }
        ]
    }
    client = FakeClient(get_weigh_ins=weigh_ins)

    [record] = run_json(["weight"], client, capsys)
    raw = run_json(["weight", "--raw"], client, capsys)

    assert (record["weight_kg"], record["body_fat_pct"]) == (70.41, 18.5)
    assert raw == weigh_ins
