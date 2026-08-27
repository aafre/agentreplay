# Task 3A: PydanticAI Adapter

## Goal
Create the PydanticAI adapter — an `AbstractCapability` subclass that records model/tool interactions in record mode and replays them from cassette in replay mode.

## Context
You are working on the `agentreplay` package at `c:\projects\agenttrace`. Read these files first:
- `AGENTS.md` — project principles (especially: no monkey-patching, no silent fallback)
- `src/agentreplay/trace.py` — `TraceEvent` model and `EventKind`
- `src/agentreplay/cassette.py` — `Cassette` and `CassetteHeader`
- `src/agentreplay/_cursor.py` — `CassetteCursor` (must exist before you start)
- `src/agentreplay/divergence.py` — `DivergenceError` (must exist before you start)

## Files to create

### `src/agentreplay/adapters/__init__.py`
```python
"""Framework adapters for agentreplay."""
```

### `src/agentreplay/adapters/pydantic_ai.py`

#### Imports needed
```python
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.exceptions import SkipModelRequest, SkipToolExecution
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai._agent_graph import ModelRequestContext
from pydantic_ai.tools import RunContext, ToolDefinition
```

#### Class: `AgentReplayCapability(AbstractCapability[Any])`

Constructor:
```python
def __init__(self, *, mode: Literal["record", "replay"], cassette_path: str | Path):
```

#### Record mode behaviour:

1. **`for_run`**: Return a fresh copy of self (per-run state isolation). Create a new `Cassette` instance. Set `cassette.header.framework = "pydantic-ai"`.

2. **`before_model_request`**: Record a `model_request` TraceEvent. Do NOT raise `SkipModelRequest` — let the real model call happen. Return `request_context` unchanged.

3. **`after_model_request`**: Record a `model_response` TraceEvent. Serialise `ModelResponse` via `dataclasses.asdict()` into the event's `result` field. Deep-copy the dict. Return `response` unchanged.

4. **`after_tool_execute`**: Record a `tool_result` TraceEvent with:
   - `name = call.tool_name`
   - `arguments = copy.deepcopy(dict(args))` (args is `ValidatedToolArgs`, may be dict-like)
   - `result = copy.deepcopy(result)`
   Return `result` unchanged.

5. **`after_run`**: Record a `run_end` TraceEvent. Save the cassette to `cassette_path`.

#### Replay mode behaviour:

1. **`for_run`**: Return a fresh copy. Load the `Cassette` from `cassette_path`. Create a `CassetteCursor` from the cassette events.

2. **`before_model_request`**: Get next event from cursor expecting `model_response` kind. Reconstruct a `ModelResponse` from the event's `result` dict. Raise `SkipModelRequest(response=reconstructed_response)`. The model is NEVER called.

3. **`before_tool_execute`**: Get next event from cursor expecting `tool_result` kind. Verify `call.tool_name == event.name` — if not, raise `DivergenceError`. Raise `SkipToolExecution(result=event.result)`. Tools are NEVER executed.

4. **`after_run`**: Call `cursor.assert_exhausted()` to reject leftover events.

#### Helper: `_reconstruct_model_response(data: dict) -> ModelResponse`

PydanticAI's `ModelResponse` is a dataclass with `parts` being a list of typed part objects. Reconstruct by dispatching on `part_kind`:
- `"text"` → `TextPart(content=...)`
- `"tool-call"` → `ToolCallPart(tool_name=..., args=..., tool_call_id=...)`
- Other part kinds: store raw dict for now, or raise

Also reconstruct `RequestUsage` from the usage dict if present.

**Important serialisation note**: `ModelResponse.timestamp` is a `datetime`. When round-tripping through `dataclasses.asdict()` → JSON → dict, timestamps become strings. Handle this in reconstruction (parse ISO format strings back to `datetime`).

## Test file to create: `tests/test_pydantic_ai_adapter.py`

Use PydanticAI's `TestModel` for ALL tests — no real API calls ever.

Define a simple test tool:
```python
def lookup_customer(ctx: RunContext[None], customer_id: str) -> str:
    """Look up a customer by ID."""
    return f"Customer {customer_id}: John Doe, tier=gold"
```

### Tests to write:
- `test_record_captures_model_events` — record mode produces cassette with `model_request` and `model_response` events
- `test_record_captures_tool_events` — cassette contains `tool_result` events when agent uses tools
- `test_record_cassette_saved_to_disk` — cassette file exists after run
- `test_record_cassette_is_valid_jsonl` — each line of the file is valid JSON
- `test_replay_produces_same_result` — record then replay, same output string
- `test_replay_skips_model_call` — in replay, the model's request method is not called (you can verify by checking that replay works even without a model that can handle the prompt)
- `test_replay_skips_tool_execution` — tools are not actually called during replay (use a tool that would fail if called, verify no error)
- `test_replay_divergence_on_exhausted_cassette` — if you replay with a cassette that has fewer events than the agent needs, get DivergenceError
- `test_replay_divergence_on_leftover_events` — if cassette has more events than consumed, get DivergenceError
- `test_record_deep_copies_arguments` — mutating args after recording doesn't corrupt cassette

### Test pattern:
```python
from pathlib import Path
import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from agentreplay.adapters.pydantic_ai import AgentReplayCapability


@pytest.fixture
def tmp_cassette(tmp_path: Path) -> Path:
    return tmp_path / "test.jsonl"


def test_record_then_replay(tmp_cassette: Path) -> None:
    agent = Agent(TestModel(), tools=[lookup_customer])

    # Record
    cap = AgentReplayCapability(mode="record", cassette_path=tmp_cassette)
    result1 = agent.run_sync("Look up customer 123", capabilities=[cap])

    # Replay
    cap2 = AgentReplayCapability(mode="replay", cassette_path=tmp_cassette)
    result2 = agent.run_sync("Look up customer 123", capabilities=[cap2])

    assert result1.output == result2.output
```

## Validation
```bash
uv run ruff check src/agentreplay/adapters/ tests/test_pydantic_ai_adapter.py
uv run ruff format --check src/agentreplay/adapters/ tests/test_pydantic_ai_adapter.py
uv run mypy src/agentreplay/adapters/
uv run pytest tests/test_pydantic_ai_adapter.py -v
```
All must pass. Also run existing tests to make sure nothing is broken:
```bash
uv run pytest -v
```
