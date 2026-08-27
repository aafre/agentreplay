"""Integration tests for agentreplay record, replay, and divergence detection."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext  # noqa: TC002

from agentreplay.adapters.pydantic_ai import AgentReplayCapability
from agentreplay.cassette import Cassette
from agentreplay.diff import format_trace_diff
from agentreplay.divergence import DivergenceError
from agentreplay.trace import TraceEvent

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def cassette_path(tmp_path: Path) -> Path:
    return tmp_path / "integration_test.jsonl"


def lookup_customer(ctx: RunContext[None], customer_id: str) -> str:
    return f"Customer {customer_id}: John Doe (tier=gold)"


def check_refund_policy(ctx: RunContext[None], tier: str) -> str:
    return f"Policy for {tier}: max_amount=500, auto_approve=True"


def test_record_then_replay_identical_result(cassette_path: Path) -> None:
    agent = Agent(
        TestModel(call_tools=["lookup_customer", "check_refund_policy"]),
        tools=[lookup_customer, check_refund_policy],
    )

    cap_rec = AgentReplayCapability(mode="record", cassette_path=cassette_path)
    res_rec = agent.run_sync("Refund for customer 123", capabilities=[cap_rec])

    cap_rep = AgentReplayCapability(mode="replay", cassette_path=cassette_path)
    res_rep = agent.run_sync("Refund for customer 123", capabilities=[cap_rep])

    assert res_rec.output == res_rep.output


def test_replay_zero_model_calls(cassette_path: Path) -> None:
    agent = Agent(TestModel())
    cap_rec = AgentReplayCapability(mode="record", cassette_path=cassette_path)
    res_rec = agent.run_sync("Hello model", capabilities=[cap_rec])

    # Replay with an empty / dummy agent name; model is never queried
    replay_agent = Agent("test")
    cap_rep = AgentReplayCapability(mode="replay", cassette_path=cassette_path)
    res_rep = replay_agent.run_sync("Hello model", capabilities=[cap_rep])

    assert res_rep.output == res_rec.output


def test_replay_zero_tool_execution(cassette_path: Path) -> None:
    invocations: list[str] = []

    def tracking_tool(ctx: RunContext[None], item_id: str) -> str:
        invocations.append(item_id)
        return f"Item {item_id} fetched"

    agent = Agent(
        TestModel(call_tools=["tracking_tool"]),
        tools=[tracking_tool],
    )

    cap_rec = AgentReplayCapability(mode="record", cassette_path=cassette_path)
    agent.run_sync("Fetch item A", capabilities=[cap_rec])
    assert len(invocations) == 1

    # Replay mode — tracking_tool must NOT be executed again
    cap_rep = AgentReplayCapability(mode="replay", cassette_path=cassette_path)
    agent.run_sync("Fetch item A", capabilities=[cap_rep])
    assert len(invocations) == 1


def test_divergence_on_changed_tool(cassette_path: Path) -> None:
    agent_a = Agent(
        TestModel(call_tools=["lookup_customer"]),
        tools=[lookup_customer],
    )
    cap_rec = AgentReplayCapability(mode="record", cassette_path=cassette_path)
    agent_a.run_sync("Find customer", capabilities=[cap_rec])

    # Replay with agent that attempts a different tool call
    agent_b = Agent(
        TestModel(call_tools=["check_refund_policy"]),
        tools=[check_refund_policy],
    )
    cap_rep = AgentReplayCapability(mode="replay", cassette_path=cassette_path)

    with pytest.raises(DivergenceError) as exc_info:
        agent_b.run_sync("Find customer", capabilities=[cap_rep])

    assert exc_info.value.divergence_kind in ("kind_mismatch", "argument_mismatch")


def test_divergence_on_changed_arguments(cassette_path: Path) -> None:
    # Construct a cassette expecting tool_result with specific arguments
    cassette = Cassette()
    cassette.append(TraceEvent(kind="run_start", timestamp=0.0))
    cassette.append(TraceEvent(kind="model_request", timestamp=1.0))
    cassette.append(
        TraceEvent(
            kind="tool_result",
            timestamp=2.0,
            name="lookup_customer",
            arguments={"customer_id": "123"},
            result="Customer 123 details",
        )
    )
    cassette.append(TraceEvent(kind="run_end", timestamp=3.0))
    cassette.save(cassette_path)

    # Agent requests a different tool
    other_agent = Agent(
        TestModel(call_tools=["check_refund_policy"]),
        tools=[check_refund_policy],
    )
    cap_rep = AgentReplayCapability(mode="replay", cassette_path=cassette_path)

    with pytest.raises(DivergenceError):
        other_agent.run_sync("Look up", capabilities=[cap_rep])


def test_divergence_on_leftover_cassette_entries(cassette_path: Path) -> None:
    agent_with_tool = Agent(
        TestModel(call_tools=["lookup_customer"]),
        tools=[lookup_customer],
    )
    cap_rec = AgentReplayCapability(mode="record", cassette_path=cassette_path)
    agent_with_tool.run_sync("Lookup 123", capabilities=[cap_rec])

    # Replay with an agent that stops earlier without using tools
    agent_no_tool = Agent(TestModel())
    cap_rep = AgentReplayCapability(mode="replay", cassette_path=cassette_path)

    with pytest.raises(DivergenceError):
        agent_no_tool.run_sync("Lookup 123", capabilities=[cap_rep])


def test_cassette_is_valid_jsonl(cassette_path: Path) -> None:
    agent = Agent(TestModel())
    cap = AgentReplayCapability(mode="record", cassette_path=cassette_path)
    agent.run_sync("Sample query", capabilities=[cap])

    assert cassette_path.exists()
    lines = cassette_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) >= 3  # header + events
    for line in lines:
        data = json.loads(line)
        assert isinstance(data, dict)


def test_cassette_has_format_version(cassette_path: Path) -> None:
    agent = Agent(TestModel())
    cap = AgentReplayCapability(mode="record", cassette_path=cassette_path)
    agent.run_sync("Sample query", capabilities=[cap])

    cassette = Cassette.load(cassette_path)
    assert cassette.header.format_version == 1
    assert cassette.header.framework == "pydantic-ai"


def test_sync_execution(cassette_path: Path) -> None:
    agent = Agent(TestModel())
    cap_rec = AgentReplayCapability(mode="record", cassette_path=cassette_path)
    res_rec = agent.run_sync("Sync test", capabilities=[cap_rec])

    cap_rep = AgentReplayCapability(mode="replay", cassette_path=cassette_path)
    res_rep = agent.run_sync("Sync test", capabilities=[cap_rep])

    assert res_rec.output == res_rep.output


async def test_async_execution(cassette_path: Path) -> None:
    agent = Agent(TestModel())
    cap_rec = AgentReplayCapability(mode="record", cassette_path=cassette_path)
    res_rec = await agent.run("Async test", capabilities=[cap_rec])

    cap_rep = AgentReplayCapability(mode="replay", cassette_path=cassette_path)
    res_rep = await agent.run("Async test", capabilities=[cap_rep])

    assert res_rec.output == res_rep.output


def test_meaningful_diff_output() -> None:
    expected = [
        TraceEvent(kind="model_request", timestamp=1.0),
        TraceEvent(
            kind="tool_call", timestamp=2.0, name="lookup_customer", arguments={"id": "123"}
        ),
        TraceEvent(
            kind="tool_call",
            timestamp=3.0,
            name="check_refund_policy",
            arguments={"tier": "gold"},
        ),
        TraceEvent(kind="model_response", timestamp=4.0, result="Refund processed."),
    ]
    actual = [
        TraceEvent(kind="model_request", timestamp=1.0),
        TraceEvent(
            kind="tool_call", timestamp=2.0, name="lookup_customer", arguments={"id": "123"}
        ),
        TraceEvent(
            kind="tool_call",
            timestamp=3.0,
            name="refund_customer",
            arguments={"amount": 39},
        ),
    ]
    diff = format_trace_diff(expected, actual)
    assert "Agent trajectory changed" in diff
    assert "Expected:" in diff
    assert "Actual:" in diff
    assert "Divergence at step 3:" in diff
    assert "- tool_call: check_refund_policy(tier='gold')" in diff
    assert "+ tool_call: refund_customer(amount=39)" in diff
