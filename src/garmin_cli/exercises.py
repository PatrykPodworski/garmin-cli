import argparse
import difflib
import re
import sys
from typing import Any

from garminconnect.exercises import EXERCISES

from garmin_cli.activities import positive_int
from garmin_cli.client import Connect


def words(text: str) -> str:
    """`text` in lowercase, with punctuation as single spaces."""
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


BY_WORDS = {words(exercise["name"]): exercise for exercise in EXERCISES}
BY_KEYS = {
    (exercise["category"], exercise["exercise"]): exercise["name"]
    for exercise in EXERCISES
}
CATEGORIES = sorted({exercise["category"] for exercise in EXERCISES})


def display_name(category: str | None, exercise: str | None) -> str | None:
    """The catalog name of a step's exercise. A warm-up or cool-down step has an
    empty exercise name, and an exercise newer than the catalog shows its keys."""
    if not (category and exercise):
        return None
    return BY_KEYS.get((category, exercise), f"{category}/{exercise}")


def category(value: str) -> str:
    key = value.upper()
    if key in CATEGORIES:
        return key
    problem = f"Unknown exercise category '{value}'."
    # 'calf' is too short for difflib to find 'CALF_RAISE'.
    containing = [name for name in CATEGORIES if key in name]
    if match := containing or difflib.get_close_matches(key, CATEGORIES):
        problem += f" Did you mean '{match[0]}'?"
    raise argparse.ArgumentTypeError(
        f"{problem} Run 'garmin exercise list --help' to list the categories."
    )


def matches(query: list[str], name: str) -> bool:
    """Whether `name` contains every query word. Words are compared without the
    spaces between them, so 'pushup' finds 'Push-up'."""
    joined = words(name).replace(" ", "")
    return all(word in joined for word in query)


def exercise_list(args: argparse.Namespace, _connect: Connect) -> Any:
    query = words(args.search or "")
    catalog = [
        exercise
        for exercise in EXERCISES
        if args.category in (None, exercise["category"])
    ]
    found = sorted(
        (exercise for exercise in catalog if matches(query.split(), exercise["name"])),
        key=lambda exercise: exercise["name"].lower(),
    )
    if not found and query:
        # Closest first, so the likeliest name leads.
        by_words = {words(exercise["name"]): exercise for exercise in catalog}
        found = [
            by_words[match]
            for match in difflib.get_close_matches(query, by_words, n=args.limit)
        ]
        if found:
            print(
                f"garmin: No exercise has every word of '{args.search}'. "
                "Showing the closest names; search again if none fits.",
                file=sys.stderr,
            )
    if (more := len(found) - args.limit) > 0:
        what = "exercise matches" if more == 1 else "exercises match"
        print(
            f"garmin: {more} more {what}. Raise --limit to see them.",
            file=sys.stderr,
        )
    return [
        {"name": exercise["name"], "category": exercise["category"]}
        for exercise in found[: args.limit]
    ]


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    exercise_parser = subparsers.add_parser(
        "exercise",
        help="strength exercise names for 'garmin workout add --strength'",
    )
    # `CliParser.explain` names a missing command by this metavar.
    list_parser = exercise_parser.add_subparsers(
        dest="subcommand", required=True, metavar="{list}"
    ).add_parser(
        "list",
        help="search the strength exercise catalog",
        description="Exercises from the Garmin Connect strength exercise catalog, "
        'sorted by name. A name goes in the "exercise" key of a strength workout '
        "file. The catalog comes with the garminconnect library, so this command "
        "needs no login.",
    )
    list_parser.add_argument(
        "--search",
        metavar="TEXT",
        help="words the name contains, in any order; with no such name, the "
        "closest names",
    )
    list_parser.add_argument(
        "--category",
        type=category,
        help=f"only exercises in this category, one of: {', '.join(CATEGORIES)}",
    )
    list_parser.add_argument(
        "--limit",
        type=positive_int,
        default=20,
        help="max exercises to return (default: 20)",
    )
    list_parser.set_defaults(run=exercise_list)
