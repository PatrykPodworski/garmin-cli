from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError, GarminConnectNotFoundError
from test_courses import INVALID_ID, run

COURSE = {"courseId": 111, "courseName": "Hill Loop", "activityTypePk": 6}
HILLS = {"paceBandPk": 501, "paceBandSummary": {"courseId": 111, "name": "Hills 10k"}}
FAST = {"paceBandPk": 502, "paceBandSummary": {"courseId": 111, "name": "Fast 10k"}}
OTHER = {"paceBandPk": 503, "paceBandSummary": {"courseId": 222, "name": "Other"}}
DELETED = '{\n  "deleted": 111\n}\n'
CALLS: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = [
    ("get_course", (111,), {}),
    ("get_pace_bands", (), {}),
    ("delete_course", (111,), {}),
]


def delete_client(
    course: Any = COURSE, plans: Any = (), deleted: Any = None
) -> FakeClient:
    # Garmin answers the delete with 204, which garminconnect returns as None.
    return FakeClient(
        get_course=course, get_pace_bands=list(plans), delete_course=deleted
    )


def test_course_delete_deletes_without_asking(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client(plans=[OTHER])

    result = run(["course", "delete", "0111"], client, capsys)

    assert result == (0, DELETED, 'garmin: Deleted course "Hill Loop".\n')
    assert client.calls == CALLS


@pytest.mark.parametrize(
    ("plans", "named"),
    [
        ([HILLS, OTHER], ' and its PacePro plan "Hills 10k"'),
        ([FAST, OTHER, HILLS], ' and its 2 PacePro plans "Fast 10k", "Hills 10k"'),
        (
            [{"paceBandPk": 504, "paceBandSummary": {"courseId": 111}}],
            (" and its PacePro plan 504"),
        ),
        (
            [HILLS, {"paceBandPk": 504, "paceBandSummary": {"courseId": 111}}],
            ' and its 2 PacePro plans "Hills 10k", 504',
        ),
        ([{"paceBandPk": 505, "paceBandSummary": None}], ""),
        ([{"paceBandPk": 506}], ""),
    ],
)
def test_course_delete_names_the_plans_garmin_deletes_with_it(
    capsys: pytest.CaptureFixture[str], plans: list[dict[str, Any]], named: str
) -> None:
    client = delete_client(plans=plans)

    result = run(["course", "delete", "111"], client, capsys)

    assert result == (0, DELETED, f'garmin: Deleted course "Hill Loop"{named}.\n')
    assert client.calls == CALLS


def test_course_delete_dry_run_deletes_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client(plans=[HILLS])

    result = run(["course", "delete", "111", "--dry-run"], client, capsys)

    assert result == (
        0,
        '{\n  "would_delete": 111\n}\n',
        'garmin: Would delete course "Hill Loop" and its PacePro plan "Hills 10k".\n',
    )
    assert client.calls == CALLS[:2]


def test_course_delete_without_name_shows_id(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client(course={"courseId": 111}, plans=[HILLS])

    result = run(["course", "delete", "111"], client, capsys)

    assert result == (
        0,
        DELETED,
        'garmin: Deleted course 111 and its PacePro plan "Hills 10k".\n',
    )


def test_course_delete_unknown_id_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client(course=GarminConnectNotFoundError("API Error 404"))

    result = run(["course", "delete", "999"], client, capsys)

    assert result == (1, "", f"garmin: No course with ID 999. {INVALID_ID}\n")
    assert client.calls == [("get_course", (999,), {})]


@pytest.mark.parametrize("value", ["abc", "0", "-5", "1.5"])
def test_course_delete_invalid_id_exits_2(
    capsys: pytest.CaptureFixture[str], value: str
) -> None:
    client = delete_client()

    result = run(["course", "delete", "--", value], client, capsys)

    assert result == (2, "", f"garmin: Invalid course ID '{value}'. {INVALID_ID}\n")
    assert client.calls == []


def test_course_delete_missing_id_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = run(["course", "delete"], delete_client(), capsys)

    assert result == (
        2,
        "",
        "garmin: Missing course ID. Run 'garmin course list' to list IDs, then "
        "'garmin course delete <id>'.\n",
    )


def test_course_delete_not_yet_ready_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client(
        deleted=GarminConnectConnectionError(
            "API Error 429 - The course [111] is not yet ready to delete or update"
        )
    )

    result = run(["course", "delete", "111"], client, capsys)

    assert result == (
        1,
        "",
        "garmin: Garmin is still processing course 111 after a change. "
        "Try again in a few minutes.\n",
    )


def test_course_delete_other_429_is_a_rate_limit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client(deleted=GarminConnectConnectionError("API Error 429"))

    result = run(["course", "delete", "111"], client, capsys)

    assert result == (
        1,
        "",
        "garmin: Garmin is rate-limiting requests from this machine. "
        "Wait a few minutes and try again.\n",
    )
