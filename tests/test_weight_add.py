from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError
from test_health import run_health

from garmin_cli.cli import main

# Made-up shape; garmin-cli prints whatever Garmin returns.
CREATED = {"samplePk": 1, "weight": 82400.0, "sourceType": "MANUAL"}


@pytest.mark.parametrize(
    ("argv", "call"),
    [
        (["82.4"], (82.4, "kg", "")),
        (["82.4", "--at", "2026-07-05 07:30"], (82.4, "kg", "2026-07-05T07:30:00")),
        (["181.5", "--unit", "lbs"], (181.5, "lbs", "")),
        (["0.5"], (0.5, "kg", "")),
    ],
)
def test_weight_add_logs_weigh_in(
    argv: list[str], call: tuple[Any, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(add_weigh_in=CREATED)

    assert run_health(client, capsys, "weight", "add", *argv) == CREATED
    assert client.calls == [("add_weigh_in", call, {})]


def test_weight_add_garmin_error(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(add_weigh_in=GarminConnectConnectionError("Server error"))

    assert main(["weight", "add", "82.4"], connect=lambda: client) == 1
    assert capsys.readouterr().err == (
        "garmin: Could not reach Garmin Connect (GarminConnectConnectionError: "
        "Server error). Check your internet connection and try again.\n"
    )
