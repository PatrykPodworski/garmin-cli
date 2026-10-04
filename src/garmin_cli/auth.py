import argparse
import os
import subprocess
from typing import cast

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from garmin_cli.client import Connect, GarminClient
from garmin_cli.errors import GarminCliError


def tokenstore() -> str:
    return os.environ.get("GARMINTOKENS", "~/.garminconnect")


def tokenstore_name() -> str:
    """The tokenstore for output. GARMINTOKENS may hold the token JSON itself, so
    its value is never printed."""
    if "GARMINTOKENS" in os.environ:
        return "the token store in GARMINTOKENS"
    return tokenstore()


def not_logged_in() -> GarminCliError:
    return GarminCliError(
        f"Not logged in: no valid saved login in {tokenstore_name()}.",
        "Run 'garmin login'.",
    )


def connect() -> GarminClient:
    client = Garmin()
    try:
        client.login(tokenstore())
    except GarminConnectAuthenticationError:
        # Garmin reports missing and expired tokens the same way.
        raise not_logged_in() from None
    # garminconnect ships no py.typed, so `Garmin` is Any to mypy.
    return cast(GarminClient, client)


def ask_mfa_code() -> str:
    try:
        code = input("MFA code: ")
    except EOFError:
        code = ""
    if not code:
        raise GarminCliError(
            "No MFA code entered.",
            "Run 'garmin login' in a terminal and type the code from your Garmin "
            "app or email.",
        )
    return code


def login(_args: argparse.Namespace, _connect: Connect) -> dict[str, str]:
    email = os.environ.get("GARMIN_EMAIL")
    if not email:
        raise GarminCliError(
            "GARMIN_EMAIL is not set.",
            "Run 'export GARMIN_EMAIL=you@example.com' with your Garmin account email.",
        )
    path = tokenstore()
    try:
        keychain = subprocess.run(
            ["security", "find-generic-password", "-s", "garmin", "-a", email, "-w"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        raise GarminCliError(
            "'garmin login' reads the password from the macOS Keychain, which is "
            "not available here.",
            "Copy a token folder from a Mac that ran 'garmin login' and point "
            "GARMINTOKENS at it."
            if "GARMINTOKENS" in os.environ
            else f"Log in on a Mac and copy {tokenstore()} to this machine, or set "
            "GARMINTOKENS to a copied token folder.",
        ) from None
    if keychain.returncode != 0:
        raise GarminCliError(
            f"No Keychain password for account {email} (service 'garmin').",
            f"Add it with 'security add-generic-password -s garmin -a {email} -w'.",
        )
    password = keychain.stdout.rstrip("\n")
    client = Garmin(email, password, prompt_mfa=ask_mfa_code)
    try:
        client.login(path)
    except GarminConnectAuthenticationError:
        raise GarminCliError(
            f"Garmin rejected the login for {email}.",
            "Check the Keychain password for service 'garmin' and run "
            "'garmin login' again.",
        ) from None
    except GarminConnectTooManyRequestsError:
        raise GarminCliError(
            "Garmin is rate-limiting logins from this machine.",
            "Wait about an hour, then run 'garmin login' again.",
        ) from None
    except GarminConnectConnectionError as error:
        # garminconnect wraps what prompt_mfa raises in a connection error, but
        # turns it into an auth error when its text contains "authentication",
        # "401", "unauthorized" or "login failed"; the MFA message avoids them.
        if isinstance(error.__cause__, GarminCliError):
            raise error.__cause__ from None
        raise
    return {"tokenstore": tokenstore_name()}


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    login_parser = subparsers.add_parser(
        "login",
        help="log in as GARMIN_EMAIL with the Keychain password, save tokens",
    )
    login_parser.set_defaults(run=login)
