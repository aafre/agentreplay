"""Tests for TraceDiff and event formatting."""

from __future__ import annotations

from agentreplay.diff import format_event, format_trace_diff
from agentreplay.trace import TraceEvent


def test_format_event_tool_call() -> None:
    event = TraceEvent(
        kind="tool_call",
        timestamp=1.0,
        name="lookup_customer",
        arguments={"id": "123", "include_orders": True},
    )
    text = format_event(event)
    assert text == "tool_call: lookup_customer(id='123', include_orders=True)"


def test_format_event_tool_call_no_args() -> None:
    event = TraceEvent(kind="tool_call", timestamp=1.0, name="get_version")
    assert format_event(event) == "tool_call: get_version()"


def test_format_event_model_request() -> None:
    event = TraceEvent(kind="model_request", timestamp=1.0)
    assert format_event(event) == "model_request"


def test_format_event_model_response_truncates() -> None:
    long_text = "x" * 100
    event = TraceEvent(kind="model_response", timestamp=1.0, result=long_text)
    text = format_event(event)
    assert text.startswith('model_response → "')
    assert text.endswith('..."')
    assert len(text) < 80


def test_format_event_run_start() -> None:
    event = TraceEvent(kind="run_start", timestamp=0.0)
    assert format_event(event) == "run_start"


def test_format_trace_diff_identical() -> None:
    events = [
        TraceEvent(kind="run_start", timestamp=0.0),
        TraceEvent(kind="model_request", timestamp=1.0),
    ]
    assert format_trace_diff(events, list(events)) == "Traces are identical"


def test_format_trace_diff_divergence() -> None:
    expected = [
        TraceEvent(kind="model_request", timestamp=1.0),
        TraceEvent(
            kind="tool_call", timestamp=2.0, name="lookup_customer", arguments={"id": "123"}
        ),
        TraceEvent(
            kind="tool_call", timestamp=3.0, name="check_refund_policy", arguments={"tier": "gold"}
        ),
        TraceEvent(kind="model_response", timestamp=4.0, result="Refund processed."),
    ]
    actual = [
        TraceEvent(kind="model_request", timestamp=1.0),
        TraceEvent(
            kind="tool_call", timestamp=2.0, name="lookup_customer", arguments={"id": "123"}
        ),
        TraceEvent(
            kind="tool_call", timestamp=3.0, name="refund_customer", arguments={"amount": 39}
        ),
    ]
    diff = format_trace_diff(expected, actual)
    assert "Agent trajectory changed" in diff
    assert "Expected:" in diff
    assert "Actual:" in diff
    assert "Divergence at step 3:" in diff
    assert "- tool_call: check_refund_policy(tier='gold')" in diff
    assert "+ tool_call: refund_customer(amount=39)" in diff


def test_format_trace_diff_different_lengths() -> None:
    expected = [
        TraceEvent(kind="model_request", timestamp=1.0),
        TraceEvent(kind="tool_call", timestamp=2.0, name="tool_a"),
    ]
    actual = [
        TraceEvent(kind="model_request", timestamp=1.0),
    ]
    diff = format_trace_diff(expected, actual)
    assert "Divergence at step 2:" in diff
    assert "- tool_call: tool_a()" in diff
    assert "+ (end of trace)" in diff


def test_format_trace_diff_empty_vs_events() -> None:
    expected: list[TraceEvent] = []
    actual = [TraceEvent(kind="run_start", timestamp=0.0)]
    diff = format_trace_diff(expected, actual)
    assert "Divergence at step 1:" in diff
    assert "- (end of trace)" in diff
    assert "+ run_start" in diff
