import argparse
from typing import Any

from garmin_cli.client import Connect
from garmin_cli.dates import add_date_argument
from garmin_cli.errors import GarminCliError


def stats(args: argparse.Namespace, connect: Connect) -> Any:
    day = args.date.isoformat()
    response = connect().get_stats(day)
    if args.raw:
        return response
    if response.get("totalKilocalories") is None:
        raise GarminCliError(
            f"No daily summary for {day} yet.",
            "Sync your watch with Garmin Connect, then try again.",
        )
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


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    stats_parser = subparsers.add_parser(
        "stats", help="daily summary: calories, resting HR, body battery, stress"
    )
    add_date_argument(stats_parser)
    stats_parser.add_argument(
        "--raw", action="store_true", help="print the full Garmin response"
    )
    stats_parser.set_defaults(run=stats)
