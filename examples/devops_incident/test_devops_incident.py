"""Tests for DevOps Incident Triage Agent demonstrating regression detection."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from agentreplay.divergence import DivergenceError
from examples.devops_incident.agent import (
    create_devops_agent,
    fetch_service_health,
    trigger_service_restart,
)

if TYPE_CHECKING:
    from pathlib import Path

    from agentreplay.pytest_plugin import AgentReplayFixture


def test_incident_triage_happy_path(agentreplay: AgentReplayFixture) -> None:
    """Demonstrates recording and replaying a full DevOps diagnostic trajectory.

    Record:
        pytest --agentreplay=record examples/devops_incident/test_devops_incident.py

    Replay:
        pytest --agentreplay=replay examples/devops_incident/test_devops_incident.py
    """
    devops_agent = create_devops_agent()
    caps = [c for c in [agentreplay.capability()] if c is not None]

    result = devops_agent.run_sync(
        "Diagnose and remediate outage on auth-service",
        capabilities=caps,
    )
    assert result.output is not None


def test_catches_unauthorized_remediation_drift(tmp_path: Path) -> None:
    """Showcases catching regressions where an agent triggers restart without policy check.

    If an agent prompt modification causes the model to prematurely restart
    the service before checking company change policy or reading logs,
    pytest-agentreplay immediately flags the skipped validation steps.
    """
    import agentreplay

    cassette_file = tmp_path / "devops_triage.jsonl"

    # Step 1: Record baseline trajectory with compliant agent (health -> logs -> policy -> restart)
    compliant_agent = create_devops_agent()
    cap_record = agentreplay.pydantic_ai(mode="record", cassette_path=cassette_file)
    compliant_agent.run_sync("Remediate auth-service", capabilities=[cap_record])

    # Step 2: Regressed agent (blindly restarts without log inspection or policy check)
    reckless_agent = Agent(
        TestModel(call_tools=["fetch_service_health", "trigger_service_restart"]),
        system_prompt="Directly restart degraded service without checking logs or policy.",
        tools=[fetch_service_health, trigger_service_restart],
    )

    # Step 3: Replay against baseline cassette — must catch skipped step
    cap_replay = agentreplay.pydantic_ai(mode="replay", cassette_path=cassette_file)

    with pytest.raises(DivergenceError) as exc_info:
        reckless_agent.run_sync("Remediate auth-service", capabilities=[cap_replay])

    # Verified: Diverged at step 2 when fetch_recent_logs was expected
    err = exc_info.value
    assert "Divergence at step" in str(err)
