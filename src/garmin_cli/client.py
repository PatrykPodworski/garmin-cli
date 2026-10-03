from collections.abc import Callable
from typing import Any, Protocol


class GarminClient(Protocol):
    """The `garminconnect.Garmin` methods the subcommands call."""

    def get_stats(self, _cdate: str, /) -> dict[str, Any]: ...

    def get_sleep_data(self, _cdate: str, /) -> dict[str, Any]: ...

    def get_weigh_ins(self, _start: str, _end: str, /) -> dict[str, Any]: ...

    def get_blood_pressure(self, _start: str, _end: str, /) -> dict[str, Any]: ...

    def get_activities(
        self, _start: int, _limit: int, /, *, activitytype: str | None
    ) -> list[dict[str, Any]]: ...

    def get_activities_by_date(
        self, _start: str, _end: str | None, _activitytype: str | None, /
    ) -> list[dict[str, Any]]: ...

    def get_activity(self, _activity_id: str, /) -> dict[str, Any]: ...

    def get_activity_splits(self, _activity_id: str, /) -> dict[str, Any]: ...

    def get_activity_hr_in_timezones(
        self, _activity_id: str, /
    ) -> list[dict[str, Any]]: ...


Connect = Callable[[], GarminClient]
