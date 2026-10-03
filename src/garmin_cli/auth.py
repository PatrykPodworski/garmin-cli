import argparse
import os
import subprocess
from collections.abc import Callable
from typing import Any

from garminconnect import Garmin, GarminConnectAuthenticationError


def tokenstore() -> str:
    return os.environ.get("GARMINTOKENS", "~/.garminconnect")


def connect() -> Any:
    client = Garmin()
    try:
        client.login(tokenstore())
    except GarminConnectAuthenticationError:
        raise RuntimeError("no valid saved tokens, run 'garmin login'") from None
    return client


def login(_args: argparse.Namespace, _connect: Callable[[], Any]) -> dict[str, str]:
    email = os.environ.get("GARMIN_EMAIL")
    if not email:
        raise RuntimeError("set GARMIN_EMAIL to your Garmin account email")
    keychain = subprocess.run(
        ["security", "find-generic-password", "-s", "garmin", "-a", email, "-w"],
        capture_output=True,
        text=True,
    )
    if keychain.returncode != 0:
        raise RuntimeError(
            f"no Keychain password for service 'garmin', account {email}"
        )
    password = keychain.stdout.rstrip("\n")
    client = Garmin(email, password, prompt_mfa=lambda: input("MFA code: "))
    path = tokenstore()
    client.login(path)
    return {"tokenstore": path}


def register(subparsers: Any) -> None:
    login_parser = subparsers.add_parser(
        "login",
        help="log in as GARMIN_EMAIL with the Keychain password, save tokens",
    )
    login_parser.set_defaults(run=login)
