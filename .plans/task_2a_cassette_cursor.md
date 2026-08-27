# Task 2A: CassetteCursor

## Goal
Create `src/agentreplay/_cursor.py` — a stateful, one-shot iterator over cassette events used during replay.

## Context
You are working on the `agentreplay` package at `c:\projects\agenttrace`. Read these files first:
- `AGENTS.md` — project principles
- `src/agentreplay/trace.py` — `TraceEvent` model and `EventKind` type
- `src/agentreplay/divergence.py` — `DivergenceError` (must exist before you start this task)

## File to create: `src/agentreplay/_cursor.py`

### Requirements
1. `CassetteCursor` class wrapping a `list[TraceEvent]`
2. Method `next(kind: EventKind) -> TraceEvent`:
   - Returns the next event from the list
   - Raises `DivergenceError` with `divergence_kind="cassette_exhausted"` if no more events remain
   - Raises `DivergenceError` with `divergence_kind="kind_mismatch"` if the next event's `kind` doesn't match the expected `kind`
   - Advances the internal position by 1
3. Method `assert_exhausted() -> None`:
   - Raises `DivergenceError` with `divergence_kind="leftover_events"` if there are unconsumed events
   - No-op if all events have been consumed
4. Property `position: int` — current read position (0-based)
5. One-shot: no reset/rewind capability
6. Internal module — underscore prefix, not exported from `__init__.py`
7. Use `from __future__ import annotations` at the top
8. All code must pass `mypy --strict` and `ruff check`

## Test file to create: `tests/test_cursor.py`

Write these tests:
- `test_next_returns_matching_event` — happy path, correct kind
- `test_next_advances_position` — position increments after each call
- `test_next_raises_on_exhausted` — no more events → DivergenceError
- `test_next_raises_on_kind_mismatch` — wrong event kind → DivergenceError
- `test_assert_exhausted_passes_when_empty` — all events consumed → no error
- `test_assert_exhausted_raises_with_leftover` — unconsumed events → DivergenceError
- `test_no_reset_method` — `CassetteCursor` has no `reset` or `__iter__` method

## Validation
```bash
uv run ruff check src/agentreplay/_cursor.py tests/test_cursor.py
uv run ruff format --check src/agentreplay/_cursor.py tests/test_cursor.py
uv run mypy src/agentreplay/_cursor.py
uv run pytest tests/test_cursor.py -v
```
All must pass.
