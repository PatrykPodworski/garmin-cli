import json
from datetime import date
from typing import Any

import pytest
from conftest import FakeClient

from garmin_cli.cli import main


def run_health(
    client: FakeClient, capsys: pytest.CaptureFixture[str], *argv: str
) -> Any:
    assert main(list(argv), connect=lambda: client) == 0
    return json.loads(capsys.readouterr().out)


WEIGH_INS = {
    "dailyWeightSummaries": [
        {
            "summaryDate": "2026-07-05",
            "allWeightMetrics": [
                {
                    "calendarDate": "2026-07-05",
                    # Local wall-clock time encoded as epoch ms.
                    "date": 1783236900000,
                    "weight": 70500.0,
                    "bodyFat": 18.5,
                    "muscleMass": 31250.0,
                    "bodyWater": 55.2,
                },
                {
                    "calendarDate": "2026-07-05",
                    "date": 1783275600000,
                    "weight": 71000.0,
                    "bodyFat": None,
                },
            ],
        }
    ]
}


def test_weight_records_per_weigh_in(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_weigh_ins=WEIGH_INS)

    records = run_health(
        client, capsys, "weight", "--from", "2026-07-01", "--to", "2026-07-05"
    )

    assert client.calls == [("get_weigh_ins", ("2026-07-01", "2026-07-05"), {})]
    assert records == [
        {
            "date": "2026-07-05",
            "time": "07:35:00",
            "weight_kg": 70.5,
            "body_fat_pct": 18.5,
            "muscle_mass_kg": 31.25,
            "body_water_pct": 55.2,
        },
        {
            "date": "2026-07-05",
            "time": "18:20:00",
            "weight_kg": 71.0,
            "body_fat_pct": None,
            "muscle_mass_kg": None,
            "body_water_pct": None,
        },
    ]


def test_weight_empty_range(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_weigh_ins={"dailyWeightSummaries": []})

    assert run_health(client, capsys, "weight", "--from", "2026-07-01") == []
    assert client.calls == [
        ("get_weigh_ins", ("2026-07-01", date.today().isoformat()), {})
    ]


@pytest.mark.parametrize(
    ("command", "method", "response"),
    [
        ("weight", "get_weigh_ins", {}),
        ("weight", "get_weigh_ins", {"dailyWeightSummaries": [{}]}),
        ("bp", "get_blood_pressure", {}),
        ("bp", "get_blood_pressure", {"measurementSummaries": [{}]}),
    ],
)
def test_missing_lists_are_empty(
    command: str,
    method: str,
    response: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_health(FakeClient(**{method: response}), capsys, command) == []


BLOOD_PRESSURE = {
    "measurementSummaries": [
        {
            "startDate": "2026-07-05",
            "measurements": [
                {
                    "measurementTimestampLocal": "2026-07-05T08:15:00.0",
                    "systolic": 118,
                    "diastolic": 76,
                    "pulse": 62,
                    "notes": "after coffee",
                },
                {
                    "measurementTimestampLocal": "2026-07-05T21:40:30.0",
                    "systolic": 121,
                    "diastolic": 79,
                },
            ],
        }
    ]
}


def test_bp_records_per_reading(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_blood_pressure=BLOOD_PRESSURE)

    records = run_health(
        client, capsys, "bp", "--from", "2026-07-01", "--to", "2026-07-05"
    )

    assert client.calls == [("get_blood_pressure", ("2026-07-01", "2026-07-05"), {})]
    assert records == [
        {
            "date": "2026-07-05",
            "time": "08:15:00",
            "systolic": 118,
            "diastolic": 76,
            "pulse": 62,
            "notes": "after coffee",
        },
        {
            "date": "2026-07-05",
            "time": "21:40:30",
            "systolic": 121,
            "diastolic": 79,
            "pulse": None,
            "notes": None,
        },
    ]


def test_bp_empty_range(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_blood_pressure={"measurementSummaries": []})

    assert run_health(client, capsys, "bp") == []
    today = date.today().isoformat()
    assert client.calls == [("get_blood_pressure", (today, today), {})]


@pytest.mark.parametrize(
    ("command", "method", "response"),
    [
        ("weight", "get_weigh_ins", WEIGH_INS),
        ("bp", "get_blood_pressure", BLOOD_PRESSURE),
    ],
)
def test_raw_prints_full_response(
    command: str, method: str, response: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(**{method: response})

    assert run_health(client, capsys, command, "--raw") == response
