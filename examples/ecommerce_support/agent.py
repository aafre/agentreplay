"""E-commerce Refund & Fraud Prevention Agent.

Demonstrates a multi-step customer support agent that enforces fraud checks
and restocking policy calculations before processing payment refunds.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext  # noqa: TC002

# Simulated database
ORDERS_DB: dict[str, dict[str, Any]] = {
    "ORD-901": {
        "customer_id": "CUST-44",
        "item": "Wireless Noise-Canceling Headphones",
        "category": "electronics",
        "price": 199.99,
        "status": "delivered",
    },
    "ORD-902": {
        "customer_id": "CUST-88",
        "item": "Designer Silk Shirt",
        "category": "apparel",
        "price": 89.50,
        "status": "delivered",
    },
}

FRAUD_SCORES: dict[str, dict[str, Any]] = {
    "CUST-44": {"risk_level": "low", "score": 12, "allowed_auto_refund": True},
    "CUST-88": {"risk_level": "high", "score": 85, "allowed_auto_refund": False},
}


def get_order_details(ctx: RunContext[None], order_id: str) -> dict[str, Any]:
    """Retrieve order information including customer ID, item category, and price."""
    order = ORDERS_DB.get(order_id)
    if not order:
        return {"error": f"Order {order_id} not found"}
    return {"order_id": order_id, **order}


def verify_fraud_risk(ctx: RunContext[None], customer_id: str) -> dict[str, Any]:
    """Check customer account fraud score and auto-refund clearance."""
    risk = FRAUD_SCORES.get(customer_id, {"risk_level": "medium", "allowed_auto_refund": True})
    return {"customer_id": customer_id, **risk}


def calculate_restocking_fee(ctx: RunContext[None], category: str, amount: float) -> float:
    """Calculate category-specific restocking fee (electronics=10%, apparel=0%)."""
    if category.lower() == "electronics":
        return round(amount * 0.10, 2)
    return 0.0


def execute_refund(
    ctx: RunContext[None], order_id: str, final_amount: float, reason: str
) -> dict[str, Any]:
    """Issue payment gateway refund after all policy and fraud checks pass."""
    return {
        "status": "success",
        "order_id": order_id,
        "refund_amount": final_amount,
        "message": f"Refund of £{final_amount:.2f} executed. Reason: {reason}",
    }


def create_ecommerce_agent(model: Any = None) -> Agent[None, str]:
    """Factory creating the e-commerce support agent."""
    selected_model = model or TestModel(
        call_tools=[
            "get_order_details",
            "verify_fraud_risk",
            "calculate_restocking_fee",
            "execute_refund",
        ]
    )

    return Agent(
        selected_model,
        system_prompt=(
            "You are an automated e-commerce refund agent. "
            "Follow these strict business rules in order: "
            "1. Fetch the order details. "
            "2. Verify fraud risk for the customer. If high risk, reject auto-refund. "
            "3. Calculate restocking fee for the category. "
            "4. Execute the refund for (amount - restocking_fee)."
        ),
        tools=[
            get_order_details,
            verify_fraud_risk,
            calculate_restocking_fee,
            execute_refund,
        ],
    )


if __name__ == "__main__":
    agent = create_ecommerce_agent()
    result = agent.run_sync("Please process a return for order ORD-901 because it arrived damaged")
    print(result.output)
