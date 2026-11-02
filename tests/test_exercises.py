import json

import pytest

from garmin_cli.cli import main
from garmin_cli.client import GarminClient


def no_login() -> GarminClient:
    raise AssertionError("exercise list logged in")


def run_exercises(argv: list[str], capsys: pytest.CaptureFixture[str]) -> object:
    assert main(["exercise", "list", *argv], connect=no_login) == 0
    return json.loads(capsys.readouterr().out)


def test_search_matches_every_word_sorted_by_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_exercises(["--search", "FLOOR press"], capsys) == [
        {"name": "Barbell Floor Press", "category": "BENCH_PRESS"},
        {"name": "Dumbbell Floor Press", "category": "BENCH_PRESS"},
        {"name": "Floor Inverted Shoulder Press", "category": "SHOULDER_PRESS"},
        {"name": "One-arm Floor Press", "category": "BENCH_PRESS"},
        {
            "name": "Weighted Floor Inverted Shoulder Press",
            "category": "SHOULDER_PRESS",
        },
        {"name": "Weighted One-arm Floor Press", "category": "BENCH_PRESS"},
    ]


def test_search_ignores_punctuation(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_exercises(["--search", "one arm floor-press"], capsys) == [
        {"name": "One-arm Floor Press", "category": "BENCH_PRESS"},
        {"name": "Weighted One-arm Floor Press", "category": "BENCH_PRESS"},
    ]


def test_without_search_lists_the_first_names_up_to_the_limit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_exercises(["--limit", "2"], capsys) == [
        {"name": "3-way Calf Raise", "category": "CALF_RAISE"},
        {"name": "3-way Single-leg Calf Raise", "category": "CALF_RAISE"},
    ]


def test_limit_defaults_to_20(capsys: pytest.CaptureFixture[str]) -> None:
    found = run_exercises(["--search", "press"], capsys)

    assert isinstance(found, list)
    assert (len(found), found[0]) == (
        20,
        {"name": "Alternating Dumbbell Chest Press", "category": "BENCH_PRESS"},
    )


def test_no_match_prints_an_empty_list(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_exercises(["--search", "zzz"], capsys) == []


def test_exercise_without_a_command_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["exercise"], connect=no_login)

    out = capsys.readouterr()
    assert (exit.value.code, out.out, out.err) == (
        2,
        "",
        "garmin: No command given. Run 'garmin exercise <command>', one of: list.\n",
    )
