import json
import subprocess
from collections.abc import Callable
from typing import Any

import pytest
from garminconnect import GarminConnectAuthenticationError

from garmin_cli import auth
from garmin_cli.cli import main
from garmin_cli.errors import GarminCliError


def test_connect_logs_in_with_tokenstore(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GARMINTOKENS", raising=False)
    logins: list[str] = []

    class FakeGarmin:
        def login(self, tokenstore: str) -> None:
            logins.append(tokenstore)

    monkeypatch.setattr(auth, "Garmin", FakeGarmin)

    assert isinstance(auth.connect(), FakeGarmin)
    assert logins == ["~/.garminconnect"]


def test_connect_uses_garmintokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GARMINTOKENS", "/tokens")
    fake = FakeGarmin()
    monkeypatch.setattr(auth, "Garmin", lambda: fake)

    auth.connect()

    assert fake.tokenstore == "/tokens"


def test_connect_without_tokens_says_to_log_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NoTokens:
        def login(self, tokenstore: str) -> None:
            raise GarminConnectAuthenticationError("Username and password are required")

    monkeypatch.setattr(auth, "Garmin", NoTokens)

    with pytest.raises(GarminCliError) as error:
        auth.connect()

    assert str(error.value) == "No valid saved tokens. Run 'garmin login'."


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

    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert kwargs == {"capture_output": True, "text": True}
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

    monkeypatch.setattr(auth, "Garmin", create)
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
    prompts: list[str] = []

    def answer(prompt: str) -> str:
        prompts.append(prompt)
        return "123456"

    monkeypatch.setattr("builtins.input", answer)

    assert main(["login"], connect=no_connect) == 0
    assert prompts == ["MFA code: "]
    assert clients[0].mfa_code == "123456"


# Keychain passwords may end in any character; only the newline `security`
# appends is stripped.
@pytest.mark.parametrize("password", ["fake-pass ", "fake-passX"])
def test_login_keeps_trailing_password_characters(
    password: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GARMIN_EMAIL", "runner@example.com")
    fake_keychain(monkeypatch, stdout=password + "\n")
    clients = fake_garmin(monkeypatch)

    assert main(["login"], connect=no_connect) == 0
    assert clients[0].password == password


def test_login_without_email_names_the_variable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GARMIN_EMAIL", raising=False)
    calls = fake_keychain(monkeypatch)

    code = main(["login"], connect=no_connect)

    assert code == 1
    assert (
        capsys.readouterr().err
        == "garmin: GARMIN_EMAIL is not set. Set it to your Garmin account email.\n"
    )
    assert calls == []


def test_login_keychain_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GARMIN_EMAIL", "runner@example.com")
    fake_keychain(monkeypatch, returncode=44, stdout="")
    clients = fake_garmin(monkeypatch)

    code = main(["login"], connect=no_connect)

    assert code == 1
    assert capsys.readouterr().err == (
        "garmin: No Keychain password for service 'garmin', "
        "account runner@example.com. Add it as the README shows.\n"
    )
    assert clients == []


def test_login_rejected_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GARMIN_EMAIL", "runner@example.com")
    fake_keychain(monkeypatch)

    class RejectingGarmin(FakeGarmin):
        def login(self, tokenstore: str) -> None:
            raise GarminConnectAuthenticationError("401 Unauthorized")

    monkeypatch.setattr(auth, "Garmin", RejectingGarmin)

    code = main(["login"], connect=no_connect)

    assert code == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == "garmin: 401 Unauthorized\n"
