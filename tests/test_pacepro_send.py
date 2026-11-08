import json
from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError, GarminConnectNotFoundError
from test_pacepro import LIST_IDS, PLAN, PLAN_PATH, run

WATCH = {"deviceId": 3333, "displayName": "Test Watch", "productDisplayName": "Model"}
SCALE = {"deviceId": 4444, "productDisplayName": "Test Scale"}
SEND_PATH = "/course-service/pacebands/501/device/3333"
QUEUED = (
    'garmin: Queued PacePro plan "Test Hills 10k" (ID 501) for device "Test Watch" '
    "(ID 3333). The watch gets it on its next sync.\n"
)
SEND = ["pacepro", "send", "501", "--device", "3333"]


def send_client(**responses: Any) -> FakeClient:
    # Garmin answers the send with 204, which garminconnect returns as `{}`.
    client = FakeClient(
        **{"connectapi": PLAN, "get_devices": [SCALE, WATCH], "post": {}, **responses}
    )
    client.client = client
    return client


def test_pacepro_send_posts_the_plan_to_the_device(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = send_client()

    code, out, err = run(SEND, client, capsys)

    assert (code, err) == (0, QUEUED)
    assert json.loads(out) == {
        "plan_id": 501,
        "plan": "Test Hills 10k",
        "device_id": 3333,
        "device": "Test Watch",
    }
    assert client.calls == [
        ("connectapi", (PLAN_PATH,), {}),
        ("get_devices", (), {}),
        ("post", ("connectapi", SEND_PATH), {"api": True}),
    ]


@pytest.mark.parametrize(
    "plan", [{"paceBandPk": 501}, {"paceBandPk": 501, "paceBandSummary": None}]
)
def test_pacepro_send_plan_without_name_shows_its_id(
    capsys: pytest.CaptureFixture[str], plan: dict[str, Any]
) -> None:
    code, out, err = run(SEND, send_client(connectapi=plan), capsys)

    assert code == 0
    assert err == (
        'garmin: Queued PacePro plan 501 for device "Test Watch" (ID 3333). '
        "The watch gets it on its next sync.\n"
    )
    assert json.loads(out) == {
        "plan_id": 501,
        "device_id": 3333,
        "device": "Test Watch",
    }


def test_pacepro_send_device_without_display_name_uses_the_model(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = send_client()

    code, out, err = run(["pacepro", "send", "501", "--device", "4444"], client, capsys)

    assert code == 0
    assert 'for device "Test Scale" (ID 4444).' in err
    assert json.loads(out)["device"] == "Test Scale"
    assert client.calls[-1][1] == (
        "connectapi",
        "/course-service/pacebands/501/device/4444",
    )


def test_pacepro_send_raw_prints_garmin_answer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = send_client(post={"status": "queued"})

    code, out, err = run([*SEND, "--raw"], client, capsys)

    assert (code, err) == (0, QUEUED)
    assert json.loads(out) == {"status": "queued"}


def test_pacepro_send_raw_prints_empty_answer_for_204(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run([*SEND, "--raw"], send_client(), capsys) == (0, "{}\n", QUEUED)


def test_pacepro_send_unknown_plan_exits_before_the_send(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = send_client(connectapi=GarminConnectNotFoundError("404"))

    assert run(SEND, client, capsys) == (
        1,
        "",
        f"garmin: No PacePro plan with ID 501. {LIST_IDS}\n",
    )
    assert [call[0] for call in client.calls] == ["connectapi"]


def test_pacepro_send_unknown_device_exits_before_the_send(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = send_client(get_devices=[SCALE])

    assert run(SEND, client, capsys) == (
        1,
        "",
        "garmin: No device with ID 3333. Run 'garmin device list' to list IDs.\n",
    )
    assert [call[0] for call in client.calls] == ["connectapi", "get_devices"]


def test_pacepro_send_rejected_by_garmin_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = send_client(post=GarminConnectConnectionError("API Error 400: bad"))

    code, out, err = run(SEND, client, capsys)

    assert (code, out) == (1, "")
    assert err.startswith("garmin: Garmin Connect rejected the request (HTTP 400).")
    assert "Queued" not in err


@pytest.mark.parametrize("value", ["abc", "0", "-5"])
def test_pacepro_send_invalid_plan_exits_2(
    capsys: pytest.CaptureFixture[str], value: str
) -> None:
    client = send_client()

    result = run(["pacepro", "send", "--device", "3333", "--", value], client, capsys)

    assert result == (2, "", f"garmin: Invalid PacePro plan ID '{value}'. {LIST_IDS}\n")
    assert client.calls == []


@pytest.mark.parametrize("value", ["x", "0", "-1"])
def test_pacepro_send_invalid_device_exits_2(
    capsys: pytest.CaptureFixture[str], value: str
) -> None:
    client = send_client()

    assert run(["pacepro", "send", "501", f"--device={value}"], client, capsys) == (
        2,
        "",
        f"garmin: Invalid device ID '{value}'. Run 'garmin device list' to list IDs.\n",
    )
    assert client.calls == []


def test_pacepro_send_without_device_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = send_client()

    assert run(["pacepro", "send", "501"], client, capsys) == (
        2,
        "",
        "garmin: Missing --device for 'garmin pacepro send'. Run 'garmin pacepro send "
        "--help'.\n",
    )
    assert client.calls == []
