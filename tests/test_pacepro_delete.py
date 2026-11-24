from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError, GarminConnectNotFoundError
from test_pacepro import LIST_IDS, PLAN, PLAN_PATH, run

DELETED = 'garmin: Deleted PacePro plan "Test Hills 10k".\n'


def delete_client(plan: Any = PLAN, deleted: Any = None) -> FakeClient:
    # Garmin answers the delete with 204, which garminconnect returns as `{}`.
    client = FakeClient(connectapi=plan, delete={} if deleted is None else deleted)
    client.client = client
    return client


def test_pacepro_delete_deletes_without_asking(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client()

    result = run(["pacepro", "delete", "0501"], client, capsys)

    assert result == (0, '{\n  "deleted": 501\n}\n', DELETED)
    assert client.calls == [
        ("connectapi", (PLAN_PATH,), {}),
        ("delete", ("connectapi", PLAN_PATH), {"api": True}),
    ]


def test_pacepro_delete_dry_run_deletes_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client()

    result = run(["pacepro", "delete", "501", "--dry-run"], client, capsys)

    assert result == (
        0,
        '{\n  "would_delete": 501\n}\n',
        'garmin: Would delete PacePro plan "Test Hills 10k".\n',
    )
    assert client.calls == [("connectapi", (PLAN_PATH,), {})]


@pytest.mark.parametrize(
    "plan",
    [
        {"paceBandPk": 501},
        {"paceBandPk": 501, "paceBandSummary": None},
        {"paceBandPk": 501, "paceBandSummary": {"name": None}},
    ],
)
def test_pacepro_delete_without_name_shows_id(
    capsys: pytest.CaptureFixture[str], plan: dict[str, Any]
) -> None:
    client = delete_client(plan)

    result = run(["pacepro", "delete", "501"], client, capsys)

    assert result == (
        0,
        '{\n  "deleted": 501\n}\n',
        "garmin: Deleted PacePro plan 501.\n",
    )


def test_pacepro_delete_unknown_id_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client(GarminConnectNotFoundError("404"))

    result = run(["pacepro", "delete", "999"], client, capsys)

    assert result == (1, "", f"garmin: No PacePro plan with ID 999. {LIST_IDS}\n")
    assert client.calls == [("connectapi", ("/course-service/pacebands/999",), {})]


@pytest.mark.parametrize("value", ["abc", "0", "-5", "1.5"])
def test_pacepro_delete_invalid_id_exits_2(
    capsys: pytest.CaptureFixture[str], value: str
) -> None:
    client = delete_client()

    result = run(["pacepro", "delete", "--", value], client, capsys)

    assert result == (
        2,
        "",
        f"garmin: Invalid PacePro plan ID '{value}'. {LIST_IDS}\n",
    )
    assert client.calls == []


def test_pacepro_delete_missing_id_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = run(["pacepro", "delete"], delete_client(), capsys)

    assert result == (
        2,
        "",
        "garmin: Missing pacepro ID. Run 'garmin pacepro list' to list IDs, then "
        "'garmin pacepro delete <id>'.\n",
    )


def test_pacepro_delete_garmin_error_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client(deleted=GarminConnectConnectionError("API Error 500"))

    code, out, err = run(["pacepro", "delete", "501"], client, capsys)

    assert (code, out) == (1, "")
    assert err.startswith("garmin: Could not reach Garmin Connect")
    assert "Deleted" not in err
