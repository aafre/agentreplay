"""Tool function interception and wrapping for vanilla Python agent loops."""

from __future__ import annotations

import copy
import functools
import inspect
import time
from typing import TYPE_CHECKING, Any

from agentreplay.divergence import DivergenceError
from agentreplay.trace import TraceEvent

if TYPE_CHECKING:
    from collections.abc import Callable

    from agentreplay._cursor import CassetteCursor
    from agentreplay.cassette import Cassette

_ACTIVE_SESSION: Any = None


def _sanitize_for_json(data: Any) -> Any:
    """Recursively convert dataclasses, pydantic models, and sets to JSON-compatible types."""
    if data is None or isinstance(data, (str, int, float, bool)):
        return data
    if isinstance(data, dict):
        return {str(k): _sanitize_for_json(v) for k, v in data.items()}
    if isinstance(data, (list, tuple, set)):
        return [_sanitize_for_json(item) for item in data]
    if hasattr(data, "model_dump"):
        return _sanitize_for_json(data.model_dump())
    if hasattr(data, "__dataclass_fields__"):
        import dataclasses

        return _sanitize_for_json(dataclasses.asdict(data))
    return repr(data)


class ToolWrapper:
    """Wraps a callable tool to record or substitute its execution during agent runs."""

    def __init__(
        self,
        func: Callable[..., Any],
        name: str | None = None,
        mode: str | None = None,
        cassette: Cassette | None = None,
        cursor: CassetteCursor | None = None,
    ) -> None:
        self.func = func
        self.name = name or getattr(func, "__name__", "tool")
        self._mode = mode
        self._cassette = cassette
        self._cursor = cursor
        functools.update_wrapper(self, func)

    def bind_session(
        self,
        mode: str | None,
        cassette: Cassette | None,
        cursor: CassetteCursor | None,
    ) -> None:
        """Attach an active recording cassette or replay cursor."""
        self._mode = mode
        self._cassette = cassette
        self._cursor = cursor

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        mode = self._mode
        cassette = self._cassette
        cursor = self._cursor

        # If not locally bound, check global active session
        from agentreplay.adapters.session import get_active_session

        active = get_active_session()
        if active is not None and mode is None:
            mode = active.mode
            cassette = active.cassette
            cursor = active.cursor

        # Format arguments for inspection
        sig = inspect.signature(self.func)
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        safe_args = _sanitize_for_json(copy.deepcopy(bound.arguments))

        if mode == "replay" and cursor is not None:
            event = cursor.next("tool_result")
            if event.name != self.name:
                raise DivergenceError(
                    position=cursor.position - 1,
                    expected=event,
                    actual=TraceEvent(
                        kind="tool_result",
                        timestamp=time.time(),
                        name=self.name,
                        arguments=safe_args,
                    ),
                    divergence_kind="kind_mismatch",
                    message=f"Tool mismatch: expected '{event.name}', got '{self.name}'.",
                )
            return copy.deepcopy(event.result)

        # Record or unmonitored execution
        result = self.func(*args, **kwargs)

        if mode == "record" and cassette is not None:
            cassette.append(
                TraceEvent(
                    kind="tool_result",
                    timestamp=time.time(),
                    name=self.name,
                    arguments=safe_args,
                    result=_sanitize_for_json(copy.deepcopy(result)),
                )
            )

        return result


def tool(
    func: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    mode: str | None = None,
) -> Any:
    """Decorator to mark a Python function as a traceable agent tool."""
    if func is not None:
        return ToolWrapper(func, name=name, mode=mode)

    def decorator(fn: Callable[..., Any]) -> ToolWrapper:
        return ToolWrapper(fn, name=name, mode=mode)

    return decorator
