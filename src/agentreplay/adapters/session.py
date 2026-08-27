"""Active recording & replay session management for raw SDK adapters."""

from __future__ import annotations

import contextvars
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentreplay._cursor import CassetteCursor
from agentreplay.cassette import Cassette, CassetteHeader
from agentreplay.trace import TraceEvent

if TYPE_CHECKING:
    from agentreplay.adapters.anthropic import AnthropicReplayWrapper
    from agentreplay.adapters.openai import OpenAIReplayWrapper

_session_var: contextvars.ContextVar[Session | None] = contextvars.ContextVar(
    "_agentreplay_active_session", default=None
)


def get_active_session() -> Session | None:
    """Return the currently active agentreplay recording/replay session, if any."""
    return _session_var.get()


class Session:
    """Manages recording and replaying state across clients and tools."""

    def __init__(
        self,
        mode: str | None = None,
        cassette_path: str | Path | None = None,
        framework: str = "raw-sdk",
    ) -> None:
        self.mode = mode
        self.cassette_path = Path(cassette_path) if cassette_path else None
        self.framework = framework
        self.cassette: Cassette | None = None
        self.cursor: CassetteCursor | None = None
        self._token: contextvars.Token[Session | None] | None = None

        if self.mode == "record":
            self.cassette = Cassette(header=CassetteHeader(framework=self.framework))
            self.cassette.append(TraceEvent(kind="run_start", timestamp=time.time()))
        elif self.mode == "replay":
            if self.cassette_path and self.cassette_path.exists():
                loaded = Cassette.load(self.cassette_path)
                self.cursor = CassetteCursor(loaded.events)
                # Consume run_start if present
                if loaded.events and loaded.events[0].kind == "run_start":
                    self.cursor.next("run_start")
            else:
                self.cursor = CassetteCursor([])

    def __enter__(self) -> Session:
        self._token = _session_var.set(self)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            if exc_type is None:
                if self.mode == "record" and self.cassette is not None and self.cassette_path:
                    self.cassette.append(TraceEvent(kind="run_end", timestamp=time.time()))
                    self.cassette.save(self.cassette_path)
                elif self.mode == "replay" and self.cursor is not None:
                    # Consume run_end if present, then verify exhaustion
                    if (
                        self.cursor.position < len(self.cursor._events)
                        and self.cursor._events[self.cursor.position].kind == "run_end"
                    ):
                        self.cursor.next("run_end")
                    self.cursor.assert_exhausted()
        finally:
            if self._token is not None:
                _session_var.reset(self._token)
                self._token = None

    def wrap_openai(self, client: Any) -> OpenAIReplayWrapper:
        """Wrap an OpenAI or AsyncOpenAI client for recording/replaying."""
        from agentreplay.adapters.openai import openai as openai_wrapper

        return openai_wrapper(client, mode=self.mode, cassette=self.cassette, cursor=self.cursor)

    def wrap_anthropic(self, client: Any) -> AnthropicReplayWrapper:
        """Wrap an Anthropic or AsyncAnthropic client for recording/replaying."""
        from agentreplay.adapters.anthropic import anthropic as anthropic_wrapper

        return anthropic_wrapper(
            client, mode=self.mode, cassette=self.cassette, cursor=self.cursor
        )

    def wrap(self, client: Any) -> Any:
        """Auto-detect client type and wrap it."""
        client_type = type(client).__module__
        if "openai" in client_type:
            return self.wrap_openai(client)
        if "anthropic" in client_type:
            return self.wrap_anthropic(client)
        msg = f"Unsupported client type: {type(client)}. Expected OpenAI or Anthropic client."
        raise TypeError(msg)


def session(
    mode: str | None = None,
    cassette_path: str | Path | None = None,
    framework: str = "raw-sdk",
) -> Session:
    """Create a new recording/replay session."""
    return Session(mode=mode, cassette_path=cassette_path, framework=framework)
