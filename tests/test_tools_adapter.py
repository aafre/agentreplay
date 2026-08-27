"""Unit tests for tool wrapper and decorator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

import agentreplay
from agentreplay.divergence import DivergenceError

if TYPE_CHECKING:
    from pathlib import Path


def test_tool_unmonitored_execution() -> None:
    @agentreplay.tool
    def add(a: int, b: int) -> int:
        return a + b

    assert add(2, 3) == 5


def test_tool_record_and_replay_session(tmp_path: Path) -> None:
    cassette_file = tmp_path / "tools_test.jsonl"

    call_count = 0

    @agentreplay.tool
    def compute_tax(amount: float) -> float:
        nonlocal call_count
        call_count += 1
        return round(amount * 0.2, 2)

    # 1. Record
    with agentreplay.session(mode="record", cassette_path=cassette_file):
        tax = compute_tax(100.0)
        assert tax == 20.0
        assert call_count == 1

    assert cassette_file.exists()

    # 2. Replay (body should NOT be executed)
    with agentreplay.session(mode="replay", cassette_path=cassette_file):
        replay_tax = compute_tax(100.0)
        assert replay_tax == 20.0
        # Call count remains 1 because execution was substituted offline!
        assert call_count == 1


def test_tool_divergence_detection(tmp_path: Path) -> None:
    cassette_file = tmp_path / "tools_divergence.jsonl"

    @agentreplay.tool
    def tool_a() -> str:
        return "result_a"

    @agentreplay.tool
    def tool_b() -> str:
        return "result_b"

    # Record tool_a
    with agentreplay.session(mode="record", cassette_path=cassette_file):
        tool_a()

    # Replay with tool_b
    with (
        pytest.raises(DivergenceError) as exc_info,
        agentreplay.session(mode="replay", cassette_path=cassette_file),
    ):
        tool_b()

    assert "Tool mismatch" in str(exc_info.value)
