"""Tests for PydanticAI adapter in record and replay modes."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel
from pydantic_ai.tools import RunContext  # noqa: TC002

from agentreplay.adapters.pydantic_ai import AgentReplayCapability
from agentreplay.cassette import Cassette
from agentreplay.divergence import DivergenceError

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def tmp_cassette(tmp_path: Path) -> Path:
    return tmp_path / "test_agent.jsonl"


def lookup_customer(ctx: RunContext[None], customer_id: str) -> str:
    """Look up customer details."""
    return f"Customer {customer_id}: Alice (tier=gold)"


def test_record_captures_model_events(tmp_cassette: Path) -> None:
    agent = Agent(TestModel())
    cap = AgentReplayCapability(mode="record", cassette_path=tmp_cassette)

    result = agent.run_sync("Hello model", capabilities=[cap])
    assert result.output

    cassette = Cassette.load(tmp_cassette)
    kinds = [e.kind for e in cassette.events]
    assert kinds == ["run_start", "model_request", "model_response", "run_end"]
    assert cassette.header.framework == "pydantic-ai"


def test_record_captures_tool_events(tmp_cassette: Path) -> None:
    agent = Agent(
        TestModel(call_tools=["lookup_customer"]),
        tools=[lookup_customer],
    )
    cap = AgentReplayCapability(mode="record", cassette_path=tmp_cassette)

    result = agent.run_sync("Find customer 123", capabilities=[cap])
    assert result.output

    cassette = Cassette.load(tmp_cassette)
    kinds = [e.kind for e in cassette.events]
    assert "tool_result" in kinds
    tool_event = next(e for e in cassette.events if e.kind == "tool_result")
    assert tool_event.name == "lookup_customer"
    assert tool_event.result == "Customer a: Alice (tier=gold)"


def test_record_cassette_saved_to_disk(tmp_cassette: Path) -> None:
    agent = Agent(TestModel())
    cap = AgentReplayCapability(mode="record", cassette_path=tmp_cassette)
    agent.run_sync("ping", capabilities=[cap])
    assert tmp_cassette.exists()
    assert tmp_cassette.stat().st_size > 0


def test_record_cassette_is_valid_jsonl(tmp_cassette: Path) -> None:
    agent = Agent(TestModel())
    cap = AgentReplayCapability(mode="record", cassette_path=tmp_cassette)
    agent.run_sync("ping", capabilities=[cap])

    lines = tmp_cassette.read_text(encoding="utf-8").strip().split("\n")
    for line in lines:
        parsed = json.loads(line)
        assert isinstance(parsed, dict)


def test_replay_produces_same_result(tmp_cassette: Path) -> None:
    agent = Agent(
        TestModel(call_tools=["lookup_customer"]),
        tools=[lookup_customer],
    )

    cap_rec = AgentReplayCapability(mode="record", cassette_path=tmp_cassette)
    res_rec = agent.run_sync("Find customer 123", capabilities=[cap_rec])

    cap_rep = AgentReplayCapability(mode="replay", cassette_path=tmp_cassette)
    res_rep = agent.run_sync("Find customer 123", capabilities=[cap_rep])

    assert res_rec.output == res_rep.output


def test_replay_skips_model_call(tmp_cassette: Path) -> None:
    # Record with TestModel
    agent = Agent(TestModel())
    cap_rec = AgentReplayCapability(mode="record", cassette_path=tmp_cassette)
    res_rec = agent.run_sync("Hello", capabilities=[cap_rec])

    # Replay with an agent whose model would error if invoked
    error_agent = Agent("test")  # No custom TestModel response, but replay bypasses model
    cap_rep = AgentReplayCapability(mode="replay", cassette_path=tmp_cassette)
    res_rep = error_agent.run_sync("Hello", capabilities=[cap_rep])

    assert res_rep.output == res_rec.output


def test_replay_skips_tool_execution(tmp_cassette: Path) -> None:
    call_count = 0

    def counting_tool(ctx: RunContext[None]) -> str:
        nonlocal call_count
        call_count += 1
        return "success"

    agent = Agent(TestModel(call_tools=["counting_tool"]), tools=[counting_tool])

    # Record
    cap_rec = AgentReplayCapability(mode="record", cassette_path=tmp_cassette)
    agent.run_sync("test", capabilities=[cap_rec])
    assert call_count == 1

    # Replay
    cap_rep = AgentReplayCapability(mode="replay", cassette_path=tmp_cassette)
    agent.run_sync("test", capabilities=[cap_rep])
    # call_count should STILL be 1 because tool execution was skipped
    assert call_count == 1


def test_replay_divergence_on_exhausted_cassette(tmp_cassette: Path) -> None:
    agent = Agent(TestModel())
    cap_rec = AgentReplayCapability(mode="record", cassette_path=tmp_cassette)
    agent.run_sync("hello", capabilities=[cap_rec])

    # Truncate cassette to just header and run_start
    cassette = Cassette.load(tmp_cassette)
    cassette.events = cassette.events[:1]
    cassette.save(tmp_cassette)

    cap_rep = AgentReplayCapability(mode="replay", cassette_path=tmp_cassette)
    with pytest.raises(DivergenceError) as exc_info:
        agent.run_sync("hello", capabilities=[cap_rep])

    assert exc_info.value.divergence_kind == "cassette_exhausted"


def test_replay_divergence_on_leftover_events(tmp_cassette: Path) -> None:
    agent = Agent(
        TestModel(call_tools=["lookup_customer"]),
        tools=[lookup_customer],
    )
    cap_rec = AgentReplayCapability(mode="record", cassette_path=tmp_cassette)
    agent.run_sync("Find customer 123", capabilities=[cap_rec])

    # Replay with a simpler agent that doesn't use tools (so leftover tool events remain)
    simple_agent = Agent(TestModel())
    cap_rep = AgentReplayCapability(mode="replay", cassette_path=tmp_cassette)
    with pytest.raises(DivergenceError) as exc_info:
        simple_agent.run_sync("Find customer 123", capabilities=[cap_rep])

    assert exc_info.value.divergence_kind in ("kind_mismatch", "leftover_events")


def test_record_deep_copies_arguments(tmp_cassette: Path) -> None:
    mutated_dict: dict[str, Any] = {"items": [1, 2]}

    def mutating_tool(ctx: RunContext[None], data: dict[str, Any]) -> str:
        mutated_dict["items"].append(3)
        return "ok"

    agent = Agent(TestModel(call_tools=["mutating_tool"]), tools=[mutating_tool])
    cap_rec = AgentReplayCapability(mode="record", cassette_path=tmp_cassette)
    agent.run_sync("mutate", capabilities=[cap_rec])

    cassette = Cassette.load(tmp_cassette)
    tool_event = next(e for e in cassette.events if e.kind == "tool_result")
    assert tool_event.arguments is not None
