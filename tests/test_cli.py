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


class FakeStats:
    def __init__(self, stats: dict[str, Any]) -> None:
        self.stats = stats
        self.dates: list[str] = []

    def get_stats(self, cdate: str) -> dict[str, Any]:
        self.dates.append(cdate)
        return self.stats


SYNCED_DAY = {
    "calendarDate": "2026-07-05",
    "totalKilocalories": 2400.0,
    "activeKilocalories": 600.0,
    "bmrKilocalories": 1800.0,
    "restingHeartRate": 55,
    "bodyBatteryHighestValue": 90,
    "bodyBatteryLowestValue": 20,
    "averageStressLevel": 30,
    "totalSteps": 1000,
}


def test_stats_prints_summary(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeStats(SYNCED_DAY)

    code = main(["stats", "2026-07-05"], connect=lambda: client)

    assert code == 0
    assert client.dates == ["2026-07-05"]
    out = capsys.readouterr()
    assert json.loads(out.out) == {
        "date": "2026-07-05",
        "total_kcal": 2400.0,
        "active_kcal": 600.0,
        "bmr_kcal": 1800.0,
        "resting_hr": 55,
        "body_battery_high": 90,
        "body_battery_low": 20,
        "avg_stress": 30,
    }
    assert out.err == ""


def test_stats_missing_optional_fields_are_null(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeStats({"totalKilocalories": 2400.0})

    assert main(["stats", "2026-07-05"], connect=lambda: client) == 0
    assert json.loads(capsys.readouterr().out) == {
        "date": "2026-07-05",
        "total_kcal": 2400.0,
        "active_kcal": None,
        "bmr_kcal": None,
        "resting_hr": None,
        "body_battery_high": None,
        "body_battery_low": None,
        "avg_stress": None,
    }


@pytest.mark.parametrize(
    "stats", [{"calendarDate": "2026-07-05"}, {"totalKilocalories": None}]
)
def test_stats_not_synced_exits_1(
    stats: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["stats", "2026-07-05"], connect=lambda: FakeStats(stats))

    assert code == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == "garmin: 2026-07-05 is not synced (no totalKilocalories)\n"


def test_stats_raw_prints_full_response(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["stats", "--raw", "2026-07-05"], connect=lambda: FakeStats(SYNCED_DAY))

    assert code == 0
    assert json.loads(capsys.readouterr().out) == SYNCED_DAY


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


class FakeHealth:
    def __init__(self, weigh_ins: Any = None, blood_pressure: Any = None) -> None:
        self.weigh_ins = weigh_ins
        self.blood_pressure = blood_pressure
        self.calls: list[tuple[str, str, str]] = []

    def get_weigh_ins(self, startdate: str, enddate: str) -> Any:
        self.calls.append(("get_weigh_ins", startdate, enddate))
        return self.weigh_ins

    def get_blood_pressure(self, startdate: str, enddate: str) -> Any:
        self.calls.append(("get_blood_pressure", startdate, enddate))
        return self.blood_pressure


def run_health(
    client: FakeHealth, capsys: pytest.CaptureFixture[str], *argv: str
) -> Any:
    assert main(list(argv), connect=lambda: client) == 0
    return json.loads(capsys.readouterr().out)


WEIGH_INS = {
    "dailyWeightSummaries": [
        {
            "summaryDate": "2026-07-05",
            "allWeightMetrics": [
                {
                    "calendarDate": "2026-07-05",
                    # Local wall-clock time encoded as epoch ms.
                    "date": 1783236900000,
                    "weight": 70500.0,
                    "bodyFat": 18.5,
                    "muscleMass": 31250.0,
                    "bodyWater": 55.2,
                },
                {
                    "calendarDate": "2026-07-05",
                    "date": 1783275600000,
                    "weight": 71000.0,
                    "bodyFat": None,
                },
            ],
        }
    ]
}


def test_weight_records_per_weigh_in(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeHealth(weigh_ins=WEIGH_INS)

    records = run_health(
        client, capsys, "weight", "--from", "2026-07-01", "--to", "2026-07-05"
    )

    assert client.calls == [("get_weigh_ins", "2026-07-01", "2026-07-05")]
    assert records == [
        {
            "date": "2026-07-05",
            "time": "07:35:00",
            "weight_kg": 70.5,
            "body_fat_pct": 18.5,
            "muscle_mass_kg": 31.25,
            "body_water_pct": 55.2,
        },
        {
            "date": "2026-07-05",
            "time": "18:20:00",
            "weight_kg": 71.0,
            "body_fat_pct": None,
            "muscle_mass_kg": None,
            "body_water_pct": None,
        },
    ]


def test_weight_empty_range(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeHealth(weigh_ins={"dailyWeightSummaries": []})

    assert run_health(client, capsys, "weight", "--from", "2026-07-01") == []
    assert client.calls == [("get_weigh_ins", "2026-07-01", date.today().isoformat())]


BLOOD_PRESSURE = {
    "measurementSummaries": [
        {
            "startDate": "2026-07-05",
            "measurements": [
                {
                    "measurementTimestampLocal": "2026-07-05T08:15:00.0",
                    "systolic": 118,
                    "diastolic": 76,
                    "pulse": 62,
                    "notes": "after coffee",
                },
                {
                    "measurementTimestampLocal": "2026-07-05T21:40:30.0",
                    "systolic": 121,
                    "diastolic": 79,
                },
            ],
        }
    ]
}


def test_bp_records_per_reading(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeHealth(blood_pressure=BLOOD_PRESSURE)

    records = run_health(
        client, capsys, "bp", "--from", "2026-07-01", "--to", "2026-07-05"
    )

    assert client.calls == [("get_blood_pressure", "2026-07-01", "2026-07-05")]
    assert records == [
        {
            "date": "2026-07-05",
            "time": "08:15:00",
            "systolic": 118,
            "diastolic": 76,
            "pulse": 62,
            "notes": "after coffee",
        },
        {
            "date": "2026-07-05",
            "time": "21:40:30",
            "systolic": 121,
            "diastolic": 79,
            "pulse": None,
            "notes": None,
        },
    ]


def test_bp_empty_range(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeHealth(blood_pressure={"measurementSummaries": []})

    assert run_health(client, capsys, "bp") == []
    today = date.today().isoformat()
    assert client.calls == [("get_blood_pressure", today, today)]
