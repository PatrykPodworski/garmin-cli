from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import FakeClient, run_json
from garminconnect import Garmin, GarminConnectConnectionError
from test_activities import activity_client

from garmin_cli import dates
from garmin_cli.cli import main

TYPES = [
    {"typeId": 1, "typeKey": "running"},
    {"typeId": 13, "typeKey": "strength_training"},
]
ARGS = ["activity", "add", "--type", "strength_training", "--start", "2026-07-05 18:30"]


@pytest.fixture(autouse=True)
def time_zone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TZ", "Europe/Warsaw")
    monkeypatch.setattr(dates, "LOCALTIME", tmp_path / "localtime")


def add_client(created: Any = None) -> FakeClient:
    client = activity_client()
    client.responses.update(
        get_activity_types=TYPES,
        create_manual_activity_from_json=(
            {"activityId": 101} if created is None else created
        ),
    )
    return client


def create_call(client: FakeClient) -> dict[str, Any]:
    calls = [
        call for call in client.calls if call[0] == "create_manual_activity_from_json"
    ]
    assert len(calls) == 1
    payload: dict[str, Any] = calls[0][1][0]
    return payload


def run_error(
    argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str]:
    try:
        code = main(argv, connect=lambda: client)
    except SystemExit as exit:
        code = int(exit.code or 0)
    out = capsys.readouterr()
    assert out.out == ""
    return code, out.err


def test_activity_add_creates_and_prints_the_activity(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = add_client()

    result = run_json([*ARGS, "--duration", "45", "--distance", "5.2"], client, capsys)

    payload = {
        "activityTypeDTO": {"typeKey": "strength_training"},
        "accessControlRuleDTO": {"typeId": 2, "typeKey": "private"},
        "timeZoneUnitDTO": {"unitKey": "Europe/Warsaw"},
        "activityName": "Strength Training",
        "metadataDTO": {"autoCalcCalories": True},
        "summaryDTO": {
            "startTimeLocal": "2026-07-05T18:30:00.000",
            "distance": 5200.0,
            "duration": 2700,
        },
    }
    library = Garmin.create_manual_activity(
        SimpleNamespace(create_manual_activity_from_json=lambda payload: payload),
        "2026-07-05T18:30:00.000",
        "Europe/Warsaw",
        "strength_training",
        5.2,
        45,
        "Strength Training",
    )
    assert payload == library
    assert client.calls[:2] == [
        ("get_activity_types", (), {}),
        ("create_manual_activity_from_json", (payload,), {}),
    ]
    assert client.calls[2] == ("get_activity", ("101",), {})
    assert result["id"] == 101
    assert result["laps"][0]["distance_m"] == 1000.0


def test_activity_add_takes_name_zero_distance_and_one_minute(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = add_client()

    argv = [*ARGS, "--duration", "1", "--distance", "0", "--name", "Gym"]
    run_json(argv, client, capsys)

    payload = create_call(client)
    assert payload["summaryDTO"]["distance"] == 0
    assert payload["summaryDTO"]["duration"] == 60
    assert payload["activityName"] == "Gym"


def test_activity_add_distance_defaults_to_zero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = add_client()

    run_json([*ARGS, "--duration", "45"], client, capsys)

    assert create_call(client)["summaryDTO"]["distance"] == 0


@pytest.mark.parametrize(("value", "calories"), [("266.7", 266.7), ("0.5", 0.5)])
def test_activity_add_sends_calories(
    capsys: pytest.CaptureFixture[str], value: str, calories: float
) -> None:
    client = add_client()

    run_json([*ARGS, "--duration", "65", "--calories", value], client, capsys)

    payload = create_call(client)
    assert payload["metadataDTO"] == {"autoCalcCalories": False}
    assert payload["summaryDTO"] == {
        "startTimeLocal": "2026-07-05T18:30:00.000",
        "distance": 0.0,
        "duration": 3900,
        "calories": calories,
    }


def test_activity_add_time_zone_from_tz_option(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = add_client()

    run_json([*ARGS, "--duration", "45", "--tz", "America/New_York"], client, capsys)

    assert create_call(client)["timeZoneUnitDTO"]["unitKey"] == "America/New_York"


def test_activity_add_time_zone_from_localtime_symlink(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("TZ")
    (tmp_path / "localtime").symlink_to("/var/db/timezone/zoneinfo/Asia/Tokyo")
    client = add_client()

    run_json([*ARGS, "--duration", "45"], client, capsys)

    assert create_call(client)["timeZoneUnitDTO"]["unitKey"] == "Asia/Tokyo"


def test_activity_add_empty_tz_falls_back_to_symlink(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TZ", "")
    (tmp_path / "localtime").symlink_to("../usr/share/zoneinfo/Europe/Lisbon")
    client = add_client()

    run_json([*ARGS, "--duration", "45"], client, capsys)

    assert create_call(client)["timeZoneUnitDTO"]["unitKey"] == "Europe/Lisbon"


NO_TIME_ZONE = (
    "garmin: Could not find this machine's time zone. "
    "Pass --tz, for example --tz Europe/Warsaw.\n"
)


@pytest.mark.parametrize("target", [None, "/etc/zones/CET"])
def test_activity_add_without_time_zone_exits_2(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    target: str | None,
) -> None:
    monkeypatch.delenv("TZ")
    if target:
        (tmp_path / "localtime").symlink_to(target)
    client = add_client()

    assert run_error([*ARGS, "--duration", "45"], client, capsys) == (2, NO_TIME_ZONE)
    assert client.calls == []


@pytest.mark.parametrize("option", [["--tz", "Mars/Olympus"], ["--tz", "../etc"]])
def test_activity_add_invalid_tz_option_exits_2(
    capsys: pytest.CaptureFixture[str], option: list[str]
) -> None:
    client = add_client()

    code, err = run_error([*ARGS, "--duration", "45", *option], client, capsys)

    assert (code, err) == (
        2,
        f"garmin: Unknown time zone '{option[1]}'. Pass --tz with an IANA name, "
        "for example --tz Europe/Warsaw.\n",
    )
    assert client.calls == []


def test_activity_add_invalid_tz_variable_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TZ", "CET-1CEST")
    client = add_client()

    code, err = run_error([*ARGS, "--duration", "45"], client, capsys)

    assert code == 2
    assert err.startswith("garmin: Unknown time zone 'CET-1CEST'.")


@pytest.mark.parametrize(
    ("type_key", "message"),
    [
        ("strength_trainig", "Did you mean 'strength_training'?"),
        ("yoga", "Use a Garmin type key, like running, cycling or strength_training."),
    ],
)
def test_activity_add_unknown_type_exits_2(
    capsys: pytest.CaptureFixture[str], type_key: str, message: str
) -> None:
    client = add_client()
    argv = ["activity", "add", "--type", type_key, "--start", "2026-07-05 18:30"]

    code, err = run_error([*argv, "--duration", "45"], client, capsys)

    assert (code, err) == (
        2,
        f"garmin: Unknown activity type '{type_key}'. {message}\n",
    )
    assert client.calls == [("get_activity_types", (), {})]


@pytest.mark.parametrize(
    ("option", "message"),
    [
        (
            ["--start", "2026-07-05"],
            "Invalid time '2026-07-05'. Use 'YYYY-MM-DD HH:MM', "
            "for example '2026-07-05 18:30'.",
        ),
        (["--duration", "0"], "Invalid --duration '0'. Use whole minutes, 1 or more."),
        (["--duration", "x"], "Invalid --duration 'x'. Use whole minutes, 1 or more."),
        (
            ["--distance", "-1"],
            "Invalid --distance '-1'. Use kilometers, 0 or more, like 5.2.",
        ),
        (
            ["--distance", "x"],
            "Invalid --distance 'x'. Use kilometers, 0 or more, like 5.2.",
        ),
        (
            ["--distance", "inf"],
            "Invalid --distance 'inf'. Use kilometers, 0 or more, like 5.2.",
        ),
        (
            ["--calories", "0"],
            "Invalid --calories '0'. Use kilocalories, more than 0, like 266.7.",
        ),
        (
            ["--calories", "-5"],
            "Invalid --calories '-5'. Use kilocalories, more than 0, like 266.7.",
        ),
        (
            ["--calories", "x"],
            "Invalid --calories 'x'. Use kilocalories, more than 0, like 266.7.",
        ),
        (
            ["--calories", "inf"],
            "Invalid --calories 'inf'. Use kilocalories, more than 0, like 266.7.",
        ),
    ],
)
def test_activity_add_invalid_argument_exits_2(
    capsys: pytest.CaptureFixture[str], option: list[str], message: str
) -> None:
    client = add_client()

    code, err = run_error([*ARGS, "--duration", "45", *option], client, capsys)

    assert (code, err) == (2, f"garmin: {message}\n")
    assert client.calls == []


def test_activity_add_missing_options_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, err = run_error(["activity", "add"], add_client(), capsys)

    assert (code, err) == (
        2,
        "garmin: Missing --type, --start, --duration for 'garmin activity add'. "
        "Run 'garmin activity add --help'.\n",
    )


def test_activity_add_garmin_error_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = add_client(GarminConnectConnectionError("API Error 400 - Bad request"))

    code, err = run_error([*ARGS, "--duration", "45"], client, capsys)

    assert code == 1
    assert err.startswith("garmin: Could not reach Garmin Connect")


def test_activity_add_after_debug_flag(capsys: pytest.CaptureFixture[str]) -> None:
    client = add_client()

    run_json(["--debug", *ARGS, "--duration", "45"], client, capsys)

    assert create_call(client)["activityTypeDTO"]["typeKey"] == "strength_training"


def test_activity_id_still_shows_one_activity(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = activity_client()

    assert run_json(["activity", "101"], client, capsys)["id"] == 101


def test_activity_help_names_activity_add(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["activity", "--help"])

    assert "'garmin activity add' creates" in " ".join(capsys.readouterr().out.split())
