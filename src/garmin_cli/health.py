import argparse
from datetime import date
from typing import Any

from garmin_cli.client import Connect
from garmin_cli.dates import add_range_arguments, wall_clock


def kilograms(grams: float | None) -> float | None:
    return None if grams is None else grams / 1000


def weight(args: argparse.Namespace, connect: Connect) -> Any:
    data = connect().get_weigh_ins(args.start.isoformat(), args.end.isoformat())
    if args.raw:
        return data
    records = []
    for day in data.get("dailyWeightSummaries", []):
        for metric in day.get("allWeightMetrics", []):
            records.append(
                {
                    "date": metric["calendarDate"],
                    "time": wall_clock(metric["date"]).strftime("%H:%M:%S"),
                    "weight_kg": kilograms(metric.get("weight")),
                    "body_fat_pct": metric.get("bodyFat"),
                    "muscle_mass_kg": kilograms(metric.get("muscleMass")),
                    "body_water_pct": metric.get("bodyWater"),
                }
            )
    return records


def blood_pressure(args: argparse.Namespace, connect: Connect) -> Any:
    data = connect().get_blood_pressure(args.start.isoformat(), args.end.isoformat())
    if args.raw:
        return data
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


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    weight_parser = subparsers.add_parser("weight", help="weigh-ins in a date range")
    bp_parser = subparsers.add_parser("bp", help="blood pressure in a date range")
    for parser, run in ((weight_parser, weight), (bp_parser, blood_pressure)):
        add_range_arguments(parser, date.today())
        parser.add_argument(
            "--raw", action="store_true", help="print the full Garmin response"
        )
        parser.set_defaults(run=run)
