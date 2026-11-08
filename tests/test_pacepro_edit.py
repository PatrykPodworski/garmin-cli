from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectNotFoundError
from test_pacepro import LIST_IDS, PLAN_PATH, run
from test_pacepro_create import COURSE, SUMMARY, point

# Made-up values in the shape Garmin stores a plan made on the website.
STORED_SUMMARY = {
    **SUMMARY,
    "paceBandPk": 501,
    "userProfilePk": 900,
    "createdDate": "2026-01-02T03:04:05.0",
    "lastUpdatedDate": "2026-01-03T03:04:05.0",
    "eventDate": "2026-02-01",
    "name": "Old Name",
    "goalTime": 1000,
    "goalSpeed": 2.0,
}
STORED_SPLITS = [
    {
        "paceBandSplitPk": 71,
        "bearing": 12.5,
        "splitDistance": 1000.0,
        "splitAvgSpeed": 2.1,
        "cumulativeDistanceFromStart": 1000.0,
        "cumulativeTimeFromStart": 476.19,
        "startPoint": {"latitude": 0.0, "longitude": 0.0, "elevation": 100.0},
        "endPoint": {"latitude": 0.009, "longitude": 0.0, "elevation": 100.0},
    },
    {
        "paceBandSplitPk": 72,
        "bearing": 13.5,
        "splitDistance": 1000.0,
        "splitAvgSpeed": 1.9,
        "cumulativeDistanceFromStart": 2000.0,
        "cumulativeTimeFromStart": 1000.5,
        "startPoint": {"latitude": 0.009, "longitude": 0.0, "elevation": 100.0},
        "endPoint": {"latitude": 0.018, "longitude": 0.0, "elevation": 100.0},
    },
]
STORED = {
    "paceBandPk": 501,
    "paceBandSummary": STORED_SUMMARY,
    "paceBandSplits": STORED_SPLITS,
}
CUSTOM = {
    "splitType": "ELEVATION",
    "uphillEffort": 1.5,
    "pacingStrategy": -0.25,
    "manualPaceEdit": True,
}
# Garmin's answer to the update: the plan as it stored it.
ANSWER = {
    "paceBandPk": 501,
    "paceBandSummary": {"name": "Stored Name", "courseId": 111, "goalTime": 800},
}
SHOWN = '{\n  "id": 501,\n  "name": "Stored Name",\n  "course_id": 111,\n'
SHOWN += '  "goal_time_s": 800,\n  "splits": []\n}\n'
NEW_GOAL = ["--goal-time", "0:13:20"]


def edit_client(plan: Any = STORED, course: Any = COURSE) -> FakeClient:
    client = FakeClient(connectapi=plan, get_course=course, put=ANSWER)
    client.client = client
    return client


def custom(**settings: Any) -> dict[str, Any]:
    return {**STORED, "paceBandSummary": {**STORED_SUMMARY, **settings}}


def put_body(client: FakeClient) -> dict[str, Any]:
    [(name, args, kwargs)] = [call for call in client.calls if call[0] == "put"]
    assert (name, args, kwargs["api"]) == ("put", ("connectapi", PLAN_PATH), True)
    body: dict[str, Any] = kwargs["json"]
    return body


def test_pacepro_edit_name_sends_the_stored_plan_back_with_the_new_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = edit_client(custom(**CUSTOM))

    result = run(["pacepro", "edit", "501", "--name", "New Name"], client, capsys)

    assert result == (0, SHOWN, 'garmin: Updated PacePro plan "New Name".\n')
    assert put_body(client) == {
        "paceBandSummary": {
            **SUMMARY,
            **CUSTOM,
            "name": "New Name",
            "goalTime": 1000,
            "goalSpeed": 2.0,
        },
        "paceBandSplits": [
            {
                "splitDistance": 1000.0,
                "splitAvgSpeed": 2.1,
                "cumulativeDistanceFromStart": 1000.0,
                "cumulativeTimeFromStart": 476.19,
                "startPoint": {"latitude": 0.0, "longitude": 0.0, "elevation": 100.0},
                "endPoint": {"latitude": 0.009, "longitude": 0.0, "elevation": 100.0},
            },
            {
                "splitDistance": 1000.0,
                "splitAvgSpeed": 1.9,
                "cumulativeDistanceFromStart": 2000.0,
                "cumulativeTimeFromStart": 1000.5,
                "startPoint": {
                    "latitude": 0.009,
                    "longitude": 0.0,
                    "elevation": 100.0,
                },
                "endPoint": {"latitude": 0.018, "longitude": 0.0, "elevation": 100.0},
            },
        ],
    }
    assert [name for name, *_ in client.calls] == ["connectapi", "put"]


def test_pacepro_edit_goal_recomputes_the_splits(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = edit_client()

    result = run(["pacepro", "edit", "501", *NEW_GOAL], client, capsys)

    assert result == (0, SHOWN, 'garmin: Updated PacePro plan "Old Name".\n')
    body = put_body(client)
    assert body["paceBandSummary"] == {**SUMMARY, "name": "Old Name"}
    assert [
        (
            split["splitDistance"],
            split["splitAvgSpeed"],
            split["cumulativeDistanceFromStart"],
            round(split["cumulativeTimeFromStart"], 6),
            split["startPoint"]["elevation"],
        )
        for split in body["paceBandSplits"]
    ] == [(1000.0, 2.5, 1000.0, 400.0, 100.0), (1000.0, 2.5, 2000.0, 800.0, 100.0)]
    assert [call[:2] for call in client.calls] == [
        ("connectapi", (PLAN_PATH,)),
        ("get_course", (111,)),
        ("put", ("connectapi", PLAN_PATH)),
    ]


def test_pacepro_edit_goal_pace_and_name_together(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = edit_client(course={**COURSE, "distanceMeter": 2050.0})

    argv = ["pacepro", "edit", "501", "--goal-pace", "6:00", "--name", "Race"]
    code, _, err = run(argv, client, capsys)

    assert (code, err) == (0, 'garmin: Updated PacePro plan "Race".\n')
    summary = put_body(client)["paceBandSummary"]
    assert (summary["name"], summary["goalTime"], summary["goalSpeed"]) == (
        "Race",
        738,
        2050.0 / 738,
    )


@pytest.mark.parametrize(
    "settings",
    [
        CUSTOM,
        {"splitType": "ELEVATION"},
        {"uphillEffort": 1.5},
        {"pacingStrategy": -0.25},
        {"manualPaceEdit": True},
    ],
)
def test_pacepro_edit_goal_saves_other_settings_as_a_v1_plan(
    settings: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    client = edit_client(custom(**settings))

    result = run(["pacepro", "edit", "501", *NEW_GOAL], client, capsys)

    assert result == (
        0,
        SHOWN,
        'garmin: Updated PacePro plan "Old Name"; it now has km splits at the '
        "default sliders.\n",
    )
    assert put_body(client)["paceBandSummary"] == {**SUMMARY, "name": "Old Name"}


def test_pacepro_edit_unknown_id_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    client = edit_client(GarminConnectNotFoundError("404"))

    result = run(["pacepro", "edit", "999", "--name", "New Name"], client, capsys)

    assert result == (1, "", f"garmin: No PacePro plan with ID 999. {LIST_IDS}\n")
    assert client.calls == [("connectapi", ("/course-service/pacebands/999",), {})]


def test_pacepro_edit_goal_on_a_course_without_elevation_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    course = {**COURSE, "geoPoints": [point(0.0), point(1000.0, None)]}
    client = edit_client(course=course)

    result = run(["pacepro", "edit", "501", *NEW_GOAL], client, capsys)

    assert result == (
        1,
        "",
        "garmin: Course 111 has no track with elevation, which PacePro needs. Pick "
        "another course from 'garmin course list'.\n",
    )
    assert [name for name, *_ in client.calls] == ["connectapi", "get_course"]


HELP = "Run 'garmin pacepro edit --help'."


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (
            ["pacepro", "edit", "501"],
            "Nothing to change. Give --name, --goal-time or --goal-pace.",
        ),
        (
            ["pacepro", "edit", "501", *NEW_GOAL, "--goal-pace", "6:00"],
            f"Give either --goal-time or --goal-pace, not both. {HELP}",
        ),
        (
            ["pacepro", "edit", "501", "--goal-time", "60:00"],
            "Invalid --goal-time '60:00'. Use H:MM:SS, like 1:05:00.",
        ),
        (
            ["pacepro", "edit", "501", "--goal-pace", "5"],
            "Invalid --goal-pace '5'. Use M:SS per km, like 5:30.",
        ),
        (
            ["pacepro", "edit", "x", "--name", "New Name"],
            f"Invalid PacePro plan ID 'x'. {LIST_IDS}",
        ),
    ],
)
def test_pacepro_edit_invalid_arguments_exit_2(
    argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    client = edit_client()

    assert run(argv, client, capsys) == (2, "", f"garmin: {message}\n")
    assert client.calls == []
