import argparse
import math
from datetime import date, datetime
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


def positive_weight(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        number = 0
    if not (math.isfinite(number) and number > 0):
        raise argparse.ArgumentTypeError(
            f"Invalid weight '{value}'. Use a number above 0, like 82.4."
        )
    return number


def weight_unit(value: str) -> str:
    if value not in ("kg", "lbs"):
        raise argparse.ArgumentTypeError(f"Invalid --unit '{value}'. Use kg or lbs.")
    return value


def local_time(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M").isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid --at '{value}'. Use 'YYYY-MM-DD HH:MM' in local time."
        ) from None


def add_weight(args: argparse.Namespace, connect: Connect) -> Any:
    # An empty timestamp makes garminconnect use the current time.
    return connect().add_weigh_in(args.weight, args.unit, args.at or "")


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
    add_parser = weight_parser.add_subparsers(dest="subcommand").add_parser(
        "add", help="log a weigh-in"
    )
    add_parser.add_argument("weight", type=positive_weight, help="e.g. 82.4")
    add_parser.add_argument(
        "--at",
        type=local_time,
        metavar="'YYYY-MM-DD HH:MM'",
        help="local time of the weigh-in (default: now)",
    )
    add_parser.add_argument(
        "--unit", type=weight_unit, default="kg", help="kg or lbs (default: kg)"
    )
    add_parser.set_defaults(run=add_weight)
