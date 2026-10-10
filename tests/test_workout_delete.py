from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError, GarminConnectNotFoundError
from test_activity_delete import run
from test_workouts import INTERVALS

DELETED = 'garmin: Deleted "Test Intervals".\n'


def delete_client(detail: Any = INTERVALS, deleted: Any = None) -> FakeClient:
    return FakeClient(get_workout_by_id=detail, delete_workout=deleted or {})


def test_workout_delete_deletes_without_asking(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client()

    result = run(["workout", "delete", "0501"], client, capsys)

    assert result == (0, '{\n  "deleted": 501\n}\n', DELETED)
    assert client.calls == [
        ("get_workout_by_id", (501,), {}),
        ("delete_workout", (501,), {}),
    ]


def test_workout_delete_dry_run_deletes_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client()

    result = run(["workout", "delete", "501", "--dry-run"], client, capsys)

    assert result == (
        0,
        '{\n  "would_delete": 501\n}\n',
        'garmin: Would delete "Test Intervals".\n',
    )
    assert client.calls == [("get_workout_by_id", (501,), {})]


@pytest.mark.parametrize("detail", [{}, {"workoutName": None}])
def test_workout_delete_without_name_shows_id(
    capsys: pytest.CaptureFixture[str], detail: dict[str, Any]
) -> None:
    client = delete_client(detail)

    result = run(["workout", "delete", "501"], client, capsys)

    assert result == (0, '{\n  "deleted": 501\n}\n', "garmin: Deleted workout 501.\n")


def test_workout_delete_unknown_id_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client(GarminConnectNotFoundError("404"))

    result = run(["workout", "delete", "999"], client, capsys)

    assert result == (
        1,
        "",
        "garmin: No workout with ID 999. Run 'garmin workouts' to list IDs.\n",
    )
    assert client.calls == [("get_workout_by_id", (999,), {})]


@pytest.mark.parametrize("value", ["abc", "0", "-5", "1.5"])
def test_workout_delete_invalid_id_exits_2(
    capsys: pytest.CaptureFixture[str], value: str
) -> None:
    client = delete_client()

    result = run(["workout", "delete", value], client, capsys)

    assert result == (
        2,
        "",
        f"garmin: Invalid workout ID '{value}'. Run 'garmin workouts' to list IDs.\n",
    )
    assert client.calls == []


def test_workout_delete_missing_id_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = run(["workout", "delete"], delete_client(), capsys)

    assert result == (
        2,
        "",
        "garmin: Missing workout ID. Run 'garmin workouts' to list IDs, then "
        "'garmin workout delete <id>'.\n",
    )


def test_workout_delete_garmin_error_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client(deleted=GarminConnectConnectionError("API Error 500"))

    code, out, err = run(["workout", "delete", "501"], client, capsys)

    assert (code, out) == (1, "")
    assert err.startswith("garmin: Could not reach Garmin Connect")
    assert "Deleted" not in err
