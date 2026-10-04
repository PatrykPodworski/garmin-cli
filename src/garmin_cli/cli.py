"""`garmin` entry point. A subcommand gets the parsed args and a `connect`
function, returns JSON-serializable data, and `main` prints it to stdout."""

import argparse
import difflib
import json
import os
import re
import sys
from collections.abc import Mapping
from typing import Any, NoReturn, cast

import requests
from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from garmin_cli import activities, auth, health, sleep, stats
from garmin_cli.client import Connect
from garmin_cli.errors import GarminCliError

REQUIRED = "the following arguments are required: "
ISSUES = "https://github.com/PatrykPodworski/garmin-cli/issues"


class CliParser(argparse.ArgumentParser):
    """Reports an argument error on one stderr line, `garmin: <problem> <action>`,
    instead of a usage block."""

    # Only the top-level parser has commands.
    commands: Mapping[str, argparse.ArgumentParser] = {}

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**{**kwargs, "allow_abbrev": False})

    def fail(self, message: str) -> NoReturn:
        self.exit(2, f"garmin: {message}\n")

    def error(self, message: str) -> NoReturn:
        self.fail(self.explain(message))

    def explain(self, message: str) -> str:
        detail = re.sub(r"^argument [^:]+: ", "", message)
        # argparse's own messages start lowercase; type functions raise final ones.
        if detail[0].isupper():
            return detail
        option = message.removeprefix("argument ").partition(":")[0]
        if detail == "expected one argument":
            return f"Option '{option}' needs a value. Run '{self.prog} --help'."
        if value := re.match(r"ignored explicit argument '(.*)'", detail):
            return f"Option '{option}' takes no value. Remove '={value[1]}'."
        if self.commands and (choice := re.match(r"invalid choice: '(.*?)'", detail)):
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

    def reject(self, argv: list[str], command: str, arg: str) -> NoReturn:
        """Reports an argument the parser of `command` did not consume."""
        subparser = self.commands[command]
        prog = subparser.prog
        help = f"Run '{prog} --help' for all options."
        if not arg.startswith("-"):
            self.fail(f"Unexpected argument '{arg}' for '{prog}'. {help}")
        options = [
            option for action in subparser._actions for option in action.option_strings
        ]
        # The command's parser consumes its own options, so one left over came
        # before the command.
        if arg.partition("=")[0] in options:
            rest = list(argv)
            rest.remove(arg)
            rest.insert(rest.index(command) + 1, arg)
            self.fail(
                f"Option '{arg}' goes after the command. Run 'garmin {' '.join(rest)}'."
            )
        problem = f"Unknown option '{arg}' for '{prog}'."
        if match := difflib.get_close_matches(arg, options):
            problem += f" Did you mean '{match[0]}'?"
        self.fail(f"{problem} {help}")


def reason(error: BaseException) -> str:
    """`<type>: <message>` for an error line, without secrets and on one line."""
    text = f"{type(error).__name__}: {str(error).partition(chr(10))[0]}"
    text = re.sub(r"\?\S+", "?…", text)
    text = re.sub(r"Bearer \S+", "Bearer …", text)
    # GARMINTOKENS may hold the token JSON itself, and error texts may quote it.
    if tokens := os.environ.get("GARMINTOKENS"):
        text = text.replace(tokens, "GARMINTOKENS")
    return text[:100]


def round_floats(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, dict):
        return {key: round_floats(item) for key, item in value.items()}
    if isinstance(value, list):
        return [round_floats(item) for item in value]
    return value


def build_parser() -> CliParser:
    parser = CliParser(prog="garmin", description="Read Garmin Connect data as JSON.")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="show the full traceback for unexpected errors",
    )
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
    if argv is None:
        argv = sys.argv[1:]
    args, extras = parser.parse_known_args(argv)
    if extras:
        parser.reject(argv, args.command, extras[0])
    try:
        result = args.run(args, connect)
    except GarminCliError as error:
        message = str(error)
    except GarminConnectTooManyRequestsError:
        message = (
            "Garmin is rate-limiting requests from this machine. "
            "Wait a few minutes and try again."
        )
    except GarminConnectAuthenticationError:
        message = str(auth.not_logged_in())
    # Subclasses RequestException, so it goes before the network branch.
    except requests.exceptions.JSONDecodeError:
        message = (
            "Garmin Connect sent a response garmin-cli could not read. Try again in "
            "a few minutes; if it keeps failing, rerun with --debug and report it at "
            f"{ISSUES}."
        )
    except (
        GarminConnectConnectionError,
        requests.exceptions.RequestException,
    ) as error:
        message = (
            f"Could not reach Garmin Connect ({reason(error)}). "
            "Check your internet connection and try again."
        )
    except Exception as error:
        if args.debug:
            raise
        message = (
            f"Unexpected error ({reason(error)}). "
            f"Rerun with --debug and report it at {ISSUES}."
        )
    else:
        if not getattr(args, "raw", False):
            result = round_floats(result)
        print(json.dumps(result, indent=2))
        return 0
    print(f"garmin: {message}", file=sys.stderr)
    return 1
