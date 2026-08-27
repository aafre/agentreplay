"""agentreplay — Regression tests for AI agents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from agentreplay.cassette import Cassette
from agentreplay.diff import format_event, format_trace_diff
from agentreplay.divergence import DivergenceError
from agentreplay.trace import TraceEvent

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from agentreplay.adapters.anthropic import AnthropicReplayWrapper
    from agentreplay.adapters.openai import OpenAIReplayWrapper
    from agentreplay.adapters.pydantic_ai import AgentReplayCapability
    from agentreplay.adapters.session import Session

__version__ = "0.2.2"

__all__ = [
    "Cassette",
    "DivergenceError",
    "TraceEvent",
    "anthropic",
    "format_event",
    "format_trace_diff",
    "openai",
    "pydantic_ai",
    "session",
    "tool",
]


def pydantic_ai(
    *,
    mode: Literal["record", "replay"],
    cassette_path: str | Path,
) -> AgentReplayCapability:
    """Create a PydanticAI capability for record/replay.

    Args:
        mode: Either "record" or "replay".
        cassette_path: Path to the JSONL cassette file.

    Returns:
        An AgentReplayCapability instance.
    """
    from agentreplay.adapters.pydantic_ai import AgentReplayCapability

    return AgentReplayCapability(mode=mode, cassette_path=cassette_path)


def openai(
    client: Any,
    *,
    mode: str | None = None,
    cassette_path: str | Path | None = None,
) -> OpenAIReplayWrapper:
    """Wrap an OpenAI or AsyncOpenAI client for recording and replay."""
    from agentreplay.adapters.openai import openai as openai_wrapper
    from agentreplay.adapters.session import session as create_session

    if mode and cassette_path:
        sess = create_session(mode=mode, cassette_path=cassette_path, framework="openai")
        return openai_wrapper(client, mode=mode, cassette=sess.cassette, cursor=sess.cursor)

    return openai_wrapper(client, mode=mode)


def anthropic(
    client: Any,
    *,
    mode: str | None = None,
    cassette_path: str | Path | None = None,
) -> AnthropicReplayWrapper:
    """Wrap an Anthropic or AsyncAnthropic client for recording and replay."""
    from agentreplay.adapters.anthropic import anthropic as anthropic_wrapper
    from agentreplay.adapters.session import session as create_session

    if mode and cassette_path:
        sess = create_session(mode=mode, cassette_path=cassette_path, framework="anthropic")
        return anthropic_wrapper(client, mode=mode, cassette=sess.cassette, cursor=sess.cursor)

    return anthropic_wrapper(client, mode=mode)


def tool(
    func: Any = None,
    *,
    name: str | None = None,
    mode: str | None = None,
) -> Any:
    """Decorator to mark a Python function as a traceable agent tool."""
    from agentreplay.adapters.tools import tool as tool_decorator

    return tool_decorator(func, name=name, mode=mode)


def session(
    mode: str | None = None,
    cassette_path: str | Path | None = None,
    framework: str = "raw-sdk",
) -> Session:
    """Create a new recording or replay session context manager."""
    from agentreplay.adapters.session import session as create_session

    return create_session(mode=mode, cassette_path=cassette_path, framework=framework)
