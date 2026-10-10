import pytest
from conftest import FakeClient, run_json
from garminconnect import GarminConnectNotFoundError

from garmin_cli.cli import main

INTERVALS = {
    "workoutId": 501,
    "workoutName": "Test Intervals",
    "sportType": {"sportTypeId": 1, "sportTypeKey": "running"},
    "estimatedDurationInSecs": 2730,
    "estimatedDistanceInMeters": 8000.0,
    "createdDate": "2026-07-05T08:00:00.0",
    "updateDate": "2026-07-06T09:00:00.0",
    "description": "fake description",
}
EASY = {
    "workoutId": 502,
    "workoutName": "Test Easy",
    "sportType": {"sportTypeKey": "running"},
    "createdDate": "2026-07-01T08:00:00.0",
}
SUMMARY = {
    "id": 501,
    "name": "Test Intervals",
    "sport": "running",
    "estimated_duration_min": 45.5,
    "created": "2026-07-05T08:00:00.0",
    "updated": "2026-07-06T09:00:00.0",
}
WARMUP = {
    "type": "ExecutableStepDTO",
    "stepOrder": 1,
    "stepType": {"stepTypeId": 1, "stepTypeKey": "warmup"},
    "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
    "endConditionValue": 600.0,
    "targetType": {"workoutTargetTypeKey": "no.target"},
}
INTERVAL = {
    "type": "ExecutableStepDTO",
    "stepOrder": 3,
    "stepType": {"stepTypeKey": "interval"},
    "endCondition": {"conditionTypeKey": "distance"},
    "endConditionValue": 1000.0,
    "targetType": {"workoutTargetTypeKey": "pace.zone"},
    "targetValueOne": 3.7,
    "targetValueTwo": 4.0,
    "description": "fake step note",
}
REPEAT = {
    "type": "RepeatGroupDTO",
    "stepOrder": 2,
    "stepType": {"stepTypeKey": "repeat"},
    "numberOfIterations": 4,
    "workoutSteps": [INTERVAL],
}
DETAIL = {
    **INTERVALS,
    "workoutSegments": [{"segmentOrder": 1, "workoutSteps": [WARMUP, REPEAT]}],
}


def test_workouts_compact_list(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_workouts=[INTERVALS, EASY])

    result = run_json(["workouts"], client, capsys)

    assert client.calls == [("get_workouts", (0, 20), {})]
    assert result == [
        SUMMARY,
        {
            "id": 502,
            "name": "Test Easy",
            "sport": "running",
            "created": "2026-07-01T08:00:00.0",
        },
    ]


def test_workouts_empty_library(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_workouts=[])

    assert run_json(["workouts"], client, capsys) == []


def test_workouts_missing_fields(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_workouts=[{"workoutId": 503, "sportType": None}])

    assert run_json(["workouts"], client, capsys) == [{"id": 503}]


def test_workouts_raw(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_workouts=[INTERVALS])

    result = run_json(["workouts", "--limit", "1", "--raw"], client, capsys)

    assert client.calls == [("get_workouts", (0, 1), {})]
    assert result == [INTERVALS]


class PagedClient:
    """Serves `get_workouts` from a library of `size` workouts."""

    def __init__(self, size: int) -> None:
        self.library = [{"workoutId": n} for n in range(1, size + 1)]
        self.calls: list[tuple[int, int]] = []

    def get_workouts(self, start: int, limit: int) -> list[dict[str, int]]:
        self.calls.append((start, limit))
        return self.library[start : start + limit]


def test_workouts_pages_above_100(capsys: pytest.CaptureFixture[str]) -> None:
    client = PagedClient(300)

    result = run_json(["workouts", "--limit", "250"], client, capsys)

    assert client.calls == [(0, 100), (100, 100), (200, 50)]
    assert [w["id"] for w in result] == list(range(1, 251))


def test_workouts_stops_at_the_end_of_the_library(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = PagedClient(150)

    result = run_json(["workouts", "--limit", "500"], client, capsys)

    assert client.calls == [(0, 100), (100, 100)]
    assert len(result) == 150


def test_workout_with_steps(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_workout_by_id=DETAIL)

    result = run_json(["workout", "501"], client, capsys)

    assert client.calls == [("get_workout_by_id", (501,), {})]
    assert result == {
        **SUMMARY,
        "steps": [
            {
                "type": "warmup",
                "end": "time",
                "end_value": 600.0,
                "target": "no.target",
            },
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


def test_workout_missing_fields(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_workout_by_id={"workoutId": 1})

    assert run_json(["workout", "1"], client, capsys) == {"id": 1, "steps": []}


def test_workout_raw(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_workout_by_id=DETAIL)

    assert run_json(["workout", "501", "--raw"], client, capsys) == DETAIL


def test_workout_unknown_id(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_workout_by_id=GarminConnectNotFoundError("404"))

    assert main(["workout", "999"], connect=lambda: client) == 1
    assert capsys.readouterr().err == (
        "garmin: No workout with ID 999. Run 'garmin workouts' to list IDs.\n"
    )


@pytest.mark.parametrize("value", ["abc", "0"])
def test_workout_invalid_id(value: str, capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_workout_by_id=DETAIL)

    with pytest.raises(SystemExit) as exit:
        main(["workout", value], connect=lambda: client)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        f"garmin: Invalid workout ID '{value}'. Run 'garmin workouts' to list IDs.\n"
    )


def test_workout_missing_id(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["workout"])

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        "garmin: Missing workout ID. Run 'garmin workouts' to list IDs, "
        "then 'garmin workout <id>'.\n"
    )
