# Task 3B: Update `__init__.py` Exports

## Goal
Update `src/agentreplay/__init__.py` to export key types and a convenience `pydantic_ai()` factory function.

## Context
You are working on the `agentreplay` package at `c:\projects\agenttrace`. The following modules must exist before you start:
- `src/agentreplay/divergence.py` — `DivergenceError`
- `src/agentreplay/adapters/pydantic_ai.py` — `AgentReplayCapability`

Read the current `src/agentreplay/__init__.py` (currently just has `__version__`).

## File to modify: `src/agentreplay/__init__.py`

Replace the contents with:

```python
"""agentreplay — Regression tests for AI agents."""

from __future__ import annotations

__version__ = "0.1.0"

from agentreplay.cassette import Cassette
from agentreplay.divergence import DivergenceError
from agentreplay.trace import TraceEvent

__all__ = [
    "Cassette",
    "DivergenceError",
    "TraceEvent",
    "pydantic_ai",
]


def pydantic_ai(
    *,
    mode: str,
    cassette_path: str,
) -> AgentReplayCapability:
    """Create a PydanticAI capability for record/replay.

    Args:
        mode: Either "record" or "replay".
        cassette_path: Path to the JSONL cassette file.

    Returns:
        An AgentReplayCapability instance.
    """
    from agentreplay.adapters.pydantic_ai import AgentReplayCapability

    return AgentReplayCapability(mode=mode, cassette_path=cassette_path)  # type: ignore[arg-type]
```

Note: The lazy import of `AgentReplayCapability` inside the function body is intentional — it avoids importing `pydantic_ai` as a hard dependency at package import time. The return type annotation uses a forward reference.

## Validation
```bash
uv run ruff check src/agentreplay/__init__.py
uv run ruff format --check src/agentreplay/__init__.py
uv run mypy src/agentreplay/__init__.py
uv run pytest -v
```
All must pass.
