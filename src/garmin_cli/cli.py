"""`garmin` entry point. A subcommand gets the parsed args and a Garmin client,
returns JSON-serializable data, and `main` prints it to stdout."""

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from garminconnect import Garmin, GarminConnectAuthenticationError


def tokenstore() -> str:
    return os.environ.get("GARMINTOKENS", "~/.garminconnect")


def connect() -> Any:
    client = Garmin()
    try:
        client.login(tokenstore())
    except GarminConnectAuthenticationError:
        raise RuntimeError("no valid saved tokens, run 'garmin login'") from None
    return client


def login() -> dict[str, str]:
    email = os.environ.get("GARMIN_EMAIL")
    if not email:
        raise RuntimeError("set GARMIN_EMAIL to your Garmin account email")
    keychain = subprocess.run(
        ["security", "find-generic-password", "-s", "garmin", "-a", email, "-w"],
        capture_output=True,
        text=True,
    )
    if keychain.returncode != 0:
        raise RuntimeError(
            f"no Keychain password for service 'garmin', account {email}"
        )
    password = keychain.stdout.rstrip("\n")
    client = Garmin(email, password, prompt_mfa=lambda: input("MFA code: "))
    path = tokenstore()
    client.login(path)
    return {"tokenstore": path}


def parse_date(value: str) -> date:
    if value == "today":
        return date.today()
    if value == "yesterday":
        return date.today() - timedelta(days=1)
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected today, yesterday or YYYY-MM-DD, got {value!r}"
        ) from None


def add_date_argument(parser: argparse._ActionsContainer) -> None:
    parser.add_argument(
        "date",
        nargs="?",
        default=date.today(),
        type=parse_date,
        help="today | yesterday | YYYY-MM-DD (default: today)",
    )


def add_range_arguments(parser: argparse.ArgumentParser) -> None:
    for flag, dest in (("--from", "start"), ("--to", "end")):
        parser.add_argument(
            flag,
            dest=dest,
            metavar="DATE",
            default="today",
            type=parse_date,
            help="today | yesterday | YYYY-MM-DD (default: today)",
        )


def kilograms(grams: float | None) -> float | None:
    return None if grams is None else grams / 1000


def weight(args: argparse.Namespace, client: Any) -> list[dict[str, Any]]:
    data = client.get_weigh_ins(args.start.isoformat(), args.end.isoformat())
    records = []
    for day in data.get("dailyWeightSummaries", []):
        for metric in day.get("allWeightMetrics", []):
            # Garmin encodes the local wall-clock time as if it were UTC.
            local = datetime.fromtimestamp(metric["date"] / 1000, UTC)
            records.append(
                {
                    "date": metric["calendarDate"],
                    "time": local.strftime("%H:%M:%S"),
                    "weight_kg": kilograms(metric.get("weight")),
                    "body_fat_pct": metric.get("bodyFat"),
                    "muscle_mass_kg": kilograms(metric.get("muscleMass")),
                    "body_water_pct": metric.get("bodyWater"),
                }
            )
    return records


def blood_pressure(args: argparse.Namespace, client: Any) -> list[dict[str, Any]]:
    data = client.get_blood_pressure(args.start.isoformat(), args.end.isoformat())
    records = []
    for day in data.get("measurementSummaries", []):
        for reading in day.get("measurements", []):
            day_part, time_part = reading["measurementTimestampLocal"].split("T")
            records.append(
                {
                    "date": day_part,
                    "time": time_part[:8],
                    "systolic": reading.get("systolic"),
                    "diastolic": reading.get("diastolic"),
                    "pulse": reading.get("pulse"),
                    "notes": reading.get("notes"),
                }
            )
    return records


def local_time(timestamp_ms: int) -> str:
    # Garmin "Local" timestamps hold the wall-clock time encoded as UTC.
    return datetime.fromtimestamp(timestamp_ms / 1000, UTC).strftime("%H:%M")


def sleep(args: argparse.Namespace, client: Any) -> Any:
    day = args.night_of + timedelta(days=1) if args.night_of else args.date
    data: dict[str, Any] = client.get_sleep_data(day.isoformat())
    night = data.get("dailySleepDTO") or {}
    if not night.get("sleepTimeSeconds"):
        raise RuntimeError(f"no sleep data for {day}, not synced yet")
    if args.raw:
        return data
    scores = dict(night.get("sleepScores") or {})
    overall = scores.pop("overall", None) or {}
    return {
        "date": night["calendarDate"],
        "start": local_time(night["sleepStartTimestampLocal"]),
        "end": local_time(night["sleepEndTimestampLocal"]),
        "duration_min": night["sleepTimeSeconds"] // 60,
        "deep_min": night["deepSleepSeconds"] // 60,
        "light_min": night["lightSleepSeconds"] // 60,
        "rem_min": night["remSleepSeconds"] // 60,
        "awake_min": night["awakeSleepSeconds"] // 60,
        "score": overall.get("value"),
        "scores": {
            re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower(): {
                "value": score.get("value"),
                "qualifier": score.get("qualifierKey"),
            }
            for name, score in scores.items()
        },
    }


# Output name -> Garmin key. A list item and a detail `summaryDTO` name the
# aerobic training effect differently, so either key fills `aerobic_te`.
FIELDS = {
    "id": ("activityId",),
    "date": ("startTimeLocal",),
    "name": ("activityName",),
    "duration_s": ("duration",),
    "distance_m": ("distance",),
    "avg_hr": ("averageHR",),
    "max_hr": ("maxHR",),
    "elevation_gain_m": ("elevationGain",),
    "calories": ("calories",),
    "aerobic_te": ("aerobicTrainingEffect", "trainingEffect"),
    "anaerobic_te": ("anaerobicTrainingEffect",),
    "vo2max": ("vO2MaxValue",),
}


def summarize(raw: dict[str, Any], type_key: str | None) -> dict[str, Any]:
    picked = {
        name: next((raw[key] for key in keys if raw.get(key) is not None), None)
        for name, keys in FIELDS.items()
    }
    summary = {name: value for name, value in picked.items() if value is not None}
    if type_key:
        summary["type"] = type_key
    speed = raw.get("averageSpeed")
    if speed:
        if type_key and "running" in type_key:
            summary["avg_pace_s_per_km"] = round(1000 / speed)
        else:
            summary["avg_speed_kmh"] = round(speed * 3.6, 1)
    return summary


def activities(args: argparse.Namespace, client: Any) -> Any:
    if args.start or args.end:
        # Garmin needs a start date; 2000-01-01 predates any Garmin Connect upload.
        # ponytail: --to alone pages through the whole history before the limit
        # applies; page with get_activities and stop at --to if that gets slow.
        start = (args.start or date(2000, 1, 1)).isoformat()
        end = args.end and args.end.isoformat()
        found = client.get_activities_by_date(start, end, args.type)[: args.limit]
    else:
        found = client.get_activities(0, args.limit, activitytype=args.type)
    if args.raw:
        return found
    return [summarize(a, a.get("activityType", {}).get("typeKey")) for a in found]


def activity(args: argparse.Namespace, client: Any) -> Any:
    summary = client.get_activity(args.id)
    splits = client.get_activity_splits(args.id)
    zones = client.get_activity_hr_in_timezones(args.id)
    if args.raw:
        return {"summary": summary, "splits": splits, "hr_zones": zones}
    type_key = summary.get("activityTypeDTO", {}).get("typeKey")
    result = summarize({**summary, **summary.get("summaryDTO", {})}, type_key)
    laps = [summarize(lap, type_key) for lap in splits.get("lapDTOs", [])]
    result["laps"] = [
        {name: value for name, value in lap.items() if name != "type"} for lap in laps
    ]
    result["hr_zones"] = [
        {
            "zone": zone.get("zoneNumber"),
            "seconds": zone.get("secsInZone"),
            "low_bpm": zone.get("zoneLowBoundary"),
        }
        for zone in zones or []
    ]
    return result


def stats(args: argparse.Namespace, client: Any) -> Any:
    day = args.date.isoformat()
    response = client.get_stats(day)
    if args.raw:
        return response
    if response.get("totalKilocalories") is None:
        raise RuntimeError(f"{day} is not synced (no totalKilocalories)")
    return {
        "date": day,
        "total_kcal": response["totalKilocalories"],
        "active_kcal": response.get("activeKilocalories"),
        "bmr_kcal": response.get("bmrKilocalories"),
        "resting_hr": response.get("restingHeartRate"),
        "body_battery_high": response.get("bodyBatteryHighestValue"),
        "body_battery_low": response.get("bodyBatteryLowestValue"),
        "avg_stress": response.get("averageStressLevel"),
    }


def main(argv: list[str] | None = None, connect: Callable[[], Any] = connect) -> int:
    parser = argparse.ArgumentParser(
        prog="garmin", description="Read Garmin Connect data as JSON."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "login",
        help="log in as GARMIN_EMAIL with the Keychain password, save tokens",
    )
    weight_parser = subparsers.add_parser("weight", help="weigh-ins in a date range")
    add_range_arguments(weight_parser)
    weight_parser.set_defaults(run=weight)
    bp_parser = subparsers.add_parser("bp", help="blood pressure in a date range")
    add_range_arguments(bp_parser)
    bp_parser.set_defaults(run=blood_pressure)
    sleep_parser = subparsers.add_parser(
        "sleep",
        help="sleep window, sleep score and stages for one night",
        description="Garmin files a night under its wake-up date: `date` is the "
        "morning you woke up. --night-of DATE takes the lights-out date instead "
        "and shows the night that started on DATE.",
    )
    night = sleep_parser.add_mutually_exclusive_group()
    add_date_argument(night)
    night.add_argument(
        "--night-of",
        type=parse_date,
        metavar="DATE",
        help="lights-out date: the night that started on DATE",
    )
    sleep_parser.add_argument(
        "--raw", action="store_true", help="print the full Garmin response"
    )
    sleep_parser.set_defaults(run=sleep)

    activities_parser = subparsers.add_parser(
        "activities", help="recent activities, newest first"
    )
    activities_parser.add_argument("--from", dest="start", type=parse_date)
    activities_parser.add_argument("--to", dest="end", type=parse_date)
    activities_parser.add_argument("--type", help="running, cycling, swimming, ...")
    activities_parser.add_argument("--limit", type=int, default=20)
    activities_parser.add_argument("--raw", action="store_true")
    activities_parser.set_defaults(run=activities)
    activity_parser = subparsers.add_parser(
        "activity", help="one activity with laps and HR zones"
    )
    activity_parser.add_argument("id")
    activity_parser.add_argument("--raw", action="store_true")
    activity_parser.set_defaults(run=activity)

    stats_parser = subparsers.add_parser(
        "stats", help="daily summary: calories, resting HR, body battery, stress"
    )
    add_date_argument(stats_parser)
    stats_parser.add_argument(
        "--raw", action="store_true", help="print the full get_stats response"
    )
    stats_parser.set_defaults(run=stats)
    args = parser.parse_args(argv)

    try:
        if args.command == "login":
            result: Any = login()
        else:
            result = args.run(args, connect())
    except Exception as error:
        print(f"garmin: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0
