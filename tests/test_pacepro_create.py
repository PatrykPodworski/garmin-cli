import json
import math
from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectNotFoundError

from garmin_cli.cli import main

METERS_PER_DEGREE = 6371000 * math.pi / 180


def point(distance: float, elevation: float | None = 100.0) -> dict[str, Any]:
    return {
        "latitude": distance / METERS_PER_DEGREE,
        "longitude": 0.0,
        "elevation": elevation,
        "distance": distance,
    }


# A made-up flat 2000 m course due north along the prime meridian.
COURSE = {
    "courseId": 111,
    "courseName": "Test Loop",
    "distanceMeter": 2000.0,
    "geoPoints": [point(0.0), point(1000.0), point(2000.0)],
}
CREATE = ["pacepro", "create", "--course", "111", "--goal-time", "0:13:20"]
SUMMARY = {
    "courseId": 111,
    "name": "Test Loop",
    "goalTime": 800,
    "goalSpeed": 2.5,
    "splitType": "DISTANCE_KILOMETER",
    "distanceUnit": None,
    "totalDistance": 2000.0,
    "uphillEffort": 0.0,
    "pacingStrategy": 0.0,
    "manualPaceEdit": False,
    "elevationSegmentationTolerance": 50.0,
    "paceFactor": 2.0,
    "elevationSegmentMinLength": 1700.0,
}
SHOWN = {
    "name": "Test Loop",
    "course_id": 111,
    "split": "km",
    "distance_m": 2000.0,
    "goal_time_s": 800,
    "goal_pace_s_per_km": 400,
    "pacing_strategy": 0.0,
    "uphill_effort": 0.0,
    "splits": [
        {
            "distance_m": 1000.0,
            "pace_s_per_km": 400,
            "elevation_change_m": 0.0,
            "cumulative_distance_m": 1000.0,
            "cumulative_time_s": 400.0,
        },
        {
            "distance_m": 1000.0,
            "pace_s_per_km": 400,
            "elevation_change_m": 0.0,
            "cumulative_distance_m": 2000.0,
            "cumulative_time_s": 800.0,
        },
    ],
}
CREATED = "garmin: Created PacePro plan 501 from course 111.\n"


def split(end: float, time: float) -> dict[str, Any]:
    return {
        "splitDistance": 1000.0,
        "splitAvgSpeed": 2.5,
        "cumulativeDistanceFromStart": end,
        "cumulativeTimeFromStart": time,
        "startPoint": {"elevation": 100.0},
        "endPoint": {"elevation": 100.0},
    }


# Garmin's answer to the create: the posted plan with its new ID.
STORED = {
    "paceBandPk": 501,
    "paceBandSummary": SUMMARY,
    "paceBandSplits": [split(1000.0, 400.0), split(2000.0, 800.0)],
}


def create_client(course: Any = COURSE, answer: Any = STORED) -> FakeClient:
    client = FakeClient(get_course=course, post=answer)
    client.client = client
    return client


def run(
    argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    try:
        code = main(argv, connect=lambda: client)
    except SystemExit as exit:
        code = int(exit.code or 0)
    out = capsys.readouterr()
    return code, out.out, out.err


def posted(client: FakeClient) -> dict[str, Any]:
    [(name, args, kwargs)] = [call for call in client.calls if call[0] == "post"]
    assert (name, args, kwargs["api"]) == (
        "post",
        ("connectapi", "/course-service/pacebands"),
        True,
    )
    body: dict[str, Any] = kwargs["json"]
    return body


def test_pacepro_create_posts_the_plan_and_prints_the_stored_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = create_client()

    code, out, err = run(CREATE, client, capsys)

    assert (code, err) == (0, CREATED)
    assert json.loads(out) == {"id": 501, **SHOWN}
    body = posted(client)
    assert body["paceBandSummary"] == SUMMARY
    assert [
        (
            split["splitDistance"],
            split["splitAvgSpeed"],
            split["cumulativeDistanceFromStart"],
            round(split["cumulativeTimeFromStart"], 6),
            split["startPoint"]["elevation"],
            split["endPoint"]["elevation"],
        )
        for split in body["paceBandSplits"]
    ] == [
        (1000.0, 2.5, 1000.0, 400.0, 100.0, 100.0),
        (1000.0, 2.5, 2000.0, 800.0, 100.0, 100.0),
    ]
    assert client.calls[0] == ("get_course", (111,), {})


def test_pacepro_create_prints_what_garmin_stored(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = create_client(
        answer={
            "paceBandPk": 777,
            "paceBandSummary": {"name": "Stored Name", "courseId": 111},
        }
    )

    code, out, err = run(CREATE, client, capsys)

    assert (code, json.loads(out), err) == (
        0,
        {"id": 777, "name": "Stored Name", "course_id": 111, "splits": []},
        "garmin: Created PacePro plan 777 from course 111.\n",
    )


def test_pacepro_create_dry_run_prints_the_plan_and_saves_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = create_client()

    code, out, err = run([*CREATE, "--dry-run"], client, capsys)

    assert (code, json.loads(out), err) == (
        0,
        SHOWN,
        "garmin: Would create a PacePro plan from course 111; nothing saved.\n",
    )
    assert [name for name, *_ in client.calls] == ["get_course"]


def test_pacepro_create_takes_name_split_and_sliders(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = create_client()

    code, _, _ = run(
        [
            *CREATE,
            "--name",
            "Race Plan",
            "--split",
            "elevation",
            "--pacing-strategy",
            "-0.5",
            "--uphill-effort",
            "1.5",
        ],
        client,
        capsys,
    )

    assert code == 0
    summary = posted(client)["paceBandSummary"]
    assert {
        key: summary[key]
        for key in ("name", "splitType", "pacingStrategy", "uphillEffort")
    } == {
        "name": "Race Plan",
        "splitType": "ELEVATION",
        "pacingStrategy": -0.5,
        "uphillEffort": 1.5,
    }
    assert len(posted(client)["paceBandSplits"]) == 1


def test_pacepro_create_goal_pace_sets_the_goal_time_from_the_course_distance(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = create_client({**COURSE, "distanceMeter": 2050.0})

    argv = ["pacepro", "create", "--course", "111", "--goal-pace", "6:00"]
    code, _, _ = run(argv, client, capsys)

    assert code == 0
    summary = posted(client)["paceBandSummary"]
    assert (summary["goalTime"], summary["goalSpeed"]) == (738, 2050.0 / 738)


def test_pacepro_create_unknown_course_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = create_client(GarminConnectNotFoundError("404"))

    assert run(CREATE, client, capsys) == (
        1,
        "",
        "garmin: No course with ID 111. Run 'garmin course list' to list IDs.\n",
    )


@pytest.mark.parametrize(
    "points",
    [
        [],
        [point(0.0)],
        [point(0.0), point(1000.0, None), point(2000.0)],
    ],
)
def test_pacepro_create_course_without_an_elevation_track_exits_1(
    points: list[dict[str, Any]], capsys: pytest.CaptureFixture[str]
) -> None:
    client = create_client({**COURSE, "geoPoints": points})

    assert run(CREATE, client, capsys) == (
        1,
        "",
        "garmin: Course 111 has no track with elevation, which PacePro needs. Pick "
        "another course from 'garmin course list'.\n",
    )
    assert [name for name, *_ in client.calls] == ["get_course"]


def test_pacepro_create_accepts_a_track_of_two_points(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = create_client({**COURSE, "geoPoints": [point(0.0), point(2000.0)]})

    code, out, _ = run([*CREATE, "--dry-run"], client, capsys)

    assert (code, json.loads(out)["splits"]) == (0, SHOWN["splits"])


def test_pacepro_create_course_without_geo_points_key_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    course = {key: value for key, value in COURSE.items() if key != "geoPoints"}

    code, _, err = run(CREATE, create_client(course), capsys)

    assert (code, err.startswith("garmin: Course 111 has no track")) == (1, True)


HELP = "Run 'garmin pacepro create --help'."


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (
            ["pacepro", "create", "--course", "111"],
            f"One of the arguments --goal-time --goal-pace is required. {HELP}",
        ),
        (
            [*CREATE, "--goal-pace", "6:00"],
            f"Give either --goal-time or --goal-pace, not both. {HELP}",
        ),
        (
            ["pacepro", "create", "--goal-time", "1:00:00"],
            f"Missing --course for 'garmin pacepro create'. {HELP}",
        ),
        (
            ["pacepro", "create", "--course", "x", "--goal-time", "1:00:00"],
            "Invalid course ID 'x'. Run 'garmin course list' to list IDs.",
        ),
        *(
            (
                ["pacepro", "create", "--course", "111", "--goal-time", value],
                f"Invalid --goal-time '{value}'. Use H:MM:SS, like 1:05:00.",
            )
            for value in ("60:00", "1:60:00", "1:00:60", "0:00:00", "a:00:00")
        ),
        *(
            (
                ["pacepro", "create", "--course", "111", "--goal-pace", value],
                f"Invalid --goal-pace '{value}'. Use M:SS per km, like 5:30.",
            )
            for value in ("5", "5:60", "0:00", "1:05:00", "x:30")
        ),
        *(
            (
                [*CREATE, f"{option}={value}"],
                f"Invalid {option} '{value}'. Use a number, like -0.5.",
            )
            for option in ("--pacing-strategy", "--uphill-effort")
            for value in ("nan", "inf", "-inf", "x")
        ),
        (
            [*CREATE, "--split", "mile"],
            "Argument --split: invalid choice: 'mile' (choose from km, elevation). "
            f"{HELP}",
        ),
    ],
)
def test_pacepro_create_invalid_arguments_exit_2(
    argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    client = create_client()

    assert run(argv, client, capsys) == (2, "", f"garmin: {message}\n")
    assert client.calls == []


@pytest.mark.parametrize(
    ("value", "seconds"), [("1:00:00", 3600), ("0:00:01", 1), ("12:34:56", 45296)]
)
def test_pacepro_create_reads_goal_time(
    value: str, seconds: int, capsys: pytest.CaptureFixture[str]
) -> None:
    client = create_client()

    argv = ["pacepro", "create", "--course", "111", "--goal-time", value, "--dry-run"]
    _, out, _ = run(argv, client, capsys)

    assert json.loads(out)["goal_time_s"] == seconds


@pytest.mark.parametrize(("value", "seconds"), [("5:30", 330), ("0:01", 1)])
def test_pacepro_create_reads_goal_pace(
    value: str, seconds: int, capsys: pytest.CaptureFixture[str]
) -> None:
    client = create_client({**COURSE, "distanceMeter": 1000.0})

    argv = ["pacepro", "create", "--course", "111", "--goal-pace", value, "--dry-run"]
    _, out, _ = run(argv, client, capsys)

    assert json.loads(out)["goal_time_s"] == seconds
