import argparse
from typing import Any

from garmin_cli.client import Connect, GarminClient
from garmin_cli.errors import GarminCliError

LIST_IDS = "Run 'garmin device list' to list IDs."


def device_id(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        number = 0
    if number < 1:
        raise argparse.ArgumentTypeError(f"Invalid device ID '{value}'. {LIST_IDS}")
    return number


def summarize(raw: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "id": raw.get("deviceId"),
        "name": raw.get("displayName"),
        "model": raw.get("productDisplayName"),
    }
    return {name: value for name, value in summary.items() if value is not None}


def find_device(client: GarminClient, device_id: int) -> dict[str, Any]:
    """The account's device with this ID; Garmin has no call for one device."""
    for device in client.get_devices():
        if device.get("deviceId") == device_id:
            return device
    raise GarminCliError(f"No device with ID {device_id}.", LIST_IDS)


def device_list(args: argparse.Namespace, connect: Connect) -> Any:
    found = connect().get_devices()
    return found if args.raw else [summarize(device) for device in found]


def register(subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    device_parser = subparsers.add_parser(
        "device", help="devices: the watches registered to the account"
    )
    # `CliParser.explain` names a missing command by this metavar.
    commands = device_parser.add_subparsers(
        dest="subcommand", required=True, metavar="{list}"
    )
    list_parser = commands.add_parser(
        "list",
        help="registered devices",
        description="The devices registered to the Garmin Connect account, with "
        "the ID that 'garmin course send --device' takes.",
    )
    list_parser.add_argument(
        "--raw", action="store_true", help="print the full Garmin response"
    )
    list_parser.set_defaults(run=device_list)
