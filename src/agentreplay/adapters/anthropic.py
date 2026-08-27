"""Anthropic SDK recording and replay adapter."""

from __future__ import annotations

import copy
import inspect
import time
from typing import TYPE_CHECKING, Any

from agentreplay.trace import TraceEvent

if TYPE_CHECKING:
    from agentreplay._cursor import CassetteCursor
    from agentreplay.cassette import Cassette


def _sanitize_for_json(data: Any) -> Any:
    """Recursively convert dataclasses and pydantic models to JSON types."""
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


class MessagesProxy:
    """Proxies Anthropic .messages namespace."""

    def __init__(
        self,
        real_messages: Any,
        mode: str | None,
        cassette: Cassette | None,
        cursor: CassetteCursor | None,
    ) -> None:
        self._real = real_messages
        self._mode = mode
        self._cassette = cassette
        self._cursor = cursor

    def create(self, *args: Any, **kwargs: Any) -> Any:
        from agentreplay.adapters.session import get_active_session

        active = get_active_session()
        mode = active.mode if active is not None else self._mode
        cassette = active.cassette if active is not None else self._cassette
        cursor = active.cursor if active is not None else self._cursor

        # If async call
        if inspect.iscoroutinefunction(getattr(self._real, "create", None)):
            return self._acreate(*args, **kwargs)

        model_name = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])

        if mode == "replay" and cursor is not None:
            if (
                cursor.position < len(cursor._events)
                and cursor._events[cursor.position].kind == "model_request"
            ):
                cursor.next("model_request")
            event = cursor.next("model_response")
            # Reconstruct typed Anthropic Message
            try:
                from anthropic.types import Message

                return Message.model_validate(copy.deepcopy(event.result))
            except Exception:
                return copy.deepcopy(event.result)

        # Record or unmonitored call
        response = self._real.create(*args, **kwargs)

        if mode == "record" and cassette is not None:
            cassette.append(
                TraceEvent(
                    kind="model_request",
                    timestamp=time.time(),
                    name=str(model_name),
                    arguments=_sanitize_for_json(
                        {
                            "messages": messages,
                            **{k: v for k, v in kwargs.items() if k not in ("messages", "model")},
                        }
                    ),
                )
            )
            serialized_resp = (
                response.model_dump() if hasattr(response, "model_dump") else response
            )
            cassette.append(
                TraceEvent(
                    kind="model_response",
                    timestamp=time.time(),
                    name=str(model_name),
                    result=_sanitize_for_json(serialized_resp),
                )
            )

        return response

    async def _acreate(self, *args: Any, **kwargs: Any) -> Any:
        from agentreplay.adapters.session import get_active_session

        active = get_active_session()
        mode = active.mode if active is not None else self._mode
        cassette = active.cassette if active is not None else self._cassette
        cursor = active.cursor if active is not None else self._cursor

        model_name = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])

        if mode == "replay" and cursor is not None:
            if (
                cursor.position < len(cursor._events)
                and cursor._events[cursor.position].kind == "model_request"
            ):
                cursor.next("model_request")
            event = cursor.next("model_response")
            try:
                from anthropic.types import Message

                return Message.model_validate(copy.deepcopy(event.result))
            except Exception:
                return copy.deepcopy(event.result)

        response = await self._real.create(*args, **kwargs)

        if mode == "record" and cassette is not None:
            cassette.append(
                TraceEvent(
                    kind="model_request",
                    timestamp=time.time(),
                    name=str(model_name),
                    arguments=_sanitize_for_json(
                        {
                            "messages": messages,
                            **{k: v for k, v in kwargs.items() if k not in ("messages", "model")},
                        }
                    ),
                )
            )
            serialized_resp = (
                response.model_dump() if hasattr(response, "model_dump") else response
            )
            cassette.append(
                TraceEvent(
                    kind="model_response",
                    timestamp=time.time(),
                    name=str(model_name),
                    result=_sanitize_for_json(serialized_resp),
                )
            )

        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


class AnthropicReplayWrapper:
    """Transparent proxy wrapping Anthropic or AsyncAnthropic client."""

    def __init__(
        self,
        client: Any,
        mode: str | None = None,
        cassette: Cassette | None = None,
        cursor: CassetteCursor | None = None,
    ) -> None:
        self._client = client
        self._mode = mode
        self._cassette = cassette
        self._cursor = cursor
        self.messages = MessagesProxy(client.messages, mode, cassette, cursor)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def anthropic(
    client: Any,
    *,
    mode: str | None = None,
    cassette: Cassette | None = None,
    cursor: CassetteCursor | None = None,
) -> AnthropicReplayWrapper:
    """Wrap an Anthropic or AsyncAnthropic client for recording and replay."""
    return AnthropicReplayWrapper(client, mode=mode, cassette=cassette, cursor=cursor)
