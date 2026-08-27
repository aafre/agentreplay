"""Example support agent for agentreplay demos and tests.

This agent handles customer refund inquiries using three tools.
By default, it uses PydanticAI's TestModel so no live API keys are required.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext  # noqa: TC002

CUSTOMERS: dict[str, dict[str, Any]] = {
    "123": {"name": "John Doe", "email": "john@example.com", "tier": "gold"},
    "456": {"name": "Jane Smith", "email": "jane@example.com", "tier": "silver"},
}

REFUND_POLICIES: dict[str, dict[str, Any]] = {
    "gold": {"max_amount": 500, "auto_approve": True},
    "silver": {"max_amount": 100, "auto_approve": False},
}


def lookup_customer(ctx: RunContext[None], customer_id: str) -> str:
    """Look up customer information by customer ID."""
    info = CUSTOMERS.get(customer_id)
    if info is None:
        return f"Customer {customer_id} not found."
    return f"Customer {customer_id}: name={info['name']}, tier={info['tier']}"


def check_refund_policy(ctx: RunContext[None], tier: str) -> str:
    """Check refund policy limits and auto-approval status for a customer tier."""
    policy = REFUND_POLICIES.get(tier.lower())
    if policy is None:
        return f"No policy found for tier '{tier}'."
    return (
        f"Policy for {tier}: max_amount={policy['max_amount']}, "
        f"auto_approve={policy['auto_approve']}"
    )


def process_refund(ctx: RunContext[None], customer_id: str, amount: float) -> str:
    """Process a refund transaction for a customer."""
    return f"Refund of £{amount:.2f} successfully processed for customer {customer_id}."


support_agent = Agent(
    TestModel(),
    system_prompt=(
        "You are a customer support agent. "
        "When handling refund requests, first look up the customer, "
        "check the refund policy, and process the refund if approved."
    ),
    tools=[lookup_customer, check_refund_policy, process_refund],
)

if __name__ == "__main__":
    result = support_agent.run_sync("Please refund order 123 for customer 123 amount 50")
    print("Agent Result:", result.output)
