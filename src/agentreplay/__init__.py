"""agentreplay — Regression tests for AI agents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from agentreplay.cassette import Cassette
from agentreplay.diff import format_event, format_trace_diff
from agentreplay.divergence import DivergenceError
from agentreplay.trace import TraceEvent

if TYPE_CHECKING:
    from pathlib import Path

    from agentreplay.adapters.pydantic_ai import AgentReplayCapability

__version__ = "0.1.2"

__all__ = [
    "Cassette",
    "DivergenceError",
    "TraceEvent",
    "format_event",
    "format_trace_diff",
    "pydantic_ai",
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
