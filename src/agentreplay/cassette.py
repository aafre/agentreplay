"""Cassette — JSONL persistence for agent trace recordings."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentreplay.trace import TraceEvent

CASSETTE_FORMAT_VERSION = 1


@dataclass
class CassetteHeader:
    """Metadata written as the first line of a cassette file."""

    format_version: int = CASSETTE_FORMAT_VERSION
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    framework: str | None = None
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "format_version": self.format_version,
            "created_at": self.created_at,
        }
        if self.framework is not None:
            d["framework"] = self.framework
        if self.model is not None:
            d["model"] = self.model
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CassetteHeader:
        return cls(
            format_version=data["format_version"],
            created_at=data["created_at"],
            framework=data.get("framework"),
            model=data.get("model"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Cassette:
    """An ordered collection of trace events with a header.

    Persisted as JSONL: header on line 1, one event per subsequent line.
    Serialisation is canonical (sorted keys, compact separators, UTF-8)
    so logically equal cassettes produce byte-identical files.
    """

    header: CassetteHeader = field(default_factory=CassetteHeader)
    events: list[TraceEvent] = field(default_factory=list)

    def append(self, event: TraceEvent) -> None:
        """Append an event, deep-copying mutable fields to prevent corruption."""
        safe_event = TraceEvent(
            kind=event.kind,
            timestamp=event.timestamp,
            name=event.name,
            arguments=copy.deepcopy(event.arguments),
            result=copy.deepcopy(event.result),
            tool_calls=copy.deepcopy(event.tool_calls),
            event_id=event.event_id,
            metadata=copy.deepcopy(event.metadata),
        )
        self.events.append(safe_event)

    def save(self, path: Path | str) -> None:
        """Write cassette to a JSONL file with canonical serialisation."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = []
        lines.append(json.dumps(self.header.to_dict(), sort_keys=True, separators=(",", ":")))
        for event in self.events:
            lines.append(event.to_json())

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> Cassette:
        """Load a cassette from a JSONL file."""
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        lines = [line for line in text.strip().split("\n") if line.strip()]

        if not lines:
            msg = f"Empty cassette file: {path}"
            raise ValueError(msg)

        header_data = json.loads(lines[0])
        if "format_version" not in header_data:
            msg = f"Missing format_version in cassette header: {path}"
            raise ValueError(msg)

        header = CassetteHeader.from_dict(header_data)
        events = [TraceEvent.from_dict(json.loads(line)) for line in lines[1:]]

        return cls(header=header, events=events)
