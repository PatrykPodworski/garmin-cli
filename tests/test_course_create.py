import contextlib
import io
import json
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import FakeClient

from garmin_cli.cli import main

TYPES = [
    {"typeId": 1, "typeKey": "running"},
    {"typeId": 6, "typeKey": "trail_running"},
]
GPX = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">'
    b"<trk><name>Test Track</name><trkseg>"
    b'<trkpt lat="10.0" lon="20.0"/><trkpt lat="10.001" lon="20.001"/>'
    b"</trkseg></trk></gpx>"
)
POINTS = [
    {"latitude": 10.0, "longitude": 20.0, "elevation": None},
    {"latitude": 10.001, "longitude": 20.001, "elevation": None},
]
IMPORTED = {"courseId": None, "courseName": "Test Track", "geoPoints": POINTS}
SAVED = {
    "courseId": 111,
    "courseName": "Hill Loop",
    "activityTypePk": 6,
    "distanceMeter": 150.5,
    "elevationGainMeter": 12.0,
    "elevationLossMeter": 3.0,
    "rulePK": 2,
}
SHOWN = {
    "id": 111,
    "name": "Hill Loop",
    "type": "trail_running",
    "distance_m": 150.5,
    "elevation_gain_m": 12.0,
    "elevation_loss_m": 3.0,
    "privacy": "private",
}


def create_client(imported: Any = IMPORTED, saved: Any = SAVED) -> FakeClient:
    return FakeClient(
        get_activity_types=TYPES, import_course=imported, create_course=saved
    )


@pytest.fixture(autouse=True)
def folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The folder the GPX copy goes to, kept so a test can read the copy."""
    folder = tmp_path / "import"
    folder.mkdir()

    @contextlib.contextmanager
    def temporary_directory() -> Iterator[str]:
        yield str(folder)

    monkeypatch.setattr(tempfile, "TemporaryDirectory", temporary_directory)
    return folder


def write(tmp_path: Path, data: bytes = GPX, name: str = "hills.gpx") -> str:
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


def test_course_create_imports_then_saves(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, folder: Path
) -> None:
    client = create_client()
    path = write(tmp_path)

    code, out, err = run(
        [
            "course",
            "create",
            "--file",
            path,
            "--name",
            "Hill Loop",
            "--type",
            "trail_running",
        ],
        client,
        capsys,
    )

    assert (code, json.loads(out)) == (0, SHOWN)
    assert err == (
        f"garmin: Imported '{path}' and saved it as course \"Hill Loop\" (ID 111).\n"
    )
    assert client.calls == [
        ("get_activity_types", (), {}),
        ("import_course", (str(folder / "hills.gpx"),), {}),
        (
            "create_course",
            (
                {
                    "courseId": None,
                    "courseName": "Hill Loop",
                    "geoPoints": POINTS,
                    "activityTypePk": 6,
                    "rulePK": 2,
                },
            ),
            {},
        ),
    ]
    assert (folder / "hills.gpx").read_bytes() == GPX


def test_course_create_defaults_to_running_private_and_the_imported_name(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = create_client()

    code, _, _ = run(["course", "create", "--file", write(tmp_path)], client, capsys)

    assert code == 0
    sent = client.calls[-1][1][0]
    assert (sent["courseName"], sent["activityTypePk"], sent["rulePK"]) == (
        "Test Track",
        1,
        2,
    )


def test_course_create_public(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = create_client(saved={**SAVED, "rulePK": 1})

    code, out, _ = run(
        ["course", "create", "--file", write(tmp_path), "--privacy", "public"],
        client,
        capsys,
    )

    assert (code, json.loads(out)["privacy"]) == (0, "public")
    assert client.calls[-1][1][0]["rulePK"] == 1


@pytest.mark.parametrize("name", [None, ""])
def test_course_create_without_any_name_uses_the_file_name(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, name: str | None
) -> None:
    client = create_client(imported={**IMPORTED, "courseName": name})

    code, _, _ = run(
        ["course", "create", "--file", write(tmp_path, name="hill-repeats.gpx")],
        client,
        capsys,
    )

    assert code == 0
    assert client.calls[-1][1][0]["courseName"] == "hill-repeats"


def test_course_create_strips_the_name(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = create_client()

    run(
        ["course", "create", "--file", write(tmp_path), "--name", "  Hill Loop "],
        client,
        capsys,
    )

    assert client.calls[-1][1][0]["courseName"] == "Hill Loop"


def test_course_create_any_file_name_is_imported_as_gpx(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, folder: Path
) -> None:
    client = create_client()

    code, _, _ = run(
        ["course", "create", "--file", write(tmp_path, name="route.xml")],
        client,
        capsys,
    )

    assert code == 0
    assert client.calls[1] == ("import_course", (str(folder / "route.gpx"),), {})


def test_course_create_reads_stdin(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, folder: Path
) -> None:
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(GPX)))
    client = create_client(imported={**IMPORTED, "courseName": None})

    code, _, err = run(["course", "create", "--file", "-"], client, capsys)

    assert code == 0
    assert (
        err == 'garmin: Imported stdin and saved it as course "Hill Loop" (ID 111).\n'
    )
    assert client.calls[1] == ("import_course", (str(folder / "Course.gpx"),), {})
    assert client.calls[-1][1][0]["courseName"] == "Course"
    assert (folder / "Course.gpx").read_bytes() == GPX


@pytest.mark.parametrize(
    "gpx",
    [
        # A route instead of a track, in GPX 1.0.
        b'<gpx version="1.0" xmlns="http://www.topografix.com/GPX/1/0"><rte>'
        b'<rtept lat="1" lon="2"/><rtept lat="1.1" lon="2"/></rte></gpx>',
        # No namespace.
        b'<gpx><trk><trkseg><trkpt lat="1" lon="2"/><trkpt lat="1.1" lon="2"/>'
        b"</trkseg></trk></gpx>",
    ],
)
def test_course_create_accepts_routes_and_any_gpx_namespace(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, gpx: bytes
) -> None:
    client = create_client()

    code, _, _ = run(
        ["course", "create", "--file", write(tmp_path, gpx)], client, capsys
    )

    assert code == 0


@pytest.mark.parametrize(
    ("gpx", "message"),
    [
        (
            b"",
            "Invalid XML in '{path}': no element found: line 1, column 0. Pass a "
            "GPX file.",
        ),
        (
            b"<gpx><trk>",
            "Invalid XML in '{path}': no element found: line 1, column "
            "10. Pass a GPX file.",
        ),
        (
            b'<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/'
            b'TrainingCenterDatabase/v2"/>',
            "The XML in '{path}' is <TrainingCenterDatabase>, not GPX. Pass a GPX "
            "file; TCX and FIT are not supported.",
        ),
        (
            b"<gpx/>",
            "The GPX in '{path}' has 0 track or route points. A course "
            "needs at least 2.",
        ),
        (
            b'<gpx><wpt lat="1" lon="2"/><trk><trkseg><trkpt lat="1" lon="2"/>'
            b"</trkseg></trk></gpx>",
            "The GPX in '{path}' has 1 track or route points. A course needs at "
            "least 2.",
        ),
    ],
)
def test_course_create_rejects_a_file_that_is_not_a_gpx_course(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, gpx: bytes, message: str
) -> None:
    client = FakeClient()
    path = write(tmp_path, gpx)

    assert run(["course", "create", "--file", path], client, capsys) == (
        2,
        "",
        f"garmin: {message.format(path=path)}\n",
    )
    assert client.calls == []


def test_course_create_invalid_stdin_says_stdin(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"<gpx/>")))

    assert run(["course", "create", "--file", "-"], FakeClient(), capsys) == (
        2,
        "",
        "garmin: The GPX in stdin has 0 track or route points. A course needs at "
        "least 2.\n",
    )


def test_course_create_unreadable_file_exits_2(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    client = FakeClient()
    path = str(tmp_path / "missing.gpx")

    assert run(["course", "create", "--file", path], client, capsys) == (
        2,
        "",
        f"garmin: Cannot read '{path}' (No such file or directory). Pass a GPX "
        "file, or '-' for stdin.\n",
    )
    assert client.calls == []


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("--name", "", "Invalid --name ''. Give a name that is not blank."),
        ("--name", "  ", "Invalid --name '  '. Give a name that is not blank."),
        ("--privacy", "friends", "Invalid --privacy 'friends'. Use private or public."),
        ("--privacy", "Private", "Invalid --privacy 'Private'. Use private or public."),
    ],
)
def test_course_create_invalid_option_exits_2(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    option: str,
    value: str,
    message: str,
) -> None:
    client = FakeClient()

    assert run(
        ["course", "create", "--file", write(tmp_path), f"{option}={value}"],
        client,
        capsys,
    ) == (2, "", f"garmin: {message}\n")
    assert client.calls == []


def test_course_create_without_file_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run(["course", "create"], FakeClient(), capsys) == (
        2,
        "",
        "garmin: Missing --file for 'garmin course create'. Run 'garmin course "
        "create --help'.\n",
    )


@pytest.mark.parametrize(
    ("type_key", "message"),
    [
        ("trail-running", "Did you mean 'trail_running'?"),
        (
            "xyz",
            "Use a Garmin type key, like running, cycling or strength_training.",
        ),
    ],
)
def test_course_create_unknown_type_exits_2_before_the_import(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, type_key: str, message: str
) -> None:
    client = create_client()

    assert run(
        ["course", "create", "--file", write(tmp_path), "--type", type_key],
        client,
        capsys,
    ) == (2, "", f"garmin: Unknown activity type '{type_key}'. {message}\n")
    assert client.calls == [("get_activity_types", (), {})]


@pytest.mark.parametrize("imported", [None, [], {**IMPORTED, "geoPoints": []}, {}])
def test_course_create_import_without_track_saves_nothing(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, imported: Any
) -> None:
    client = create_client(imported=imported)
    path = write(tmp_path)

    assert run(["course", "create", "--file", path], client, capsys) == (
        1,
        "",
        f"garmin: Garmin found no track in '{path}', so no course was saved. Check "
        "that the file imports in Garmin Connect's course import.\n",
    )
    assert [call[0] for call in client.calls] == [
        "get_activity_types",
        "import_course",
    ]
