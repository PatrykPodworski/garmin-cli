from datetime import date
from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError

from garmin_cli.cli import main

READINGS = {
    "measurementSummaries": [
        {
            "startDate": "2026-07-05",
            "measurements": [
                {
                    "version": 2001,
                    "measurementTimestampLocal": "2026-07-05T08:15:00.0",
                    "systolic": 118,
                    "diastolic": 76,
                },
                {
                    "version": 2002,
                    "measurementTimestampLocal": "2026-07-05T21:40:30.0",
                    "systolic": 121,
                    "diastolic": 79,
                },
            ],
        }
    ]
}
WHAT = "the reading of 2026-07-05 21:40 (121/79)"


def delete_client(readings: Any = READINGS, deleted: Any = None) -> FakeClient:
    return FakeClient(get_blood_pressure=readings, delete_blood_pressure=deleted)


def run(
    argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    try:
        code = main(argv, connect=lambda: client)
    except SystemExit as exit:
        code = int(exit.code or 0)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_bp_delete_deletes_without_asking(capsys: pytest.CaptureFixture[str]) -> None:
    client = delete_client()

    result = run(["bp", "delete", "02002", "--date", "2026-07-05"], client, capsys)

    assert result == (0, '{\n  "deleted": 2002\n}\n', f"garmin: Deleted {WHAT}.\n")
    assert client.calls == [
        ("get_blood_pressure", ("2026-07-05", "2026-07-05"), {}),
        ("delete_blood_pressure", ("2002", "2026-07-05"), {}),
    ]


def test_bp_delete_takes_a_relative_date(capsys: pytest.CaptureFixture[str]) -> None:
    client = delete_client()

    assert run(["bp", "delete", "2002", "--date", "today"], client, capsys)[0] == 0
    today = date.today().isoformat()
    assert client.calls[-1] == ("delete_blood_pressure", ("2002", today), {})


def test_bp_delete_takes_id_1(capsys: pytest.CaptureFixture[str]) -> None:
    reading = {
        "version": 1,
        "measurementTimestampLocal": "2026-07-05T08:15:00.0",
        "systolic": 118,
        "diastolic": 76,
    }
    client = delete_client({"measurementSummaries": [{"measurements": [reading]}]})

    result = run(["bp", "delete", "1", "--date", "2026-07-05"], client, capsys)

    assert result[2] == "garmin: Deleted the reading of 2026-07-05 08:15 (118/76).\n"
    assert client.calls[-1] == ("delete_blood_pressure", ("1", "2026-07-05"), {})


def test_bp_delete_dry_run_deletes_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client()

    result = run(
        ["bp", "delete", "2002", "--date", "2026-07-05", "--dry-run"], client, capsys
    )

    assert result == (
        0,
        '{\n  "would_delete": 2002\n}\n',
        f"garmin: Would delete {WHAT}.\n",
    )
    assert client.calls == [("get_blood_pressure", ("2026-07-05", "2026-07-05"), {})]


@pytest.mark.parametrize(
    "readings",
    [
        READINGS,
        {"measurementSummaries": []},
        {"measurementSummaries": [{}]},
        {},
    ],
)
def test_bp_delete_unknown_id_exits_1(
    capsys: pytest.CaptureFixture[str], readings: dict[str, Any]
) -> None:
    client = delete_client(readings)

    result = run(["bp", "delete", "999", "--date", "2026-07-05"], client, capsys)

    assert result == (
        1,
        "",
        "garmin: No blood pressure reading with ID 999 on 2026-07-05. Run 'garmin bp "
        "--from 2026-07-05 --to 2026-07-05' to list its IDs.\n",
    )
    assert client.calls == [("get_blood_pressure", ("2026-07-05", "2026-07-05"), {})]


@pytest.mark.parametrize("value", ["abc", "0", "-5", "1.5"])
def test_bp_delete_invalid_id_exits_2(
    capsys: pytest.CaptureFixture[str], value: str
) -> None:
    client = delete_client()

    result = run(["bp", "delete", value, "--date", "2026-07-05"], client, capsys)

    assert result == (
        2,
        "",
        f"garmin: Invalid reading ID '{value}'. Run 'garmin bp --from DATE "
        "--to DATE' to list IDs.\n",
    )
    assert client.calls == []


def test_bp_delete_invalid_date_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    client = delete_client()

    result = run(["bp", "delete", "2002", "--date", "2026-13-01"], client, capsys)

    assert result == (
        2,
        "",
        "garmin: Invalid date '2026-13-01'. Use today, yesterday, tomorrow or "
        "YYYY-MM-DD.\n",
    )
    assert client.calls == []


def test_bp_delete_missing_date_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    client = delete_client()

    result = run(["bp", "delete", "2002"], client, capsys)

    assert result == (
        2,
        "",
        "garmin: Missing --date for 'garmin bp delete'. Run 'garmin bp delete "
        "--help'.\n",
    )
    assert client.calls == []


def test_bp_delete_missing_id_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    client = delete_client()

    result = run(["bp", "delete", "--date", "2026-07-05"], client, capsys)

    assert result == (
        2,
        "",
        "garmin: Missing bp ID. Run 'garmin bp --from DATE --to DATE' to list IDs, "
        "then 'garmin bp delete <id>'.\n",
    )
    assert client.calls == []


def test_bp_delete_garmin_error_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    client = delete_client(deleted=GarminConnectConnectionError("Server error"))

    result = run(["bp", "delete", "2002", "--date", "2026-07-05"], client, capsys)

    assert result == (
        1,
        "",
        "garmin: Could not reach Garmin Connect (GarminConnectConnectionError: "
        "Server error). Check your internet connection and try again.\n",
    )


def test_bp_unknown_command_lists_delete(capsys: pytest.CaptureFixture[str]) -> None:
    client = delete_client()

    result = run(["bp", "120"], client, capsys)

    assert result == (
        2,
        "",
        "garmin: Unknown command '120'. Run 'garmin bp <command>', one of: delete.\n",
    )
    assert client.calls == []


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (
            ["--from", "today"],
            "Unknown option '--from' for 'garmin bp delete'. Run 'garmin bp delete "
            "--help' for all options.",
        ),
        (
            ["extra"],
            "Unexpected argument 'extra' for 'garmin bp delete'. Run 'garmin bp "
            "delete --help' for all options.",
        ),
    ],
)
def test_bp_delete_extra_argument_exits_2(
    capsys: pytest.CaptureFixture[str], extra: list[str], message: str
) -> None:
    client = delete_client()

    result = run(
        ["bp", "delete", "2002", "--date", "2026-07-05", *extra], client, capsys
    )

    assert result == (2, "", f"garmin: {message}\n")
    assert client.calls == []
