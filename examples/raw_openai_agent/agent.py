"""Vanilla OpenAI Agent Loop without any agent framework.

Demonstrates how to build and test custom agent loops written directly
with the official OpenAI Python SDK.
"""

from __future__ import annotations

import json
from typing import Any

import agentreplay


@agentreplay.tool
def get_user_subscription(user_id: str) -> dict[str, Any]:
    """Retrieve account tier and plan details for a customer."""
    return {"user_id": user_id, "tier": "enterprise", "seats": 50, "renewal": "2026-12-31"}


@agentreplay.tool
def generate_discount_code(percentage: int, reason: str) -> dict[str, Any]:
    """Generate a custom billing promotion coupon code."""
    return {"code": f"SAVE{percentage}-VIP", "discount_pct": percentage, "reason": reason}


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_user_subscription",
            "description": "Retrieve account tier and plan details for a customer.",
            "parameters": {
                "type": "object",
                "properties": {"user_id": {"type": "string"}},
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_discount_code",
            "description": "Generate a custom billing promotion coupon code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "percentage": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["percentage", "reason"],
            },
        },
    },
]

TOOL_REGISTRY: dict[str, Any] = {
    "get_user_subscription": get_user_subscription,
    "generate_discount_code": generate_discount_code,
}


def run_vanilla_agent(
    client: Any,
    user_prompt: str,
    model: str = "gpt-4o",
    max_turns: int = 5,
) -> str:
    """Execute a standard multi-turn tool-calling loop using the OpenAI SDK."""
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are a customer loyalty assistant. Look up customer subscription details "
                "first, then generate an appropriate loyalty coupon."
            ),
        },
        {"role": "user", "content": user_prompt},
    ]

    for _ in range(max_turns):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS_SCHEMA,
        )
        msg = response.choices[0].message

        # If model answered with plain text and no tool calls, return answer
        if not getattr(msg, "tool_calls", None):
            return str(msg.content or "")

        # Append assistant turn
        tool_calls_list = []
        for tc in msg.tool_calls or []:
            func_obj = getattr(tc, "function", None)
            if func_obj is not None:
                tool_calls_list.append(
                    {
                        "id": tc.id,
                        "type": getattr(tc, "type", "function"),
                        "function": {
                            "name": func_obj.name,
                            "arguments": func_obj.arguments,
                        },
                    }
                )

        messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": tool_calls_list,
            }
        )

        # Execute and append tool responses
        for tc in msg.tool_calls or []:
            func_obj = getattr(tc, "function", None)
            if func_obj is not None:
                fn_name = func_obj.name
                fn_args = json.loads(func_obj.arguments)
                fn = TOOL_REGISTRY[fn_name]
                result = fn(**fn_args)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result),
                    }
                )

    return "Max turns exceeded."
