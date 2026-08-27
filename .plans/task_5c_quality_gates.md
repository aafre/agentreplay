# Task 5C: Quality Gates

## Goal
Ensure all quality checks pass across the entire codebase.

## Context
You are working on the `agentreplay` package at `c:\projects\agenttrace`. All previous tasks must be complete.

## Steps

### 1. Run all quality checks
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest -v
```

### 2. Fix any issues
- Lint violations → fix the code
- Format issues → run `uv run ruff format .`
- Type errors → add/fix type annotations
- Test failures → debug and fix

### 3. Re-run until all pass
All four commands must exit with code 0.

### 4. Verify test count
Expected minimum test counts:
- `test_trace.py` — ~10 tests (existing)
- `test_cassette.py` — ~9 tests (existing)
- `test_divergence.py` — ~5 tests (new)
- `test_cursor.py` — ~7 tests (new)
- `test_diff.py` — ~9 tests (new)
- `test_pydantic_ai_adapter.py` — ~10 tests (new)
- `test_pytest_plugin.py` — ~5 tests (new)
- `test_integration.py` — ~10 tests (new)

Total: 60+ tests minimum

### 5. Final check
```bash
uv run pytest -v --tb=short 2>&1 | tail -5
```
Should show all tests passing.
