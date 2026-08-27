# agentreplay — Implementation Plan

## Status Summary

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Trace + Cassette core | ✅ Complete |
| Phase 2 | CassetteCursor + DivergenceError + TraceDiff | 🔲 Not started |
| Phase 3 | PydanticAI adapter (record + replay) | 🔲 Not started |
| Phase 4 | pytest plugin | 🔲 Not started |
| Phase 5 | End-to-end example + integration tests | 🔲 Not started |

---

## What already exists

```
src/agentreplay/
├── __init__.py          # Exports __version__ only
├── trace.py             # TraceEvent dataclass — 7 event kinds, canonical JSON, frozen
├── cassette.py          # Cassette + CassetteHeader — JSONL persistence, deep-copy, format_version=1
└── pytest_plugin.py     # Stub (empty docstring)

tests/
├── conftest.py          # Empty
├── test_trace.py        # 9 tests + hypothesis property tests — all passing
└── test_cassette.py     # 9 tests — round-trip, determinism, deep-copy, errors
```

Architecture from `AGENTS.md`:
```
src/agentreplay/
├── trace.py          # TraceEvent — framework-independent event model
├── cassette.py       # Cassette — JSONL persistence with format versioning
├── _cursor.py        # CassetteCursor — stateful replay position (internal)
├── divergence.py     # DivergenceError — structured failure with diff
├── diff.py           # TraceDiff — human-readable trajectory comparison
├── pytest_plugin.py  # pytest integration (--agentreplay flag, fixture)
└── adapters/
    └── pydantic_ai.py  # PydanticAI AbstractCapability for record/replay
```

---

## PydanticAI API Reference (v2.35.0)

This section is critical context for Phase 3. The adapter must use these APIs.

### AbstractCapability hooks (used for record/replay)

```python
from pydantic_ai.capabilities.abstract import AbstractCapability

class AbstractCapability(ABC, Generic[AgentDepsT]):
    # --- Lifecycle ---
    async for_run(self, ctx: RunContext[AgentDepsT]) -> AbstractCapability[AgentDepsT]
        # Called once per run. Return fresh instance for per-run state isolation.

    async before_run(self, ctx: RunContext[AgentDepsT]) -> None
        # Called before agent run starts. Observe-only.

    async after_run(self, ...)
        # Called after agent run completes.

    # --- Model hooks (RECORD: observe; REPLAY: raise SkipModelRequest) ---
    async before_model_request(self, ctx, request_context: ModelRequestContext) -> ModelRequestContext
        # Called before each model call. In replay, raise SkipModelRequest(recorded_response).

    async after_model_request(self, ctx, *, request_context, response: ModelResponse) -> ModelResponse
        # Called after model responds. In record, capture the response.

    # --- Tool hooks (RECORD: observe; REPLAY: raise SkipToolExecution) ---
    async before_tool_execute(self, ctx, *, call: ToolCallPart, tool_def, args: ValidatedToolArgs) -> ValidatedToolArgs
        # Called before tool runs. In replay, raise SkipToolExecution(recorded_result).

    async after_tool_execute(self, ctx, *, call: ToolCallPart, tool_def, args, result: Any) -> Any
        # Called after tool runs. In record, capture the result.
```

### Skip exceptions (used for replay interception)

```python
from pydantic_ai.exceptions import SkipModelRequest, SkipToolExecution

# Replay model: raise in before_model_request to skip the actual model call
raise SkipModelRequest(response=recorded_model_response)

# Replay tool: raise in before_tool_execute to skip the actual tool execution
raise SkipToolExecution(result=recorded_tool_result)
```

### Message types (for serialisation)

```python
from pydantic_ai.messages import (
    ModelResponse,  # dataclass — parts, usage, model_name, timestamp, kind="response"
    ModelRequest,  # dataclass — parts, kind="request"
    TextPart,  # part_kind="text", content: str
    ToolCallPart,  # part_kind="tool-call", tool_name, args, tool_call_id
    ToolReturnPart,  # part_kind="tool-return", tool_name, content, tool_call_id
    UserPromptPart,  # part_kind="user-prompt", content: str
)
```

`ModelResponse` and `ModelRequest` are **dataclasses** (not Pydantic models). Use `dataclasses.asdict()` for serialisation and reconstruct from dicts.

### ModelRequestContext

```python
@dataclass
class ModelRequestContext:
    model: Model
    messages: list[ModelMessage]
    model_settings: ModelSettings | None
    model_request_parameters: ModelRequestParameters
    model_id: ...
    streaming: ...
```

---

## Phase 2 — CassetteCursor, DivergenceError, TraceDiff

### Task 2A: CassetteCursor (`src/agentreplay/_cursor.py`)

**What**: A stateful, one-shot iterator over cassette events used during replay to track position and detect divergence.

**File**: `src/agentreplay/_cursor.py` (new file, internal module — underscore prefix)

**Requirements**:
1. Wraps a `list[TraceEvent]` from a loaded `Cassette`
2. `next(kind: EventKind) -> TraceEvent` — returns the next event, raises `DivergenceError` if:
   - No more events remain (cassette exhausted)
   - Next event's `kind` doesn't match the expected `kind`
3. `assert_exhausted() -> None` — raises `DivergenceError` if unconsumed events remain (agent stopped early)
4. One-shot: no re-iteration, no resetting position
5. Track current position index for error messages
6. Internal module (not exported from `__init__.py`)

**Test file**: `tests/test_cursor.py` (new)

**Tests to write**:
- `test_next_returns_matching_event` — happy path
- `test_next_advances_position` — sequential reads
- `test_next_raises_on_exhausted` — no more events
- `test_next_raises_on_kind_mismatch` — wrong event kind
- `test_assert_exhausted_passes_when_empty` — all consumed
- `test_assert_exhausted_raises_with_leftover` — unconsumed events
- `test_one_shot_no_reset` — no way to restart iteration

**Depends on**: `TraceEvent` from `trace.py`, `DivergenceError` from Task 2B

**Implementation order**: Implement Task 2B first (DivergenceError), then 2A.

---

### Task 2B: DivergenceError (`src/agentreplay/divergence.py`)

**What**: A structured exception raised when replay diverges from the recorded cassette. Carries enough context for a human-readable diff.

**File**: `src/agentreplay/divergence.py` (new)

**Requirements**:
1. Subclass of `AssertionError` (so pytest treats it as a test failure)
2. Fields:
   - `position: int` — the step index where divergence occurred (0-based)
   - `expected: TraceEvent | None` — what the cassette said should happen
   - `actual: TraceEvent | None` — what actually happened (None if cassette exhausted)
   - `message: str` — human-readable summary
3. `__str__` must produce a clear, developer-friendly message like:
   ```
   Divergence at step 3:
     Expected: tool_call: check_refund_policy(tier="gold")
     Actual:   tool_call: refund_customer(amount=39)
   ```
4. Include a `kind` property: `"kind_mismatch"`, `"cassette_exhausted"`, `"leftover_events"`, `"argument_mismatch"`

**Test file**: `tests/test_divergence.py` (new)

**Tests to write**:
- `test_kind_mismatch_message` — clear output
- `test_cassette_exhausted_message` — no more events
- `test_leftover_events_message` — agent stopped early
- `test_is_assertion_error` — `isinstance(err, AssertionError)` is True
- `test_fields_accessible` — position, expected, actual are set

**Depends on**: `TraceEvent` from `trace.py`

---

### Task 2C: TraceDiff (`src/agentreplay/diff.py`)

**What**: Human-readable trajectory comparison between recorded and actual event sequences.

**File**: `src/agentreplay/diff.py` (new)

**Requirements**:
1. `format_trace_diff(expected: list[TraceEvent], actual: list[TraceEvent]) -> str`
   - Produces a side-by-side or sequential diff of two event lists
   - Shows numbered steps
   - Highlights the first divergence point
   - Format tool calls with name and arguments: `tool: lookup_customer(id="123")`
   - Format model events concisely: `model_request`, `model_response → "text..."`
2. `format_event(event: TraceEvent) -> str`
   - Single-line human-readable representation of one event
   - Tool events: `tool_call: name(arg1=val1, arg2=val2)`
   - Model events: `model_request` or `model_response → "truncated text..."`
   - Run events: `run_start` / `run_end`
3. Output should look like:
   ```
   Agent trajectory changed

   Expected:
     1. model_request
     2. tool_call: lookup_customer(id="123")
     3. tool_call: check_refund_policy(tier="gold")
     4. model_response → "Refund processed."

   Actual:
     1. model_request
     2. tool_call: lookup_customer(id="123")
     3. tool_call: refund_customer(amount=39)

   Divergence at step 3:
     - tool_call: check_refund_policy(tier="gold")
     + tool_call: refund_customer(amount=39)
   ```

**Test file**: `tests/test_diff.py` (new)

**Tests to write**:
- `test_format_event_tool_call` — tool name + args
- `test_format_event_model_request` — concise
- `test_format_event_model_response_truncates` — long text truncated
- `test_format_trace_diff_identical` — no diff when equal
- `test_format_trace_diff_divergence` — shows first difference
- `test_format_trace_diff_different_lengths` — handles missing/extra events
- `test_format_trace_diff_empty_vs_events` — edge case

**Depends on**: `TraceEvent` from `trace.py`

---

## Phase 3 — PydanticAI Adapter (Record + Replay)

### Task 3A: PydanticAI Adapter (`src/agentreplay/adapters/pydantic_ai.py`)

**What**: An `AbstractCapability` subclass that records model/tool interactions in record mode and replays them from cassette in replay mode.

**File**: `src/agentreplay/adapters/pydantic_ai.py` (new file, create `adapters/` package)

**Also create**: `src/agentreplay/adapters/__init__.py` (empty, just docstring)

**Requirements**:

#### Record mode:
1. `before_run`: create a new `Cassette`, emit `run_start` event
2. `after_model_request`: capture `ModelResponse` as a `model_response` TraceEvent
   - Serialise the full `ModelResponse` via `dataclasses.asdict()` into event's `result` field
   - Deep-copy before storing
3. `before_model_request`: record a `model_request` TraceEvent (capture the messages/request context)
   - Do NOT raise `SkipModelRequest` — let the real model run
4. `after_tool_execute`: capture tool result as `tool_result` TraceEvent
   - `name` = tool name from `call.tool_name`
   - `arguments` = deep-copy of args dict
   - `result` = deep-copy of result
5. `after_run`: emit `run_end` event, save cassette to disk

#### Replay mode:
1. `before_run`: load cassette from disk, create `CassetteCursor`
2. `before_model_request`:
   - Get next `model_response` event from cursor
   - Reconstruct `ModelResponse` from the stored dict
   - Raise `SkipModelRequest(response=reconstructed_response)`
   - This means the model is NEVER called
3. `before_tool_execute`:
   - Get next `tool_result` event from cursor
   - Verify tool name matches: `call.tool_name == event.name`
   - Raise `SkipToolExecution(result=event.result)`
   - This means tools are NEVER executed
4. `after_run`: call `cursor.assert_exhausted()` to reject leftover events

#### Class structure:
```python
from pydantic_ai.capabilities import AbstractCapability


class AgentReplayCapability(AbstractCapability[Any]):
    def __init__(self, *, mode: Literal["record", "replay"], cassette_path: str | Path): ...
```

#### Serialisation of PydanticAI types:
- `ModelResponse` → `dataclasses.asdict()` → store in TraceEvent `result`
- Reconstruct: from dict, rebuild `ModelResponse` with correct part types based on `part_kind`
- Part types: `TextPart` (`part_kind="text"`), `ToolCallPart` (`part_kind="tool-call"`), etc.
- Write a helper `_reconstruct_model_response(data: dict) -> ModelResponse` that dispatches on `part_kind`

**Important**: The adapter translates between PydanticAI's native types and our framework-independent `TraceEvent`. The cassette stores `TraceEvent`s. The adapter converts PydanticAI `ModelResponse` → `TraceEvent.result` dict on record, and `TraceEvent.result` dict → PydanticAI `ModelResponse` on replay.

**Test file**: `tests/test_pydantic_ai_adapter.py` (new)

**Tests to write** (use PydanticAI `TestModel` — no real API calls):
- `test_record_captures_model_interaction` — record mode produces cassette with model events
- `test_record_captures_tool_calls` — tool_call and tool_result events present
- `test_record_cassette_saved_to_disk` — file exists after record run
- `test_replay_no_model_calls` — replay uses recorded response, TestModel not called
- `test_replay_no_tool_execution` — tools not actually executed in replay
- `test_replay_divergence_wrong_tool` — raises DivergenceError if tool name differs
- `test_replay_divergence_leftover` — raises DivergenceError if cassette has unconsumed events
- `test_replay_divergence_exhausted` — raises DivergenceError if cassette runs out
- `test_record_then_replay_round_trip` — record a run, replay it, same result
- `test_record_deep_copies_args` — mutation after capture doesn't corrupt cassette

**Example test pattern** (for the implementer):
```python
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from agentreplay.adapters.pydantic_ai import AgentReplayCapability

agent = Agent(
    TestModel(),
    tools=[lookup_customer],
)

# Record
cap = AgentReplayCapability(mode="record", cassette_path=tmp_path / "test.jsonl")
result = agent.run_sync("test prompt", capabilities=[cap])

# Replay
cap2 = AgentReplayCapability(mode="replay", cassette_path=tmp_path / "test.jsonl")
result2 = agent.run_sync("test prompt", capabilities=[cap2])
```

**Depends on**: Phase 2 complete (CassetteCursor, DivergenceError), `Cassette` from `cassette.py`

---

### Task 3B: Update `__init__.py` exports

**File**: `src/agentreplay/__init__.py`

**Requirements**:
1. Export a convenience function `pydantic_ai(*, mode, cassette_path)` that returns `AgentReplayCapability`
2. Export key types: `TraceEvent`, `Cassette`, `DivergenceError`
3. Keep imports lazy where possible

```python
"""agentreplay — Regression tests for AI agents."""

__version__ = "0.1.0"

from agentreplay.cassette import Cassette
from agentreplay.divergence import DivergenceError
from agentreplay.trace import TraceEvent


def pydantic_ai(*, mode: str, cassette_path: str) -> "adapters.pydantic_ai.AgentReplayCapability":
    from agentreplay.adapters.pydantic_ai import AgentReplayCapability

    return AgentReplayCapability(mode=mode, cassette_path=cassette_path)
```

**Depends on**: Task 3A

---

## Phase 4 — pytest Plugin

### Task 4A: pytest Plugin (`src/agentreplay/pytest_plugin.py`)

**What**: Registered via entry point (already configured in `pyproject.toml`). Provides `--agentreplay` CLI flag and auto-configuration.

**File**: `src/agentreplay/pytest_plugin.py` (replace stub)

**Requirements**:
1. Add `--agentreplay` command-line option via `pytest_addoption`:
   - `--agentreplay=record` — record mode
   - `--agentreplay=replay` — replay mode
   - No flag = no agentreplay behaviour (tests run normally)
2. Provide an `agentreplay` fixture:
   - Returns a helper/factory that creates `AgentReplayCapability` instances
   - Cassette path derived from test name: `tests/cassettes/{test_module}/{test_name}.jsonl`
   - Mode comes from the `--agentreplay` CLI flag
3. The fixture should be usable like:
   ```python
   def test_refund(agentreplay):
       cap = agentreplay.capability()
       result = agent.run_sync("prompt", capabilities=[cap])
   ```
   Or even simpler, auto-derive path:
   ```python
   def test_refund(agentreplay):
       result = agent.run_sync("prompt", capabilities=[agentreplay.capability()])
   ```
4. When `--agentreplay` is not passed, the fixture should return a no-op (tests run normally without record/replay)
5. Print status messages: `RECORD tests/cassettes/...` or `REPLAY tests/cassettes/...`

**Test file**: `tests/test_pytest_plugin.py` (new)

**Tests to write** (use `pytester` fixture for plugin testing):
- `test_record_flag_accepted` — `--agentreplay=record` doesn't error
- `test_replay_flag_accepted` — `--agentreplay=replay` doesn't error
- `test_no_flag_no_effect` — tests run normally without flag
- `test_cassette_path_derived_from_test_name` — predictable naming
- `test_fixture_available` — `agentreplay` fixture is injectable

**Depends on**: Task 3A (adapter), Task 3B (exports)

---

## Phase 5 — End-to-End Example + Integration Tests

### Task 5A: Example Agent (`examples/support_agent.py`)

**What**: A realistic PydanticAI agent that can be used for demos and integration tests.

**File**: `examples/support_agent.py` (new, create `examples/` directory)

**Requirements**:
1. A support agent with 2–3 tools:
   - `lookup_customer(customer_id: str) -> dict` — returns customer info
   - `check_refund_policy(tier: str) -> dict` — returns policy details
   - `process_refund(customer_id: str, amount: float) -> str` — processes refund
2. Agent uses `TestModel` by default (no real API keys needed)
3. Simple, readable, demonstrates the product value
4. Include docstrings explaining what it demonstrates

**Depends on**: Nothing (standalone)

---

### Task 5B: Integration Tests (`tests/test_integration.py`)

**What**: Full record → replay → divergence cycle tests.

**File**: `tests/test_integration.py` (new)

**Requirements** (use `TestModel` throughout — no real API calls):
1. `test_record_then_replay_identical_result` — record a run, replay it, assert same output
2. `test_replay_zero_model_calls` — verify TestModel is never called during replay
3. `test_replay_zero_tool_execution` — verify tools are never called during replay
4. `test_divergence_on_changed_tool` — modify agent between record/replay, get DivergenceError
5. `test_divergence_on_changed_arguments` — tool args changed → DivergenceError
6. `test_divergence_leftover_cassette_entries` — agent does fewer steps → DivergenceError
7. `test_cassette_is_valid_jsonl` — each line is valid JSON
8. `test_cassette_has_format_version` — header line has format_version field
9. `test_sync_execution` — `run_sync` works
10. `test_async_execution` — `run` (async) works
11. `test_meaningful_diff_output` — DivergenceError message contains tool names and diff

**Depends on**: Phase 3 + Phase 4 complete

---

### Task 5C: Quality Gates

**What**: Ensure all quality checks pass.

**Commands**:
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest -v
```

**Requirements**:
1. All tests pass
2. `mypy --strict` passes — all new code has full type annotations
3. `ruff check` passes — no lint violations
4. `ruff format --check` passes — code is formatted
5. Fix any issues found

**Depends on**: All previous tasks

---

## File Creation Summary

| File | Task | Type |
|------|------|------|
| `src/agentreplay/divergence.py` | 2B | New |
| `src/agentreplay/_cursor.py` | 2A | New |
| `src/agentreplay/diff.py` | 2C | New |
| `src/agentreplay/adapters/__init__.py` | 3A | New |
| `src/agentreplay/adapters/pydantic_ai.py` | 3A | New |
| `src/agentreplay/__init__.py` | 3B | Modify |
| `src/agentreplay/pytest_plugin.py` | 4A | Replace |
| `examples/support_agent.py` | 5A | New |
| `tests/test_divergence.py` | 2B | New |
| `tests/test_cursor.py` | 2A | New |
| `tests/test_diff.py` | 2C | New |
| `tests/test_pydantic_ai_adapter.py` | 3A | New |
| `tests/test_pytest_plugin.py` | 4A | New |
| `tests/test_integration.py` | 5B | New |

## Dependency Graph

```
Task 2B (DivergenceError)
  └─→ Task 2A (CassetteCursor) ─── depends on 2B
  └─→ Task 2C (TraceDiff)      ─── independent of 2A

Task 3A (PydanticAI Adapter) ──── depends on 2A, 2B
  └─→ Task 3B (Exports)        ─── depends on 3A

Task 4A (pytest plugin) ───────── depends on 3A, 3B

Task 5A (Example agent) ───────── independent
Task 5B (Integration tests) ──── depends on 3A, 4A, 5A
Task 5C (Quality gates) ───────── depends on all
```

**Recommended execution order**:
1. `2B` → `2A` → `2C` (can parallelise 2A and 2C after 2B)
2. `3A` → `3B`
3. `4A`
4. `5A` (can run in parallel with 3/4)
5. `5B` → `5C`
