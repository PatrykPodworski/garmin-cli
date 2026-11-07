import argparse
import sys
from typing import Any

from garmin_cli.client import Connect
from garmin_cli.courses import course_id, fetch_course
from garmin_cli.devices import device_id, find_device


def send_course(args: argparse.Namespace, connect: Connect) -> Any:
    client = connect()
    course = fetch_course(client, args.id)
    device = find_device(client, args.device)
    name = course.get("courseName")
    # garminconnect sends workouts with `push_workout_to_device` but has no call
    # for courses. This is the same device message with the course fields of
    # bpauli/gccli `SendCourseToDevice` (internal/garminapi/courses.go).
    answer = client.client.post(
        "connectapi",
        "/device-service/devicemessage/messages",
        json=[
            {
                "deviceId": args.device,
                "messageUrl": f"course-service/course/fit/{args.id}/{args.device}"
                "?elevation=true",
                "messageType": "courses",
                "messageName": name,
                "groupName": None,
                "priority": 0,
                "fileType": "FIT",
                "metaDataId": args.id,
            }
        ],
        api=True,
    )
    device_name = device.get("displayName") or device.get("productDisplayName")
    print(
        f'garmin: Queued course "{name}" (ID {args.id}) for device "{device_name}" '
        f"(ID {args.device}). The watch gets it on its next sync.",
        file=sys.stderr,
    )
    if args.raw:
        return answer
    message = answer[0] if isinstance(answer, list) and answer else {}
    sent = {
        "course_id": args.id,
        "course": name,
        "device_id": args.device,
        "device": device_name,
        "message_id": message.get("messageId"),
    }
    return {key: value for key, value in sent.items() if value is not None}


def register(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    send_parser = commands.add_parser(
        "send",
        help="queue a course for a watch",
        description="Queues a saved course for one device, like 'Send to Device' in "
        "Garmin Connect. Garmin accepting the message does not mean the course is on "
        "the watch: the watch gets it on its next sync.",
    )
    send_parser.add_argument(
        "id", type=course_id, help="course ID from 'garmin course list'"
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
    send_parser.set_defaults(run=send_course)
