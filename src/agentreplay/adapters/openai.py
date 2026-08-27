"""OpenAI SDK recording and replay adapter."""

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
    if isinstance(data, type):
        return getattr(data, "__name__", str(data))
    if isinstance(data, dict):
        return {str(k): _sanitize_for_json(v) for k, v in data.items()}
    if isinstance(data, (list, tuple, set)):
        return [_sanitize_for_json(item) for item in data]
    if hasattr(data, "model_dump") and callable(getattr(data, "model_dump", None)):
        return _sanitize_for_json(data.model_dump())
    if hasattr(data, "__dataclass_fields__"):
        import dataclasses

        return _sanitize_for_json(dataclasses.asdict(data))
    return repr(data)


class CompletionsProxy:
    """Proxies OpenAI .chat.completions and .beta.chat.completions namespace."""

    def __init__(
        self,
        real_completions: Any,
        mode: str | None,
        cassette: Cassette | None,
        cursor: CassetteCursor | None,
    ) -> None:
        self._real = real_completions
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
            # Reconstruct typed OpenAI ChatCompletion
            try:
                from openai.types.chat import ChatCompletion

                return ChatCompletion.model_validate(copy.deepcopy(event.result))
            except Exception:
                return copy.deepcopy(event.result)

        # Record or unmonitored call
        response = self._real.create(*args, **kwargs)

        if mode == "record" and cassette is not None:
            # Capture request event
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
            # Capture response event
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
                from openai.types.chat import ChatCompletion

                return ChatCompletion.model_validate(copy.deepcopy(event.result))
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

    def parse(self, *args: Any, **kwargs: Any) -> Any:
        """Handle OpenAI Structured Outputs (client.beta.chat.completions.parse)."""
        from agentreplay.adapters.session import get_active_session

        active = get_active_session()
        mode = active.mode if active is not None else self._mode
        cassette = active.cassette if active is not None else self._cassette
        cursor = active.cursor if active is not None else self._cursor

        if inspect.iscoroutinefunction(getattr(self._real, "parse", None)):
            return self._aparse(*args, **kwargs)

        model_name = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        response_format = kwargs.get("response_format")

        if mode == "replay" and cursor is not None:
            if (
                cursor.position < len(cursor._events)
                and cursor._events[cursor.position].kind == "model_request"
            ):
                cursor.next("model_request")
            event = cursor.next("model_response")
            try:
                from openai.types.chat import ParsedChatCompletion

                parsed_comp: Any = ParsedChatCompletion.model_validate(copy.deepcopy(event.result))
                if response_format and hasattr(response_format, "model_validate_json"):
                    content_str = parsed_comp.choices[0].message.content or ""
                    parsed_comp.choices[0].message.parsed = response_format.model_validate_json(
                        content_str
                    )
                return parsed_comp
            except Exception:
                return copy.deepcopy(event.result)

        response = self._real.parse(*args, **kwargs)

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

    async def _aparse(self, *args: Any, **kwargs: Any) -> Any:
        from agentreplay.adapters.session import get_active_session

        active = get_active_session()
        mode = active.mode if active is not None else self._mode
        cassette = active.cassette if active is not None else self._cassette
        cursor = active.cursor if active is not None else self._cursor

        model_name = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        response_format = kwargs.get("response_format")

        if mode == "replay" and cursor is not None:
            if (
                cursor.position < len(cursor._events)
                and cursor._events[cursor.position].kind == "model_request"
            ):
                cursor.next("model_request")
            event = cursor.next("model_response")
            try:
                from openai.types.chat import ParsedChatCompletion

                parsed_comp: Any = ParsedChatCompletion.model_validate(copy.deepcopy(event.result))
                if response_format and hasattr(response_format, "model_validate_json"):
                    content_str = parsed_comp.choices[0].message.content or ""
                    parsed_comp.choices[0].message.parsed = response_format.model_validate_json(
                        content_str
                    )
                return parsed_comp
            except Exception:
                return copy.deepcopy(event.result)

        response = await self._real.parse(*args, **kwargs)

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


class ChatProxy:
    """Proxies OpenAI .chat namespace."""

    def __init__(
        self,
        real_chat: Any,
        mode: str | None,
        cassette: Cassette | None,
        cursor: CassetteCursor | None,
    ) -> None:
        self._real = real_chat
        self.completions = CompletionsProxy(real_chat.completions, mode, cassette, cursor)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


class BetaProxy:
    """Proxies OpenAI .beta namespace."""

    def __init__(
        self,
        real_beta: Any,
        mode: str | None,
        cassette: Cassette | None,
        cursor: CassetteCursor | None,
    ) -> None:
        self._real = real_beta
        if hasattr(real_beta, "chat"):
            self.chat = ChatProxy(real_beta.chat, mode, cassette, cursor)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


class OpenAIReplayWrapper:
    """Transparent proxy wrapping OpenAI or AsyncOpenAI client."""

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
        self.chat = ChatProxy(client.chat, mode, cassette, cursor)
        if hasattr(client, "beta"):
            self.beta = BetaProxy(client.beta, mode, cassette, cursor)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def openai(
    client: Any,
    *,
    mode: str | None = None,
    cassette: Cassette | None = None,
    cursor: CassetteCursor | None = None,
) -> OpenAIReplayWrapper:
    """Wrap an OpenAI or AsyncOpenAI client for recording and replay."""
    return OpenAIReplayWrapper(client, mode=mode, cassette=cassette, cursor=cursor)
