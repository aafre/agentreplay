"""Canonical trace event model — framework-independent."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

EventKind = Literal[
    "run_start",
    "run_end",
    "model_request",
    "model_response",
    "tool_call",
    "tool_result",
    "error",
]


@dataclass(frozen=True)
class TraceEvent:
    """A single event in an agent execution trace.

    Events are immutable after creation. The ``kind`` field determines the
    semantic type — payloads are interpreted based on kind, not on in-band
    type tags in the data itself.
    """

    kind: EventKind
    timestamp: float
    name: str | None = None
    arguments: dict[str, Any] | None = None
    result: Any | None = None
    tool_calls: list[dict[str, Any]] | None = None
    event_id: str = field(default_factory=lambda: uuid4().hex[:12])
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a dictionary, omitting None fields for compactness."""
        d: dict[str, Any] = {
            "kind": self.kind,
            "timestamp": self.timestamp,
            "event_id": self.event_id,
        }
        if self.name is not None:
            d["name"] = self.name
        if self.arguments is not None:
            d["arguments"] = self.arguments
        if self.result is not None:
            d["result"] = self.result
        if self.tool_calls is not None:
            d["tool_calls"] = self.tool_calls
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceEvent:
        """Deserialise from a dictionary."""
        return cls(
            kind=data["kind"],
            timestamp=data["timestamp"],
            event_id=data.get("event_id", uuid4().hex[:12]),
            name=data.get("name"),
            arguments=data.get("arguments"),
            result=data.get("result"),
            tool_calls=data.get("tool_calls"),
            metadata=data.get("metadata", {}),
        )

    def to_json(self) -> str:
        """Canonical JSON string — sorted keys, compact separators."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
