from typing import Any

import pytest
from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from garmin_cli.cli import main
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
