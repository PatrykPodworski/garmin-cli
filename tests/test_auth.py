import json
import subprocess
from collections.abc import Callable
from typing import Any

import pytest
from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

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
    monkeypatch.setenv("GARMINTOKENS", "/tokens")

    class NoTokens:
        def login(self, tokenstore: str) -> None:
            raise GarminConnectAuthenticationError("Username and password are required")

    monkeypatch.setattr(auth, "Garmin", NoTokens)

    with pytest.raises(GarminCliError) as error:
        auth.connect()

    assert str(error.value) == (
        "Not logged in: no valid saved login in /tokens. Run 'garmin login'."
    )


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
            # garminconnect wraps whatever prompt_mfa raises.
            try:
                self.mfa_code = self.prompt_mfa()
            except Exception as error:
                raise GarminConnectConnectionError(f"Login failed: {error}") from error


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


def assert_login_error(capsys: pytest.CaptureFixture[str], code: int, err: str) -> None:
    assert code == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == f"garmin: {err}\n"
    assert "fake-pass" not in out.err


def test_login_without_email_names_the_variable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GARMIN_EMAIL", raising=False)
    calls = fake_keychain(monkeypatch)

    code = main(["login"], connect=no_connect)

    assert_login_error(
        capsys,
        code,
        "GARMIN_EMAIL is not set. Run 'export GARMIN_EMAIL=you@example.com' "
        "with your Garmin account email.",
    )
    assert calls == []


def test_login_without_keychain_entry(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GARMIN_EMAIL", "runner@example.com")
    fake_keychain(monkeypatch, returncode=44, stdout="")
    clients = fake_garmin(monkeypatch)

    code = main(["login"], connect=no_connect)

    assert_login_error(
        capsys,
        code,
        "No Keychain password for account runner@example.com (service 'garmin'). "
        "Add it with 'security add-generic-password -s garmin -a "
        "runner@example.com -w'.",
    )
    assert clients == []


def test_login_without_security_tool(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GARMIN_EMAIL", "runner@example.com")
    monkeypatch.setenv("GARMINTOKENS", "/tokens")

    def run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(2, "No such file or directory", "security")

    monkeypatch.setattr(subprocess, "run", run)

    code = main(["login"], connect=no_connect)

    assert_login_error(
        capsys,
        code,
        "'garmin login' reads the password from the macOS Keychain, which is not "
        "available here. Log in on a Mac and copy /tokens to this machine, or set "
        "GARMINTOKENS to a copied token folder.",
    )


def failing_garmin(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    class FailingGarmin(FakeGarmin):
        def login(self, tokenstore: str) -> None:
            raise error

    monkeypatch.setattr(auth, "Garmin", FailingGarmin)


def test_login_rejected_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GARMIN_EMAIL", "runner@example.com")
    fake_keychain(monkeypatch)
    failing_garmin(monkeypatch, GarminConnectAuthenticationError("401 fake-pass"))

    code = main(["login"], connect=no_connect)

    assert_login_error(
        capsys,
        code,
        "Garmin rejected the login for runner@example.com. Check the Keychain "
        "password for service 'garmin' and run 'garmin login' again.",
    )


def test_login_rate_limited(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GARMIN_EMAIL", "runner@example.com")
    fake_keychain(monkeypatch)
    failing_garmin(monkeypatch, GarminConnectTooManyRequestsError("429"))

    code = main(["login"], connect=no_connect)

    assert_login_error(
        capsys,
        code,
        "Garmin is rate-limiting logins from this machine. Wait about an hour, "
        "then run 'garmin login' again.",
    )


def test_login_connection_error_passes_through(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GARMIN_EMAIL", "runner@example.com")
    fake_keychain(monkeypatch)
    failing_garmin(monkeypatch, GarminConnectConnectionError("Login failed: timeout"))

    code = main(["login"], connect=no_connect)

    assert_login_error(capsys, code, "Login failed: timeout")


def mfa_answer(monkeypatch: pytest.MonkeyPatch, answer: Callable[[str], str]) -> None:
    monkeypatch.setenv("GARMIN_EMAIL", "runner@example.com")
    fake_keychain(monkeypatch)
    fake_garmin(monkeypatch, needs_mfa=True)
    monkeypatch.setattr("builtins.input", answer)


NO_MFA_CODE = (
    "No MFA code entered. Run 'garmin login' in a terminal and type the code from "
    "your Garmin app or email."
)


def test_login_mfa_end_of_input(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def end_of_input(prompt: str) -> str:
        raise EOFError

    mfa_answer(monkeypatch, end_of_input)

    assert_login_error(capsys, main(["login"], connect=no_connect), NO_MFA_CODE)


def test_login_mfa_empty_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mfa_answer(monkeypatch, lambda prompt: "")

    assert_login_error(capsys, main(["login"], connect=no_connect), NO_MFA_CODE)
