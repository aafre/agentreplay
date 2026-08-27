# agentreplay — Task Tracker

## Phase 2 — Core Replay Infrastructure

- [x] **Task 2B**: DivergenceError (`src/agentreplay/divergence.py` + `tests/test_divergence.py`)
- [x] **Task 2A**: CassetteCursor (`src/agentreplay/_cursor.py` + `tests/test_cursor.py`) — depends on 2B
- [x] **Task 2C**: TraceDiff (`src/agentreplay/diff.py` + `tests/test_diff.py`)

## Phase 3 — PydanticAI Adapter

- [x] **Task 3A**: PydanticAI adapter (`src/agentreplay/adapters/pydantic_ai.py` + `tests/test_pydantic_ai_adapter.py`) — depends on 2A, 2B
- [x] **Task 3B**: Update `__init__.py` exports — depends on 3A

## Phase 4 — pytest Plugin

- [x] **Task 4A**: pytest plugin (`src/agentreplay/pytest_plugin.py` + `tests/test_pytest_plugin.py`) — depends on 3A, 3B

## Phase 5 — Integration

- [x] **Task 5A**: Example agent (`examples/support_agent.py`)
- [x] **Task 5B**: Integration tests (`tests/test_integration.py`) — depends on 3A, 4A, 5A
- [x] **Task 5C**: Quality gates (ruff, mypy, pytest all pass) — depends on all
