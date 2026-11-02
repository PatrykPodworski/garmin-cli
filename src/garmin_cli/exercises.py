import argparse
import re
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


def display_name(category: str | None, exercise: str | None) -> str | None:
    """The catalog name of a step's exercise. A warm-up or cool-down step has an
    empty exercise name, and an exercise newer than the catalog shows its keys."""
    if not (category and exercise):
        return None
    return BY_KEYS.get((category, exercise), f"{category}/{exercise}")


def exercise_list(args: argparse.Namespace, _connect: Connect) -> Any:
    query = words(args.search or "").split()
    found = sorted(
        (
            exercise
            for exercise in EXERCISES
            if all(word in words(exercise["name"]) for word in query)
        ),
        key=lambda exercise: exercise["name"].lower(),
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
        help="words the name contains, in any order",
    )
    list_parser.add_argument(
        "--limit",
        type=positive_int,
        default=20,
        help="max exercises to return (default: 20)",
    )
    list_parser.set_defaults(run=exercise_list)
