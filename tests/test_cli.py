from typing import Any

import pytest
from conftest import FakeClient, run_json
from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from garmin_cli.cli import CliParser, main, round_floats
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


def test_subcommand_help_exits_0(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["sleep", "--help"])

    assert exit.value.code == 0
    assert capsys.readouterr().out.startswith("usage: garmin sleep")


COMMANDS = "login, weight, bp, sleep, activities, activity, stats"
SLEEP_HELP = "Run 'garmin sleep --help' for all options."
INVALID_DATE = "Use today, yesterday or YYYY-MM-DD."
INVALID_LIMIT = "Use a whole number of 1 or more."
CONFLICT = (
    "Give either a date or --night-of, not both. Use 'garmin sleep DATE' for the "
    "wake-up date or 'garmin sleep --night-of DATE' for the lights-out date."
)


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        ([], f"No command given. Run 'garmin <command>', one of: {COMMANDS}."),
        (["slep"], "Unknown command 'slep'. Did you mean 'sleep'?"),
        (
            ["xyz"],
            f"Unknown command 'xyz'. Run 'garmin <command>', one of: {COMMANDS}.",
        ),
        (
            ["sleep", "--nigth-of", "today"],
            "Unknown option '--nigth-of' for 'garmin sleep'. "
            f"Did you mean '--night-of'? {SLEEP_HELP}",
        ),
        (
            ["sleep", "--xyz"],
            f"Unknown option '--xyz' for 'garmin sleep'. {SLEEP_HELP}",
        ),
        (
            ["stats", "today", "extra"],
            "Unexpected argument 'extra' for 'garmin stats'. "
            "Run 'garmin stats --help' for all options.",
        ),
        (["sleep", "tomorrow"], f"Invalid date 'tomorrow'. {INVALID_DATE}"),
        (
            ["weight", "--from", "2026-13-01"],
            f"Invalid date '2026-13-01'. {INVALID_DATE}",
        ),
        (["activities", "--limit", "x"], f"Invalid --limit 'x'. {INVALID_LIMIT}"),
        (["activities", "--limit", "0"], f"Invalid --limit '0'. {INVALID_LIMIT}"),
        (["activities", "--limit", "-1"], f"Invalid --limit '-1'. {INVALID_LIMIT}"),
        (
            ["activity"],
            "Missing activity ID. Run 'garmin activities' to list IDs, "
            "then 'garmin activity <id>'.",
        ),
        (["sleep", "2026-07-05", "--night-of", "2026-07-04"], CONFLICT),
        (["sleep", "--night-of", "2026-07-04", "2026-07-05"], CONFLICT),
        (
            ["activities", "--limit"],
            "Argument --limit: expected one argument. Run 'garmin activities --help'.",
        ),
    ],
)
def test_argument_error_exits_2_with_one_line(
    argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(argv, connect=FakeClient)

    assert exit.value.code == 2
    out = capsys.readouterr()
    assert out.err == f"garmin: {message}\n"
    assert out.out == ""


def test_missing_argument_generic_message(capsys: pytest.CaptureFixture[str]) -> None:
    parser = CliParser(prog="garmin demo")
    parser.add_argument("name")

    with pytest.raises(SystemExit) as exit:
        parser.parse_args([])

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        "garmin: Missing name for 'garmin demo'. Run 'garmin demo --help'.\n"
    )


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
        GarminCliError("Not synced.", "Sync it."),
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
