from datetime import date, timedelta
from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError, GarminConnectNotFoundError

from garmin_cli.cli import main

WORKOUT = {"workoutId": 501, "workoutName": "Test Intervals"}
ENTRY = {"workoutScheduleId": 7001, "calendarDate": "2026-10-12"}


def run(
    argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    try:
        code = main(argv, connect=lambda: client)
    except SystemExit as exit:
        code = int(exit.code or 0)
    out = capsys.readouterr()
    return code, out.out, out.err


@pytest.mark.parametrize(
    ("value", "day"),
    [
        ("2026-10-12", "2026-10-12"),
        ("today", date.today().isoformat()),
        ("tomorrow", (date.today() + timedelta(days=1)).isoformat()),
    ],
)
def test_workout_schedule_puts_the_workout_on_the_calendar(
    capsys: pytest.CaptureFixture[str], value: str, day: str
) -> None:
    client = FakeClient(get_workout_by_id=WORKOUT, schedule_workout=ENTRY)

    code, out, err = run(["workout", "schedule", "501", value], client, capsys)

    assert code == 0
    assert out == (
        '{\n  "schedule_id": 7001,\n  "date": "' + day + '",\n  "workout_id": 501,\n'
        '  "name": "Test Intervals"\n}\n'
    )
    assert err == f'garmin: Scheduled workout "Test Intervals" (ID 501) for {day}.\n'
    assert client.calls == [
        ("get_workout_by_id", (501,), {}),
        ("schedule_workout", (501, day), {}),
    ]


def test_workout_schedule_unknown_workout_exits_1_before_the_post(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(
        get_workout_by_id=GarminConnectNotFoundError("404"), schedule_workout=ENTRY
    )

    result = run(["workout", "schedule", "999", "2026-10-12"], client, capsys)

    assert result == (
        1,
        "",
        "garmin: No workout with ID 999. Run 'garmin workouts' to list IDs.\n",
    )
    assert [call[0] for call in client.calls] == ["get_workout_by_id"]


def test_workout_schedule_error_prints_no_confirmation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(
        get_workout_by_id=WORKOUT,
        schedule_workout=GarminConnectConnectionError("API Error 500"),
    )

    code, out, err = run(["workout", "schedule", "501", "2026-10-12"], client, capsys)

    assert (code, out) == (1, "")
    assert err.startswith("garmin: Could not reach Garmin Connect")
    assert "Scheduled" not in err


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (
            ["501", "soon"],
            "Invalid date 'soon'. Use today, yesterday, tomorrow or YYYY-MM-DD.",
        ),
        (
            ["0", "2026-10-12"],
            "Invalid workout ID '0'. Run 'garmin workouts' to list IDs.",
        ),
        (
            ["501"],
            "Missing date for 'garmin workout schedule'. "
            "Run 'garmin workout schedule --help'.",
        ),
    ],
)
def test_workout_schedule_bad_arguments_exit_2_before_any_call(
    capsys: pytest.CaptureFixture[str], argv: list[str], message: str
) -> None:
    client = FakeClient(get_workout_by_id=WORKOUT, schedule_workout=ENTRY)

    result = run(["workout", "schedule", *argv], client, capsys)

    assert result == (2, "", f"garmin: {message}\n")
    assert client.calls == []
