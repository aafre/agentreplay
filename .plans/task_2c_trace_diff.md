# Task 2C: TraceDiff

## Goal
Create `src/agentreplay/diff.py` — human-readable trajectory comparison between recorded and actual event sequences.

## Context
You are working on the `agentreplay` package at `c:\projects\agenttrace`. Read these files first:
- `AGENTS.md` — project principles
- `src/agentreplay/trace.py` — `TraceEvent` model

## File to create: `src/agentreplay/diff.py`

### Requirements

#### `format_event(event: TraceEvent) -> str`
Single-line human-readable representation of one event:
- `tool_call` → `tool_call: name(arg1=val1, arg2=val2)` (format args as `key=repr(value)`)
- `tool_result` → `tool_result: name → result_preview`
- `model_request` → `model_request`
- `model_response` → `model_response → "first 60 chars..."` (truncate long text)
- `run_start` → `run_start`
- `run_end` → `run_end`
- `error` → `error: message`

#### `format_trace_diff(expected: list[TraceEvent], actual: list[TraceEvent]) -> str`
Full trajectory diff output:
1. Header line: `Agent trajectory changed`
2. `Expected:` section — numbered list of events via `format_event`
3. `Actual:` section — numbered list of events via `format_event`
4. `Divergence at step N:` section showing the first difference with `-`/`+` prefixes
5. If traces are identical, return `"Traces are identical"` or similar
6. Handle different-length lists gracefully

Target output format:
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

### Code style
- Use `from __future__ import annotations` at the top
- All code must pass `mypy --strict` and `ruff check`
- Keep it simple — no external dependencies

## Test file to create: `tests/test_diff.py`

Write these tests:
- `test_format_event_tool_call` — tool name + args formatted correctly
- `test_format_event_tool_call_no_args` — tool call without arguments
- `test_format_event_model_request` — concise single word
- `test_format_event_model_response_truncates` — long text gets truncated with ellipsis
- `test_format_event_run_start` — simple format
- `test_format_trace_diff_identical` — returns "identical" message when equal
- `test_format_trace_diff_divergence` — shows first difference correctly
- `test_format_trace_diff_different_lengths` — handles extra/missing events
- `test_format_trace_diff_empty_vs_events` — edge case with empty list

## Validation
```bash
uv run ruff check src/agentreplay/diff.py tests/test_diff.py
uv run ruff format --check src/agentreplay/diff.py tests/test_diff.py
uv run mypy src/agentreplay/diff.py
uv run pytest tests/test_diff.py -v
```
All must pass.
