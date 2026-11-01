import argparse
import re
from typing import Any

from garmin_cli.client import Connect
from garmin_cli.dates import add_date_argument
from garmin_cli.errors import GarminCliError

# Output name → the prefix of Garmin's `<prefix>FactorPercent` and
# `<prefix>FactorFeedback` readiness keys.
FACTORS = {
    "sleep": "sleepScore",
    "recovery_time": "recoveryTime",
    "hrv": "hrv",
    "acute_load": "acwr",
    "sleep_history": "sleepHistory",
    "stress_history": "stressHistory",
}

# Output name → the infix of Garmin's `monthlyLoad<infix>` load balance keys.
LOADS = {
    "aerobic_low": "AerobicLow",
    "aerobic_high": "AerobicHigh",
    "anaerobic": "Anaerobic",
}


def device_entry(by_device: dict[str, Any] | None, day: str) -> dict[str, Any]:
    """The primary training device's entry, else the first; empty when it is for
    another day than `day`."""
    entries = list((by_device or {}).values())
    entry = next(
        (entry for entry in entries if entry.get("primaryTrainingDevice")),
        entries[0] if entries else {},
    )
    return entry if entry.get("calendarDate") == day else {}


def latest(snapshots: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """The newest readiness snapshot; Garmin updates readiness during the day."""
    if not snapshots:
        return None
    return max(snapshots, key=lambda snapshot: snapshot.get("timestamp") or "")


def readiness(latest: dict[str, Any] | None) -> dict[str, Any] | None:
    if latest is None:
        return None
    return {
        "score": latest.get("score"),
        "level": latest.get("level"),
        "feedback": latest.get("feedbackShort"),
        "factors": {
            name: {
                "pct": latest.get(f"{key}FactorPercent"),
                "feedback": latest.get(f"{key}FactorFeedback"),
            }
            for name, key in FACTORS.items()
        },
    }


def recovery_hours(latest: dict[str, Any] | None) -> float | None:
    if latest is None:
        return None
    # Garmin keeps the last value after the recovery clock reaches zero.
    if latest.get("recoveryTimeChangePhrase") == "REACHED_ZERO":
        return 0
    minutes = latest.get("recoveryTime")
    return None if minutes is None else minutes / 60


def training_status(data: dict[str, Any], day: str) -> dict[str, Any] | None:
    status = device_entry(
        (data.get("mostRecentTrainingStatus") or {}).get("latestTrainingStatusData"),
        day,
    )
    balance = device_entry(
        (data.get("mostRecentTrainingLoadBalance") or {}).get(
            "metricsTrainingLoadBalanceDTOMap"
        ),
        day,
    )
    if not status and not balance:
        return None
    phrase = status.get("trainingStatusFeedbackPhrase")
    load = status.get("acuteTrainingLoadDTO") or {}
    return {
        # `MAINTAINING_2` → `MAINTAINING`; the number picks Garmin's feedback text.
        "status": None if phrase is None else re.sub(r"_\d+$", "", phrase),
        "since": status.get("sinceDate"),
        "paused": status.get("trainingPaused"),
        "acute_load": load.get("dailyTrainingLoadAcute"),
        "chronic_load": load.get("dailyTrainingLoadChronic"),
        "chronic_load_min": load.get("minTrainingLoadChronic"),
        "chronic_load_max": load.get("maxTrainingLoadChronic"),
        "acwr": load.get("dailyAcuteChronicWorkloadRatio"),
        "acwr_status": load.get("acwrStatus"),
        "load_focus": balance.get("trainingBalanceFeedbackPhrase"),
        "monthly_load": {
            name: {
                "load": balance.get(f"monthlyLoad{key}"),
                "target_min": balance.get(f"monthlyLoad{key}TargetMin"),
                "target_max": balance.get(f"monthlyLoad{key}TargetMax"),
            }
            for name, key in LOADS.items()
        },
    }


def hrv(data: dict[str, Any] | None, day: str) -> dict[str, Any] | None:
    summary = (data or {}).get("hrvSummary") or {}
    if summary.get("calendarDate") != day:
        return None
    baseline = summary.get("baseline") or {}
    return {
        "status": summary.get("status"),
        "last_night_ms": summary.get("lastNightAvg"),
        "weekly_avg_ms": summary.get("weeklyAvg"),
        "baseline_low_ms": baseline.get("balancedLow"),
        "baseline_high_ms": baseline.get("balancedUpper"),
    }


def recovery(args: argparse.Namespace, connect: Connect) -> Any:
    day = args.date.isoformat()
    client = connect()
    snapshots = client.get_training_readiness(day)
    status_data = client.get_training_status(day)
    hrv_data = client.get_hrv_data(day)
    if args.raw:
        return {
            "training_readiness": snapshots,
            "training_status": status_data,
            "hrv": hrv_data,
        }
    snapshot = latest(snapshots)
    sections = {
        "readiness": readiness(snapshot),
        "training_status": training_status(status_data or {}, day),
        "hrv": hrv(hrv_data, day),
    }
    if not any(sections.values()):
        raise GarminCliError(
            f"No recovery data for {day} yet.",
            "Sync your watch with Garmin Connect, then try again.",
        )
    return {"date": day, "recovery_time_h": recovery_hours(snapshot), **sections}


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    recovery_parser = subparsers.add_parser(
        "recovery",
        help="training readiness, training status, recovery time and HRV status",
    )
    # `CliParser.explain` names a missing command by this metavar.
    view_parser = recovery_parser.add_subparsers(
        dest="subcommand", required=True, metavar="{view}"
    ).add_parser(
        "view",
        help="one day's recovery data",
        description="Training readiness and its factors, training status and "
        "load, recovery time and HRV status for one day. A section the watch does "
        "not record is null.",
    )
    add_date_argument(view_parser)
    view_parser.add_argument(
        "--raw", action="store_true", help="print the full Garmin response"
    )
    view_parser.set_defaults(run=recovery)
