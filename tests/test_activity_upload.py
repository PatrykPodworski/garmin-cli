import io
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import GarminConnectConnectionError
from requests.structures import CaseInsensitiveDict
from test_activities import activity_client

from garmin_cli.cli import main

UPLOAD = "/upload-service/upload"
STATUS = (
    "https://connectapi.garmin.com/activity-service/activity/status/1700000000000/ab12"
)
CREATED = "https://connectapi.garmin.com/activity-service/activity/101"
# A FIT file header: size, protocol, profile, data size, then ".FIT" at bytes 8-11.
FIT = b"\x0e\x10\x00\x00\x10\x00\x00\x00.FIT\x00\x00"
GPX = b'<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk/></gpx>'
TCX = (
    b'<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/'
    b'TrainingCenterDatabase/v2"><Activities/></TrainingCenterDatabase>'
)
REJECTED = "Check that the file opens in another app, or upload it in Garmin Connect.\n"


def answer(status: int, location: str | None = None, body: Any = None) -> Any:
    """A `Any` stand-in; Garmin sends the header as `Location`."""
    headers = CaseInsensitiveDict({"Location": location} if location else {})
    return SimpleNamespace(status_code=status, headers=headers, json=lambda: body)


def result(
    successes: list[Any] | None = None, failures: list[Any] | None = None
) -> dict[str, Any]:
    return {
        "detailedImportResult": {
            "uploadId": 555,
            "fileName": "run.gpx",
            "successes": successes or [],
            "failures": failures or [],
        }
    }


ACCEPTED = answer(202, STATUS, result())
DONE = answer(201, CREATED, result(successes=[{"internalId": 101}]))


def upload_client(post: Any = ACCEPTED, request: Any = DONE) -> FakeClient:
    client = activity_client()
    client.responses.update(post=post, request=request)
    client.client = client
    return client


@pytest.fixture(autouse=True)
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    waited: list[float] = []
    monkeypatch.setattr(time, "sleep", waited.append)
    return waited


def write(tmp_path: Path, data: bytes = GPX, name: str = "run.gpx") -> str:
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


def run(
    argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    try:
        code = main(argv, connect=lambda: client)
    except SystemExit as exit:
        code = int(exit.code or 0)
    out = capsys.readouterr()
    return code, out.out, out.err


def add(file: str) -> list[str]:
    return ["activity", "add", "--file", file]


@pytest.mark.parametrize(
    ("data", "name", "sent"),
    [
        (FIT, "ride.fit", "ride.fit"),
        (GPX, "run.gpx", "run.gpx"),
        (TCX, "swim.tcx", "swim.tcx"),
        # The format comes from the content, not the extension.
        (GPX, "export.xml", "export.gpx"),
        (FIT, "track", "track.fit"),
    ],
)
def test_activity_add_file_uploads_and_prints_the_activity(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    sleeps: list[float],
    data: bytes,
    name: str,
    sent: str,
) -> None:
    client = upload_client()
    path = write(tmp_path, data, name)

    code, out, err = run(add(path), client, capsys)

    assert code == 0
    assert json.loads(out)["id"] == 101
    assert err == f"garmin: Uploaded '{path}' as activity 101.\n"
    assert client.calls[:3] == [
        ("post", ("connectapi", UPLOAD), {"files": {"file": (sent, data)}}),
        ("request", ("GET", "connectapi", STATUS), {}),
        ("get_activity", ("101",), {}),
    ]
    assert sleeps == []


def test_activity_add_file_reads_stdin(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(GPX)))
    client = upload_client()

    code, out, err = run(add("-"), client, capsys)

    assert (code, json.loads(out)["id"], err) == (
        0,
        101,
        "garmin: Uploaded stdin as activity 101.\n",
    )
    assert client.calls[0] == (
        "post",
        ("connectapi", UPLOAD),
        {"files": {"file": ("activity.gpx", GPX)}},
    )


def test_activity_add_file_polls_until_garmin_creates_the_activity(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = upload_client(request=answer(202))
    waited: list[float] = []

    def sleep(seconds: float) -> None:
        waited.append(seconds)
        client.responses["request"] = DONE

    monkeypatch.setattr(time, "sleep", sleep)

    code, out, _ = run(add(write(tmp_path)), client, capsys)

    assert (code, json.loads(out)["id"]) == (0, 101)
    polls = [call for call in client.calls if call[0] == "request"]
    assert polls == [("request", ("GET", "connectapi", STATUS), {})] * 2
    assert waited == [1]


def test_activity_add_file_still_processing_after_30_polls(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, sleeps: list[float]
) -> None:
    client = upload_client(request=answer(202))
    path = write(tmp_path)

    code, out, err = run(add(path), client, capsys)

    assert (code, json.loads(out)) == (0, {"upload_id": 555, "file": "run.gpx"})
    assert err == (
        f"garmin: Uploaded '{path}'; Garmin is still processing it. "
        "Run 'garmin activities' in a minute to find it.\n"
    )
    assert [call[0] for call in client.calls] == ["post"] + ["request"] * 30
    assert sleeps == [1] * 29


@pytest.mark.parametrize(
    ("post", "poll", "reason"),
    [
        (
            ACCEPTED,
            answer(
                201,
                CREATED,
                result(
                    failures=[{"messages": [{"code": 1, "content": "Invalid file."}]}]
                ),
            ),
            "Invalid file",
        ),
        (ACCEPTED, answer(201, CREATED, result(failures=[{}])), "no reason given"),
        (ACCEPTED, answer(200, None, result()), "no reason given"),
        (answer(202, None, result()), DONE, "no reason given"),
        (
            answer(
                202,
                None,
                result(failures=[{"messages": [{"code": 2, "content": "Bad data"}]}]),
            ),
            DONE,
            "Bad data",
        ),
    ],
)
def test_activity_add_file_rejected_exits_1(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    post: Any,
    poll: Any,
    reason: str,
) -> None:
    client = upload_client(post, poll)
    path = write(tmp_path)

    assert run(add(path), client, capsys) == (
        1,
        "",
        f"garmin: Garmin did not accept '{path}': {reason}. {REJECTED}",
    )
    assert "get_activity" not in [call[0] for call in client.calls]


def conflict(status: int, body: Any) -> GarminConnectConnectionError:
    error = GarminConnectConnectionError(f"API Error {status} - Duplicate Activity.")
    error.response = answer(status, None, body)
    return error


def test_activity_add_file_duplicate_names_the_activity(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    failure = {
        "internalId": 202,
        "externalId": None,
        "messages": [{"code": 202, "content": "Duplicate Activity."}],
    }
    client = upload_client(post=conflict(409, result(failures=[failure])))
    path = write(tmp_path)

    assert run(add(path), client, capsys) == (
        1,
        "",
        f"garmin: '{path}' is already on Garmin Connect as activity 202. "
        "Run 'garmin activity 202' to see it.\n",
    )
    assert [call[0] for call in client.calls] == ["post"]


@pytest.mark.parametrize("body", [result(failures=[{"messages": []}]), result()])
def test_activity_add_file_duplicate_without_id(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    body: dict[str, Any],
) -> None:
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(FIT)))
    client = upload_client(post=conflict(409, body))

    assert run(add("-"), client, capsys) == (
        1,
        "",
        "garmin: stdin is already on Garmin Connect. "
        "Run 'garmin activities' to find it.\n",
    )


@pytest.mark.parametrize(
    "error",
    [conflict(400, result()), GarminConnectConnectionError("API Error 400")],
)
def test_activity_add_file_other_garmin_error_exits_1(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    error: GarminConnectConnectionError,
) -> None:
    client = upload_client(post=error)

    assert run(add(write(tmp_path)), client, capsys) == (
        1,
        "",
        "garmin: Garmin Connect rejected the request (HTTP 400). Check the values "
        "you gave, or rerun with --debug to see Garmin's response.\n",
    )


@pytest.mark.parametrize(
    "data",
    [b"hello", b"", b"<kml/>", b"\x0e\x10\x00\x00\x10\x00\x00\x00.FTI\x00\x00"],
)
def test_activity_add_file_unknown_content_exits_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, data: bytes
) -> None:
    client = upload_client()
    path = write(tmp_path, data, "run.gpx")

    assert run(add(path), client, capsys) == (
        2,
        "",
        f"garmin: '{path}' is not a FIT, GPX or TCX file.\n",
    )
    assert client.calls == []


def test_activity_add_file_unknown_stdin_exits_2(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"hello")))

    assert run(add("-"), upload_client(), capsys) == (
        2,
        "",
        "garmin: stdin is not a FIT, GPX or TCX file.\n",
    )


@pytest.mark.parametrize(
    ("name", "reason"),
    [("missing.fit", "No such file or directory"), ("", "Is a directory")],
)
def test_activity_add_file_unreadable_exits_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, name: str, reason: str
) -> None:
    client = upload_client()
    path = str(tmp_path / name)

    assert run(add(path), client, capsys) == (
        2,
        "",
        f"garmin: Cannot read '{path}' ({reason}). Pass a FIT, GPX or TCX file, "
        "or '-' for stdin.\n",
    )
    assert client.calls == []


@pytest.mark.parametrize(
    "option",
    [
        ["--type", "running"],
        ["--start", "2026-07-05 18:30"],
        ["--duration", "45"],
        ["--distance", "0"],
        ["--calories", "100"],
        ["--name", "Run"],
        ["--tz", "Europe/Warsaw"],
    ],
)
def test_activity_add_file_with_a_manual_option_exits_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, option: list[str]
) -> None:
    client = upload_client()

    assert run([*add(write(tmp_path)), *option], client, capsys) == (
        2,
        "",
        f"garmin: Give either --file or {option[0]}, not both. "
        "Run 'garmin activity add --help'.\n",
    )
    assert client.calls == []


def test_activity_add_file_names_the_first_manual_option(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    argv = [*add(write(tmp_path)), "--tz", "Europe/Warsaw", "--duration", "45"]

    _, _, err = run(argv, upload_client(), capsys)

    assert err == (
        "garmin: Give either --file or --duration, not both. "
        "Run 'garmin activity add --help'.\n"
    )
