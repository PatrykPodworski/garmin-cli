import argparse
import sys
from typing import Any

from garmin_cli.client import Connect
from garmin_cli.devices import device_id, find_device
from garmin_cli.pacepro import fetch_plan, plan_id, plan_path


def send_plan(args: argparse.Namespace, connect: Connect) -> Any:
    client = connect()
    plan = fetch_plan(client, args.id)
    device = find_device(client, args.device)
    name = (plan.get("paceBandSummary") or {}).get("name")
    # garminconnect has no send call; this is the website's request. Garmin
    # answers 204 with no body, which garminconnect returns as `{}`.
    answer = client.client.post(
        "connectapi", f"{plan_path(args.id)}/device/{args.device}", api=True
    )
    what = (
        f'PacePro plan "{name}" (ID {args.id})'
        if name is not None
        else f"PacePro plan {args.id}"
    )
    device_name = device.get("displayName") or device.get("productDisplayName")
    print(
        f'garmin: Queued {what} for device "{device_name}" (ID {args.device}). '
        "The watch gets it on its next sync.",
        file=sys.stderr,
    )
    if args.raw:
        return answer
    sent = {
        "plan_id": args.id,
        "plan": name,
        "device_id": args.device,
        "device": device_name,
    }
    return {key: value for key, value in sent.items() if value is not None}


def register(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    send_parser = commands.add_parser(
        "send",
        help="queue a PacePro plan for a watch",
        description="Queues a PacePro plan for one device, like 'Send to Device' in "
        "Garmin Connect. Garmin accepting it does not mean the plan is on the watch: "
        "the watch gets it on its next sync. The plan's course has to be on the "
        "watch too; send it with 'garmin course send' if it does not arrive.",
    )
    send_parser.add_argument(
        "id", type=plan_id, help="plan ID from 'garmin pacepro list'"
    )
    send_parser.add_argument(
        "--device",
        type=device_id,
        required=True,
        help="device ID from 'garmin device list'",
    )
    send_parser.add_argument(
        "--raw", action="store_true", help="print Garmin's answer to the send"
    )
    send_parser.set_defaults(run=send_plan)
