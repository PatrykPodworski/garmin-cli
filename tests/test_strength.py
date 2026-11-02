import json
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeClient

from garmin_cli.cli import main

STRENGTH = {"sportTypeId": 5, "sportTypeKey": "strength_training", "displayOrder": 3}
NO_TARGET = {
    "workoutTargetTypeId": 1,
    "workoutTargetTypeKey": "no.target",
    "displayOrder": 1,
}
LAP_BUTTON = {
    "conditionTypeId": 1,
    "conditionTypeKey": "lap.button",
    "displayOrder": 1,
    "displayable": True,
}
TIME = {
    "conditionTypeId": 2,
    "conditionTypeKey": "time",
    "displayOrder": 2,
    "displayable": True,
}
REPS = {
    "conditionTypeId": 10,
    "conditionTypeKey": "reps",
    "displayOrder": 10,
    "displayable": True,
}
ITERATIONS = {
    "conditionTypeId": 7,
    "conditionTypeKey": "iterations",
    "displayOrder": 7,
    "displayable": False,
}
WARMUP = {"stepTypeId": 1, "stepTypeKey": "warmup", "displayOrder": 1}
COOLDOWN = {"stepTypeId": 2, "stepTypeKey": "cooldown", "displayOrder": 2}
INTERVAL = {"stepTypeId": 3, "stepTypeKey": "interval", "displayOrder": 3}
REST = {"stepTypeId": 5, "stepTypeKey": "rest", "displayOrder": 5}
REPEAT = {"stepTypeId": 6, "stepTypeKey": "repeat", "displayOrder": 6}

PLAN = {
    "name": "Upper A",
    "note": "Gym by the river",
    "warmup": {"time_s": 300, "note": "Rower"},
    "blocks": [
        {
            "sets": 3,
            "steps": [
                {
                    "exercise": "barbell bench press",
                    "reps": 8,
                    "weight_kg": 42.5,
                    "note": "Pause at the chest",
                },
                {"rest": True, "time_s": 90},
            ],
        },
        {"sets": 2, "steps": [{"exercise": "Plank", "time_s": 40}, {"rest": True}]},
    ],
    "cooldown": {},
}
UPLOADED = {
    "sportType": STRENGTH,
    "subSportType": None,
    "workoutName": "Upper A",
    "description": "Gym by the river",
    "estimatedDistanceUnit": {"unitKey": None},
    "workoutSegments": [
        {
            "segmentOrder": 1,
            "sportType": STRENGTH,
            "workoutSteps": [
                {
                    "stepId": 1,
                    "stepOrder": 1,
                    "type": "ExecutableStepDTO",
                    "stepType": WARMUP,
                    "endCondition": TIME,
                    "endConditionValue": 300,
                    "targetType": NO_TARGET,
                    "category": "CARDIO",
                    "exerciseName": "CARDIO",
                    "description": "Rower",
                },
                {
                    "stepId": 4,
                    "stepOrder": 2,
                    "type": "RepeatGroupDTO",
                    "stepType": REPEAT,
                    "numberOfIterations": 3,
                    "smartRepeat": False,
                    "childStepId": 1,
                    "endCondition": ITERATIONS,
                    "skipLastRestStep": False,
                    "workoutSteps": [
                        {
                            "stepId": 2,
                            "stepOrder": 3,
                            "type": "ExecutableStepDTO",
                            "stepType": INTERVAL,
                            "endCondition": REPS,
                            "endConditionValue": 8,
                            "targetType": NO_TARGET,
                            "childStepId": 1,
                            "category": "BENCH_PRESS",
                            "exerciseName": "BARBELL_BENCH_PRESS",
                            "weightValue": 42.5,
                            "weightUnit": {"unitKey": "kilogram"},
                            "description": "Pause at the chest",
                        },
                        {
                            "stepId": 3,
                            "stepOrder": 4,
                            "type": "ExecutableStepDTO",
                            "stepType": REST,
                            "endCondition": TIME,
                            "endConditionValue": 90,
                            "targetType": NO_TARGET,
                            "childStepId": 1,
                        },
                    ],
                },
                {
                    "stepId": 7,
                    "stepOrder": 5,
                    "type": "RepeatGroupDTO",
                    "stepType": REPEAT,
                    "numberOfIterations": 2,
                    "smartRepeat": False,
                    "childStepId": 2,
                    "endCondition": ITERATIONS,
                    "skipLastRestStep": False,
                    "workoutSteps": [
                        {
                            "stepId": 5,
                            "stepOrder": 6,
                            "type": "ExecutableStepDTO",
                            "stepType": INTERVAL,
                            "endCondition": TIME,
                            "endConditionValue": 40,
                            "targetType": NO_TARGET,
                            "childStepId": 2,
                            "category": "PLANK",
                            "exerciseName": "PLANK",
                        },
                        {
                            "stepId": 6,
                            "stepOrder": 7,
                            "type": "ExecutableStepDTO",
                            "stepType": REST,
                            "endCondition": LAP_BUTTON,
                            "endConditionValue": 10,
                            "targetType": NO_TARGET,
                            "childStepId": 2,
                        },
                    ],
                },
                {
                    "stepId": 8,
                    "stepOrder": 8,
                    "type": "ExecutableStepDTO",
                    "stepType": COOLDOWN,
                    "endCondition": LAP_BUTTON,
                    "endConditionValue": 10,
                    "targetType": NO_TARGET,
                    "category": "CARDIO",
                    "exerciseName": "CARDIO",
                },
            ],
        }
    ],
    # Warm-up 300 + 3 x (8 reps x 3 + rest 90) + 2 x (plank 40 + lap rest 0) + lap
    # cool-down 0.
    "estimatedDurationInSecs": 722,
    "estimatedDistanceInMeters": 0,
    "estimateType": None,
    "isWheelchair": False,
}
CREATED = {"workoutId": 777, "workoutName": "Upper A", "estimatedDurationInSecs": 0}


def write(tmp_path: Path, plan: Any) -> str:
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
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


def uploaded(client: FakeClient) -> Any:
    [(name, (workout,), _)] = client.calls
    assert name == "upload_workout"
    return workout


def test_strength_file_becomes_a_garmin_strength_workout(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = FakeClient(upload_workout=CREATED)
    path = write(tmp_path, PLAN)

    code, out, err = run(
        ["workout", "add", "--strength", "--file", path], client, capsys
    )

    assert (code, json.loads(out), err) == (
        0,
        {
            "id": 777,
            "name": "Upper A",
            "estimated_duration_min": 12.03,
            "scheduled": None,
        },
        'garmin: Created workout "Upper A" (ID 777).\n',
    )
    assert uploaded(client) == UPLOADED


def test_strength_add_prints_the_duration_garmin_stored(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = FakeClient(upload_workout={**CREATED, "estimatedDurationInSecs": 900})

    _, out, _ = run(
        ["workout", "add", "--strength", "--file", write(tmp_path, PLAN)],
        client,
        capsys,
    )

    assert json.loads(out)["estimated_duration_min"] == 15.0


def test_strength_estimate_without_reps_or_time_is_0(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = FakeClient(upload_workout=CREATED)
    plan = {
        "name": "Pull",
        "warmup": {},
        "blocks": [{"sets": 4, "steps": [{"exercise": "Pull-up"}, {"rest": True}]}],
    }

    _, out, _ = run(
        ["workout", "add", "--strength", "--file", write(tmp_path, plan)],
        client,
        capsys,
    )

    assert uploaded(client)["estimatedDurationInSecs"] == 0
    assert json.loads(out)["estimated_duration_min"] == 0


def test_minimal_strength_file_ends_steps_on_the_lap_button(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = FakeClient(upload_workout=CREATED)
    plan = {"name": "Pull", "blocks": [{"sets": 1, "steps": [{"exercise": "Pull-up"}]}]}

    code, _, _ = run(
        ["workout", "add", "--strength", "--file", write(tmp_path, plan)],
        client,
        capsys,
    )

    workout = uploaded(client)
    assert (code, workout["workoutName"], workout["description"]) == (0, "Pull", None)
    assert workout["workoutSegments"][0]["workoutSteps"] == [
        {
            "stepId": 2,
            "stepOrder": 1,
            "type": "RepeatGroupDTO",
            "stepType": REPEAT,
            "numberOfIterations": 1,
            "smartRepeat": False,
            "childStepId": 1,
            "endCondition": ITERATIONS,
            "skipLastRestStep": False,
            "workoutSteps": [
                {
                    "stepId": 1,
                    "stepOrder": 2,
                    "type": "ExecutableStepDTO",
                    "stepType": INTERVAL,
                    "endCondition": LAP_BUTTON,
                    "endConditionValue": 10,
                    "targetType": NO_TARGET,
                    "childStepId": 1,
                    "category": "PULL_UP",
                    "exerciseName": "PULL_UP",
                }
            ],
        }
    ]


@pytest.mark.parametrize(
    ("name", "category", "exercise"),
    [
        (
            "Close-grip Barbell Bench Press",
            "BENCH_PRESS",
            "CLOSE_GRIP_BARBELL_BENCH_PRESS",
        ),
        (
            "close grip barbell bench press",
            "BENCH_PRESS",
            "CLOSE_GRIP_BARBELL_BENCH_PRESS",
        ),
        (
            "  DUMBBELL bulgarian split-squat ",
            "LUNGE",
            "DUMBBELL_BULGARIAN_SPLIT_SQUAT",
        ),
    ],
)
def test_exercise_names_match_ignoring_case_and_punctuation(
    name: str,
    category: str,
    exercise: str,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    client = FakeClient(upload_workout=CREATED)
    plan = {"name": "A", "blocks": [{"sets": 1, "steps": [{"exercise": name}]}]}

    run(
        ["workout", "add", "--strength", "--file", write(tmp_path, plan)],
        client,
        capsys,
    )

    step = uploaded(client)["workoutSegments"][0]["workoutSteps"][0]["workoutSteps"][0]
    assert (step["category"], step["exerciseName"]) == (category, exercise)


def test_limits_are_inclusive(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = FakeClient(upload_workout=CREATED)
    plan = {
        "name": "A",
        "note": "w" * 512,
        "blocks": [
            {
                "sets": 1,
                "steps": [{"exercise": "Plank", "weight_kg": 0.5, "note": "s" * 200}],
            }
        ],
    }

    code, _, _ = run(
        ["workout", "add", "--strength", "--file", write(tmp_path, plan)],
        client,
        capsys,
    )

    workout = uploaded(client)
    step = workout["workoutSegments"][0]["workoutSteps"][0]["workoutSteps"][0]
    assert (code, workout["description"], step["weightValue"], step["description"]) == (
        0,
        "w" * 512,
        0.5,
        "s" * 200,
    )


def test_strength_workout_can_be_scheduled(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = FakeClient(
        upload_workout=CREATED,
        schedule_workout={"workoutScheduleId": 9, "calendarDate": "2026-11-05"},
    )

    code, out, err = run(
        [
            "workout",
            "add",
            "--strength",
            "--file",
            write(tmp_path, PLAN),
            "--schedule",
            "2026-11-05",
        ],
        client,
        capsys,
    )

    assert (code, json.loads(out)["scheduled"], err) == (
        0,
        "2026-11-05",
        'garmin: Created workout "Upper A" (ID 777) and scheduled it for 2026-11-05.\n',
    )
    assert client.calls[1] == ("schedule_workout", (777, "2026-11-05"), {})


def block(*steps: Any) -> dict[str, Any]:
    return {"name": "A", "blocks": [{"sets": 3, "steps": list(steps)}]}


BENCH = {"exercise": "Bench Press"}
HINT = "Find names with 'garmin exercise list --search TEXT'."


@pytest.mark.parametrize(
    ("plan", "message"),
    [
        (
            [],
            "The workout in {source} is not a JSON object. Pass one strength workout "
            "object with name and blocks.",
        ),
        (
            {"blocks": []},
            'The workout in {source} has no name. Add "name" with the workout name.',
        ),
        (
            {"name": " ", "blocks": []},
            'The workout in {source} has no name. Add "name" with the workout name.',
        ),
        (
            {"name": 5, "blocks": []},
            'The workout in {source} has no name. Add "name" with the workout name.',
        ),
        (
            {"name": "A", "block": []},
            "The workout in {source} has an unknown key 'block'. Use only name, note, "
            "warmup, blocks, cooldown.",
        ),
        (
            {"name": "A"},
            'The workout in {source} has no blocks. Add "blocks", a list of '
            '{{"sets": N, "steps": [...]}}.',
        ),
        (
            {"name": "A", "blocks": []},
            'The workout in {source} has no blocks. Add "blocks", a list of '
            '{{"sets": N, "steps": [...]}}.',
        ),
        (
            {"name": "A", "blocks": {}},
            'The workout in {source} has no blocks. Add "blocks", a list of '
            '{{"sets": N, "steps": [...]}}.',
        ),
        (
            {"name": "A", "note": "x" * 513, "blocks": []},
            "The workout in {source} has a note of 513 characters. Shorten it to 512.",
        ),
        (
            {"name": "A", "note": 1, "blocks": []},
            "The workout in {source} has a note that is not text. Give the note as a "
            "string.",
        ),
        (
            {"name": "A", "warmup": True, "blocks": []},
            "The warmup in {source} is not a JSON object. Give {{}} to end it with the "
            'lap button, or {{"time_s": N}}.',
        ),
        (
            {**block(BENCH), "cooldown": {"reps": 5}},
            "The cooldown in {source} has an unknown key 'reps'. Use only time_s, "
            "note.",
        ),
        (
            {"name": "A", "blocks": [[]]},
            'Block 1 in {source} is not a JSON object. Give {{"sets": N, "steps": '
            "[...]}}.",
        ),
        (
            {"name": "A", "blocks": [{"steps": [BENCH]}]},
            'Block 1 in {source} has no sets. Add "sets", the number of rounds.',
        ),
        (
            {"name": "A", "blocks": [{"sets": 0, "steps": [BENCH]}]},
            "Block 1 in {source} has sets 0. Give a whole number from 1.",
        ),
        (
            {"name": "A", "blocks": [{"sets": 2.5, "steps": [BENCH]}]},
            "Block 1 in {source} has sets 2.5. Give a whole number from 1.",
        ),
        (
            {"name": "A", "blocks": [{"sets": True, "steps": [BENCH]}]},
            "Block 1 in {source} has sets true. Give a whole number from 1.",
        ),
        (
            {"name": "A", "blocks": [{"sets": 1, "steps": [BENCH], "rest_s": 60}]},
            "Block 1 in {source} has an unknown key 'rest_s'. Use only sets, steps.",
        ),
        (
            {"name": "A", "blocks": [{"sets": 1, "steps": []}]},
            'Block 1 in {source} has no steps. Add "steps", a list of exercise and '
            "rest steps.",
        ),
        (
            {"name": "A", "blocks": [{"sets": 1}]},
            'Block 1 in {source} has no steps. Add "steps", a list of exercise and '
            "rest steps.",
        ),
        (
            {
                "name": "A",
                "blocks": [{"sets": 1, "steps": [BENCH]}, {"sets": 1, "steps": ["x"]}],
            },
            'Step 1 of block 2 in {source} is not a JSON object. Give {{"exercise": '
            'NAME, ...}} or {{"rest": true, ...}}.',
        ),
        (
            block(BENCH, {"reps": 5}),
            'Step 2 of block 1 in {source} has no exercise. Add "exercise" with a name '
            "from 'garmin exercise list', or \"rest\": true for a rest step.",
        ),
        (
            block({"exercise": "barbel bench pres"}),
            "Step 1 of block 1 in {source} has an unknown exercise 'barbel bench "
            f"pres'. Did you mean 'Barbell Bench Press'? {HINT}",
        ),
        (
            block({"exercise": "zzz"}),
            f"Step 1 of block 1 in {{source}} has an unknown exercise 'zzz'. {HINT}",
        ),
        (
            block({"exercise": 7}),
            f"Step 1 of block 1 in {{source}} has an unknown exercise '7'. {HINT}",
        ),
        (
            block({"exercise": "Plank", "reps": 10, "time_s": 30}),
            "Step 1 of block 1 in {source} has both reps and time_s. Keep one; with "
            "neither, the step ends when you press the lap button.",
        ),
        (
            block({"exercise": "Plank", "reps": 0}),
            "Step 1 of block 1 in {source} has reps 0. Give a whole number from 1.",
        ),
        (
            block({"exercise": "Plank", "time_s": "45"}),
            'Step 1 of block 1 in {source} has time_s "45". Give a whole number '
            "from 1.",
        ),
        (
            block({"exercise": "Plank", "weight_kg": 0}),
            "Step 1 of block 1 in {source} has weight_kg 0. Give the weight in "
            "kilograms, above 0.",
        ),
        (
            block({"exercise": "Plank", "weight_kg": "20"}),
            'Step 1 of block 1 in {source} has weight_kg "20". Give the weight in '
            "kilograms, above 0.",
        ),
        (
            block({"exercise": "Plank", "weight_kg": False}),
            "Step 1 of block 1 in {source} has weight_kg false. Give the weight in "
            "kilograms, above 0.",
        ),
        (
            block({"exercise": "Plank", "note": "x" * 201}),
            "Step 1 of block 1 in {source} has a note of 201 characters. Shorten it "
            "to 200.",
        ),
        (
            block({"exercise": "Plank", "weight": 20}),
            "Step 1 of block 1 in {source} has an unknown key 'weight'. Use only "
            "exercise, reps, time_s, weight_kg, note.",
        ),
        (
            block(BENCH, {"rest": True, "reps": 3}),
            "Step 2 of block 1 in {source} has an unknown key 'reps'. Use only rest, "
            "time_s, note.",
        ),
        (
            block(BENCH, {"rest": True, "time_s": 0}),
            "Step 2 of block 1 in {source} has time_s 0. Give a whole number from 1.",
        ),
        (
            block(BENCH, {"rest": 90}),
            'Step 2 of block 1 in {source} has "rest" other than true. Write "rest": '
            'true and give the time in "time_s".',
        ),
    ],
)
def test_invalid_strength_file_exits_2_before_login(
    plan: Any, message: str, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = FakeClient(upload_workout=CREATED)
    path = write(tmp_path, plan)

    code, out, err = run(
        ["workout", "add", "--strength", "--file", path], client, capsys
    )

    assert (code, out, err) == (
        2,
        "",
        f"garmin: {message.format(source=repr(path))}\n",
    )
    assert client.calls == []


def test_warmup_is_checked_before_the_blocks(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    path = write(tmp_path, {"name": "A", "warmup": {"time_s": 0}})

    code, _, err = run(
        ["workout", "add", "--strength", "--file", path], FakeClient(), capsys
    )

    assert (code, err) == (
        2,
        f"garmin: The warmup in '{path}' has time_s 0. Give a whole number from 1.\n",
    )


def test_strength_file_from_stdin(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    client = FakeClient(upload_workout=CREATED)
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO('{"name": "A"}'))

    code, out, err = run(
        ["workout", "add", "--strength", "--file", "-"], client, capsys
    )

    assert (code, out, err) == (
        2,
        "",
        'garmin: The workout in stdin has no blocks. Add "blocks", a list of '
        '{"sets": N, "steps": [...]}.\n',
    )
