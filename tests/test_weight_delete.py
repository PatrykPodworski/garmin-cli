from datetime import date
from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError

from garmin_cli.cli import main

WEIGH_INS = {
    "dailyWeightSummaries": [
        {
            "summaryDate": "2026-07-05",
            "allWeightMetrics": [
                {"samplePk": 1001, "date": 1783236900000, "weight": 70500.0},
                {"samplePk": 1002, "date": 1783275600000, "weight": 71234.5},
            ],
        }
    ]
}
WHAT = "the weigh-in of 2026-07-05 18:20 (71.23 kg)"


def delete_client(weigh_ins: Any = WEIGH_INS, deleted: Any = None) -> FakeClient:
    return FakeClient(get_weigh_ins=weigh_ins, delete_weigh_in=deleted)


def run(
    argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    try:
        code = main(argv, connect=lambda: client)
    except SystemExit as exit:
        code = int(exit.code or 0)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_weight_delete_deletes_without_asking(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client()

    result = run(["weight", "delete", "01002", "--date", "2026-07-05"], client, capsys)

    assert result == (0, '{\n  "deleted": 1002\n}\n', f"garmin: Deleted {WHAT}.\n")
    assert client.calls == [
        ("get_weigh_ins", ("2026-07-05", "2026-07-05"), {}),
        ("delete_weigh_in", ("1002", "2026-07-05"), {}),
    ]


def test_weight_delete_takes_a_relative_date(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client()

    assert run(["weight", "delete", "1002", "--date", "today"], client, capsys)[0] == 0
    today = date.today().isoformat()
    assert client.calls[-1] == ("delete_weigh_in", ("1002", today), {})


def test_weight_delete_takes_id_1(capsys: pytest.CaptureFixture[str]) -> None:
    metric = {"samplePk": 1, "date": 1783236900000, "weight": 70500.0}
    client = delete_client({"dailyWeightSummaries": [{"allWeightMetrics": [metric]}]})

    assert (
        run(["weight", "delete", "1", "--date", "2026-07-05"], client, capsys)[0] == 0
    )
    assert client.calls[-1] == ("delete_weigh_in", ("1", "2026-07-05"), {})


def test_weight_delete_dry_run_deletes_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client()

    result = run(
        ["weight", "delete", "1002", "--date", "2026-07-05", "--dry-run"],
        client,
        capsys,
    )

    assert result == (
        0,
        '{\n  "would_delete": 1002\n}\n',
        f"garmin: Would delete {WHAT}.\n",
    )
    assert client.calls == [("get_weigh_ins", ("2026-07-05", "2026-07-05"), {})]


@pytest.mark.parametrize(
    "weigh_ins",
    [
        WEIGH_INS,
        {"dailyWeightSummaries": []},
        {"dailyWeightSummaries": [{}]},
        {},
    ],
)
def test_weight_delete_unknown_id_exits_1(
    capsys: pytest.CaptureFixture[str], weigh_ins: dict[str, Any]
) -> None:
    client = delete_client(weigh_ins)

    result = run(["weight", "delete", "999", "--date", "2026-07-05"], client, capsys)

    assert result == (
        1,
        "",
        "garmin: No weigh-in with ID 999 on 2026-07-05. Run 'garmin weight --from "
        "2026-07-05 --to 2026-07-05' to list its IDs.\n",
    )
    assert client.calls == [("get_weigh_ins", ("2026-07-05", "2026-07-05"), {})]


@pytest.mark.parametrize("value", ["abc", "0", "-5", "1.5"])
def test_weight_delete_invalid_id_exits_2(
    capsys: pytest.CaptureFixture[str], value: str
) -> None:
    client = delete_client()

    result = run(["weight", "delete", value, "--date", "2026-07-05"], client, capsys)

    assert result == (
        2,
        "",
        f"garmin: Invalid weigh-in ID '{value}'. Run 'garmin weight --from DATE "
        "--to DATE' to list IDs.\n",
    )
    assert client.calls == []


def test_weight_delete_invalid_date_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client()

    result = run(["weight", "delete", "1002", "--date", "2026-13-01"], client, capsys)

    assert result == (
        2,
        "",
        "garmin: Invalid date '2026-13-01'. Use today, yesterday, tomorrow or "
        "YYYY-MM-DD.\n",
    )
    assert client.calls == []


def test_weight_delete_missing_date_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client()

    result = run(["weight", "delete", "1002"], client, capsys)

    assert result == (
        2,
        "",
        "garmin: Missing --date for 'garmin weight delete'. Run 'garmin weight "
        "delete --help'.\n",
    )
    assert client.calls == []


def test_weight_delete_garmin_error_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client(deleted=GarminConnectConnectionError("Server error"))

    result = run(["weight", "delete", "1002", "--date", "2026-07-05"], client, capsys)

    assert result == (
        1,
        "",
        "garmin: Could not reach Garmin Connect (GarminConnectConnectionError: "
        "Server error). Check your internet connection and try again.\n",
    )


def test_weight_delete_missing_id_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    client = delete_client()

    result = run(["weight", "delete", "--date", "2026-07-05"], client, capsys)

    assert result == (
        2,
        "",
        "garmin: Missing weight ID. Run 'garmin weight --from DATE --to DATE' to "
        "list IDs, then 'garmin weight delete <id>'.\n",
    )
    assert client.calls == []
