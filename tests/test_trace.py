"""Tests for TraceEvent — the canonical trace event model."""

from __future__ import annotations

import json
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agentreplay.trace import TraceEvent


class TestTraceEventCreation:
    def test_minimal_event(self) -> None:
        event = TraceEvent(kind="model_request", timestamp=1.0)
        assert event.kind == "model_request"
        assert event.timestamp == 1.0
        assert event.name is None
        assert event.arguments is None
        assert event.result is None
        assert event.tool_calls is None
        assert len(event.event_id) == 12
        assert event.metadata == {}

    def test_full_event(self) -> None:
        event = TraceEvent(
            kind="tool_call",
            timestamp=2.5,
            name="lookup_customer",
            arguments={"id": "123"},
            result="found",
            tool_calls=[{"name": "sub_tool"}],
            event_id="abc123def456",
            metadata={"framework": "pydantic-ai"},
        )
        assert event.name == "lookup_customer"
        assert event.arguments == {"id": "123"}
        assert event.result == "found"
        assert event.event_id == "abc123def456"

    def test_frozen_immutability(self) -> None:
        event = TraceEvent(kind="run_start", timestamp=0.0)
        with pytest.raises(AttributeError):
            event.kind = "run_end"  # type: ignore[misc]


class TestTraceEventSerialization:
    def test_round_trip(self) -> None:
        original = TraceEvent(
            kind="tool_call",
            timestamp=1.5,
            name="refund",
            arguments={"amount": 39, "currency": "GBP"},
            event_id="aabbccddee00",
        )
        restored = TraceEvent.from_dict(original.to_dict())
        assert restored.kind == original.kind
        assert restored.timestamp == original.timestamp
        assert restored.name == original.name
        assert restored.arguments == original.arguments
        assert restored.event_id == original.event_id

    def test_omits_none_fields(self) -> None:
        event = TraceEvent(kind="run_start", timestamp=0.0, event_id="aabbccddee00")
        d = event.to_dict()
        assert "name" not in d
        assert "arguments" not in d
        assert "result" not in d
        assert "tool_calls" not in d
        assert "metadata" not in d  # empty dict is omitted

    def test_canonical_json_sorted_keys(self) -> None:
        event = TraceEvent(
            kind="tool_call",
            timestamp=1.0,
            name="test",
            arguments={"z_key": 1, "a_key": 2},
            event_id="aabbccddee00",
        )
        json_str = event.to_json()
        parsed = json.loads(json_str)
        # Keys should be sorted in the JSON string
        keys = list(parsed.keys())
        assert keys == sorted(keys)
        # Arguments keys should also be sorted
        arg_keys = list(json.loads(json_str)["arguments"].keys())
        assert arg_keys == sorted(arg_keys)

    def test_canonical_json_compact_separators(self) -> None:
        event = TraceEvent(kind="run_start", timestamp=0.0, event_id="aabbccddee00")
        json_str = event.to_json()
        # No spaces after separators
        assert ": " not in json_str
        assert ", " not in json_str

    def test_cross_order_determinism(self) -> None:
        """Dict construction order must not affect serialised output."""
        args_a: dict[str, Any] = {"z": 1, "a": 2, "m": 3}
        args_b: dict[str, Any] = {"a": 2, "m": 3, "z": 1}

        event_a = TraceEvent(kind="tool_call", timestamp=1.0, arguments=args_a, event_id="aabb")
        event_b = TraceEvent(kind="tool_call", timestamp=1.0, arguments=args_b, event_id="aabb")
        assert event_a.to_json() == event_b.to_json()

    def test_from_dict_missing_optional_fields(self) -> None:
        data = {"kind": "run_end", "timestamp": 99.0}
        event = TraceEvent.from_dict(data)
        assert event.kind == "run_end"
        assert event.timestamp == 99.0
        assert event.name is None
        assert event.arguments is None


# --- Property-based tests ---

json_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**53), max_value=2**53),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=50),
)

json_values: st.SearchStrategy[Any] = st.recursive(
    json_primitives,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(max_size=10), children, max_size=5),
    ),
    max_leaves=20,
)

event_kinds = st.sampled_from(
    [
        "run_start",
        "run_end",
        "model_request",
        "model_response",
        "tool_call",
        "tool_result",
        "error",
    ]
)


@given(
    kind=event_kinds,
    timestamp=st.floats(min_value=0, max_value=1e12, allow_nan=False),
    name=st.one_of(st.none(), st.text(max_size=30)),
    arguments=st.one_of(
        st.none(),
        st.dictionaries(st.text(max_size=10), json_values, max_size=5),
    ),
)
def test_round_trip_property(
    kind: str,
    timestamp: float,
    name: str | None,
    arguments: dict[str, Any] | None,
) -> None:
    """Any TraceEvent round-trips through to_dict/from_dict."""
    event = TraceEvent(
        kind=kind,  # type: ignore[arg-type]
        timestamp=timestamp,
        name=name,
        arguments=arguments,
    )
    restored = TraceEvent.from_dict(event.to_dict())
    assert restored.kind == event.kind
    assert restored.timestamp == event.timestamp
    assert restored.name == event.name
    assert restored.arguments == event.arguments
