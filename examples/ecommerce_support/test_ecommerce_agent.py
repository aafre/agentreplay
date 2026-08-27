"""Tests for E-commerce Refund Agent demonstrating record, replay, and drift detection."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from agentreplay.divergence import DivergenceError
from examples.ecommerce_support.agent import (
    create_ecommerce_agent,
    execute_refund,
    get_order_details,
)

if TYPE_CHECKING:
    from pathlib import Path

    from agentreplay.pytest_plugin import AgentReplayFixture


def test_refund_happy_path(agentreplay: AgentReplayFixture) -> None:
    """Demonstrates standard record & replay with pytest-agentreplay.

    Record:
        pytest --agentreplay=record examples/ecommerce_support/test_ecommerce_agent.py

    Replay:
        pytest --agentreplay=replay examples/ecommerce_support/test_ecommerce_agent.py
    """
    agent = create_ecommerce_agent()
    caps = [c for c in [agentreplay.capability()] if c is not None]

    result = agent.run_sync(
        "Please process refund for order ORD-901",
        capabilities=caps,
    )
    assert result.output is not None


def test_detecting_safety_check_bypass(tmp_path: Path) -> None:
    """Showcases how pytest-agentreplay prevents subtle regressions.

    If an engineer modifies the agent prompt or model causing it to skip
    'verify_fraud_risk' and jump straight to 'execute_refund', pytest-agentreplay
    immediately catches the skipped safety check.
    """
    import agentreplay

    cassette_file = tmp_path / "ecommerce_refund.jsonl"

    # Step 1: Baseline compliant agent (checks fraud risk before refunding)
    compliant_agent = create_ecommerce_agent()
    cap_record = agentreplay.pydantic_ai(mode="record", cassette_path=cassette_file)
    compliant_agent.run_sync("Refund ORD-901", capabilities=[cap_record])

    # Step 2: Regressed agent (skips verify_fraud_risk and calculate_restocking_fee)
    regressed_agent = Agent(
        TestModel(call_tools=["get_order_details", "execute_refund"]),
        system_prompt="Directly refund without checking fraud or restocking fee.",
        tools=[get_order_details, execute_refund],
    )

    # Step 3: Replay against baseline cassette
    cap_replay = agentreplay.pydantic_ai(mode="replay", cassette_path=cassette_file)

    with pytest.raises(DivergenceError) as exc_info:
        regressed_agent.run_sync("Refund ORD-901", capabilities=[cap_replay])

    # Verified: Divergence was detected right when the tool sequence drifted!
    err = exc_info.value
    assert err.divergence_kind in ("kind_mismatch", "argument_mismatch", "cassette_exhausted")
    assert "Divergence at step" in str(err)
