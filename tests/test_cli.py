import argparse
import json
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest

from garmin_cli import cli
from garmin_cli.cli import add_date_argument, main


def parse(*argv: str) -> date:
    parser = argparse.ArgumentParser()
    add_date_argument(parser)
    day: date = parser.parse_args(argv).date
    return day


def test_date_defaults_to_today() -> None:
    assert parse() == date.today()


def test_date_today() -> None:
    assert parse("today") == date.today()


def test_date_yesterday() -> None:
    assert parse("yesterday") == date.today() - timedelta(days=1)


def test_date_iso() -> None:
    assert parse("2026-07-05") == date(2026, 7, 5)


@pytest.mark.parametrize("value", ["2026-13-01", "tomorrow", "05.07.2026"])
def test_invalid_date_exits_2_with_message(
    value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit:
        parse(value)

    assert exit.value.code == 2
    assert value in capsys.readouterr().err


def test_help_exits_0(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit:
        main(["--help"])

    assert exit.value.code == 0
    assert "usage: garmin" in capsys.readouterr().out


def run_main(
    monkeypatch: pytest.MonkeyPatch, run: Callable[[argparse.Namespace, Any], Any]
) -> int:
    # No subcommand is registered yet, so stub the parser to hand `main` one.
    monkeypatch.setattr(
        argparse.ArgumentParser,
        "parse_args",
        lambda self, argv=None: argparse.Namespace(run=run),
    )
    client = object()
    return main([], connect=lambda: client)


def test_main_prints_result_as_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run_main(monkeypatch, lambda args, client: {"steps": 1234})

    assert code == 0
    out = capsys.readouterr()
    assert json.loads(out.out) == {"steps": 1234}
    assert out.err == ""


def test_main_reports_error_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(args: argparse.Namespace, client: Any) -> Any:
        raise RuntimeError("not synced")

    code = run_main(monkeypatch, fail)

    assert code == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == "garmin: not synced\n"


def test_connect_logs_in_with_tokenstore(monkeypatch: pytest.MonkeyPatch) -> None:
    logins: list[str] = []

    class FakeGarmin:
        def login(self, tokenstore: str) -> None:
            logins.append(tokenstore)

    monkeypatch.setattr(cli, "Garmin", FakeGarmin)

    assert isinstance(cli.connect(), FakeGarmin)
    assert logins == ["~/.garminconnect"]
