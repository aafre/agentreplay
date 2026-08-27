"""Tests for CassetteCursor."""

from __future__ import annotations

import pytest

from agentreplay._cursor import CassetteCursor
from agentreplay.divergence import DivergenceError
from agentreplay.trace import TraceEvent


def test_next_returns_matching_event() -> None:
    events = [
        TraceEvent(kind="run_start", timestamp=1.0),
        TraceEvent(kind="model_request", timestamp=2.0),
    ]
    cursor = CassetteCursor(events)
    e1 = cursor.next("run_start")
    assert e1.kind == "run_start"
    assert e1.timestamp == 1.0


def test_next_advances_position() -> None:
    events = [
        TraceEvent(kind="run_start", timestamp=1.0),
        TraceEvent(kind="model_request", timestamp=2.0),
    ]
    cursor = CassetteCursor(events)
    assert cursor.position == 0
    cursor.next("run_start")
    assert cursor.position == 1
    cursor.next("model_request")
    assert cursor.position == 2


def test_next_raises_on_exhausted() -> None:
    cursor = CassetteCursor([])
    with pytest.raises(DivergenceError) as exc_info:
        cursor.next("run_start")
    assert exc_info.value.divergence_kind == "cassette_exhausted"
    assert exc_info.value.position == 0


def test_next_raises_on_kind_mismatch() -> None:
    events = [TraceEvent(kind="tool_call", timestamp=1.0, name="calc")]
    cursor = CassetteCursor(events)
    with pytest.raises(DivergenceError) as exc_info:
        cursor.next("model_response")
    assert exc_info.value.divergence_kind == "kind_mismatch"
    assert exc_info.value.expected == events[0]
    assert exc_info.value.actual is not None
    assert exc_info.value.actual.kind == "model_response"


def test_assert_exhausted_passes_when_empty() -> None:
    events = [TraceEvent(kind="run_start", timestamp=1.0)]
    cursor = CassetteCursor(events)
    cursor.next("run_start")
    cursor.assert_exhausted()  # should not raise


def test_assert_exhausted_raises_with_leftover() -> None:
    events = [
        TraceEvent(kind="run_start", timestamp=1.0),
        TraceEvent(kind="run_end", timestamp=2.0),
    ]
    cursor = CassetteCursor(events)
    cursor.next("run_start")
    with pytest.raises(DivergenceError) as exc_info:
        cursor.assert_exhausted()
    assert exc_info.value.divergence_kind == "leftover_events"
    assert exc_info.value.position == 1
    assert exc_info.value.expected == events[1]


def test_no_reset_method() -> None:
    cursor = CassetteCursor([])
    assert not hasattr(cursor, "reset")
    assert not hasattr(cursor, "__iter__")
