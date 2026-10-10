from datetime import datetime
from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError
from test_health import run_health

from garmin_cli import weight_add
from garmin_cli.cli import main

# Made-up shape; garmin-cli prints whatever Garmin returns.
CREATED = {"samplePk": 1, "weight": 82400.0, "sourceType": "MANUAL"}


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz: Any = None) -> "FrozenDatetime":
        return cls(2026, 7, 5, 7, 30, 42, 123456)


@pytest.mark.parametrize(
    ("argv", "call"),
    [
        (["82.4"], (82.4, "kg", "2026-07-05T07:30:00")),
        (["82.4", "--at", "2026-07-06 21:05"], (82.4, "kg", "2026-07-06T21:05:00")),
        (["181.5", "--unit", "lbs"], (181.5, "lbs", "2026-07-05T07:30:00")),
        (["0.5"], (0.5, "kg", "2026-07-05T07:30:00")),
    ],
)
def test_weight_add_logs_weigh_in(
    argv: list[str],
    call: tuple[Any, ...],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(weight_add, "datetime", FrozenDatetime)
    client = FakeClient(add_weigh_in=CREATED)

    assert run_health(client, capsys, "weight", "add", *argv) == CREATED
    assert client.calls == [("add_weigh_in", call, {})]


@pytest.mark.parametrize(
    ("argv", "logged"),
    [
        (
            ["82.4"],
            {"date": "2026-07-05", "time": "07:30:00", "weight": 82.4, "unit": "kg"},
        ),
        (
            ["181.5", "--unit", "lbs", "--at", "2026-07-06 21:05"],
            {"date": "2026-07-06", "time": "21:05:00", "weight": 181.5, "unit": "lbs"},
        ),
    ],
)
def test_weight_add_no_body_prints_logged_values(
    argv: list[str],
    logged: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(weight_add, "datetime", FrozenDatetime)
    client = FakeClient(add_weigh_in=None)

    assert run_health(client, capsys, "weight", "add", *argv) == logged


def test_weight_add_garmin_error(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(add_weigh_in=GarminConnectConnectionError("Server error"))

    assert main(["weight", "add", "82.4"], connect=lambda: client) == 1
    assert capsys.readouterr().err == (
        "garmin: Could not reach Garmin Connect (GarminConnectConnectionError: "
        "Server error). Check your internet connection and try again.\n"
    )
