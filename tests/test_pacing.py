import math
from typing import Any

import pytest

from garmin_cli.pacing import compute_splits

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


def plan(**settings: Any) -> dict[str, Any]:
    return {
        "splitType": "DISTANCE_KILOMETER",
        "goalTime": 800,
        "uphillEffort": 0.0,
        "pacingStrategy": 0.0,
        "elevationSegmentMinLength": 1700.0,
        **settings,
    }


def lengths(splits: list[dict[str, Any]]) -> list[float]:
    return [round(split["splitDistance"], 3) for split in splits]


def times(splits: list[dict[str, Any]]) -> list[float]:
    return [round(split["cumulativeTimeFromStart"], 3) for split in splits]


def test_flat_even_plan_runs_every_km_split_at_the_goal_speed() -> None:
    splits = compute_splits(flat(2500), plan(goalTime=1000))

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
    # 0.01 degrees of latitude is 1111.95 m on a 6371 km sphere; the stored
    # distances say 1200 m.
    track = [
        {"latitude": 0.0, "longitude": 0.0, "elevation": 100.0, "distance": 0.0},
        {"latitude": 0.01, "longitude": 0.0, "elevation": 100.0, "distance": 1200.0},
    ]

    splits = compute_splits(track, plan(goalTime=600))

    assert lengths(splits) == [1000.0, 111.949]
    assert times(splits) == [539.593, 600.0]


def test_uphill_km_is_slower_than_the_downhill_km_by_the_uphill_effort() -> None:
    track = course((0, 100.0), (1000, 120.0), (2000, 100.0))

    splits = compute_splits(track, plan(uphillEffort=1.0))

    # Speed factors 1 - 1 * 2 % and 1 + 1 * 2 %, scaled to the 800 s goal.
    assert times(splits) == [408.0, 800.0]


def test_zero_uphill_effort_ignores_hills() -> None:
    track = course((0, 100.0), (1000, 120.0), (2000, 100.0))

    splits = compute_splits(track, plan())

    assert times(splits) == [400.0, 800.0]


def test_negative_pacing_strategy_slows_the_second_half() -> None:
    splits = compute_splits(flat(2000), plan(pacingStrategy=-1.0))

    # Speed factors 1 + 0.09 * 0.25 and 1 - 0.09 * 0.25 at the split mid-points.
    assert times(splits) == [391.0, 800.0]


def test_positive_pacing_strategy_speeds_up_the_second_half() -> None:
    splits = compute_splits(flat(2000), plan(pacingStrategy=2.0))

    assert times(splits) == [418.0, 800.0]


def test_partial_last_km_split_runs_at_the_goal_pace() -> None:
    track = course((0, 100.0), (1000, 120.0), (2000, 100.0), (2500, 110.0))

    splits = compute_splits(track, plan(goalTime=1000, uphillEffort=1.0))

    assert times(splits) == [408.0, 800.0, 1000.0]
    assert round(splits[-1]["splitAvgSpeed"], 6) == 2.5


def test_course_shorter_than_a_km_is_one_split_at_the_goal_pace() -> None:
    splits = compute_splits(flat(600), plan(goalTime=300, pacingStrategy=-1.0))

    assert (lengths(splits), times(splits)) == ([600.0], [300.0])


def test_steep_climb_never_drops_below_a_fifth_of_the_goal_speed() -> None:
    track = course((0, 100.0), (1000, 400.0), (2000, 400.0))

    splits = compute_splits(track, plan(goalTime=1200, uphillEffort=10.0))

    # Factors 0.2 (floor) and 1: the climb takes 5 of every 6 seconds.
    assert times(splits) == [1000.0, 1200.0]


def test_elevation_splits_start_where_the_grade_changes() -> None:
    track = course(
        *((distance, 100.0) for distance in range(0, 2001, 100)),
        *(
            (2000 + distance, 100.0 + distance / 50)
            for distance in range(100, 2001, 100)
        ),
        *(
            (4000 + distance, 140.0 - distance / 50)
            for distance in range(100, 2001, 100)
        ),
    )

    splits = compute_splits(track, plan(splitType="ELEVATION", goalTime=2400))

    assert lengths(splits) == [2000.0, 2000.0, 2000.0]
    assert [
        round(split["endPoint"]["elevation"] - split["startPoint"]["elevation"], 3)
        for split in splits
    ] == [0.0, 40.0, -40.0]
    assert times(splits)[-1] == 2400.0


def test_elevation_splits_scale_every_split_to_the_goal() -> None:
    track = course((0, 100.0), (2000, 100.0), (2500, 110.0))

    splits = compute_splits(
        track,
        plan(
            splitType="ELEVATION",
            goalTime=1000,
            uphillEffort=1.0,
            elevationSegmentMinLength=100.0,
        ),
    )

    # Factors 1 and 0.98 over 2000 m and 500 m.
    assert lengths(splits) == [2000.0, 500.0]
    assert times(splits) == [796.748, 1000.0]


def test_elevation_split_shorter_than_the_minimum_joins_the_closer_grade() -> None:
    # Flat, a 600 m climb, a gentle 1200 m climb, flat: the short climb joins the
    # gentle one, not the flat start.
    track = course(
        (0, 100.0), (2000, 100.0), (2600, 130.0), (3800, 142.0), (6000, 142.0)
    )

    splits = compute_splits(track, plan(splitType="ELEVATION", goalTime=2400))

    assert lengths(splits) == [2000.0, 1800.0, 2200.0]


def test_elevation_split_at_the_start_or_end_joins_its_only_neighbour() -> None:
    track = course((0, 100.0), (500, 120.0), (3000, 120.0), (3500, 100.0))

    splits = compute_splits(track, plan(splitType="ELEVATION", goalTime=1400))

    assert lengths(splits) == [3500.0]


@pytest.mark.parametrize(("bump", "count"), [(2.9, 1), (3.1, 2)])
def test_elevation_splits_ignore_bumps_within_3_m(bump: float, count: int) -> None:
    track = course((0, 100.0), (1000, 100.0 + bump), (2000, 100.0))

    splits = compute_splits(
        track,
        plan(splitType="ELEVATION", elevationSegmentMinLength=100.0),
    )

    assert len(splits) == count


def test_great_circle_length_follows_a_parallel() -> None:
    # 0.02 degrees of longitude at 60 degrees north is about as long as 0.01
    # degrees of latitude: 1111.95 m.
    track = [
        {"latitude": 60.0, "longitude": 10.0, "elevation": 100.0, "distance": 0.0},
        {"latitude": 60.0, "longitude": 10.02, "elevation": 100.0, "distance": 1100.0},
    ]

    splits = compute_splits(track, plan(goalTime=600))

    assert round(splits[-1]["cumulativeDistanceFromStart"], 2) == 1111.95


def test_split_past_the_stored_distances_ends_at_the_last_point() -> None:
    track = [
        {"latitude": 0.0, "longitude": 0.0, "elevation": 100.0, "distance": 0.0},
        {"latitude": 0.01, "longitude": 0.0, "elevation": 104.0, "distance": 1000.0},
    ]

    splits = compute_splits(track, plan(goalTime=600))

    assert splits[-1]["endPoint"] == {
        "latitude": 0.01,
        "longitude": 0.0,
        "elevation": 104.0,
    }


def test_elevation_split_joins_the_left_neighbour_when_its_grade_is_closer() -> None:
    # 2 % for 2000 m, 1.2 % for 600 m, flat for 3000 m.
    track = course((0, 100.0), (2000, 140.0), (2600, 147.2), (5600, 147.2))

    splits = compute_splits(track, plan(splitType="ELEVATION", goalTime=2400))

    assert lengths(splits) == [2600.0, 3000.0]


def test_elevation_splits_find_corners_on_both_sides_of_the_highest_one() -> None:
    track = course(
        (0, 100.0), (2000, 100.0), (4000, 140.0), (6000, 140.0), (8000, 100.0)
    )

    splits = compute_splits(track, plan(splitType="ELEVATION", goalTime=3200))

    assert lengths(splits) == [2000.0, 2000.0, 2000.0, 2000.0]


def test_course_shorter_than_the_elevation_minimum_is_one_split() -> None:
    track = course((0, 100.0), (500, 120.0), (1000, 100.0))

    splits = compute_splits(track, plan(splitType="ELEVATION", goalTime=400))

    assert (lengths(splits), times(splits)) == ([1000.0], [400.0])
