# Task 2B: DivergenceError

## Goal
Create `src/agentreplay/divergence.py` — a structured exception raised when replay diverges from the recorded cassette.

## Context
You are working on the `agentreplay` package at `c:\projects\agenttrace`. Read `AGENTS.md` in the repo root for project principles. Read `src/agentreplay/trace.py` to understand the `TraceEvent` model you depend on.

## File to create: `src/agentreplay/divergence.py`

### Requirements
1. Subclass of `AssertionError` (so pytest treats it as a test failure)
2. Fields:
   - `position: int` — the step index where divergence occurred (0-based)
   - `expected: TraceEvent | None` — what the cassette said should happen
   - `actual: TraceEvent | None` — what actually happened (None if cassette exhausted)
   - `message: str` — human-readable summary
   - `divergence_kind: str` — one of: `"kind_mismatch"`, `"cassette_exhausted"`, `"leftover_events"`, `"argument_mismatch"`
3. `__str__` must produce a clear, developer-friendly message like:
   ```
   Divergence at step 3:
     Expected: tool_call: check_refund_policy(tier="gold")
     Actual:   tool_call: refund_customer(amount=39)
   ```
4. Use `from __future__ import annotations` at the top
5. All code must pass `mypy --strict` and `ruff check`

## Test file to create: `tests/test_divergence.py`

Write these tests:
- `test_kind_mismatch_message` — clear output for mismatched event kinds
- `test_cassette_exhausted_message` — message when no more events
- `test_leftover_events_message` — message when agent stopped early
- `test_is_assertion_error` — `isinstance(err, AssertionError)` is True
- `test_fields_accessible` — position, expected, actual, divergence_kind are set correctly

## Validation
Run these commands after implementation:
```bash
uv run ruff check src/agentreplay/divergence.py tests/test_divergence.py
uv run ruff format --check src/agentreplay/divergence.py tests/test_divergence.py
uv run mypy src/agentreplay/divergence.py
uv run pytest tests/test_divergence.py -v
```
All must pass.
