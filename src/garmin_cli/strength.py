"""The strength workout file that `garmin workout add --strength` reads, turned into
Garmin's workout JSON with the fields the Garmin Connect strength editor sends."""

import difflib
import itertools
import json
from collections.abc import Iterator
from typing import Any

from garmin_cli.exercises import BY_WORDS, words

STRENGTH = {"sportTypeId": 5, "sportTypeKey": "strength_training", "displayOrder": 3}
NO_TARGET = {
    "workoutTargetTypeId": 1,
    "workoutTargetTypeKey": "no.target",
    "displayOrder": 1,
}
WORKOUT_KEYS = ("name", "note", "warmup", "blocks", "cooldown")
EDGE_KEYS = ("time_s", "note")
BLOCK_KEYS = ("sets", "steps")
EXERCISE_KEYS = ("exercise", "reps", "time_s", "weight_kg", "note")
REST_KEYS = ("rest", "time_s", "note")
WORKOUT_NOTE = 512
STEP_NOTE = 200
# The editor sends this value with a lap-button end, which has no value of its own.
LAP_VALUE = 10
# The duration estimate counts this many seconds for each rep.
SECONDS_PER_REP = 3


class InvalidWorkout(Exception):
    def __init__(self, where: str, problem: str) -> None:
        self.where = where
        self.problem = problem


def condition(type_id: int, key: str, displayable: bool = True) -> dict[str, Any]:
    return {
        "conditionTypeId": type_id,
        "conditionTypeKey": key,
        "displayOrder": type_id,
        "displayable": displayable,
    }


def step_type(type_id: int, key: str) -> dict[str, Any]:
    return {"stepTypeId": type_id, "stepTypeKey": key, "displayOrder": type_id}


def check_keys(value: dict[str, Any], allowed: tuple[str, ...], where: str) -> None:
    if unknown := [key for key in value if key not in allowed]:
        raise InvalidWorkout(
            where, f"has an unknown key '{unknown[0]}'. Use only {', '.join(allowed)}."
        )


def whole(value: dict[str, Any], key: str, where: str) -> int:
    number = value[key]
    # `bool` is an `int` subclass, so `true` would pass an isinstance check.
    if type(number) is not int or number < 1:
        raise InvalidWorkout(
            where, f"has {key} {json.dumps(number)}. Give a whole number from 1."
        )
    return number


def note(value: dict[str, Any], limit: int, where: str) -> str | None:
    text = value.get("note")
    if text is None:
        return None
    if not isinstance(text, str):
        raise InvalidWorkout(
            where, "has a note that is not text. Give the note as a string."
        )
    if len(text) > limit:
        raise InvalidWorkout(
            where, f"has a note of {len(text)} characters. Shorten it to {limit}."
        )
    return text


def ending(value: dict[str, Any], where: str) -> dict[str, Any]:
    """The end condition fields: reps, time_s, or the lap button without either."""
    if "reps" in value and "time_s" in value:
        raise InvalidWorkout(
            where,
            "has both reps and time_s. Keep one; with neither, the step ends when you "
            "press the lap button.",
        )
    if "reps" in value:
        end, amount = condition(10, "reps"), whole(value, "reps", where)
    elif "time_s" in value:
        end, amount = condition(2, "time"), whole(value, "time_s", where)
    else:
        end, amount = condition(1, "lap.button"), LAP_VALUE
    return {"endCondition": end, "endConditionValue": amount}


def executable(
    type_id: int, key: str, value: dict[str, Any], where: str, **fields: Any
) -> dict[str, Any]:
    step = {
        "type": "ExecutableStepDTO",
        "stepType": step_type(type_id, key),
        **ending(value, where),
        "targetType": NO_TARGET,
        **fields,
    }
    if (text := note(value, STEP_NOTE, where)) is not None:
        step["description"] = text
    return step


def edge(value: Any, type_id: int, key: str) -> dict[str, Any]:
    """A warm-up or cool-down step."""
    where = f"The {key}"
    if not isinstance(value, dict):
        raise InvalidWorkout(
            where,
            "is not a JSON object. Give {} to end it with the lap button, or "
            '{"time_s": N}.',
        )
    check_keys(value, EDGE_KEYS, where)
    return executable(
        type_id, key, value, where, category="CARDIO", exerciseName="CARDIO"
    )


def find_exercise(name: Any, where: str) -> dict[str, str]:
    typed = str(name)
    if found := BY_WORDS.get(words(typed)):
        return found
    problem = f"has an unknown exercise '{typed}'."
    if match := difflib.get_close_matches(words(typed), BY_WORDS):
        problem += f" Did you mean '{BY_WORDS[match[0]]['name']}'?"
    raise InvalidWorkout(
        where, f"{problem} Find names with 'garmin exercise list --search TEXT'."
    )


def block_step(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvalidWorkout(
            where,
            'is not a JSON object. Give {"exercise": NAME, ...} or {"rest": true, '
            "...}.",
        )
    if "rest" in value:
        check_keys(value, REST_KEYS, where)
        if value["rest"] is not True:
            raise InvalidWorkout(
                where,
                'has "rest" other than true. Write "rest": true and give the time in '
                '"time_s".',
            )
        return executable(5, "rest", value, where)
    check_keys(value, EXERCISE_KEYS, where)
    if "exercise" not in value:
        raise InvalidWorkout(
            where,
            'has no exercise. Add "exercise" with a name from \'garmin exercise '
            'list\', or "rest": true for a rest step.',
        )
    exercise = find_exercise(value["exercise"], where)
    fields: dict[str, Any] = {
        "category": exercise["category"],
        "exerciseName": exercise["exercise"],
    }
    if "weight_kg" in value:
        weight = value["weight_kg"]
        if type(weight) not in (int, float) or not weight > 0:
            raise InvalidWorkout(
                where,
                f"has weight_kg {json.dumps(weight)}. Give the weight in kilograms, "
                "above 0.",
            )
        fields |= {"weightValue": weight, "weightUnit": {"unitKey": "kilogram"}}
    return executable(3, "interval", value, where, **fields)


def repeat_group(value: Any, index: int) -> dict[str, Any]:
    where = f"Block {index}"
    if not isinstance(value, dict):
        raise InvalidWorkout(
            where, 'is not a JSON object. Give {"sets": N, "steps": [...]}.'
        )
    check_keys(value, BLOCK_KEYS, where)
    if "sets" not in value:
        raise InvalidWorkout(where, 'has no sets. Add "sets", the number of rounds.')
    sets = whole(value, "sets", where)
    steps = value.get("steps")
    if not isinstance(steps, list) or not steps:
        raise InvalidWorkout(
            where, 'has no steps. Add "steps", a list of exercise and rest steps.'
        )
    children = [
        {**block_step(step, f"Step {number} of block {index}"), "childStepId": index}
        for number, step in enumerate(steps, 1)
    ]
    return {
        "type": "RepeatGroupDTO",
        "stepType": step_type(6, "repeat"),
        "numberOfIterations": sets,
        "smartRepeat": False,
        "childStepId": index,
        "endCondition": condition(7, "iterations", displayable=False),
        "skipLastRestStep": False,
        "workoutSteps": children,
    }


def number(
    steps: list[dict[str, Any]], orders: Iterator[int], ids: Iterator[int]
) -> None:
    """Numbers steps as the editor does: `stepOrder` before a group's steps,
    `stepId` after them. Garmin replaces both."""
    for step in steps:
        step["stepOrder"] = next(orders)
        number(step.get("workoutSteps", []), orders, ids)
        step["stepId"] = next(ids)


def duration(steps: list[dict[str, Any]]) -> int:
    """Seconds the steps take: a time end as given, 3 seconds per rep, a repeat
    group times its sets, and nothing for a lap-button end."""
    seconds = 0
    for step in steps:
        if "workoutSteps" in step:
            seconds += step["numberOfIterations"] * duration(step["workoutSteps"])
        elif step["endCondition"]["conditionTypeKey"] == "time":
            seconds += step["endConditionValue"]
        elif step["endCondition"]["conditionTypeKey"] == "reps":
            seconds += step["endConditionValue"] * SECONDS_PER_REP
    return seconds


def build(data: Any) -> dict[str, Any]:
    where = "The workout"
    if not isinstance(data, dict):
        raise InvalidWorkout(
            where,
            "is not a JSON object. Pass one strength workout object with name and "
            "blocks.",
        )
    check_keys(data, WORKOUT_KEYS, where)
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise InvalidWorkout(where, 'has no name. Add "name" with the workout name.')
    description = note(data, WORKOUT_NOTE, where)
    steps = []
    if "warmup" in data:
        steps.append(edge(data["warmup"], 1, "warmup"))
    blocks = data.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise InvalidWorkout(
            where,
            'has no blocks. Add "blocks", a list of {"sets": N, "steps": [...]}.',
        )
    steps += [repeat_group(block, index) for index, block in enumerate(blocks, 1)]
    if "cooldown" in data:
        steps.append(edge(data["cooldown"], 2, "cooldown"))
    number(steps, itertools.count(1), itertools.count(1))
    return {
        "sportType": STRENGTH,
        "subSportType": None,
        "workoutName": name,
        "description": description,
        "estimatedDistanceUnit": {"unitKey": None},
        "workoutSegments": [
            {"segmentOrder": 1, "sportType": STRENGTH, "workoutSteps": steps}
        ],
        "estimatedDurationInSecs": duration(steps),
        "estimatedDistanceInMeters": 0,
        "estimateType": None,
        "isWheelchair": False,
    }
