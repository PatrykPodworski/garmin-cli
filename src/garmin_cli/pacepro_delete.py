import argparse
import sys
from typing import Any

from garmin_cli.client import Connect
from garmin_cli.pacepro import fetch_plan, plan_id, plan_path


def delete_plan(args: argparse.Namespace, connect: Connect) -> Any:
    client = connect()
    plan = fetch_plan(client, args.id)
    name = (plan.get("paceBandSummary") or {}).get("name")
    what = f'PacePro plan "{name}"' if name is not None else f"PacePro plan {args.id}"
    if args.dry_run:
        print(f"garmin: Would delete {what}.", file=sys.stderr)
        return {"would_delete": args.id}
    # garminconnect has no delete call; this is the website's request. Garmin
    # answers 204 with no body.
    client.client.delete("connectapi", plan_path(args.id), api=True)
    print(f"garmin: Deleted {what}.", file=sys.stderr)
    return {"deleted": args.id}


def register(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    delete_parser = commands.add_parser(
        "delete",
        help="delete a PacePro plan",
        description="Deletes a PacePro plan from Garmin Connect without asking. "
        "--dry-run shows what would be deleted.",
    )
    delete_parser.add_argument(
        "id", type=plan_id, help="plan ID from 'garmin pacepro list'"
    )
    delete_parser.add_argument(
        "--dry-run", action="store_true", help="show the plan, delete nothing"
    )
    delete_parser.set_defaults(run=delete_plan)
