"""Checks docs/adr: file names, numbering, frontmatter, headings and the index."""

import re
import sys
from pathlib import Path

NAME = re.compile(r"^(\d{4})-[a-z0-9-]+\.md$")
INDEX_LINE = re.compile(r"^- \[\d{4}\. .+\]\((\S+\.md)\) — (.+)$")
STATUS = re.compile(r"^---\nstatus: (.+)\n---\n")
SUPERSEDED = re.compile(r"^superseded by (\d{4})$")


def check(folder: Path) -> list[str]:
    errors: list[str] = []
    files = sorted(p.name for p in folder.glob("*.md") if p.name != "README.md")
    numbered: dict[str, str] = {}
    for name in files:
        match = NAME.match(name)
        if match is None:
            errors.append(f"{name}: file name is not NNNN-slug.md")
        else:
            numbered[name] = match.group(1)

    numbers = list(numbered.values())
    if numbers != [f"{i:04d}" for i in range(1, len(numbers) + 1)]:
        errors.append(f"numbers skip or repeat: {', '.join(numbers)}")

    index = {
        m.group(1): m.group(2)
        for line in (folder / "README.md").read_text().splitlines()
        if (m := INDEX_LINE.match(line))
    }
    for name, number in numbered.items():
        text = (folder / name).read_text()
        status = STATUS.match(text)
        if status is None:
            errors.append(f"{name}: no status frontmatter")
        if not re.search(rf"^# {number}\. ", text, re.MULTILINE):
            errors.append(f"{name}: no '# {number}.' heading")
        if name not in index:
            errors.append(f"{name}: missing from README.md")
        elif status is not None and index[name] != status.group(1):
            errors.append(
                f"{name}: README.md says '{index[name]}', "
                f"the file says '{status.group(1)}'"
            )
        sup = SUPERSEDED.match(status.group(1)) if status else None
        if sup is not None and sup.group(1) not in numbers:
            errors.append(f"{name}: {sup.group(0)}, which does not exist")
    for name in index:
        if name not in files:
            errors.append(f"README.md lists {name}, which does not exist")
    return errors


def main() -> int:
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/adr")
    errors = check(folder)
    for error in errors:
        print(f"check_adrs: {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
