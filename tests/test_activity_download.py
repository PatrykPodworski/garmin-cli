import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeClient
from garminconnect import Garmin, GarminConnectNotFoundError
from test_activities import DETAIL

from garmin_cli.cli import main

FIT = b"\x0e\x10\x00\x00fake-fit-records"
GPX = b'<?xml version="1.0"?><gpx><trk>fake track</trk></gpx>'
NO_FIT = (
    "garmin: Garmin sent no FIT file for activity 101. Rerun with --debug and "
    "report it at https://github.com/PatrykPodworski/garmin-cli/issues.\n"
)
MANUAL = {**DETAIL, "metadataDTO": {"manualActivity": True}}
Formats = Garmin.ActivityDownloadFormat


def archive(*entries: tuple[str, bytes]) -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as file:
        for name, content in entries:
            file.writestr(name, content)
    return data.getvalue()


def download_client(detail: Any = DETAIL, data: Any = GPX) -> FakeClient:
    return FakeClient(get_activity=detail, download_activity=data)


def run(
    argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]
) -> tuple[int, str, str]:
    try:
        code = main(argv, connect=lambda: client)
    except SystemExit as exit:
        code = int(exit.code or 0)
    out = capsys.readouterr()
    return code, out.out, out.err


def never_connect() -> Any:
    raise AssertionError("connect was called")


@pytest.mark.parametrize(
    ("argv", "fmt", "dl_fmt", "data", "saved"),
    [
        ([], "fit", Formats.ORIGINAL, archive(("101_ACTIVITY.fit", FIT)), FIT),
        (
            ["--format", "fit"],
            "fit",
            Formats.ORIGINAL,
            archive(("101_ACTIVITY.FIT", FIT)),
            FIT,
        ),
        (["--format", "gpx"], "gpx", Formats.GPX, GPX, GPX),
        (["--format", "tcx"], "tcx", Formats.TCX, b"<?xml?><tcx/>", b"<?xml?><tcx/>"),
        (["--format", "kml"], "kml", Formats.KML, b"<?xml?><kml/>", b"<?xml?><kml/>"),
        (["--format", "csv"], "csv", Formats.CSV, b"Split,Time\n1,5:00\n", None),
    ],
)
def test_activity_download_saves_each_format(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    argv: list[str],
    fmt: str,
    dl_fmt: Any,
    data: bytes,
    saved: bytes | None,
) -> None:
    client = download_client(data=data)
    path = tmp_path / f"run.{fmt}"
    expected = data if saved is None else saved

    code, out, err = run(
        ["activity", "download", "0101", *argv, "--output", str(path)], client, capsys
    )

    assert (code, json.loads(out)) == (
        0,
        {"id": 101, "format": fmt, "file": str(path), "bytes": len(expected)},
    )
    assert err == (
        f'garmin: Saved activity "Morning Run" as {path} ({len(expected)} bytes).\n'
    )
    assert path.read_bytes() == expected
    assert client.calls == [
        ("get_activity", ("101",), {}),
        ("download_activity", ("101",), {"dl_fmt": dl_fmt}),
    ]


def test_activity_download_overwrites_a_file(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    path = tmp_path / "run.gpx"
    path.write_bytes(b"old content that is longer than the new one" * 10)

    code, _, _ = run(
        ["activity", "download", "101", "--format", "gpx", "--output", str(path)],
        download_client(),
        capsys,
    )

    assert (code, path.read_bytes()) == (0, GPX)


@pytest.mark.parametrize(
    "detail",
    [
        {},
        {"activityName": None},
        {"metadataDTO": None},
        {"metadataDTO": {"manualActivity": False}},
    ],
)
def test_activity_download_without_name_or_manual_flag(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, detail: dict[str, Any]
) -> None:
    path = tmp_path / "run.gpx"

    result = run(
        ["activity", "download", "101", "--format", "gpx", "--output", str(path)],
        download_client(detail),
        capsys,
    )

    assert result[0] == 0
    assert result[2] == f"garmin: Saved activity 101 as {path} ({len(GPX)} bytes).\n"


@pytest.mark.parametrize(
    ("argv", "data", "written"),
    [
        (["--format", "gpx"], GPX, GPX),
        ([], archive(("101_ACTIVITY.fit", FIT)), FIT),
    ],
)
def test_activity_download_to_stdout_writes_only_the_file(
    capsysbinary: pytest.CaptureFixture[bytes],
    argv: list[str],
    data: bytes,
    written: bytes,
) -> None:
    client = download_client(data=data)

    code = main(["activity", "download", "101", *argv, "--output", "-"], lambda: client)

    out = capsysbinary.readouterr()
    assert (code, out.out, out.err) == (0, written, b"")


def test_activity_download_to_a_terminal_exits_2(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    result = run(["activity", "download", "101", "--output", "-"], None, capsys)

    assert result == (
        2,
        "",
        "garmin: --output - writes the file to stdout, which is a terminal. Pipe it "
        "to another command, or give a file name.\n",
    )


@pytest.mark.parametrize(
    ("entry", "kind", "use"),
    [
        ("101_ACTIVITY.gpx", "GPX", "gpx"),
        ("101_ACTIVITY.tcx", "TCX", "tcx"),
        ("101_ACTIVITY.bin", "BIN", "gpx"),
    ],
)
def test_activity_download_fit_of_an_uploaded_file_exits_1(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    entry: str,
    kind: str,
    use: str,
) -> None:
    path = tmp_path / "run.fit"

    result = run(
        ["activity", "download", "101", "--output", str(path)],
        download_client(data=archive((entry, GPX))),
        capsys,
    )

    assert result == (
        1,
        "",
        f"garmin: Activity 101 was uploaded as a {kind} file, so Garmin has no FIT "
        f"file for it. Use --format {use}.\n",
    )
    assert not path.exists()


@pytest.mark.parametrize(
    "data",
    [
        archive(("101_ACTIVITY.fit", FIT), ("101_extra.fit", FIT)),
        archive(),
        FIT,
    ],
)
def test_activity_download_fit_without_one_entry_exits_1(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, data: bytes
) -> None:
    path = tmp_path / "run.fit"

    result = run(
        ["activity", "download", "101", "--output", str(path)],
        download_client(data=data),
        capsys,
    )

    assert result == (1, "", NO_FIT)
    assert not path.exists()


@pytest.mark.parametrize("fmt", ["gpx", "csv", "fit"])
def test_activity_download_manual_activity_exits_1(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, fmt: str
) -> None:
    client = download_client(MANUAL)
    path = tmp_path / "run.out"

    result = run(
        ["activity", "download", "101", "--format", fmt, "--output", str(path)],
        client,
        capsys,
    )

    assert result == (
        1,
        "",
        "garmin: Activity 101 is a manual entry, so it has no recording to "
        "download. Run 'garmin activity 101' to see it.\n",
    )
    assert client.calls == [("get_activity", ("101",), {})]
    assert not path.exists()


def test_activity_download_unknown_id_exits_1(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = download_client(GarminConnectNotFoundError("404"))

    result = run(
        ["activity", "download", "999", "--output", str(tmp_path / "run.fit")],
        client,
        capsys,
    )

    assert result == (
        1,
        "",
        "garmin: No activity with ID 999. Run 'garmin activities' to list recent "
        "IDs.\n",
    )
    assert client.calls == [("get_activity", ("999",), {})]


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (
            ["abc", "--output", "run.fit"],
            "Invalid activity ID 'abc'. Run 'garmin activities' to list IDs.",
        ),
        (
            ["101", "--format", "zip", "--output", "run.fit"],
            "Invalid --format 'zip'. Use fit, gpx, tcx, kml or csv.",
        ),
        (
            ["101", "--format", "GPX", "--output", "run.gpx"],
            "Invalid --format 'GPX'. Use fit, gpx, tcx, kml or csv.",
        ),
        (
            ["101"],
            "Missing --output for 'garmin activity download'. Run 'garmin activity "
            "download --help'.",
        ),
        (
            ["101", "--output", "missing/run.fit"],
            "Cannot write 'missing/run.fit': folder 'missing' does not exist. Give a "
            "path in an existing folder.",
        ),
        (
            ["101", "--output", "missing/deeper/run.fit"],
            "Cannot write 'missing/deeper/run.fit': folder 'missing/deeper' does not "
            "exist. Give a path in an existing folder.",
        ),
    ],
)
def test_activity_download_bad_arguments_exit_2_without_login(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    argv: list[str],
    message: str,
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exit:
        main(["activity", "download", *argv], connect=never_connect)

    out = capsys.readouterr()
    assert (exit.value.code, out.out, out.err) == (2, "", f"garmin: {message}\n")


def test_activity_download_into_the_current_folder(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    code, out, _ = run(
        ["activity", "download", "101", "--format", "gpx", "--output", "run.gpx"],
        download_client(),
        capsys,
    )

    assert (code, json.loads(out)["file"]) == (0, "run.gpx")
    assert (tmp_path / "run.gpx").read_bytes() == GPX
