import json
from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError, GarminConnectNotFoundError
from test_courses import COURSE, INVALID_ID, SHOWN, TYPES, run


def edit_client(course: Any = COURSE, saved: Any = COURSE) -> FakeClient:
    return FakeClient(get_course=course, update_course=saved, get_activity_types=TYPES)


@pytest.mark.parametrize(
    ("options", "changed", "shown"),
    [
        (
            ["--name", "Hill Repeats"],
            {"courseName": "Hill Repeats"},
            {"name": "Hill Repeats"},
        ),
        (["--privacy", "public"], {"rulePK": 1}, {"privacy": "public"}),
        (
            ["--privacy", "public", "--name", " Hill Repeats "],
            {"courseName": "Hill Repeats", "rulePK": 1},
            {"name": "Hill Repeats", "privacy": "public"},
        ),
    ],
)
def test_course_edit_sends_the_course_with_only_the_given_fields_changed(
    capsys: pytest.CaptureFixture[str],
    options: list[str],
    changed: dict[str, Any],
    shown: dict[str, Any],
) -> None:
    body = {**COURSE, **changed}
    client = edit_client(saved=body)

    code, out, err = run(["course", "edit", "111", *options], client, capsys)

    name = body["courseName"]
    assert (code, err) == (0, f'garmin: Updated course "{name}" (ID 111).\n')
    assert json.loads(out) == {**SHOWN, **shown}
    assert client.calls == [
        ("get_course", (111,), {}),
        ("update_course", (111, body), {}),
        ("get_activity_types", (), {}),
    ]


def test_course_edit_fetches_the_course_when_garmin_answers_empty(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = edit_client(saved=None)

    code, out, err = run(
        ["course", "edit", "111", "--privacy", "private"], client, capsys
    )

    assert (code, err) == (0, 'garmin: Updated course "Hill Loop" (ID 111).\n')
    assert json.loads(out) == SHOWN
    assert client.calls == [
        ("get_course", (111,), {}),
        ("update_course", (111, COURSE), {}),
        ("get_course", (111,), {}),
        ("get_activity_types", (), {}),
    ]


def test_course_edit_without_name_shows_id(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = edit_client(course={"courseId": 111}, saved={"courseId": 111, "rulePK": 1})

    result = run(["course", "edit", "111", "--privacy", "public"], client, capsys)

    assert result == (
        0,
        '{\n  "id": 111,\n  "privacy": "public"\n}\n',
        "garmin: Updated course 111.\n",
    )


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["111"], "Nothing to change. Give --name or --privacy."),
        (["111", "--name", ""], "Invalid --name ''. Give a name that is not blank."),
        (
            ["111", "--name", "  "],
            "Invalid --name '  '. Give a name that is not blank.",
        ),
        (
            ["111", "--privacy", "secret"],
            "Invalid --privacy 'secret'. Use private or public.",
        ),
        (["x", "--name", "Hill Repeats"], f"Invalid course ID 'x'. {INVALID_ID}"),
        (
            [],
            "Missing course ID. Run 'garmin course list' to list IDs, then "
            "'garmin course edit <id>'.",
        ),
    ],
)
def test_course_edit_invalid_arguments_exit_2(
    capsys: pytest.CaptureFixture[str], argv: list[str], message: str
) -> None:
    client = edit_client()

    result = run(["course", "edit", *argv], client, capsys)

    assert result == (2, "", f"garmin: {message}\n")
    assert client.calls == []


def test_course_edit_unknown_id_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = edit_client(course=GarminConnectNotFoundError("API Error 404"))

    result = run(["course", "edit", "999", "--name", "Hill Repeats"], client, capsys)

    assert result == (1, "", f"garmin: No course with ID 999. {INVALID_ID}\n")
    assert client.calls == [("get_course", (999,), {})]


def test_course_edit_not_yet_ready_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = edit_client(
        saved=GarminConnectConnectionError(
            "API Error 429 - The course [111] is not yet ready to delete or update"
        )
    )

    result = run(["course", "edit", "111", "--name", "Hill Repeats"], client, capsys)

    assert result == (
        1,
        "",
        "garmin: Garmin is still processing course 111 after a change. "
        "Try again in a few minutes.\n",
    )
