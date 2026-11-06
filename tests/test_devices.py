from typing import Any

import pytest
from conftest import FakeClient, run_json

from garmin_cli.cli import main

WATCH = {
    "deviceId": 3333,
    "displayName": "Test Watch",
    "productDisplayName": "Test Model 6",
    "softwareVersion": "1.00",
}
SCALE = {"deviceId": 4444, "productDisplayName": "Test Scale"}


def test_device_list_summarizes_each_device(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get_devices=[WATCH, SCALE])

    assert run_json(["device", "list"], client, capsys) == [
        {"id": 3333, "name": "Test Watch", "model": "Test Model 6"},
        {"id": 4444, "model": "Test Scale"},
    ]
    assert client.calls == [("get_devices", (), {})]


def test_device_list_no_devices_prints_empty_list(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_json(["device", "list"], FakeClient(get_devices=[]), capsys) == []


def test_device_list_raw_prints_garmin_response(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient(get_devices=[WATCH])

    assert run_json(["device", "list", "--raw"], client, capsys) == [WATCH]


def test_device_without_command_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    client: Any = FakeClient()

    with pytest.raises(SystemExit) as exit:
        main(["device"], connect=lambda: client)

    assert exit.value.code == 2
    assert capsys.readouterr().err == (
        "garmin: No command given. Run 'garmin device <command>', one of: list.\n"
    )
