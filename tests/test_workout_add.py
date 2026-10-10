import io
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError

from garmin_cli.cli import main

WORKOUT = {
    "workoutName": "Easy Intervals",
    "sportType": {"sportTypeId": 1, "sportTypeKey": "running"},
    "workoutSegments": [
        {
            "segmentOrder": 1,
            "sportType": {"sportTypeId": 1, "sportTypeKey": "running"},
            "workoutSteps": [
                {
                    "type": "ExecutableStepDTO",
                    "stepOrder": 1,
                    "stepType": {"stepTypeId": 1, "stepTypeKey": "warmup"},
                    "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
                    "endConditionValue": 600,
                }
            ],
        }
    ],
}
CREATED = {
    "workoutId": 555,
    "workoutName": "Easy Intervals",
    "estimatedDurationInSecs": 1650,
}
SHOWN = {
    "id": 555,
    "name": "Easy Intervals",
    "estimated_duration_min": 27.5,
    "scheduled": None,
}
CREATED_LINE = 'garmin: Created workout "Easy Intervals" (ID 555).\n'


def add_client(created: Any = CREATED, scheduled: Any = None) -> FakeClient:
    return FakeClient(
        upload_workout=created,
        schedule_workout=scheduled or {"workoutScheduleId": 9, "calendarDate": "x"},
    )


def write(tmp_path: Path, text: str) -> str:
    path = tmp_path / "workout.json"
    path.write_text(text)
    return str(path)


def run(
    argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    try:
        code = main(argv, connect=lambda: client)
    except SystemExit as exit:
        code = int(exit.code or 0)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_workout_add_uploads_the_file_unchanged(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = add_client()
    path = write(tmp_path, json.dumps(WORKOUT))

    code, out, err = run(["workout", "add", "--file", path], client, capsys)

    assert (code, json.loads(out), err) == (0, SHOWN, CREATED_LINE)
    assert client.calls == [("upload_workout", (WORKOUT,), {})]


def test_workout_add_reads_stdin(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    client = add_client()
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(WORKOUT)))

    code, out, err = run(["workout", "add", "--file", "-"], client, capsys)

    assert (code, json.loads(out), err) == (0, SHOWN, CREATED_LINE)
    assert client.calls == [("upload_workout", (WORKOUT,), {})]


@pytest.mark.parametrize(
    ("value", "day"),
    [
        ("2026-10-11", "2026-10-11"),
        ("today", date.today().isoformat()),
        ("yesterday", (date.today() - timedelta(days=1)).isoformat()),
    ],
)
def test_workout_add_schedules_the_new_workout(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, value: str, day: str
) -> None:
    client = add_client()
    path = write(tmp_path, json.dumps(WORKOUT))

    code, out, err = run(
        ["workout", "add", "--file", path, "--schedule", value], client, capsys
    )

    assert (code, json.loads(out)) == (0, {**SHOWN, "scheduled": day})
    assert err == (
        f'garmin: Created workout "Easy Intervals" (ID 555) and scheduled it for '
        f"{day}.\n"
    )
    assert client.calls == [
        ("upload_workout", (WORKOUT,), {}),
        ("schedule_workout", (555, day), {}),
    ]


def test_workout_add_without_duration_prints_null(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = add_client({"workoutId": 555, "workoutName": "Easy Intervals"})

    code, out, _ = run(
        ["workout", "add", "--file", write(tmp_path, json.dumps(WORKOUT))],
        client,
        capsys,
    )

    assert (code, json.loads(out)) == (0, {**SHOWN, "estimated_duration_min": None})


def test_workout_add_invalid_schedule_exits_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = add_client()
    path = write(tmp_path, json.dumps(WORKOUT))

    result = run(
        ["workout", "add", "--file", path, "--schedule", "soon"], client, capsys
    )

    assert result == (
        2,
        "",
        "garmin: Invalid date 'soon'. Use today, yesterday or YYYY-MM-DD.\n",
    )
    assert client.calls == []


def test_workout_add_missing_file_exits_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = add_client()
    path = str(tmp_path / "nope.json")

    result = run(["workout", "add", "--file", path], client, capsys)

    assert result == (
        2,
        "",
        f"garmin: Cannot read '{path}' (No such file or directory). Pass a workout "
        "JSON file, or '-' for stdin.\n",
    )
    assert client.calls == []


def test_workout_add_binary_file_exits_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = add_client()
    path = tmp_path / "workout.json"
    path.write_bytes(b"\xff\xfe\x00")

    result = run(["workout", "add", "--file", str(path)], client, capsys)

    assert result == (
        2,
        "",
        f"garmin: Cannot read '{path}' (not UTF-8 text). Pass a workout JSON file, "
        "or '-' for stdin.\n",
    )
    assert client.calls == []


def test_workout_add_invalid_json_names_the_line(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = add_client()
    path = write(tmp_path, '{\n  "workoutName": "x"\n  "sportType": {}\n}')

    result = run(["workout", "add", "--file", path], client, capsys)

    assert result == (
        2,
        "",
        f"garmin: Invalid JSON in '{path}' at line 3, column 3: Expecting ',' "
        "delimiter. Fix it and try again.\n",
    )
    assert client.calls == []


def test_workout_add_invalid_json_on_stdin_says_stdin(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    client = add_client()
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    result = run(["workout", "add", "--file", "-"], client, capsys)

    assert result == (
        2,
        "",
        "garmin: Invalid JSON in stdin at line 1, column 1: Expecting value. Fix it "
        "and try again.\n",
    )
    assert client.calls == []


@pytest.mark.parametrize("text", ["[]", '"workout"', "null"])
def test_workout_add_non_object_exits_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, text: str
) -> None:
    client = add_client()
    path = write(tmp_path, text)

    result = run(["workout", "add", "--file", path], client, capsys)

    assert result == (
        2,
        "",
        f"garmin: The workout in '{path}' is not a JSON object. Pass one workout "
        "object with workoutName, sportType and workoutSegments.\n",
    )
    assert client.calls == []


@pytest.mark.parametrize(
    ("missing", "named"),
    [
        (["workoutName"], "workoutName"),
        (["sportType"], "sportType"),
        (["workoutSegments"], "workoutSegments"),
        (["workoutName", "workoutSegments"], "workoutName, workoutSegments"),
    ],
)
def test_workout_add_missing_key_exits_2(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    missing: list[str],
    named: str,
) -> None:
    client = add_client()
    workout = {key: value for key, value in WORKOUT.items() if key not in missing}
    path = write(tmp_path, json.dumps(workout))

    result = run(["workout", "add", "--file", path], client, capsys)

    assert result == (
        2,
        "",
        f"garmin: The workout in '{path}' has no {named}. A workout needs "
        "workoutName, sportType and workoutSegments.\n",
    )
    assert client.calls == []


def test_workout_add_missing_file_option_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = run(["workout", "add"], add_client(), capsys)

    assert result == (
        2,
        "",
        "garmin: Missing --file for 'garmin workout add'. Run 'garmin workout add "
        "--help'.\n",
    )


def test_workout_add_upload_error_exits_1(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = add_client(GarminConnectConnectionError("API Error 400"))
    path = write(tmp_path, json.dumps(WORKOUT))

    code, out, err = run(
        ["workout", "add", "--file", path, "--schedule", "2026-10-11"], client, capsys
    )

    assert (code, out) == (1, "")
    assert err.startswith("garmin: Could not reach Garmin Connect")
    assert "Created" not in err
    assert [call[0] for call in client.calls] == ["upload_workout"]


def test_workout_add_schedule_error_says_the_workout_exists(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = add_client(scheduled=GarminConnectConnectionError("API Error 500"))
    path = write(tmp_path, json.dumps(WORKOUT))

    code, out, err = run(
        ["workout", "add", "--file", path, "--schedule", "2026-10-11"], client, capsys
    )

    assert (code, out) == (1, "")
    first, second = err.splitlines()
    assert first == (
        'garmin: Created workout "Easy Intervals" (ID 555) but did not schedule it. '
        "Schedule it in Garmin Connect; running this command again creates a "
        "second copy."
    )
    assert second.startswith("garmin: Could not reach Garmin Connect")
