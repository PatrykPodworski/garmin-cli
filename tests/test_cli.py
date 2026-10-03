import argparse
import json
import subprocess
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest
from garminconnect import GarminConnectAuthenticationError

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
        lambda self, argv=None: argparse.Namespace(command="stub", run=run),
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
    monkeypatch.delenv("GARMINTOKENS", raising=False)
    logins: list[str] = []

    class FakeGarmin:
        def login(self, tokenstore: str) -> None:
            logins.append(tokenstore)

    monkeypatch.setattr(cli, "Garmin", FakeGarmin)

    assert isinstance(cli.connect(), FakeGarmin)
    assert logins == ["~/.garminconnect"]


def test_connect_uses_garmintokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GARMINTOKENS", "/tokens")
    fake = FakeGarmin()
    monkeypatch.setattr(cli, "Garmin", lambda: fake)

    cli.connect()

    assert fake.tokenstore == "/tokens"


def test_connect_without_tokens_says_to_log_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NoTokens:
        def login(self, tokenstore: str) -> None:
            raise GarminConnectAuthenticationError("Username and password are required")

    monkeypatch.setattr(cli, "Garmin", NoTokens)

    with pytest.raises(RuntimeError, match="run 'garmin login'"):
        cli.connect()


class FakeGarmin:
    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        prompt_mfa: Callable[[], str] | None = None,
        needs_mfa: bool = False,
    ) -> None:
        self.email = email
        self.password = password
        self.prompt_mfa = prompt_mfa
        self.needs_mfa = needs_mfa
        self.tokenstore: str | None = None
        self.mfa_code: str | None = None

    def login(self, tokenstore: str) -> None:
        self.tokenstore = tokenstore
        if self.needs_mfa:
            assert self.prompt_mfa is not None
            self.mfa_code = self.prompt_mfa()


def no_connect() -> Any:
    raise AssertionError("login must not load saved tokens")


def fake_keychain(
    monkeypatch: pytest.MonkeyPatch, returncode: int = 0, stdout: str = "fake-pass\n"
) -> list[list[str]]:
    calls: list[list[str]] = []

    def run(args: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args, returncode, stdout, "not found")

    monkeypatch.setattr(subprocess, "run", run)
    return calls


def fake_garmin(
    monkeypatch: pytest.MonkeyPatch, needs_mfa: bool = False
) -> list[FakeGarmin]:
    clients: list[FakeGarmin] = []

    def create(email: str, password: str, prompt_mfa: Callable[[], str]) -> FakeGarmin:
        client = FakeGarmin(email, password, prompt_mfa, needs_mfa)
        clients.append(client)
        return client

    monkeypatch.setattr(cli, "Garmin", create)
    return clients


def test_login_saves_tokens(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GARMIN_EMAIL", "runner@example.com")
    monkeypatch.delenv("GARMINTOKENS", raising=False)
    calls = fake_keychain(monkeypatch)
    clients = fake_garmin(monkeypatch)

    code = main(["login"], connect=no_connect)

    assert code == 0
    assert calls == [
        [
            "security",
            "find-generic-password",
            "-s",
            "garmin",
            "-a",
            "runner@example.com",
            "-w",
        ]
    ]
    [client] = clients
    assert (client.email, client.password) == ("runner@example.com", "fake-pass")
    assert client.tokenstore == "~/.garminconnect"
    out = capsys.readouterr()
    assert json.loads(out.out) == {"tokenstore": "~/.garminconnect"}
    assert "fake-pass" not in out.out + out.err


def test_login_saves_tokens_to_garmintokens(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GARMIN_EMAIL", "runner@example.com")
    monkeypatch.setenv("GARMINTOKENS", "/tokens")
    fake_keychain(monkeypatch)
    clients = fake_garmin(monkeypatch)

    assert main(["login"], connect=no_connect) == 0
    assert clients[0].tokenstore == "/tokens"


def test_login_prompts_for_mfa_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GARMIN_EMAIL", "runner@example.com")
    fake_keychain(monkeypatch)
    clients = fake_garmin(monkeypatch, needs_mfa=True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "123456")

    assert main(["login"], connect=no_connect) == 0
    assert clients[0].mfa_code == "123456"


def test_login_without_email_names_the_variable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GARMIN_EMAIL", raising=False)
    calls = fake_keychain(monkeypatch)

    code = main(["login"], connect=no_connect)

    assert code == 1
    assert "GARMIN_EMAIL" in capsys.readouterr().err
    assert calls == []


def test_login_keychain_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GARMIN_EMAIL", "runner@example.com")
    fake_keychain(monkeypatch, returncode=44, stdout="")
    clients = fake_garmin(monkeypatch)

    code = main(["login"], connect=no_connect)

    assert code == 1
    assert "Keychain" in capsys.readouterr().err
    assert clients == []
