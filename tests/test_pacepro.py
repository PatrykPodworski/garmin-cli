import json
from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectNotFoundError

from garmin_cli.cli import main

# Made-up values in the shape `get_pace_bands()` returns.
PLAN = {
    "paceBandPk": 501,
    "paceBandSummary": {
        "paceBandPk": 501,
        "name": "Test Hills 10k",
        "courseId": 111,
        "splitType": "ELEVATION",
        "totalDistance": 10000.0,
        "goalTime": 4000,
        "goalSpeed": 2.5,
        "pacingStrategy": -0.25,
        "uphillEffort": 1.5,
    },
    "paceBandSplits": [
        {
            "splitDistance": 4000.0,
            "splitAvgSpeed": 2.4,
            "cumulativeDistanceFromStart": 4000.0,
            "cumulativeTimeFromStart": 1666.666,
            "startPoint": {"latitude": 10.0, "longitude": 20.0, "elevation": 100.0},
            "endPoint": {"latitude": 10.1, "longitude": 20.1, "elevation": 130.5},
        },
        {
            "splitDistance": 6000.0,
            "splitAvgSpeed": 2.6,
            "cumulativeDistanceFromStart": 10000.0,
            "cumulativeTimeFromStart": 4000.0,
            "startPoint": {"latitude": 10.1, "longitude": 20.1, "elevation": 130.5},
            "endPoint": {"latitude": 10.2, "longitude": 20.2, "elevation": 90.0},
        },
    ],
}
SHOWN = {
    "id": 501,
    "name": "Test Hills 10k",
    "course_id": 111,
    "split": "elevation",
    "distance_m": 10000.0,
    "goal_time_s": 4000,
    "goal_pace_s_per_km": 400,
    "pacing_strategy": -0.25,
    "uphill_effort": 1.5,
    "splits": 2,
}
FLAT = {
    "paceBandPk": 502,
    "paceBandSummary": {"name": "Test Flat", "splitType": "DISTANCE_KILOMETER"},
    "paceBandSplits": [],
}
LIST_IDS = "Run 'garmin pacepro list' to list IDs."
PLAN_PATH = "/course-service/pacebands/501"


def run(
    argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    try:
        code = main(argv, connect=lambda: client)
    except SystemExit as exit:
        code = int(exit.code or 0)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_pacepro_list_summarizes_each_plan(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_pace_bands=[PLAN, FLAT])

    code, out, err = run(["pacepro", "list"], client, capsys)

    assert (code, err) == (0, "")
    assert json.loads(out) == [
        SHOWN,
        {"id": 502, "name": "Test Flat", "split": "km", "splits": 0},
    ]
    assert client.calls == [("get_pace_bands", (), {})]


def test_pacepro_list_passes_an_unknown_split_type_through(
    capsys: pytest.CaptureFixture[str],
) -> None:
    plan = {"paceBandPk": 503, "paceBandSummary": {"splitType": "SOMETHING_NEW"}}

    code, out, _ = run(["pacepro", "list"], FakeClient(get_pace_bands=[plan]), capsys)

    assert code == 0
    assert json.loads(out) == [{"id": 503, "split": "SOMETHING_NEW", "splits": 0}]


def test_pacepro_list_leaves_out_missing_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    plan = {"paceBandPk": 504, "paceBandSummary": None, "paceBandSplits": None}
    zero = {"paceBandPk": 505, "paceBandSummary": {"goalSpeed": 0, "courseId": None}}
    client = FakeClient(get_pace_bands=[plan, zero])

    code, out, _ = run(["pacepro", "list"], client, capsys)

    assert code == 0
    assert json.loads(out) == [{"id": 504, "splits": 0}, {"id": 505, "splits": 0}]


def test_pacepro_list_limit_keeps_the_first_plans(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get_pace_bands=[PLAN, FLAT])

    code, out, _ = run(["pacepro", "list", "--limit", "1"], client, capsys)

    assert code == 0
    assert json.loads(out) == [SHOWN]


def test_pacepro_list_default_limit_is_20(capsys: pytest.CaptureFixture[str]) -> None:
    many = [{"paceBandPk": number} for number in range(1, 25)]

    code, out, _ = run(["pacepro", "list"], FakeClient(get_pace_bands=many), capsys)

    assert code == 0
    assert [plan["id"] for plan in json.loads(out)] == list(range(1, 21))


def test_pacepro_list_empty_prints_empty_list(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get_pace_bands=[])

    assert run(["pacepro", "list"], client, capsys) == (0, "[]\n", "")


def test_pacepro_list_raw_prints_garmin_response(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get_pace_bands=[PLAN, FLAT])

    code, out, _ = run(["pacepro", "list", "--raw", "--limit", "1"], client, capsys)

    assert code == 0
    assert json.loads(out) == [PLAN]


@pytest.mark.parametrize("value", ["x", "0", "-1"])
def test_pacepro_list_invalid_limit_exits_2(
    capsys: pytest.CaptureFixture[str], value: str
) -> None:
    client = FakeClient()

    assert run(["pacepro", "list", "--limit", value], client, capsys) == (
        2,
        "",
        f"garmin: Invalid --limit '{value}'. Use a whole number of 1 or more.\n",
    )
    assert client.calls == []


def test_pacepro_view_shows_the_plan_and_its_splits(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(connectapi=PLAN)

    code, out, err = run(["pacepro", "view", "501"], client, capsys)

    assert (code, err) == (0, "")
    assert json.loads(out) == {
        **SHOWN,
        "splits": [
            {
                "distance_m": 4000.0,
                "pace_s_per_km": 417,
                "elevation_change_m": 30.5,
                "cumulative_distance_m": 4000.0,
                "cumulative_time_s": 1666.67,
            },
            {
                "distance_m": 6000.0,
                "pace_s_per_km": 385,
                "elevation_change_m": -40.5,
                "cumulative_distance_m": 10000.0,
                "cumulative_time_s": 4000.0,
            },
        ],
    }
    assert client.calls == [("connectapi", (PLAN_PATH,), {})]


def test_pacepro_view_leaves_out_missing_split_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    splits = [
        {
            "splitDistance": 1000.0,
            "splitAvgSpeed": 0.5,
            "startPoint": {"elevation": 5.0},
        },
        {"endPoint": {"elevation": 5.0}, "splitAvgSpeed": 0},
        {"startPoint": None, "endPoint": None},
    ]
    plan = {"paceBandPk": 506, "paceBandSplits": splits}

    code, out, _ = run(["pacepro", "view", "506"], FakeClient(connectapi=plan), capsys)

    assert code == 0
    assert json.loads(out) == {
        "id": 506,
        "splits": [{"distance_m": 1000.0, "pace_s_per_km": 2000}, {}, {}],
    }


def test_pacepro_view_plan_without_splits_shows_empty_list(
    capsys: pytest.CaptureFixture[str],
) -> None:
    plan = {"paceBandPk": 507}

    code, out, _ = run(["pacepro", "view", "507"], FakeClient(connectapi=plan), capsys)

    assert (code, json.loads(out)) == (0, {"id": 507, "splits": []})


def test_pacepro_view_raw_prints_garmin_response(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(connectapi=PLAN)

    code, out, _ = run(["pacepro", "view", "501", "--raw"], client, capsys)

    assert code == 0
    assert json.loads(out) == PLAN


def test_pacepro_view_unknown_id_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(connectapi=GarminConnectNotFoundError("404"))

    assert run(["pacepro", "view", "999"], client, capsys) == (
        1,
        "",
        f"garmin: No PacePro plan with ID 999. {LIST_IDS}\n",
    )
    assert client.calls == [("connectapi", ("/course-service/pacebands/999",), {})]


@pytest.mark.parametrize("value", ["x", "0", "-5"])
def test_pacepro_view_invalid_id_exits_2(
    capsys: pytest.CaptureFixture[str], value: str
) -> None:
    client = FakeClient()

    assert run(["pacepro", "view", "--", value], client, capsys) == (
        2,
        "",
        f"garmin: Invalid PacePro plan ID '{value}'. {LIST_IDS}\n",
    )
    assert client.calls == []


def test_pacepro_view_accepts_id_1(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(connectapi={"paceBandPk": 1})

    assert run(["pacepro", "view", "1", "--raw"], client, capsys)[0] == 0
    assert client.calls == [("connectapi", ("/course-service/pacebands/1",), {})]


def test_pacepro_view_missing_id_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(["pacepro", "view"], FakeClient(), capsys) == (
        2,
        "",
        "garmin: Missing pacepro ID. Run 'garmin pacepro list' to list IDs, then "
        "'garmin pacepro view <id>'.\n",
    )


def test_pacepro_without_command_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(["pacepro"], FakeClient(), capsys) == (
        2,
        "",
        "garmin: No command given. Run 'garmin pacepro <command>', one of: list, "
        "view, delete, send.\n",
    )
