"""Tests for SQL Analyst Agent showing offline DB mocking and regression detection."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from agentreplay.divergence import DivergenceError
from examples.sql_analyst.agent import (
    create_sql_analyst_agent,
    execute_read_only_query,
    list_tables,
)

if TYPE_CHECKING:
    from pathlib import Path

    from agentreplay.pytest_plugin import AgentReplayFixture


def test_mrr_breakdown_trajectory(agentreplay: AgentReplayFixture) -> None:
    """Record & replay SQL analytics trajectory without needing a live warehouse in CI.

    Record:
        pytest --agentreplay=record examples/sql_analyst/test_sql_analyst.py

    Replay:
        pytest --agentreplay=replay examples/sql_analyst/test_sql_analyst.py
    """
    analyst = create_sql_analyst_agent()
    caps = [c for c in [agentreplay.capability()] if c is not None]

    result = analyst.run_sync(
        "Calculate total MRR by subscription tier",
        capabilities=caps,
    )
    assert result.output is not None


def test_detects_query_planning_drift(tmp_path: Path) -> None:
    """Detects when an agent changes its tool choice or query planning strategy."""
    import agentreplay

    cassette_file = tmp_path / "sql_analyst.jsonl"

    # Step 1: Baseline agent (discovers schema -> inspects -> queries)
    analyst = create_sql_analyst_agent()
    cap_record = agentreplay.pydantic_ai(mode="record", cassette_path=cassette_file)
    analyst.run_sync("Calculate MRR", capabilities=[cap_record])

    # Step 2: Altered agent (attempts to blindly query without inspecting schema)
    altered_agent = Agent(
        TestModel(call_tools=["list_tables", "execute_read_only_query"]),
        system_prompt="Execute queries immediately without schema inspection.",
        tools=[list_tables, execute_read_only_query],
    )

    # Step 3: Replay catches the skipped step
    cap_replay = agentreplay.pydantic_ai(mode="replay", cassette_path=cassette_file)

    with pytest.raises(DivergenceError) as exc_info:
        altered_agent.run_sync("Calculate MRR", capabilities=[cap_replay])

    assert "Divergence at step" in str(exc_info.value)
