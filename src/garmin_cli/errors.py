import re

ISSUES = "https://github.com/PatrykPodworski/garmin-cli/issues"


class GarminCliError(Exception):
    """An expected failure that `main` reports as `garmin: <problem> <action>`."""

    def __init__(self, problem: str, action: str) -> None:
        super().__init__(f"{problem} {action}")


def client_error(error: BaseException) -> int | None:
    """The 4xx status Garmin answered with. garminconnect puts it only in the
    message, as `API Error <status>`; a 5xx or a network failure has none."""
    if match := re.search(r"API Error (4\d\d)\b", str(error)):
        return int(match[1])
    return None
