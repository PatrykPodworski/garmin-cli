from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectNotFoundError

from garmin_cli.cli import main


def run(
    argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    try:
        code = main(argv, connect=lambda: client)
    except SystemExit as exit:
        code = int(exit.code or 0)
    out = capsys.readouterr()
    return code, out.out, out.err


@pytest.mark.parametrize("id", [7001, 1])
def test_workout_unschedule_removes_the_entry(
    capsys: pytest.CaptureFixture[str], id: int
) -> None:
    client = FakeClient(unschedule_workout=None)

    result = run(["workout", "unschedule", str(id)], client, capsys)

    assert result == (
        0,
        f'{{\n  "unscheduled": {id}\n}}\n',
        f"garmin: Removed calendar entry {id}.\n",
    )
    assert client.calls == [("unschedule_workout", (id,), {})]


def test_workout_unschedule_unknown_id_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(unschedule_workout=GarminConnectNotFoundError("404"))

    result = run(["workout", "unschedule", "999"], client, capsys)

    assert result == (
        1,
        "",
        "garmin: No calendar entry with schedule ID 999. Run 'garmin workout "
        "calendar' to list schedule IDs.\n",
    )


@pytest.mark.parametrize("value", ["abc", "0", "-3"])
def test_workout_unschedule_invalid_id_exits_2(
    capsys: pytest.CaptureFixture[str], value: str
) -> None:
    client = FakeClient(unschedule_workout=None)

    result = run(["workout", "unschedule", value], client, capsys)

    assert result == (
        2,
        "",
        f"garmin: Invalid schedule ID '{value}'. Run 'garmin workout calendar' to "
        "list schedule IDs.\n",
    )
    assert client.calls == []
