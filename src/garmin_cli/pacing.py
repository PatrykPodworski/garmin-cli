"""Our own PacePro pacing algorithm (ADR 0001), tuned black-box against Garmin's
splits for known inputs.

Each split's speed is the goal speed times a factor:

    1 - uphillEffort * grade + STRATEGY_DRIFT * pacingStrategy * (x - 1/2)

where grade is the split's net elevation change over its length and x is its
mid-point as a fraction of the course. The splits are then scaled together so
the plan takes the goal time."""

import bisect
import itertools
import math
from typing import Any

EARTH_RADIUS_M = 6371000.0
KM = 1000.0
# How far a negative pacingStrategy slows the plan from start to finish: 9 % of the
# goal speed per unit. Fitted to the one reference case (-0.9).
STRATEGY_DRIFT = 0.09
# A split never runs slower than this share of the goal speed.
MIN_SPEED_FACTOR = 0.2
# Elevation splits start at the corners of the profile simplified to this many
# meters, then splits shorter than `elevationSegmentMinLength` join a neighbour.
ELEVATION_TOLERANCE_M = 3.0

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
    """The track point at a distance along the course's stored distances."""
    index = min(bisect.bisect_right(distances, distance), len(points) - 1)
    start, end = points[index - 1], points[index]
    span = distances[index] - distances[index - 1]
    share = min((distance - distances[index - 1]) / span, 1)
    return {
        key: start[key] + share * (end[key] - start[key])
        for key in ("latitude", "longitude", "elevation")
    }


def simplify(profile: list[tuple[float, float]]) -> list[int]:
    """Indexes of the profile points that Ramer-Douglas-Peucker keeps."""
    keep = {0, len(profile) - 1}
    stack = [(0, len(profile) - 1)]
    while stack:
        first, last = stack.pop()
        (x1, y1), (x2, y2) = profile[first], profile[last]
        worst, farthest = ELEVATION_TOLERANCE_M, None
        for index in range(first + 1, last):
            x, y = profile[index]
            off = abs(y - (y1 + (y2 - y1) * (x - x1) / (x2 - x1)))
            if off > worst:
                worst, farthest = off, index
        if farthest is not None:
            keep.add(farthest)
            stack += [(first, farthest), (farthest, last)]
    return sorted(keep)


def elevation_bounds(
    points: list[Point], distances: list[float], total: float, min_length: float
) -> list[float]:
    profile = [(point["distance"], point["elevation"]) for point in points]
    corners = [distances[index] for index in simplify(profile)[1:-1]]
    bounds = [0.0, *(corner for corner in corners if corner < total), total]

    def grade(index: int) -> float:
        start = point_at(points, distances, bounds[index])["elevation"]
        end = point_at(points, distances, bounds[index + 1])["elevation"]
        return float((end - start) / (bounds[index + 1] - bounds[index]))

    while len(bounds) > 2:
        sizes = [end - start for start, end in itertools.pairwise(bounds)]
        short = sizes.index(min(sizes))
        if sizes[short] >= min_length:
            break
        if short == 0:
            drop = 1
        elif short == len(sizes) - 1:
            drop = short
        else:
            left = abs(grade(short) - grade(short - 1))
            right = abs(grade(short) - grade(short + 1))
            drop = short if left <= right else short + 1
        del bounds[drop]
    return bounds


def compute_splits(
    geo_points: list[Point], summary: dict[str, Any]
) -> list[dict[str, Any]]:
    """The plan's splits in the shape Garmin stores them, from the course's track
    points (latitude, longitude, elevation, distance) and the plan settings."""
    distances = [point["distance"] for point in geo_points]
    # Garmin's splits end at the great-circle length of the track, a little short
    # of the stored course distance; split points sit on the stored distances.
    total = round(sum(map(great_circle, geo_points, geo_points[1:])), 3)
    by_elevation = summary["splitType"] == "ELEVATION"
    if by_elevation:
        bounds = elevation_bounds(
            geo_points, distances, total, summary["elevationSegmentMinLength"]
        )
    else:
        bounds = [index * KM for index in range(math.ceil(total / KM))] + [total]
    goal_speed = total / summary["goalTime"]
    splits = []
    for start, end in itertools.pairwise(bounds):
        first = point_at(geo_points, distances, start)
        last = point_at(geo_points, distances, end)
        grade = (last["elevation"] - first["elevation"]) / (end - start)
        middle = (start + end) / 2 / total - 0.5
        factor = (
            1
            - summary["uphillEffort"] * grade
            + STRATEGY_DRIFT * summary["pacingStrategy"] * middle
        )
        splits.append((start, end, first, last, max(factor, MIN_SPEED_FACTOR)))
    # A km split shorter than a km runs at the goal pace; the others share the rest.
    fixed = not by_elevation and bounds[-1] - bounds[-2] < KM
    scaled = splits[:-1] if fixed else splits
    length = sum(end - start for start, end, *_ in scaled)
    effort = sum((end - start) / factor for start, end, _, _, factor in scaled)
    scale = effort / length if scaled else 1.0
    result: list[dict[str, Any]] = []
    elapsed = 0.0
    for index, (start, end, first, last, factor) in enumerate(splits):
        speed = (
            goal_speed
            if fixed and index == len(splits) - 1
            else goal_speed * factor * scale
        )
        elapsed += (end - start) / speed
        result.append(
            {
                "splitDistance": end - start,
                "splitAvgSpeed": speed,
                "cumulativeDistanceFromStart": end,
                # Garmin rejects split times with more than 3 decimals.
                "cumulativeTimeFromStart": round(elapsed, 3),
                "startPoint": first,
                "endPoint": last,
            }
        )
    return result
