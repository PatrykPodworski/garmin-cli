from datetime import datetime
from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError
from test_bp_delete import run

from garmin_cli import bp_create

# Garmin answers the POST with the reading, but without its `version`.
POSTED = {
    "version": None,
    "measurementTimestampLocal": "2026-07-06T21:05:00.0",
    "systolic": 124,
    "diastolic": 81,
    "pulse": 66,
    "notes": "after a walk",
    "category": None,
}


def reading(version: int, at: str, systolic: int, diastolic: int, pulse: Any) -> Any:
    return {
        "version": version,
        "measurementTimestampLocal": at,
        "systolic": systolic,
        "diastolic": diastolic,
        "pulse": pulse,
        "notes": f"note {version}",
    }


def readings(*measurements: dict[str, Any]) -> dict[str, Any]:
    return {
        "measurementSummaries": [
            {"startDate": "2026-07-06", "measurements": list(measurements)}
        ]
    }


STORED = readings(
    reading(3001, "2026-07-06T08:10:00.0", 124, 81, 66),
    reading(3002, "2026-07-06T21:05:00.0", 124, 81, 66),
)


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz: Any = None) -> "FrozenDatetime":
        return cls(2026, 7, 6, 21, 5, 42, 123456)


def create_client(stored: Any = STORED, posted: Any = POSTED) -> FakeClient:
    return FakeClient(set_blood_pressure=posted, get_blood_pressure=stored)


def record(version: Any, pulse: Any = 66, notes: Any = "note 3002") -> str:
    id = "null" if version is None else version
    pulse = "null" if pulse is None else pulse
    notes = "null" if notes is None else f'"{notes}"'
    return (
        "{\n"
        f'  "id": {id},\n'
        '  "date": "2026-07-06",\n'
        '  "time": "21:05:00",\n'
        '  "systolic": 124,\n'
        '  "diastolic": 81,\n'
        f'  "pulse": {pulse},\n'
        f'  "notes": {notes}\n'
        "}\n"
    )


def test_bp_create_logs_reading(capsys: pytest.CaptureFixture[str]) -> None:
    client = create_client()

    result = run(
        [
            "bp",
            "create",
            "124",
            "81",
            "--pulse",
            "66",
            "--at",
            "2026-07-06 21:05",
            "--notes",
            "after a walk",
        ],
        client,
        capsys,
    )

    assert result == (
        0,
        record(3002),
        "garmin: Logged blood pressure 124/81, pulse 66, at 2026-07-06 21:05.\n",
    )
    assert client.calls == [
        (
            "set_blood_pressure",
            (124, 81),
            {"pulse": 66, "timestamp": "2026-07-06T21:05:00", "notes": "after a walk"},
        ),
        ("get_blood_pressure", ("2026-07-06", "2026-07-06"), {}),
    ]


def test_bp_create_without_pulse(capsys: pytest.CaptureFixture[str]) -> None:
    client = create_client(
        readings(
            reading(3001, "2026-07-06T21:05:00.0", 124, 81, 66),
            reading(3002, "2026-07-06T21:05:00.0", 124, 81, None),
        )
    )

    result = run(
        ["bp", "create", "124", "81", "--at", "2026-07-06 21:05"], client, capsys
    )

    assert result == (
        0,
        record(3002, pulse=None),
        "garmin: Logged blood pressure 124/81 at 2026-07-06 21:05.\n",
    )
    assert client.calls[0] == (
        "set_blood_pressure",
        (124, 81),
        {"pulse": None, "timestamp": "2026-07-06T21:05:00", "notes": ""},
    )


def test_bp_create_defaults_to_now(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bp_create, "datetime", FrozenDatetime)
    client = create_client()

    result = run(["bp", "create", "124", "81", "--pulse", "66"], client, capsys)

    assert result == (
        0,
        record(3002),
        "garmin: Logged blood pressure 124/81, pulse 66, at 2026-07-06 21:05.\n",
    )
    assert client.calls == [
        (
            "set_blood_pressure",
            (124, 81),
            {"pulse": 66, "timestamp": "2026-07-06T21:05:00", "notes": ""},
        ),
        ("get_blood_pressure", ("2026-07-06", "2026-07-06"), {}),
    ]


def test_bp_create_picks_highest_matching_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = create_client(
        readings(
            reading(3005, "2026-07-06T21:06:00.0", 124, 81, 66),
            reading(3006, "2026-07-06T21:05:00.0", 125, 81, 66),
            reading(3007, "2026-07-06T21:05:00.0", 124, 80, 66),
            reading(3008, "2026-07-06T21:05:00.0", 124, 81, 67),
            reading(3004, "2026-07-06T21:05:00.0", 124, 81, 66),
            reading(3002, "2026-07-06T21:05:30.0", 124, 81, 66),
            reading(3003, "2026-07-06T21:05:00.0", 124, 81, 66),
        )
    )

    result = run(
        ["bp", "create", "124", "81", "--pulse", "66", "--at", "2026-07-06 21:05"],
        client,
        capsys,
    )

    assert result[:2] == (0, record(3004, notes="note 3004"))


@pytest.mark.parametrize(
    "stored",
    [
        readings(
            reading(3001, "2026-07-06T08:10:00.0", 124, 81, 66),
            reading(3002, "2026-07-06T21:05:00.0", 124, 81, None),
        ),
        readings(),
        {"measurementSummaries": [{}]},
        {},
    ],
)
def test_bp_create_not_listed_prints_post_answer(
    capsys: pytest.CaptureFixture[str], stored: dict[str, Any]
) -> None:
    client = create_client(stored)

    result = run(
        ["bp", "create", "124", "81", "--pulse", "66", "--at", "2026-07-06 21:05"],
        client,
        capsys,
    )

    assert result == (
        0,
        record(None, notes="after a walk"),
        "garmin: Logged blood pressure 124/81, pulse 66, at 2026-07-06 21:05.\n",
    )


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["69", "81"], "Invalid systolic '69'. Use a whole number from 70 to 260."),
        (["261", "81"], "Invalid systolic '261'. Use a whole number from 70 to 260."),
        (["abc", "81"], "Invalid systolic 'abc'. Use a whole number from 70 to 260."),
        (
            ["124.5", "81"],
            "Invalid systolic '124.5'. Use a whole number from 70 to 260.",
        ),
        (["124", "39"], "Invalid diastolic '39'. Use a whole number from 40 to 150."),
        (
            ["124", "151"],
            "Invalid diastolic '151'. Use a whole number from 40 to 150.",
        ),
        (
            ["124", "abc"],
            "Invalid diastolic 'abc'. Use a whole number from 40 to 150.",
        ),
        (
            ["124", "81", "--pulse", "19"],
            "Invalid --pulse '19'. Use a whole number from 20 to 250.",
        ),
        (
            ["124", "81", "--pulse", "251"],
            "Invalid --pulse '251'. Use a whole number from 20 to 250.",
        ),
        (
            ["124", "81", "--pulse", "abc"],
            "Invalid --pulse 'abc'. Use a whole number from 20 to 250.",
        ),
        (
            ["124", "81", "--at", "2026-07-06"],
            "Invalid --at '2026-07-06'. Use 'YYYY-MM-DD HH:MM' in local time.",
        ),
        (
            ["124", "81", "--at", "2026-07-06 25:00"],
            "Invalid --at '2026-07-06 25:00'. Use 'YYYY-MM-DD HH:MM' in local time.",
        ),
        (
            ["124"],
            "Missing diastolic for 'garmin bp create'. Run 'garmin bp create --help'.",
        ),
    ],
)
def test_bp_create_invalid_argument_exits_2(
    capsys: pytest.CaptureFixture[str], argv: list[str], message: str
) -> None:
    client = create_client()

    result = run(["bp", "create", *argv], client, capsys)

    assert result == (2, "", f"garmin: {message}\n")
    assert client.calls == []


@pytest.mark.parametrize(
    ("argv", "call"),
    [
        (["70", "40", "--pulse", "20"], ((70, 40), 20)),
        (["260", "150", "--pulse", "250"], ((260, 150), 250)),
    ],
)
def test_bp_create_accepts_range_limits(
    capsys: pytest.CaptureFixture[str], argv: list[str], call: tuple[Any, Any]
) -> None:
    client = create_client(readings())

    result = run(["bp", "create", *argv, "--at", "2026-07-06 21:05"], client, capsys)

    assert result[0] == 0
    assert client.calls[0] == (
        "set_blood_pressure",
        call[0],
        {"pulse": call[1], "timestamp": "2026-07-06T21:05:00", "notes": ""},
    )


def test_bp_create_garmin_error_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    client = create_client(posted=GarminConnectConnectionError("Server error"))

    result = run(["bp", "create", "124", "81"], client, capsys)

    assert result == (
        1,
        "",
        "garmin: Could not reach Garmin Connect (GarminConnectConnectionError: "
        "Server error). Check your internet connection and try again.\n",
    )
