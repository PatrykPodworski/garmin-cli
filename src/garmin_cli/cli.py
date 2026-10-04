"""`garmin` entry point. A subcommand gets the parsed args and a `connect`
function, returns JSON-serializable data, and `main` prints it to stdout."""

import argparse
import difflib
import json
import re
import sys
from typing import NoReturn, cast

from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from garmin_cli import activities, auth, health, sleep, stats
from garmin_cli.client import Connect
from garmin_cli.errors import GarminCliError

REQUIRED = "the following arguments are required: "


class CliParser(argparse.ArgumentParser):
    """Reports an argument error on one stderr line, `garmin: <problem> <action>`,
    instead of a usage block."""

    commands: dict[str, argparse.ArgumentParser]

    def fail(self, message: str) -> NoReturn:
        self.exit(2, f"garmin: {message}\n")

    def error(self, message: str) -> NoReturn:
        self.fail(self.explain(message))

    def explain(self, message: str) -> str:
        detail = re.sub(r"^argument [^:]+: ", "", message)
        # argparse's own messages start lowercase; type functions raise final ones.
        if detail[0].isupper():
            return detail
        if choice := re.match(r"invalid choice: '(.*?)'", detail):
            name = choice[1]
            if match := difflib.get_close_matches(name, self.commands):
                return f"Unknown command '{name}'. Did you mean '{match[0]}'?"
            return f"Unknown command '{name}'. {self.run_command()}"
        if detail.startswith(REQUIRED):
            name = detail.removeprefix(REQUIRED)
            if name == "command":
                return f"No command given. {self.run_command()}"
            if name == "id":
                return (
                    "Missing activity ID. Run 'garmin activities' to list IDs, "
                    "then 'garmin activity <id>'."
                )
            return f"Missing {name} for '{self.prog}'. Run '{self.prog} --help'."
        # ponytail: only `garmin sleep` has mutually exclusive arguments; name
        # them from the message once a second command gets a group.
        if detail.startswith("not allowed with argument "):
            return (
                "Give either a date or --night-of, not both. Use 'garmin sleep DATE' "
                "for the wake-up date or 'garmin sleep --night-of DATE' for the "
                "lights-out date."
            )
        return f"{message[0].upper()}{message[1:]}. Run '{self.prog} --help'."

    def run_command(self) -> str:
        return f"Run 'garmin <command>', one of: {', '.join(self.commands)}."

    def reject(self, command: str, arg: str) -> NoReturn:
        """Reports an argument the parser of `command` did not consume."""
        subparser = self.commands[command]
        prog = subparser.prog
        help = f"Run '{prog} --help' for all options."
        if not arg.startswith("-"):
            self.fail(f"Unexpected argument '{arg}' for '{prog}'. {help}")
        options = [
            option for action in subparser._actions for option in action.option_strings
        ]
        problem = f"Unknown option '{arg}' for '{prog}'."
        if match := difflib.get_close_matches(arg, options):
            problem += f" Did you mean '{match[0]}'?"
        self.fail(f"{problem} {help}")


def build_parser() -> CliParser:
    parser = CliParser(prog="garmin", description="Read Garmin Connect data as JSON.")
    # Subparsers are CliParsers too; the cast matches the invariant type the
    # `register` functions take.
    subparsers = cast(
        "argparse._SubParsersAction[argparse.ArgumentParser]",
        parser.add_subparsers(dest="command", required=True),
    )
    auth.register(subparsers)
    health.register(subparsers)
    sleep.register(subparsers)
    activities.register(subparsers)
    stats.register(subparsers)
    parser.commands = subparsers.choices
    return parser


def main(argv: list[str] | None = None, connect: Connect = auth.connect) -> int:
    parser = build_parser()
    args, extras = parser.parse_known_args(argv)
    if extras:
        parser.reject(args.command, extras[0])
    try:
        result = args.run(args, connect)
    # OSError covers network failures: requests exceptions subclass it.
    except (
        GarminCliError,
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
        OSError,
    ) as error:
        print(f"garmin: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0
