"""Tests for DivergenceError."""

from __future__ import annotations

from agentreplay.divergence import DivergenceError
from agentreplay.trace import TraceEvent


def test_is_assertion_error() -> None:
    err = DivergenceError(
        position=0,
        expected=None,
        actual=None,
        divergence_kind="cassette_exhausted",
    )
    assert isinstance(err, AssertionError)


def test_fields_accessible() -> None:
    expected = TraceEvent(kind="model_request", timestamp=1.0)
    actual = TraceEvent(kind="tool_call", timestamp=1.0, name="fetch")
    err = DivergenceError(
        position=2,
        expected=expected,
        actual=actual,
        divergence_kind="kind_mismatch",
        message="Custom message",
    )
    assert err.position == 2
    assert err.expected == expected
    assert err.actual == actual
    assert err.divergence_kind == "kind_mismatch"
    assert err.message == "Custom message"


def test_kind_mismatch_message() -> None:
    expected = TraceEvent(
        kind="tool_call",
        timestamp=1.0,
        name="check_refund_policy",
        arguments={"tier": "gold"},
    )
    actual = TraceEvent(
        kind="tool_call",
        timestamp=1.0,
        name="refund_customer",
        arguments={"amount": 39},
    )
    err = DivergenceError(
        position=3,
        expected=expected,
        actual=actual,
        divergence_kind="kind_mismatch",
    )
    text = str(err)
    assert "Divergence at step 3:" in text
    assert "Expected: tool_call: check_refund_policy(tier='gold')" in text
    assert "Actual:   tool_call: refund_customer(amount=39)" in text


def test_cassette_exhausted_message() -> None:
    actual = TraceEvent(kind="model_request", timestamp=2.0)
    err = DivergenceError(
        position=5,
        expected=None,
        actual=actual,
        divergence_kind="cassette_exhausted",
    )
    text = str(err)
    assert "Divergence at step 5:" in text
    assert "Actual:   model_request" in text
    assert "Cassette exhausted" in text


def test_leftover_events_message() -> None:
    expected = TraceEvent(kind="tool_call", timestamp=3.0, name="finalize")
    err = DivergenceError(
        position=4,
        expected=expected,
        actual=None,
        divergence_kind="leftover_events",
    )
    text = str(err)
    assert "Divergence at step 4:" in text
    assert "Expected: tool_call: finalize()" in text
    assert "unconsumed events remaining" in text
