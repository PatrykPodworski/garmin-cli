from typing import Any

import pytest
from conftest import FakeClient, run_json

from garmin_cli.cli import main

DAY = "2026-07-05"

MORNING = {
    "calendarDate": DAY,
    "timestamp": "2026-07-05T05:00:00.0",
    "score": 40,
    "recoveryTime": 900,
}
READINESS = {
    "calendarDate": DAY,
    "timestamp": "2026-07-05T09:30:00.0",
    "score": 62,
    "level": "MODERATE",
    "feedbackShort": "RECOVERING",
    "sleepScoreFactorPercent": 80,
    "sleepScoreFactorFeedback": "GOOD",
    "recoveryTime": 750,
    "recoveryTimeFactorPercent": 40,
    "recoveryTimeFactorFeedback": "MODERATE",
    "hrvFactorPercent": 70,
    "hrvFactorFeedback": "GOOD",
    "acwrFactorPercent": 90,
    "acwrFactorFeedback": "VERY_GOOD",
    "sleepHistoryFactorPercent": 60,
    "sleepHistoryFactorFeedback": "MODERATE",
    "stressHistoryFactorPercent": 85,
    "stressHistoryFactorFeedback": "GOOD",
}
STATUS = {
    "calendarDate": DAY,
    "sinceDate": "2026-07-01",
    "primaryTrainingDevice": True,
    "trainingStatusFeedbackPhrase": "PRODUCTIVE_3",
    "trainingPaused": False,
    "acuteTrainingLoadDTO": {
        "dailyTrainingLoadAcute": 400,
        "dailyTrainingLoadChronic": 380,
        "minTrainingLoadChronic": 300.0,
        "maxTrainingLoadChronic": 500.0,
        "dailyAcuteChronicWorkloadRatio": 1.0526315,
        "acwrStatus": "OPTIMAL",
    },
}
BALANCE = {
    "calendarDate": DAY,
    "primaryTrainingDevice": True,
    "trainingBalanceFeedbackPhrase": "ANAEROBIC_SHORTAGE",
    "monthlyLoadAerobicLow": 500.0,
    "monthlyLoadAerobicLowTargetMin": 400,
    "monthlyLoadAerobicLowTargetMax": 800,
    "monthlyLoadAerobicHigh": 600.0,
    "monthlyLoadAerobicHighTargetMin": 300,
    "monthlyLoadAerobicHighTargetMax": 700,
    "monthlyLoadAnaerobic": 50.0,
    "monthlyLoadAnaerobicTargetMin": 100,
    "monthlyLoadAnaerobicTargetMax": 300,
}
HRV = {
    "hrvSummary": {
        "calendarDate": DAY,
        "weeklyAvg": 52,
        "lastNightAvg": 50,
        "baseline": {"balancedLow": 45, "balancedUpper": 60},
        "status": "BALANCED",
    }
}

FACTORS = {
    "sleep": {"pct": 80, "feedback": "GOOD"},
    "recovery_time": {"pct": 40, "feedback": "MODERATE"},
    "hrv": {"pct": 70, "feedback": "GOOD"},
    "acute_load": {"pct": 90, "feedback": "VERY_GOOD"},
    "sleep_history": {"pct": 60, "feedback": "MODERATE"},
    "stress_history": {"pct": 85, "feedback": "GOOD"},
}
TRAINING_STATUS = {
    "status": "PRODUCTIVE",
    "since": "2026-07-01",
    "paused": False,
    "acute_load": 400,
    "chronic_load": 380,
    "chronic_load_min": 300.0,
    "chronic_load_max": 500.0,
    "acwr": 1.05,
    "acwr_status": "OPTIMAL",
    "load_focus": "ANAEROBIC_SHORTAGE",
    "monthly_load": {
        "aerobic_low": {"load": 500.0, "target_min": 400, "target_max": 800},
        "aerobic_high": {"load": 600.0, "target_min": 300, "target_max": 700},
        "anaerobic": {"load": 50.0, "target_min": 100, "target_max": 300},
    },
}
NULL_TRAINING_STATUS = {
    **{key: None for key in TRAINING_STATUS},
    "monthly_load": {
        name: {"load": None, "target_min": None, "target_max": None}
        for name in ("aerobic_low", "aerobic_high", "anaerobic")
    },
}
HRV_STATUS = {
    "status": "BALANCED",
    "last_night_ms": 50,
    "weekly_avg_ms": 52,
    "baseline_low_ms": 45,
    "baseline_high_ms": 60,
}


def training_status(
    status: dict[str, Any] | None = None, balance: dict[str, Any] | None = None
) -> dict[str, Any]:
    """`get_training_status` with each entry under a made-up device ID."""
    return {
        "mostRecentTrainingStatus": {
            "latestTrainingStatusData": {"111": status} if status else {}
        },
        "mostRecentTrainingLoadBalance": {
            "metricsTrainingLoadBalanceDTOMap": {"111": balance} if balance else {}
        },
    }


def client(
    readiness: Any = (),
    status: Any = None,
    hrv: Any = None,
) -> FakeClient:
    return FakeClient(
        get_training_readiness=list(readiness),
        get_training_status=training_status() if status is None else status,
        get_hrv_data=hrv,
    )


def test_recovery_prints_summary(capsys: pytest.CaptureFixture[str]) -> None:
    fake = client([MORNING, READINESS], training_status(STATUS, BALANCE), HRV)

    assert run_json(["recovery", "view", DAY], fake, capsys) == {
        "date": DAY,
        "recovery_time_h": 12.5,
        "readiness": {
            "score": 62,
            "level": "MODERATE",
            "feedback": "RECOVERING",
            "factors": FACTORS,
        },
        "training_status": TRAINING_STATUS,
        "hrv": HRV_STATUS,
    }
    assert fake.calls == [
        ("get_training_readiness", (DAY,), {}),
        ("get_training_status", (DAY,), {}),
        ("get_hrv_data", (DAY,), {}),
    ]


def test_recovery_without_readiness_is_null(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = client([], training_status(STATUS, BALANCE), HRV)

    result = run_json(["recovery", "view", DAY], fake, capsys)

    assert result["recovery_time_h"] is None
    assert result["readiness"] is None
    assert result["training_status"] == TRAINING_STATUS


def test_recovery_reached_zero_is_0_hours(capsys: pytest.CaptureFixture[str]) -> None:
    snapshot = {**READINESS, "recoveryTimeChangePhrase": "REACHED_ZERO"}

    result = run_json(["recovery", "view", DAY], client([snapshot]), capsys)

    assert result["recovery_time_h"] == 0


def test_recovery_missing_fields_are_null(capsys: pytest.CaptureFixture[str]) -> None:
    fake = client(
        [{"score": 50}],
        training_status({"calendarDate": DAY}, {"calendarDate": DAY}),
        {"hrvSummary": {"calendarDate": DAY}},
    )

    assert run_json(["recovery", "view", DAY], fake, capsys) == {
        "date": DAY,
        "recovery_time_h": None,
        "readiness": {
            "score": 50,
            "level": None,
            "feedback": None,
            "factors": {name: {"pct": None, "feedback": None} for name in FACTORS},
        },
        "training_status": NULL_TRAINING_STATUS,
        "hrv": {key: None for key in HRV_STATUS},
    }


def test_recovery_training_status_without_load_balance(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = client(status=training_status(STATUS))

    result = run_json(["recovery", "view", DAY], fake, capsys)

    assert result["training_status"]["status"] == "PRODUCTIVE"
    assert result["training_status"]["load_focus"] is None


def test_recovery_load_balance_without_training_status(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = client(status=training_status(balance=BALANCE))

    result = run_json(["recovery", "view", DAY], fake, capsys)

    assert result["training_status"]["status"] is None
    assert result["training_status"]["load_focus"] == "ANAEROBIC_SHORTAGE"


def test_recovery_uses_primary_training_device(
    capsys: pytest.CaptureFixture[str],
) -> None:
    other = {
        **STATUS,
        "primaryTrainingDevice": False,
        "trainingStatusFeedbackPhrase": "STRAINED_1",
    }
    data = training_status()
    data["mostRecentTrainingStatus"]["latestTrainingStatusData"] = {
        "111": other,
        "222": STATUS,
    }

    result = run_json(["recovery", "view", DAY], client(status=data), capsys)

    assert result["training_status"]["status"] == "PRODUCTIVE"


def test_recovery_without_primary_device_uses_first(
    capsys: pytest.CaptureFixture[str],
) -> None:
    first = {**STATUS, "primaryTrainingDevice": False}
    second = {**first, "trainingStatusFeedbackPhrase": "STRAINED_1"}
    data = training_status()
    data["mostRecentTrainingStatus"]["latestTrainingStatusData"] = {
        "111": first,
        "222": second,
    }

    result = run_json(["recovery", "view", DAY], client(status=data), capsys)

    assert result["training_status"]["status"] == "PRODUCTIVE"


def test_recovery_ignores_data_for_another_day(
    capsys: pytest.CaptureFixture[str],
) -> None:
    earlier = "2026-07-04"
    fake = client(
        [READINESS],
        training_status(
            {**STATUS, "calendarDate": earlier}, {**BALANCE, "calendarDate": earlier}
        ),
        {"hrvSummary": {**HRV["hrvSummary"], "calendarDate": earlier}},
    )

    result = run_json(["recovery", "view", DAY], fake, capsys)

    assert result["training_status"] is None
    assert result["hrv"] is None


@pytest.mark.parametrize(
    ("readiness", "status", "hrv"),
    [
        ([], training_status(), None),
        (None, {}, {}),
        ([], {"mostRecentTrainingStatus": None}, {"hrvSummary": None}),
    ],
)
def test_recovery_not_synced_exits_1(
    readiness: Any, status: Any, hrv: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeClient(
        get_training_readiness=readiness, get_training_status=status, get_hrv_data=hrv
    )

    assert main(["recovery", "view", DAY], connect=lambda: fake) == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == (
        f"garmin: No recovery data for {DAY} yet. "
        "Sync your watch with Garmin Connect, then try again.\n"
    )


def test_recovery_raw_prints_full_responses(
    capsys: pytest.CaptureFixture[str],
) -> None:
    status = training_status(STATUS, BALANCE)
    fake = client([READINESS], status, HRV)

    assert run_json(["recovery", "view", "--raw", DAY], fake, capsys) == {
        "training_readiness": [READINESS],
        "training_status": status,
        "hrv": HRV,
    }


def test_recovery_raw_skips_not_synced_check(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_json(["recovery", "view", "--raw", DAY], client(), capsys) == {
        "training_readiness": [],
        "training_status": training_status(),
        "hrv": None,
    }


def test_recovery_without_command_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["recovery"])

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        "garmin: No command given. Run 'garmin recovery <command>', one of: view.\n"
    )
