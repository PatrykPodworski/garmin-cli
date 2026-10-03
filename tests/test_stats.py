import json
from typing import Any

import pytest
from conftest import FakeClient

from garmin_cli.cli import main

SYNCED_DAY = {
    "calendarDate": "2026-07-05",
    "totalKilocalories": 2400.0,
    "activeKilocalories": 600.0,
    "bmrKilocalories": 1800.0,
    "restingHeartRate": 55,
    "bodyBatteryHighestValue": 90,
    "bodyBatteryLowestValue": 20,
    "averageStressLevel": 30,
    "totalSteps": 1000,
}


def test_stats_prints_summary(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(get_stats=SYNCED_DAY)

    code = main(["stats", "2026-07-05"], connect=lambda: client)

    assert code == 0
    assert client.calls == [("get_stats", ("2026-07-05",), {})]
    out = capsys.readouterr()
    assert json.loads(out.out) == {
        "date": "2026-07-05",
        "total_kcal": 2400.0,
        "active_kcal": 600.0,
        "bmr_kcal": 1800.0,
        "resting_hr": 55,
        "body_battery_high": 90,
        "body_battery_low": 20,
        "avg_stress": 30,
    }
    assert out.err == ""


def test_stats_missing_optional_fields_are_null(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get_stats={"totalKilocalories": 2400.0})

    assert main(["stats", "2026-07-05"], connect=lambda: client) == 0
    assert json.loads(capsys.readouterr().out) == {
        "date": "2026-07-05",
        "total_kcal": 2400.0,
        "active_kcal": None,
        "bmr_kcal": None,
        "resting_hr": None,
        "body_battery_high": None,
        "body_battery_low": None,
        "avg_stress": None,
    }


@pytest.mark.parametrize(
    "stats", [{"calendarDate": "2026-07-05"}, {"totalKilocalories": None}]
)
def test_stats_not_synced_exits_1(
    stats: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["stats", "2026-07-05"], connect=lambda: FakeClient(get_stats=stats))

    assert code == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == "garmin: 2026-07-05 is not synced (no totalKilocalories)\n"


def test_stats_raw_prints_full_response(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        ["stats", "--raw", "2026-07-05"],
        connect=lambda: FakeClient(get_stats=SYNCED_DAY),
    )

    assert code == 0
    assert json.loads(capsys.readouterr().out) == SYNCED_DAY
