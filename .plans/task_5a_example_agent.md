# Task 5A: Example Agent

## Goal
Create `examples/support_agent.py` — a realistic PydanticAI agent for demos and integration tests.

## Context
You are working on the `agentreplay` package at `c:\projects\agenttrace`. This task is independent of other tasks and can be done in parallel.

## File to create: `examples/support_agent.py`

### Requirements
1. A customer support agent built with PydanticAI
2. Uses `TestModel` by default so no API keys are needed
3. Has 2–3 tools:
   - `lookup_customer(customer_id: str) -> str` — returns customer info (hardcoded data)
   - `check_refund_policy(tier: str) -> str` — returns policy details
   - `process_refund(customer_id: str, amount: float) -> str` — returns confirmation
4. Simple, readable, well-documented
5. Include a `__main__` block that demonstrates usage
6. Add type annotations throughout
7. Must pass `ruff check` and `ruff format --check`

### Example structure:
```python
"""Example support agent for agentreplay demos.

This agent handles customer refund requests using three tools.
It uses PydanticAI's TestModel so no API keys are required.
"""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext

# ... tool definitions ...

support_agent = Agent(
    TestModel(),
    system_prompt="You are a customer support agent. ...",
    tools=[lookup_customer, check_refund_policy, process_refund],
)

if __name__ == "__main__":
    result = support_agent.run_sync("Please refund order 123")
    print(result.output)
```

### Tool data (hardcode this):
```python
CUSTOMERS = {
    "123": {"name": "John Doe", "email": "john@example.com", "tier": "gold"},
    "456": {"name": "Jane Smith", "email": "jane@example.com", "tier": "silver"},
}

REFUND_POLICIES = {
    "gold": {"max_amount": 500, "auto_approve": True},
    "silver": {"max_amount": 100, "auto_approve": False},
}
```

## Validation
```bash
uv run ruff check examples/support_agent.py
uv run ruff format --check examples/support_agent.py
uv run python examples/support_agent.py
```
The script should run without errors and print output.
