# Task 4A: pytest Plugin

## Goal
Implement the pytest plugin in `src/agentreplay/pytest_plugin.py` — provides `--agentreplay` CLI flag and `agentreplay` fixture.

## Context
You are working on the `agentreplay` package at `c:\projects\agenttrace`. Read these files first:
- `AGENTS.md` — project principles
- `pyproject.toml` — note the entry point: `[project.entry-points.pytest11] agentreplay = "agentreplay.pytest_plugin"`
- `src/agentreplay/adapters/pydantic_ai.py` — `AgentReplayCapability` (must exist)

The plugin is already registered via `pyproject.toml` entry point. You just need to implement the module.

## File to replace: `src/agentreplay/pytest_plugin.py`

### Requirements

1. **`pytest_addoption(parser)`**: Add `--agentreplay` CLI option:
   - Choices: `"record"`, `"replay"`
   - Default: `None` (no agentreplay behaviour)
   - Help text explaining the modes

2. **`AgentReplayFixture` class**: Helper returned by the fixture
   - `__init__(self, mode: str | None, test_name: str, test_module: str, cassettes_dir: Path)`
   - `capability(self, cassette_path: str | Path | None = None) -> AgentReplayCapability | None`
     - If mode is None, return None (no-op)
     - If cassette_path not provided, derive from test name: `{cassettes_dir}/{test_module}/{test_name}.jsonl`
     - Return `AgentReplayCapability(mode=mode, cassette_path=cassette_path)`
   - `mode` property — the current mode or None

3. **`agentreplay` fixture** (session-scoped is wrong — use function-scoped):
   - Read `--agentreplay` from config
   - Derive test name from `request.node.name`
   - Derive test module from `request.node.module.__name__`
   - Default cassettes dir: `tests/cassettes/` relative to rootdir
   - Return `AgentReplayFixture(...)` or a no-op if no flag
   - Print status: `RECORD {path}` or `REPLAY {path}` to terminal

4. Usage pattern:
```python
def test_refund(agentreplay):
    cap = agentreplay.capability()
    if cap:
        result = agent.run_sync("prompt", capabilities=[cap])
    else:
        result = agent.run_sync("prompt")
```

Or cleaner — always pass capabilities list, None filtered out:
```python
def test_refund(agentreplay):
    caps = [c for c in [agentreplay.capability()] if c is not None]
    result = agent.run_sync("prompt", capabilities=caps)
```

### Code style
- Use `from __future__ import annotations` at the top
- All code must pass `mypy --strict` and `ruff check`
- Keep it minimal — YAGNI

## Test file to create: `tests/test_pytest_plugin.py`

Use the `pytester` fixture (built into pytest) for plugin testing.

**Important**: To use `pytester`, add this to `tests/conftest.py`:
```python
pytest_plugins = ["pytester"]
```

### Tests to write:
- `test_record_flag_accepted` — running pytest with `--agentreplay=record` doesn't error
- `test_replay_flag_accepted` — running pytest with `--agentreplay=replay` doesn't error
- `test_no_flag_tests_pass` — tests run normally without the flag
- `test_fixture_available` — a test requesting `agentreplay` fixture can run
- `test_cassette_path_derived_from_test_name` — verify the auto-derived path

### Test pattern with pytester:
```python
def test_fixture_available(pytester):
    pytester.makepyfile(
        \"\"\"
        def test_example(agentreplay):
            assert agentreplay is not None
        \"\"\"
    )
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)
```

## Validation
```bash
uv run ruff check src/agentreplay/pytest_plugin.py tests/test_pytest_plugin.py
uv run ruff format --check src/agentreplay/pytest_plugin.py tests/test_pytest_plugin.py
uv run mypy src/agentreplay/pytest_plugin.py
uv run pytest tests/test_pytest_plugin.py -v
uv run pytest -v  # all tests still pass
```
