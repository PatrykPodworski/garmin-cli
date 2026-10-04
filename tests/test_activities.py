import json
from typing import Any

import pytest
from conftest import FakeClient, run_json

RUN = {
    "activityId": 101,
    "activityName": "Morning Run",
    "startTimeLocal": "2026-07-05 07:00:00",
    "activityType": {"typeKey": "trail_running"},
    "duration": 1800.0,
    "distance": 6000.0,
    "averageSpeed": 4.0,
    "averageHR": 150.0,
    "maxHR": 175.0,
    "elevationGain": 80.0,
    "calories": 400.0,
    "aerobicTrainingEffect": 3.1,
    "anaerobicTrainingEffect": 1.2,
    "vO2MaxValue": 50.0,
    "polyline": "fake-polyline",
    "startLatitude": 1.0,
}
RIDE = {
    "activityId": 102,
    "startTimeLocal": "2026-07-04 18:00:00",
    "activityType": {"typeKey": "cycling"},
    "averageSpeed": 7.03,
}


def test_activities_compact_list(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_activities=[RUN, RIDE])

    result = run_json(["activities"], client, capsys)

    assert client.calls == [("get_activities", (0, 20), {"activitytype": None})]
    assert result == [
        {
            "id": 101,
            "date": "2026-07-05 07:00:00",
            "type": "trail_running",
            "name": "Morning Run",
            "duration_s": 1800.0,
            "distance_m": 6000.0,
            "avg_hr": 150.0,
            "max_hr": 175.0,
            "avg_pace_s_per_km": 250,
            "elevation_gain_m": 80.0,
            "calories": 400.0,
            "aerobic_te": 3.1,
            "anaerobic_te": 1.2,
            "vo2max": 50.0,
        },
        {
            "id": 102,
            "date": "2026-07-04 18:00:00",
            "type": "cycling",
            "avg_speed_kmh": 25.3,
        },
    ]


def test_activities_filters(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_activities_by_date=[RUN, RIDE])

    result = run_json(
        [
            "activities",
            "--from",
            "2026-07-01",
            "--to",
            "2026-07-05",
            "--type",
            "running",
            "--limit",
            "1",
        ],
        client,
        capsys,
    )

    assert client.calls == [
        ("get_activities_by_date", ("2026-07-01", "2026-07-05", "running"), {})
    ]
    assert [a["id"] for a in result] == [101]


def test_activities_recent_by_type(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_activities=[])

    assert run_json(["activities", "--type", "cycling"], client, capsys) == []
    assert client.calls == [("get_activities", (0, 20), {"activitytype": "cycling"})]


def test_activities_to_without_from(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_activities_by_date=[RUN])

    run_json(["activities", "--to", "2026-07-05"], client, capsys)

    assert client.calls == [
        ("get_activities_by_date", ("2000-01-01", "2026-07-05", None), {})
    ]


def test_activities_from_without_to(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_activities_by_date=[RUN])

    run_json(["activities", "--from", "2026-07-01"], client, capsys)

    assert client.calls == [("get_activities_by_date", ("2026-07-01", None, None), {})]


def test_activities_without_type(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_activities=[{"activityId": 103}])

    assert run_json(["activities"], client, capsys) == [{"id": 103}]


def test_activities_raw(capsys: pytest.CaptureFixture[str]) -> None:
    result = run_json(["activities", "--raw"], FakeClient(get_activities=[RUN]), capsys)

    assert result == [RUN]


SPLITS = {
    "activityId": 101,
    "lapDTOs": [
        {
            "distance": 1000.0,
            "duration": 300.0,
            "averageSpeed": 3.34,
            "averageHR": 140.0,
            "maxHR": 150.0,
            "startLatitude": 1.0,
            "startLongitude": 2.0,
        }
    ],
}
HR_ZONES = [{"zoneNumber": 1, "secsInZone": 120.0, "zoneLowBoundary": 100}]


DETAIL = {
    "activityId": 101,
    "activityName": "Morning Run",
    "activityTypeDTO": {"typeKey": "running"},
    "summaryDTO": {
        "startTimeLocal": "2026-07-05T07:00:00.0",
        "duration": 1800.0,
        "averageSpeed": 4.0,
        "trainingEffect": 3.1,
    },
    "geoPolylineDTO": {"polyline": [{"lat": 1.0, "lon": 2.0}]},
}


def activity_client(
    summary: dict[str, Any] = DETAIL,
    splits: dict[str, Any] = SPLITS,
    zones: list[dict[str, Any]] = HR_ZONES,
) -> FakeClient:
    return FakeClient(
        get_activity=summary,
        get_activity_splits=splits,
        get_activity_hr_in_timezones=zones,
    )


def test_activity_detail(capsys: pytest.CaptureFixture[str]) -> None:
    client = activity_client()

    result = run_json(["activity", "101"], client, capsys)

    assert client.calls == [
        ("get_activity", ("101",), {}),
        ("get_activity_splits", ("101",), {}),
        ("get_activity_hr_in_timezones", ("101",), {}),
    ]
    assert result == {
        "id": 101,
        "date": "2026-07-05T07:00:00.0",
        "type": "running",
        "name": "Morning Run",
        "duration_s": 1800.0,
        "avg_pace_s_per_km": 250,
        "aerobic_te": 3.1,
        "laps": [
            {
                "duration_s": 300.0,
                "distance_m": 1000.0,
                "avg_hr": 140.0,
                "max_hr": 150.0,
                "avg_pace_s_per_km": 299,
            }
        ],
        "hr_zones": [{"zone": 1, "seconds": 120.0, "low_bpm": 100}],
    }
    assert not {"polyline", "geoPolylineDTO", "startLatitude"} & set(
        json.dumps(result).replace('"', " ").split()
    )


def test_activity_not_synced(capsys: pytest.CaptureFixture[str]) -> None:
    client = activity_client({"activityId": 101}, {}, [])

    result = run_json(["activity", "101"], client, capsys)

    assert result == {"id": 101, "laps": [], "hr_zones": []}


def test_activity_raw(capsys: pytest.CaptureFixture[str]) -> None:
    client = activity_client()

    result = run_json(["activity", "101", "--raw"], client, capsys)

    assert result["summary"] == DETAIL
    assert result["splits"]["lapDTOs"][0]["startLatitude"] == 1.0
    assert result["hr_zones"][0]["zoneNumber"] == 1
