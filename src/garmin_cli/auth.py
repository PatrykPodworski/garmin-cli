import argparse
import os
import subprocess
from typing import cast

from garminconnect import Garmin, GarminConnectAuthenticationError

from garmin_cli.client import Connect, GarminClient
from garmin_cli.errors import GarminCliError


def tokenstore() -> str:
    return os.environ.get("GARMINTOKENS", "~/.garminconnect")


def connect() -> GarminClient:
    client = Garmin()
    try:
        client.login(tokenstore())
    except GarminConnectAuthenticationError:
        raise GarminCliError("No valid saved tokens.", "Run 'garmin login'.") from None
    # garminconnect ships no py.typed, so `Garmin` is Any to mypy.
    return cast(GarminClient, client)


def login(_args: argparse.Namespace, _connect: Connect) -> dict[str, str]:
    email = os.environ.get("GARMIN_EMAIL")
    if not email:
        raise GarminCliError(
            "GARMIN_EMAIL is not set.", "Set it to your Garmin account email."
        )
    keychain = subprocess.run(
        ["security", "find-generic-password", "-s", "garmin", "-a", email, "-w"],
        capture_output=True,
        text=True,
    )
    if keychain.returncode != 0:
        raise GarminCliError(
            f"No Keychain password for service 'garmin', account {email}.",
            "Add it as the README shows.",
        )
    password = keychain.stdout.rstrip("\n")
    client = Garmin(email, password, prompt_mfa=lambda: input("MFA code: "))
    path = tokenstore()
    client.login(path)
    return {"tokenstore": path}


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    login_parser = subparsers.add_parser(
        "login",
        help="log in as GARMIN_EMAIL with the Keychain password, save tokens",
    )
    login_parser.set_defaults(run=login)
