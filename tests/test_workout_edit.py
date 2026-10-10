import io
import json
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError, GarminConnectNotFoundError
from test_workout_add import WORKOUT, run, write
from test_workouts import DETAIL, SUMMARY

SHOWN = {
    **SUMMARY,
    "steps": [
        {"type": "warmup", "end": "time", "end_value": 600.0, "target": "no.target"},
        {
            "type": "repeat",
            "iterations": 4,
            "steps": [
                {
                    "type": "interval",
                    "end": "distance",
                    "end_value": 1000.0,
                    "target": "pace.zone",
                    "target_low": 3.7,
                    "target_high": 4.0,
                    "description": "fake step note",
                }
            ],
        },
    ],
}
UPDATED_LINE = 'garmin: Updated workout "Easy Intervals" (ID 501).\n'


def edit_client(found: Any = DETAIL, updated: Any = None) -> FakeClient:
    return FakeClient(get_workout_by_id=found, update_workout=updated or {})


def test_workout_edit_replaces_the_workout(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = edit_client()
    path = write(tmp_path, json.dumps(WORKOUT))

    code, out, err = run(["workout", "edit", "501", "--file", path], client, capsys)

    assert (code, json.loads(out), err) == (0, SHOWN, UPDATED_LINE)
    assert client.calls == [
        ("get_workout_by_id", (501,), {}),
        ("update_workout", (501, WORKOUT), {}),
        ("get_workout_by_id", (501,), {}),
    ]


def test_workout_edit_reads_stdin(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    client = edit_client()
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(WORKOUT)))

    code, out, err = run(["workout", "edit", "501", "--file", "-"], client, capsys)

    assert (code, json.loads(out), err) == (0, SHOWN, UPDATED_LINE)
    assert client.calls[1] == ("update_workout", (501, WORKOUT), {})


def test_workout_edit_unknown_id_exits_1_without_update(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = edit_client(GarminConnectNotFoundError("API Error 404"))
    path = write(tmp_path, json.dumps(WORKOUT))

    result = run(["workout", "edit", "501", "--file", path], client, capsys)

    assert result == (
        1,
        "",
        "garmin: No workout with ID 501. Run 'garmin workouts' to list IDs.\n",
    )
    assert [call[0] for call in client.calls] == ["get_workout_by_id"]


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("{", "Invalid JSON in"),
        ("[]", "is not a JSON object"),
        (json.dumps({"workoutName": "x"}), "has no sportType, workoutSegments"),
    ],
)
def test_workout_edit_invalid_input_exits_2_without_calls(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, text: str, problem: str
) -> None:
    client = edit_client()
    path = write(tmp_path, text)

    code, out, err = run(["workout", "edit", "501", "--file", path], client, capsys)

    assert (code, out) == (2, "")
    assert problem in err
    assert client.calls == []


def test_workout_edit_missing_file_exits_2_without_calls(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = edit_client()
    path = str(tmp_path / "nope.json")

    code, out, err = run(["workout", "edit", "501", "--file", path], client, capsys)

    assert (code, out) == (2, "")
    assert err.startswith(f"garmin: Cannot read '{path}'")
    assert client.calls == []


@pytest.mark.parametrize("value", ["0", "abc"])
def test_workout_edit_invalid_id_exits_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, value: str
) -> None:
    client = edit_client()
    path = write(tmp_path, json.dumps(WORKOUT))

    result = run(["workout", "edit", value, "--file", path], client, capsys)

    assert result == (
        2,
        "",
        f"garmin: Invalid workout ID '{value}'. Run 'garmin workouts' to list IDs.\n",
    )
    assert client.calls == []


def test_workout_edit_update_error_exits_1(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = edit_client(updated=GarminConnectConnectionError("API Error 400"))
    path = write(tmp_path, json.dumps(WORKOUT))

    code, out, err = run(["workout", "edit", "501", "--file", path], client, capsys)

    assert (code, out) == (1, "")
    assert err.startswith("garmin: Could not reach Garmin Connect")
    assert "Updated" not in err
    assert [call[0] for call in client.calls] == [
        "get_workout_by_id",
        "update_workout",
    ]


def test_workout_edit_missing_file_option_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = edit_client()

    result = run(["workout", "edit", "501"], client, capsys)

    assert result == (
        2,
        "",
        "garmin: Missing --file for 'garmin workout edit'. Run 'garmin workout edit "
        "--help'.\n",
    )
    assert client.calls == []
