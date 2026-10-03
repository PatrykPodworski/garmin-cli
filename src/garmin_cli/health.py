import argparse
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from garmin_cli.dates import add_range_arguments


def kilograms(grams: float | None) -> float | None:
    return None if grams is None else grams / 1000


def weight(
    args: argparse.Namespace, connect: Callable[[], Any]
) -> list[dict[str, Any]]:
    data = connect().get_weigh_ins(args.start.isoformat(), args.end.isoformat())
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


def blood_pressure(
    args: argparse.Namespace, connect: Callable[[], Any]
) -> list[dict[str, Any]]:
    data = connect().get_blood_pressure(args.start.isoformat(), args.end.isoformat())
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


def register(subparsers: Any) -> None:
    weight_parser = subparsers.add_parser("weight", help="weigh-ins in a date range")
    add_range_arguments(weight_parser)
    weight_parser.set_defaults(run=weight)
    bp_parser = subparsers.add_parser("bp", help="blood pressure in a date range")
    add_range_arguments(bp_parser)
    bp_parser.set_defaults(run=blood_pressure)
