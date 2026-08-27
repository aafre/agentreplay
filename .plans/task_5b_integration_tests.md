# Task 5B: Integration Tests

## Goal
Create `tests/test_integration.py` — full record → replay → divergence cycle tests.

## Context
You are working on the `agentreplay` package at `c:\projects\agenttrace`. All previous phases must be complete:
- `src/agentreplay/adapters/pydantic_ai.py` — adapter
- `src/agentreplay/_cursor.py` — cursor
- `src/agentreplay/divergence.py` — divergence error
- `src/agentreplay/diff.py` — trace diff
- `examples/support_agent.py` — example agent

Read `AGENTS.md` for project principles.

## File to create: `tests/test_integration.py`

### Requirements
Use PydanticAI's `TestModel` throughout — no real API calls ever.

Define a simple agent inline for tests:
```python
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext
from agentreplay.adapters.pydantic_ai import AgentReplayCapability
from agentreplay.divergence import DivergenceError


def lookup_customer(ctx: RunContext[None], customer_id: str) -> str:
    return f"Customer {customer_id}: John Doe"


def check_policy(ctx: RunContext[None], tier: str) -> str:
    return f"Policy for {tier}: max_refund=500"
```

### Tests to write:

1. **`test_record_then_replay_identical_result`**
   - Record a run, replay it, assert same output
   - Most important test — the core promise

2. **`test_replay_zero_model_calls`**
   - Record a run, then replay
   - In replay, pass a model that would fail if called (or verify via cassette that SkipModelRequest was used)

3. **`test_replay_zero_tool_execution`**
   - Use a tool that tracks whether it was called via a side effect (e.g. append to a list)
   - Record (tool gets called, list grows), replay (tool NOT called, list unchanged)

4. **`test_divergence_on_changed_tool`**
   - Record with agent that has tools [A, B]
   - Replay with cassette that expected tools [A, C]
   - Assert `DivergenceError` is raised

5. **`test_divergence_on_leftover_cassette_entries`**
   - Record a run that produces N events
   - Modify the cassette to have extra events
   - Replay → DivergenceError with `divergence_kind="leftover_events"`

6. **`test_cassette_is_valid_jsonl`**
   - Record a run
   - Read the file, assert every line is valid JSON

7. **`test_cassette_has_format_version`**
   - Record a run
   - Read first line, assert `format_version` field is present

8. **`test_sync_execution`**
   - `agent.run_sync()` works in both record and replay

9. **`test_async_execution`**
   - `await agent.run()` works in both record and replay
   - Use `pytest.mark.asyncio` or `async def test_...`

10. **`test_meaningful_diff_output`**
    - Trigger a DivergenceError
    - Assert the error message contains tool names and a diff-like output

### Code style
- Use `from __future__ import annotations` at the top
- Use `pytest.fixture` for common setup (tmp paths, agents)
- All code must pass `mypy --strict` and `ruff check`

## Validation
```bash
uv run ruff check tests/test_integration.py
uv run ruff format --check tests/test_integration.py
uv run mypy tests/test_integration.py
uv run pytest tests/test_integration.py -v
uv run pytest -v  # ALL tests pass
```
