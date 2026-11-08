import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "check_adrs.py"


def adr(number: str, status: str = "accepted", title: str = "Title") -> str:
    return f"---\nstatus: {status}\n---\n\n# {number}. {title}\n\nWhy.\n"


def index_line(number: str, slug: str, status: str = "accepted") -> str:
    return f"- [{number}. Title]({number}-{slug}.md) — {status}\n"


def run(folder: Path) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(folder)],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout + result.stderr


def write(folder: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        (folder / name).write_text(text)
    return folder


def test_passes_when_index_and_files_match(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "README.md": "# ADRs\n\n"
            + index_line("0001", "one", "superseded by 0002")
            + index_line("0002", "two"),
            "0001-one.md": adr("0001", "superseded by 0002"),
            "0002-two.md": adr("0002"),
        },
    )
    assert run(tmp_path) == (0, "")


@pytest.mark.parametrize(
    ("files", "error"),
    [
        (
            {"README.md": "# ADRs\n", "0001_one.md": adr("0001")},
            "0001_one.md: file name is not NNNN-slug.md",
        ),
        (
            {
                "README.md": index_line("0001", "one") + index_line("0003", "three"),
                "0001-one.md": adr("0001"),
                "0003-three.md": adr("0003"),
            },
            "numbers skip or repeat: 0001, 0003",
        ),
        (
            {
                "README.md": index_line("0001", "one") + index_line("0001", "two"),
                "0001-one.md": adr("0001"),
                "0001-two.md": adr("0001"),
            },
            "numbers skip or repeat: 0001, 0001",
        ),
        (
            {
                "README.md": index_line("0001", "one"),
                "0001-one.md": "# 0001. Title\n\nWhy.\n",
            },
            "0001-one.md: no status frontmatter",
        ),
        (
            {
                "README.md": index_line("0001", "one"),
                "0001-one.md": "---\nstatus: accepted\n---\n\n# Title\n",
            },
            "0001-one.md: no '# 0001.' heading",
        ),
        (
            {"README.md": "# ADRs\n", "0001-one.md": adr("0001")},
            "0001-one.md: missing from README.md",
        ),
        (
            {"README.md": index_line("0001", "one")},
            "README.md lists 0001-one.md, which does not exist",
        ),
        (
            {
                "README.md": index_line("0001", "one", "superseded by 0002"),
                "0001-one.md": adr("0001"),
            },
            "0001-one.md: README.md says 'superseded by 0002', the file says "
            "'accepted'",
        ),
        (
            {
                "README.md": index_line("0001", "one", "superseded by 0002"),
                "0001-one.md": adr("0001", "superseded by 0002"),
            },
            "0001-one.md: superseded by 0002, which does not exist",
        ),
    ],
)
def test_reports_each_broken_rule(
    tmp_path: Path, files: dict[str, str], error: str
) -> None:
    assert run(write(tmp_path, files)) == (1, f"check_adrs: {error}\n")


def test_repo_adrs_pass() -> None:
    assert run(SCRIPT.parent.parent / "docs" / "adr") == (0, "")
