import math
from typing import Any

import pytest

from garmin_cli.pacing import compute_splits, pace_factor

# Made-up courses run due north along the prime meridian, where the great-circle
# distance between two points is R * (difference in latitude).
METERS_PER_DEGREE = 6371000 * math.pi / 180


def course(*profile: tuple[float, float]) -> list[dict[str, Any]]:
    """Track points from (distance in m, elevation in m) pairs."""
    return [
        {
            "latitude": distance / METERS_PER_DEGREE,
            "longitude": 0.0,
            "elevation": elevation,
            "distance": distance,
        }
        for distance, elevation in profile
    ]


def flat(length: float, step: float = 100.0) -> list[dict[str, Any]]:
    return course(*((index * step, 100.0) for index in range(int(length / step) + 1)))


def plan(goal_time: int = 800) -> dict[str, Any]:
    return {"goalTime": goal_time}


def lengths(splits: list[dict[str, Any]]) -> list[float]:
    return [round(split["splitDistance"], 3) for split in splits]


def times(splits: list[dict[str, Any]]) -> list[float]:
    return [round(split["cumulativeTimeFromStart"], 3) for split in splits]


def test_flat_plan_runs_every_split_at_the_goal_speed() -> None:
    splits = compute_splits(flat(2500), plan(1000))

    assert [
        (
            round(split["splitDistance"], 3),
            round(split["splitAvgSpeed"], 6),
            round(split["cumulativeDistanceFromStart"], 3),
            round(split["cumulativeTimeFromStart"], 3),
        )
        for split in splits
    ] == [
        (1000.0, 2.5, 1000.0, 400.0),
        (1000.0, 2.5, 2000.0, 800.0),
        (500.0, 2.5, 2500.0, 1000.0),
    ]


def test_split_points_interpolate_the_track_on_its_distances() -> None:
    track = course((0, 100.0), (900, 109.0), (1200, 112.0), (2000, 104.0))

    splits = compute_splits(track, plan())

    assert [split["startPoint"]["elevation"] for split in splits] == [100.0, 110.0]
    assert [round(split["endPoint"]["elevation"], 6) for split in splits] == [
        110.0,
        104.0,
    ]
    assert round(splits[0]["endPoint"]["latitude"] * METERS_PER_DEGREE, 6) == 1000.0
    assert splits[0]["endPoint"]["longitude"] == 0.0


def test_splits_end_at_the_great_circle_length_of_the_track() -> None:
    # 0.01 degrees of latitude is 1111.949 m on a 6371 km sphere; the stored
    # distances say 1200 m.
    track = [
        {"latitude": 0.0, "longitude": 0.0, "elevation": 100.0, "distance": 0.0},
        {"latitude": 0.01, "longitude": 0.0, "elevation": 100.0, "distance": 1200.0},
    ]

    splits = compute_splits(track, plan(600))

    assert splits[-1]["cumulativeDistanceFromStart"] == 1111.949
    assert lengths(splits) == [1000.0, 111.949]
    assert times(splits) == [539.593, 600.0]


def test_climb_is_slower_than_a_descent_of_the_same_grade() -> None:
    track = course((0, 100.0), (1000, 120.0), (2000, 100.0))

    splits = compute_splits(track, plan())

    # Factors 1 + 1.68 * 2 % + 2.5 * 2 %² and 1 - 1.68 * 2 % + 10 * 2 %², scaled
    # to the 800 s goal.
    assert times(splits) == [412.808, 800.0]


def test_partial_last_split_follows_its_grade() -> None:
    track = course((0, 100.0), (1000, 100.0), (1500, 110.0))

    splits = compute_splits(track, plan(1000))

    assert times(splits) == [659.065, 1000.0]
    assert splits[-1]["splitAvgSpeed"] < 1500 / 1000


def test_grade_is_measured_along_the_great_circle_length() -> None:
    # The stored distances put the 1000 m mark a third of the way up the climb;
    # on the great-circle length the climb fills the first km.
    track = [
        {"latitude": 0.0, "longitude": 0.0, "elevation": 100.0, "distance": 0.0},
        {
            "latitude": 1000 / METERS_PER_DEGREE,
            "longitude": 0.0,
            "elevation": 120.0,
            "distance": 1500.0,
        },
        {
            "latitude": 2000 / METERS_PER_DEGREE,
            "longitude": 0.0,
            "elevation": 120.0,
            "distance": 2000.0,
        },
    ]

    splits = compute_splits(track, plan())

    # Factors 1.0346 (2 % climb) and 1 (flat).
    assert times(splits) == [406.802, 800.0]
    assert round(splits[0]["endPoint"]["elevation"], 3) == 113.333


def test_descent_gain_peaks_and_fades_on_steep_descents() -> None:
    assert pace_factor(-0.04) == pytest.approx(0.9488)
    assert pace_factor(-0.08) == pytest.approx(0.9296)
    assert pace_factor(-0.2) == pytest.approx(1.064)


def test_climbs_cost_more_as_they_steepen() -> None:
    assert pace_factor(0.0) == 1
    assert pace_factor(0.04) == pytest.approx(1.0712)
    assert pace_factor(0.1) == pytest.approx(1.193)


def test_course_shorter_than_a_km_is_one_split_at_the_goal_time() -> None:
    track = course((0, 100.0), (300, 110.0), (600, 100.0))

    splits = compute_splits(track, plan(300))

    assert (lengths(splits), times(splits)) == ([600.0], [300.0])


def test_great_circle_length_follows_a_parallel() -> None:
    # 0.02 degrees of longitude at 60 degrees north is about as long as 0.01
    # degrees of latitude: 1111.95 m.
    track = [
        {"latitude": 60.0, "longitude": 10.0, "elevation": 100.0, "distance": 0.0},
        {"latitude": 60.0, "longitude": 10.02, "elevation": 100.0, "distance": 1100.0},
    ]

    splits = compute_splits(track, plan(600))

    assert round(splits[-1]["cumulativeDistanceFromStart"], 2) == 1111.95


def test_split_past_the_stored_distances_ends_at_the_last_point() -> None:
    track = [
        {"latitude": 0.0, "longitude": 0.0, "elevation": 100.0, "distance": 0.0},
        {"latitude": 0.01, "longitude": 0.0, "elevation": 104.0, "distance": 1000.0},
    ]

    splits = compute_splits(track, plan(600))

    assert splits[-1]["endPoint"] == {
        "latitude": 0.01,
        "longitude": 0.0,
        "elevation": 104.0,
    }


def test_last_points_on_the_same_stored_distance_end_at_the_last_point() -> None:
    track = [
        {"latitude": 0.0, "longitude": 0.0, "elevation": 100.0, "distance": 0.0},
        {"latitude": 0.01, "longitude": 0.0, "elevation": 104.0, "distance": 1000.0},
        {"latitude": 0.01, "longitude": 0.0, "elevation": 106.0, "distance": 1000.0},
    ]

    splits = compute_splits(track, plan(600))

    assert splits[-1]["endPoint"]["elevation"] == 106.0
