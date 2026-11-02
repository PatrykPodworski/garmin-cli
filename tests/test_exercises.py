import json

import pytest

from garmin_cli.cli import main
from garmin_cli.client import GarminClient


def no_login() -> GarminClient:
    raise AssertionError("exercise list logged in")


def run_exercises(argv: list[str], capsys: pytest.CaptureFixture[str]) -> object:
    assert main(["exercise", "list", *argv], connect=no_login) == 0
    out = capsys.readouterr()
    assert out.err == ""
    return json.loads(out.out)


def run_with_note(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[object, str]:
    assert main(["exercise", "list", *argv], connect=no_login) == 0
    out = capsys.readouterr()
    return json.loads(out.out), out.err


def fail_exercises(argv: list[str], capsys: pytest.CaptureFixture[str]) -> str:
    with pytest.raises(SystemExit) as exit:
        main(["exercise", "list", *argv], connect=no_login)

    out = capsys.readouterr()
    assert (exit.value.code, out.out) == (2, "")
    return out.err


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
    found, _ = run_with_note(["--limit", "2"], capsys)

    assert found == [
        {"name": "3-way Calf Raise", "category": "CALF_RAISE"},
        {"name": "3-way Single-leg Calf Raise", "category": "CALF_RAISE"},
    ]


def test_limit_defaults_to_20(capsys: pytest.CaptureFixture[str]) -> None:
    found, err = run_with_note(["--search", "press"], capsys)

    assert isinstance(found, list)
    assert (len(found), found[0], err) == (
        20,
        {"name": "Alternating Dumbbell Chest Press", "category": "BENCH_PRESS"},
        "garmin: 62 more exercises match. Raise --limit to see them.\n",
    )


def test_search_ignores_the_spaces_between_words(
    capsys: pytest.CaptureFixture[str],
) -> None:
    found, _ = run_with_note(["--search", "pushup", "--limit", "2"], capsys)

    assert found == [
        {"name": "Alternating Staggered Push-up", "category": "PUSH_UP"},
        {"name": "Alternating-hands Medicine Ball Push-up", "category": "PUSH_UP"},
    ]


def test_no_match_prints_the_closest_names_first(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_with_note(["--search", "step down"], capsys) == (
        [
            {"name": "Step-out Swing", "category": "HIP_SWING"},
            {"name": "Lat Pull-down", "category": "PULL_UP"},
            {"name": "Step-up", "category": "SQUAT"},
        ],
        "garmin: No exercise has every word of 'step down'. Showing the closest "
        "names; search again if none fits.\n",
    )


def test_closest_names_stop_at_the_limit(capsys: pytest.CaptureFixture[str]) -> None:
    found, _ = run_with_note(["--search", "step down", "--limit", "1"], capsys)

    assert found == [{"name": "Step-out Swing", "category": "HIP_SWING"}]


def test_closest_names_keep_to_the_category(
    capsys: pytest.CaptureFixture[str],
) -> None:
    found, _ = run_with_note(["--search", "step down", "--category", "SQUAT"], capsys)

    assert found == [{"name": "Step-up", "category": "SQUAT"}]


def test_no_close_name_prints_an_empty_list(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_exercises(["--search", "zzz"], capsys) == []


def test_names_cut_by_the_limit_are_counted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    found, err = run_with_note(["--search", "calf raise", "--limit", "5"], capsys)

    assert (len(found) if isinstance(found, list) else found, err) == (
        5,
        "garmin: 15 more exercises match. Raise --limit to see them.\n",
    )


def test_names_that_fit_the_limit_get_no_count(
    capsys: pytest.CaptureFixture[str],
) -> None:
    found = run_exercises(["--search", "calf raise"], capsys)

    assert isinstance(found, list) and len(found) == 20


def test_category_keeps_its_exercises_in_any_case(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_exercises(
        ["--category", "calf_raise", "--search", "seated"], capsys
    ) == [
        {"name": "Seated Calf Raise", "category": "CALF_RAISE"},
        {"name": "Seated Dumbbell Toe Raise", "category": "CALF_RAISE"},
        {"name": "Weighted Seated Calf Raise", "category": "CALF_RAISE"},
    ]


def test_category_without_search_lists_the_category(
    capsys: pytest.CaptureFixture[str],
) -> None:
    found, _ = run_with_note(["--category", "SHRUG", "--limit", "1"], capsys)

    assert found == [
        {"name": "Barbell Jump Shrug", "category": "SHRUG"},
    ]


@pytest.mark.parametrize(
    ("typed", "suggested"), [("calf", "CALF_RAISE"), ("sqat", "SQUAT")]
)
def test_unknown_category_exits_2_with_a_suggestion(
    typed: str, suggested: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert fail_exercises(["--category", typed], capsys) == (
        f"garmin: Unknown exercise category '{typed}'. Did you mean '{suggested}'? "
        "Run 'garmin exercise list --help' to list the categories.\n"
    )


def test_unknown_category_without_a_close_one_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert fail_exercises(["--category", "zzz"], capsys) == (
        "garmin: Unknown exercise category 'zzz'. "
        "Run 'garmin exercise list --help' to list the categories.\n"
    )


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
