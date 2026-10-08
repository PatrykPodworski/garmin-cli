import json
from collections.abc import Callable
from typing import Any

import pytest

from garmin_cli.cli import main


class FakeClient:
    """Returns `responses[name]` for any `client.name(...)`, or raises it when it is
    an exception, and records the call."""

    def __init__(self, **responses: Any) -> None:
        self.responses = responses
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def __getattr__(self, name: str) -> Callable[..., Any]:
        if name not in self.responses:
            raise AttributeError(name)

        def method(*args: Any, **kwargs: Any) -> Any:
            self.calls.append((name, args, kwargs))
            response = self.responses[name]
            if isinstance(response, BaseException):
                raise response
            return response

        return method


def run_json(argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]) -> Any:
    assert main(argv, connect=lambda: client) == 0
    return json.loads(capsys.readouterr().out)
