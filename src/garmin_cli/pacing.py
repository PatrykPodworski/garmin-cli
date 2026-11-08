"""Our own PacePro pacing algorithm (ADR 0001), tuned black-box against plans saved
on the Garmin Connect website with its default sliders.

The plan splits the course every km. Each split runs at the goal pace times

    1 + GRADE_COST * g + curve * g**2

where g is the split's net grade (elevation change over its length) and curve is
CLIMB_CURVE on a climb and DESCENT_CURVE on a descent. The splits are then scaled
together so the plan takes the goal time."""

import bisect
import itertools
import math
from typing import Any

EARTH_RADIUS_M = 6371000.0
KM = 1000.0
# Near flat, each 1 % of grade makes a split about 1.7 % slower (or faster downhill).
GRADE_COST = 1.68
# Climbs cost a little more as they steepen.
CLIMB_CURVE = 2.5
# Descents help less as they steepen: the gain peaks at about -8 % and is gone by
# about -17 %, where braking makes a descent slower than flat ground.
DESCENT_CURVE = 10.0
# Settings the Garmin Connect website sends with a km-split plan at its default
# sliders, as the reference plans store them.
WEBSITE_SETTINGS = {
    "splitType": "DISTANCE_KILOMETER",
    "distanceUnit": None,
    "uphillEffort": 0.0,
    "pacingStrategy": 0.0,
    "manualPaceEdit": False,
    "elevationSegmentationTolerance": 50.0,
    "paceFactor": 2.0,
    "elevationSegmentMinLength": 1700.0,
}

Point = dict[str, Any]


def great_circle(start: Point, end: Point) -> float:
    lat1, lat2 = math.radians(start["latitude"]), math.radians(end["latitude"])
    lon = math.radians(end["longitude"] - start["longitude"])
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def point_at(points: list[Point], distances: list[float], distance: float) -> Point:
    """The track point at a distance along the given per-point distances."""
    index = min(bisect.bisect_right(distances, distance), len(points) - 1)
    start, end = points[index - 1], points[index]
    span = distances[index] - distances[index - 1]
    share = min((distance - distances[index - 1]) / span, 1) if span else 1
    return {
        key: start[key] + share * (end[key] - start[key])
        for key in ("latitude", "longitude", "elevation")
    }


def pace_factor(grade: float) -> float:
    return (
        1
        + GRADE_COST * grade
        + CLIMB_CURVE * max(grade, 0) ** 2
        + DESCENT_CURVE * min(grade, 0) ** 2
    )


def compute_splits(
    geo_points: list[Point], summary: dict[str, Any]
) -> list[dict[str, Any]]:
    """The plan's km splits in the shape Garmin stores them, from the course's track
    points (latitude, longitude, elevation, distance) and the plan's goalTime."""
    stored = [point["distance"] for point in geo_points]
    # Garmin's splits end at the great-circle length of the track, a little short of
    # the stored course distance. The split points sit on the stored distances, but
    # the grade that sets a split's pace is measured along the great-circle length.
    along = list(
        itertools.accumulate(map(great_circle, geo_points, geo_points[1:]), initial=0)
    )
    total = round(along[-1], 3)
    bounds = [index * KM for index in range(math.ceil(total / KM))] + [total]
    splits = []
    for start, end in itertools.pairwise(bounds):
        rise = (
            point_at(geo_points, along, end)["elevation"]
            - point_at(geo_points, along, start)["elevation"]
        )
        splits.append((start, end, pace_factor(rise / (end - start))))
    effort = sum((end - start) * factor for start, end, factor in splits)
    result: list[dict[str, Any]] = []
    elapsed = 0.0
    for start, end, factor in splits:
        speed = effort / (summary["goalTime"] * factor)
        elapsed += (end - start) / speed
        result.append(
            {
                "splitDistance": end - start,
                "splitAvgSpeed": speed,
                "cumulativeDistanceFromStart": end,
                # Garmin rejects split times with more than 3 decimals.
                "cumulativeTimeFromStart": round(elapsed, 3),
                "startPoint": point_at(geo_points, stored, start),
                "endPoint": point_at(geo_points, stored, end),
            }
        )
    return result


def km_plan(
    course_id: int,
    name: str | None,
    goal_time: int,
    distance: float,
    geo_points: list[Point],
) -> dict[str, Any]:
    """The plan in the shape the website saves it: a summary with km splits at the
    default sliders, for a course of `distance` m with these track points."""
    summary = {
        "courseId": course_id,
        "name": name,
        "goalTime": goal_time,
        "goalSpeed": distance / goal_time,
        "totalDistance": distance,
        **WEBSITE_SETTINGS,
    }
    return {
        "paceBandSummary": summary,
        "paceBandSplits": compute_splits(geo_points, summary),
    }
