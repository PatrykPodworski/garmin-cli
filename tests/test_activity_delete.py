from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError, GarminConnectNotFoundError
from test_activities import DETAIL

from garmin_cli.cli import main

DELETED = 'garmin: Deleted "Morning Run" (2026-07-05 07:00).\n'


def delete_client(detail: Any = DETAIL, deleted: Any = None) -> FakeClient:
    return FakeClient(get_activity=detail, delete_activity=deleted)


def run(
    argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    try:
        code = main(argv, connect=lambda: client)
    except SystemExit as exit:
        code = int(exit.code or 0)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_activity_delete_deletes_without_asking(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client()

    result = run(["activity", "delete", "0101"], client, capsys)

    assert result == (0, '{\n  "deleted": 101\n}\n', DELETED)
    assert client.calls == [
        ("get_activity", ("101",), {}),
        ("delete_activity", ("101",), {}),
    ]


def test_activity_delete_takes_id_1(capsys: pytest.CaptureFixture[str]) -> None:
    client = delete_client()

    assert run(["activity", "delete", "1"], client, capsys)[0] == 0
    assert client.calls[-1] == ("delete_activity", ("1",), {})


def test_activity_delete_dry_run_deletes_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client()

    result = run(["activity", "delete", "101", "--dry-run"], client, capsys)

    assert result == (
        0,
        '{\n  "would_delete": 101\n}\n',
        'garmin: Would delete "Morning Run" (2026-07-05 07:00).\n',
    )
    assert client.calls == [("get_activity", ("101",), {})]


@pytest.mark.parametrize(
    ("detail", "line"),
    [
        (
            {"summaryDTO": {"startTimeLocal": "2026-07-05T07:00:00.0"}},
            "activity 101 (2026-07-05 07:00)",
        ),
        (
            {
                "activityName": None,
                "summaryDTO": {"startTimeLocal": "2026-07-05T07:00"},
            },
            "activity 101 (2026-07-05 07:00)",
        ),
        ({"activityName": "Morning Run", "summaryDTO": {}}, '"Morning Run"'),
        ({"activityName": "Morning Run", "summaryDTO": None}, '"Morning Run"'),
        ({}, "activity 101"),
    ],
)
def test_activity_delete_missing_fields_still_deletes(
    capsys: pytest.CaptureFixture[str], detail: dict[str, Any], line: str
) -> None:
    client = delete_client(detail)

    result = run(["activity", "delete", "101"], client, capsys)

    assert result == (0, '{\n  "deleted": 101\n}\n', f"garmin: Deleted {line}.\n")
    assert client.calls[-1] == ("delete_activity", ("101",), {})


def test_activity_delete_unknown_id_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get_activity=GarminConnectNotFoundError("404"))

    result = run(["activity", "delete", "999"], client, capsys)

    assert result == (
        1,
        "",
        "garmin: No activity with ID 999. Run 'garmin activities' to list recent "
        "IDs.\n",
    )
    assert client.calls == [("get_activity", ("999",), {})]


@pytest.mark.parametrize("value", ["abc", "0", "-5", "1.5"])
def test_activity_delete_invalid_id_exits_2(
    capsys: pytest.CaptureFixture[str], value: str
) -> None:
    client = delete_client()

    result = run(["activity", "delete", value], client, capsys)

    assert result == (
        2,
        "",
        f"garmin: Invalid activity ID '{value}'. Run 'garmin activities' to list "
        "IDs.\n",
    )
    assert client.calls == []


def test_activity_delete_missing_id_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = run(["activity", "delete"], delete_client(), capsys)

    assert result == (
        2,
        "",
        "garmin: Missing activity ID. Run 'garmin activities' to list IDs, then "
        "'garmin activity delete <id>'.\n",
    )


def test_activity_delete_garmin_error_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client(deleted=GarminConnectConnectionError("API Error 500"))

    code, out, err = run(["activity", "delete", "101"], client, capsys)

    assert (code, out) == (1, "")
    assert err.startswith("garmin: Could not reach Garmin Connect")
    assert "Deleted" not in err


def test_activity_help_names_activity_delete(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        main(["activity", "--help"])

    assert "'garmin activity delete' deletes" in " ".join(
        capsys.readouterr().out.split()
    )


def test_garmin_help_leaves_out_activity_delete(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])

    assert "activity delete" not in capsys.readouterr().out
