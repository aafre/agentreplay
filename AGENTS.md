# AGENTS.md — Instructions for AI Coders

## What this project is

`agentreplay` is a framework-agnostic regression testing tool for AI agents.
It records real model and tool interactions, replays them offline in pytest,
and catches behavioural regressions via structural trace diffs.

**It is NOT an agent framework, runtime, or orchestration system.**

## Architecture

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

## Key principles

1. **YAGNI** — Do not build features for hypothetical future needs.
2. **DRY** — Avoid duplication, but not through premature abstraction.
3. **SOLID** — Especially Single Responsibility and Dependency Inversion.
4. **No monkey-patching** — Use PydanticAI's public capability API.
5. **No silent fallback** — Replay must never make live API calls.
6. **Deterministic serialisation** — `sort_keys=True`, compact separators, UTF-8.
7. **Deep-copy mutable data** — Tools can mutate argument dicts.

## Replay mechanism

- **Record**: `before_model_request` / `after_model_request` / `before_tool_execute` / `after_tool_execute` hooks capture events.
- **Replay**: `before_model_request` raises `SkipModelRequest(recorded_response)`. `before_tool_execute` raises `SkipToolExecution(recorded_result)`.

## Testing

- Use PydanticAI's `TestModel` for CI tests (no real API calls).
- All code must pass `mypy --strict`, `ruff check`, `ruff format --check`.
- Property tests with `hypothesis` where they add value.

## What NOT to build

- Additional framework adapters (until PydanticAI slice is complete)
- Agent runtime or orchestration
- Evaluation datasets or LLM-as-judge
- Behavioural assertion API (future phase)
- Abstract adapter protocol (YAGNI — one adapter)
