import io
from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError, GarminConnectNotFoundError
from test_activities import DETAIL

from garmin_cli.cli import main

PROMPT = 'Delete "Morning Run" (running, 2026-07-05 07:00)? [y/N] '
DELETED = 'garmin: Deleted "Morning Run" (2026-07-05 07:00).\n'


class Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))


def delete_client(deleted: Any = None) -> FakeClient:
    return FakeClient(get_activity=DETAIL, delete_activity=deleted)


def run(
    argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    try:
        code = main(argv, connect=lambda: client)
    except SystemExit as exit:
        code = int(exit.code or 0)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_activity_delete_with_yes_deletes_without_asking(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client()

    result = run(["activity", "delete", "0101", "--yes"], client, capsys)

    assert result == (0, '{\n  "deleted": 101\n}\n', DELETED)
    assert client.calls == [
        ("get_activity", ("101",), {}),
        ("delete_activity", ("101",), {}),
    ]


def test_activity_delete_takes_id_1(capsys: pytest.CaptureFixture[str]) -> None:
    client = delete_client()

    assert run(["activity", "delete", "1", "--yes"], client, capsys)[0] == 0
    assert client.calls[-1] == ("delete_activity", ("1",), {})


@pytest.mark.parametrize("answer", ["y\n", "yes\n", " YES \n"])
def test_activity_delete_asks_on_a_terminal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], answer: str
) -> None:
    monkeypatch.setattr("sys.stdin", Terminal(answer))
    client = delete_client()

    result = run(["activity", "delete", "101"], client, capsys)

    assert result == (0, '{\n  "deleted": 101\n}\n', PROMPT + DELETED)
    assert client.calls[-1] == ("delete_activity", ("101",), {})


@pytest.mark.parametrize("answer", ["n\n", "\n", "", "yess\n"])
def test_activity_delete_declined_deletes_nothing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], answer: str
) -> None:
    monkeypatch.setattr("sys.stdin", Terminal(answer))
    client = delete_client()

    result = run(["activity", "delete", "101"], client, capsys)

    assert result == (1, "", PROMPT + "garmin: Nothing deleted.\n")
    assert client.calls == [("get_activity", ("101",), {})]


def test_activity_delete_without_terminal_needs_yes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = delete_client()

    result = run(["activity", "delete", "101"], client, capsys)

    assert result == (
        2,
        "",
        "garmin: Cannot ask to confirm the deletion: stdin is not a terminal. "
        "Pass --yes to delete without asking.\n",
    )
    assert client.calls == []


def test_activity_delete_unknown_id_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get_activity=GarminConnectNotFoundError("404"))

    result = run(["activity", "delete", "999", "--yes"], client, capsys)

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

    result = run(["activity", "delete", value, "--yes"], client, capsys)

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
    client = delete_client(GarminConnectConnectionError("API Error 500"))

    code, out, err = run(["activity", "delete", "101", "--yes"], client, capsys)

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
