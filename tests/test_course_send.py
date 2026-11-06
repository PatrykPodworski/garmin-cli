import json
from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError, GarminConnectNotFoundError

from garmin_cli.cli import main

COURSE = {"courseId": 111, "courseName": "Hill Loop", "activityTypePk": 6}
WATCH = {"deviceId": 3333, "displayName": "Test Watch", "productDisplayName": "Model"}
SCALE = {"deviceId": 4444, "productDisplayName": "Test Scale"}
ANSWER = [{"messageId": 888, "deviceName": "Test Watch"}]
MESSAGE = {
    "deviceId": 3333,
    "messageUrl": "course-service/course/fit/111/3333?elevation=true",
    "messageType": "courses",
    "messageName": "Hill Loop",
    "groupName": None,
    "priority": 0,
    "fileType": "FIT",
    "metaDataId": 111,
}
QUEUED = (
    'garmin: Queued course "Hill Loop" (ID 111) for device "Test Watch" (ID 3333). '
    "The watch gets it on its next sync.\n"
)
SEND = ["course", "send", "111", "--device", "3333"]


def send_client(answer: Any = ANSWER, **responses: Any) -> FakeClient:
    client = FakeClient(
        **{
            "get_course": COURSE,
            "get_devices": [SCALE, WATCH],
            "post": answer,
            **responses,
        }
    )
    client.client = client
    return client


def run(
    argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    try:
        code = main(argv, connect=lambda: client)
    except SystemExit as exit:
        code = int(exit.code or 0)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_course_send_posts_one_course_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = send_client()

    code, out, err = run(SEND, client, capsys)

    assert (code, err) == (0, QUEUED)
    assert json.loads(out) == {
        "course_id": 111,
        "course": "Hill Loop",
        "device_id": 3333,
        "device": "Test Watch",
        "message_id": 888,
    }
    assert client.calls == [
        ("get_course", (111,), {}),
        ("get_devices", (), {}),
        (
            "post",
            ("connectapi", "/device-service/devicemessage/messages"),
            {"json": [MESSAGE], "api": True},
        ),
    ]


@pytest.mark.parametrize("answer", [None, [], {"status": "ok"}, [{}]])
def test_course_send_answer_without_message_id_leaves_it_out(
    capsys: pytest.CaptureFixture[str], answer: Any
) -> None:
    code, out, err = run(SEND, send_client(answer), capsys)

    assert (code, err) == (0, QUEUED)
    assert "message_id" not in json.loads(out)


def test_course_send_device_without_display_name_uses_the_model(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = send_client(get_devices=[SCALE])

    code, out, err = run(["course", "send", "111", "--device", "4444"], client, capsys)

    assert code == 0
    assert 'for device "Test Scale" (ID 4444).' in err
    assert json.loads(out)["device"] == "Test Scale"


def test_course_send_raw_prints_garmin_answer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, out, err = run([*SEND, "--raw"], send_client(), capsys)

    assert (code, err) == (0, QUEUED)
    assert json.loads(out) == ANSWER


def test_course_send_unknown_course_exits_before_the_send(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = send_client(get_course=GarminConnectNotFoundError("404"))

    assert run(SEND, client, capsys) == (
        1,
        "",
        "garmin: No course with ID 111. Run 'garmin course list' to list IDs.\n",
    )
    assert [call[0] for call in client.calls] == ["get_course"]


def test_course_send_unknown_device_exits_before_the_send(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = send_client(get_devices=[SCALE])

    assert run(SEND, client, capsys) == (
        1,
        "",
        "garmin: No device with ID 3333. Run 'garmin device list' to list IDs.\n",
    )
    assert [call[0] for call in client.calls] == ["get_course", "get_devices"]


def test_course_send_rejected_by_garmin_exits_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = send_client(post=GarminConnectConnectionError("API Error 400: bad"))

    code, out, err = run(SEND, client, capsys)

    assert (code, out) == (1, "")
    assert err.startswith("garmin: Garmin Connect rejected the request (HTTP 400).")
    assert "Queued" not in err


@pytest.mark.parametrize("value", ["x", "0", "-1"])
def test_course_send_invalid_device_exits_2(
    capsys: pytest.CaptureFixture[str], value: str
) -> None:
    client = send_client()

    assert run(["course", "send", "111", f"--device={value}"], client, capsys) == (
        2,
        "",
        f"garmin: Invalid device ID '{value}'. Run 'garmin device list' to list IDs.\n",
    )
    assert client.calls == []


def test_course_send_invalid_course_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = send_client()

    assert run(["course", "send", "abc", "--device", "3333"], client, capsys) == (
        2,
        "",
        "garmin: Invalid course ID 'abc'. Run 'garmin course list' to list IDs.\n",
    )
    assert client.calls == []


def test_course_send_without_device_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = send_client()

    assert run(["course", "send", "111"], client, capsys) == (
        2,
        "",
        "garmin: Missing --device for 'garmin course send'. Run 'garmin course send "
        "--help'.\n",
    )
    assert client.calls == []


def test_course_send_accepts_device_id_1(capsys: pytest.CaptureFixture[str]) -> None:
    client = send_client(get_devices=[{"deviceId": 1, "displayName": "One"}])

    code, out, _ = run(["course", "send", "111", "--device", "1"], client, capsys)

    assert code == 0
    assert json.loads(out)["device_id"] == 1
