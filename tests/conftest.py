import json
from collections.abc import Callable
from typing import Any

import pytest

from garmin_cli.cli import main


class FakeClient:
    """Returns `responses[name]` for any `client.name(...)` and records the call."""

    # `Garmin.client`, the HTTP client; a test sets it when the command uses it.
    client: Any

    def __init__(self, **responses: Any) -> None:
        self.responses = responses
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def __getattr__(self, name: str) -> Callable[..., Any]:
        if name not in self.responses:
            raise AttributeError(name)

        def method(*args: Any, **kwargs: Any) -> Any:
            self.calls.append((name, args, kwargs))
            return self.responses[name]

        return method


def run_json(argv: list[str], client: Any, capsys: pytest.CaptureFixture[str]) -> Any:
    assert main(argv, connect=lambda: client) == 0
    return json.loads(capsys.readouterr().out)
