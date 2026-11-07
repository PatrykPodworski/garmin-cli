import json
from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectNotFoundError

from garmin_cli.cli import main

TYPES = [
    {"typeId": 1, "typeKey": "running"},
    {"typeId": 6, "typeKey": "trail_running"},
]
COURSE = {
    "courseId": 111,
    "courseName": "Hill Loop",
    "activityTypePk": 6,
    "distanceMeter": 5321.5,
    "elevationGainMeter": 210.25,
    "elevationLossMeter": 209.75,
    "rulePK": 2,
    "geoPoints": [{"latitude": 10.0, "longitude": 20.0}],
}
SHOWN = {
    "id": 111,
    "name": "Hill Loop",
    "type": "trail_running",
    "distance_m": 5321.5,
    "elevation_gain_m": 210.25,
    "elevation_loss_m": 209.75,
    "privacy": "private",
}
SECOND = {"courseId": 222, "courseName": "Flat", "activityTypePk": 1, "rulePK": 1}
SECOND_SHOWN = {"id": 222, "name": "Flat", "type": "running", "privacy": "public"}
INVALID_ID = "Run 'garmin course list' to list IDs."


def run(
    argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    try:
        code = main(argv, connect=lambda: client)
    except SystemExit as exit:
        code = int(exit.code or 0)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_course_list_summarizes_each_course(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get_courses=[COURSE, SECOND], get_activity_types=TYPES)

    code, out, err = run(["course", "list"], client, capsys)

    assert (code, err) == (0, "")
    assert json.loads(out) == [SHOWN, SECOND_SHOWN]
    assert client.calls == [
        ("get_courses", (), {}),
        ("get_activity_types", (), {}),
    ]


def test_course_list_limit_keeps_the_first_courses(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get_courses=[COURSE, SECOND], get_activity_types=TYPES)

    code, out, _ = run(["course", "list", "--limit", "1"], client, capsys)

    assert code == 0
    assert '"id": 222' not in out
    assert '"id": 111' in out


def test_course_list_default_limit_is_20(capsys: pytest.CaptureFixture[str]) -> None:
    many = [{"courseId": number} for number in range(1, 25)]
    client = FakeClient(get_courses=many, get_activity_types=TYPES)

    code, out, _ = run(["course", "list"], client, capsys)

    assert code == 0
    assert out.count('"id"') == 20


def test_course_list_empty_prints_empty_list(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get_courses=[], get_activity_types=TYPES)

    assert run(["course", "list"], client, capsys) == (0, "[]\n", "")


def test_course_list_leaves_out_missing_and_unknown_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    course = {"courseId": 333, "activityTypePk": 99, "rulePK": 4, "distanceMeter": None}
    client = FakeClient(get_courses=[course], get_activity_types=TYPES)

    code, out, _ = run(["course", "list"], client, capsys)

    assert (code, out) == (0, '[\n  {\n    "id": 333\n  }\n]\n')


def test_course_list_raw_prints_garmin_response(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get_courses=[COURSE, SECOND])

    code, out, _ = run(["course", "list", "--raw", "--limit", "1"], client, capsys)

    assert code == 0
    assert '"geoPoints"' in out
    assert '"courseId": 222' not in out
    assert client.calls == [("get_courses", (), {})]


@pytest.mark.parametrize("value", ["x", "0", "-1"])
def test_course_list_invalid_limit_exits_2(
    capsys: pytest.CaptureFixture[str], value: str
) -> None:
    client = FakeClient()

    assert run(["course", "list", "--limit", value], client, capsys) == (
        2,
        "",
        f"garmin: Invalid --limit '{value}'. Use a whole number of 1 or more.\n",
    )
    assert client.calls == []


def test_course_view_summarizes_the_course(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_course=COURSE, get_activity_types=TYPES)

    code, out, err = run(["course", "view", "111"], client, capsys)

    assert (code, err) == (0, "")
    assert out == (
        '{\n  "id": 111,\n  "name": "Hill Loop",\n  "type": "trail_running",\n  '
        '"distance_m": 5321.5,\n  "elevation_gain_m": 210.25,\n  "elevation_loss_m": '
        '209.75,\n  "privacy": "private"\n}\n'
    )
    assert client.calls == [
        ("get_course", (111,), {}),
        ("get_activity_types", (), {}),
    ]


def test_course_view_rounds_floats(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(
        get_course={"courseId": 111, "distanceMeter": 1000.123},
        get_activity_types=TYPES,
    )

    code, out, _ = run(["course", "view", "111"], client, capsys)

    assert (code, out) == (0, '{\n  "id": 111,\n  "distance_m": 1000.12\n}\n')


def test_course_view_raw_prints_garmin_response(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get_course={"courseId": 111, "distanceMeter": 1000.123})

    code, out, _ = run(["course", "view", "111", "--raw"], client, capsys)

    assert (code, out) == (0, '{\n  "courseId": 111,\n  "distanceMeter": 1000.123\n}\n')
    assert client.calls == [("get_course", (111,), {})]


def test_course_view_unknown_id_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_course=GarminConnectNotFoundError("404"))

    assert run(["course", "view", "999"], client, capsys) == (
        1,
        "",
        f"garmin: No course with ID 999. {INVALID_ID}\n",
    )


@pytest.mark.parametrize("value", ["x", "0", "-5"])
def test_course_view_invalid_id_exits_2(
    capsys: pytest.CaptureFixture[str], value: str
) -> None:
    client = FakeClient()

    assert run(["course", "view", "--", value], client, capsys) == (
        2,
        "",
        f"garmin: Invalid course ID '{value}'. {INVALID_ID}\n",
    )
    assert client.calls == []


def test_course_view_missing_id_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(["course", "view"], FakeClient(), capsys) == (
        2,
        "",
        "garmin: Missing course ID. Run 'garmin course list' to list IDs, then "
        "'garmin course view <id>'.\n",
    )


def test_course_without_command_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(["course"], FakeClient(), capsys) == (
        2,
        "",
        "garmin: No command given. Run 'garmin course <command>', one of: list, "
        "view, create.\n",
    )


def test_course_view_accepts_id_1(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_course={"courseId": 1})

    assert run(["course", "view", "1", "--raw"], client, capsys)[0] == 0
    assert client.calls == [("get_course", (1,), {})]
