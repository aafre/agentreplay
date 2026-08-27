"""Tests for Cassette — JSONL persistence."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from agentreplay.cassette import CASSETTE_FORMAT_VERSION, Cassette, CassetteHeader
from agentreplay.trace import TraceEvent

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def tmp_cassette_path(tmp_path: Path) -> Path:
    return tmp_path / "test.jsonl"


class TestCassetteHeader:
    def test_default_header(self) -> None:
        header = CassetteHeader()
        assert header.format_version == CASSETTE_FORMAT_VERSION
        assert header.created_at  # non-empty
        assert header.framework is None
        assert header.model is None

    def test_round_trip(self) -> None:
        header = CassetteHeader(framework="pydantic-ai", model="gpt-4o", metadata={"key": "value"})
        restored = CassetteHeader.from_dict(header.to_dict())
        assert restored.format_version == header.format_version
        assert restored.framework == header.framework
        assert restored.model == header.model
        assert restored.metadata == header.metadata


class TestCassetteSaveLoad:
    def test_round_trip_empty(self, tmp_cassette_path: Path) -> None:
        cassette = Cassette()
        cassette.save(tmp_cassette_path)
        loaded = Cassette.load(tmp_cassette_path)
        assert loaded.header.format_version == CASSETTE_FORMAT_VERSION
        assert len(loaded.events) == 0

    def test_round_trip_with_events(self, tmp_cassette_path: Path) -> None:
        cassette = Cassette(
            header=CassetteHeader(framework="pydantic-ai", model="test"),
        )
        cassette.append(
            TraceEvent(kind="model_request", timestamp=1.0, name="gpt-4o", event_id="aabb")
        )
        cassette.append(
            TraceEvent(
                kind="tool_call",
                timestamp=2.0,
                name="lookup",
                arguments={"id": "123"},
                event_id="ccdd",
            )
        )
        cassette.save(tmp_cassette_path)
        loaded = Cassette.load(tmp_cassette_path)

        assert loaded.header.framework == "pydantic-ai"
        assert len(loaded.events) == 2
        assert loaded.events[0].kind == "model_request"
        assert loaded.events[0].name == "gpt-4o"
        assert loaded.events[1].kind == "tool_call"
        assert loaded.events[1].arguments == {"id": "123"}

    def test_jsonl_format(self, tmp_cassette_path: Path) -> None:
        """Each line is a valid JSON object."""
        cassette = Cassette()
        cassette.append(TraceEvent(kind="run_start", timestamp=0.0, event_id="aa"))
        cassette.append(TraceEvent(kind="run_end", timestamp=1.0, event_id="bb"))
        cassette.save(tmp_cassette_path)

        lines = tmp_cassette_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3  # header + 2 events
        for line in lines:
            parsed = json.loads(line)
            assert isinstance(parsed, dict)

    def test_format_version_present(self, tmp_cassette_path: Path) -> None:
        cassette = Cassette()
        cassette.save(tmp_cassette_path)
        text = tmp_cassette_path.read_text(encoding="utf-8")
        first_line = json.loads(text.strip().split("\n")[0])
        assert "format_version" in first_line
        assert first_line["format_version"] == CASSETTE_FORMAT_VERSION

    def test_canonical_determinism(self, tmp_cassette_path: Path) -> None:
        """Byte-identical output for logically equal cassettes."""
        header = CassetteHeader(format_version=1, created_at="2026-01-01T00:00:00+00:00")
        events = [
            TraceEvent(
                kind="tool_call",
                timestamp=1.0,
                arguments={"z": 1, "a": 2},
                event_id="fixed",
            ),
        ]
        path_a = tmp_cassette_path.parent / "a.jsonl"
        path_b = tmp_cassette_path.parent / "b.jsonl"

        Cassette(header=header, events=list(events)).save(path_a)
        # Construct with reversed dict order
        events_b = [
            TraceEvent(
                kind="tool_call",
                timestamp=1.0,
                arguments={"a": 2, "z": 1},
                event_id="fixed",
            ),
        ]
        Cassette(header=header, events=events_b).save(path_b)

        assert path_a.read_bytes() == path_b.read_bytes()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        deep_path = tmp_path / "nested" / "dirs" / "cassette.jsonl"
        Cassette().save(deep_path)
        assert deep_path.exists()


class TestCassetteDeepCopy:
    def test_append_deep_copies_arguments(self) -> None:
        """Mutations after append must not corrupt the cassette."""
        args: dict[str, Any] = {"key": [1, 2, 3]}
        event = TraceEvent(kind="tool_call", timestamp=1.0, arguments=args)

        cassette = Cassette()
        cassette.append(event)

        # Mutate the original
        args["key"].append(4)
        args["new_key"] = "sneaky"

        # Cassette should be unaffected
        assert cassette.events[0].arguments == {"key": [1, 2, 3]}


class TestCassetteErrors:
    def test_load_empty_file(self, tmp_cassette_path: Path) -> None:
        tmp_cassette_path.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="Empty cassette"):
            Cassette.load(tmp_cassette_path)

    def test_load_missing_format_version(self, tmp_cassette_path: Path) -> None:
        tmp_cassette_path.write_text('{"created_at":"now"}\n', encoding="utf-8")
        with pytest.raises(ValueError, match="Missing format_version"):
            Cassette.load(tmp_cassette_path)
