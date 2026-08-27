"""CassetteCursor — stateful, one-shot iterator over recorded trace events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentreplay.divergence import DivergenceError
from agentreplay.trace import TraceEvent

if TYPE_CHECKING:
    from collections.abc import Sequence

    from agentreplay.trace import EventKind


class CassetteCursor:
    """A stateful, one-shot cursor over cassette events for replay."""

    def __init__(self, events: Sequence[TraceEvent]) -> None:
        self._events: list[TraceEvent] = list(events)
        self._position: int = 0

    @property
    def position(self) -> int:
        """Current zero-based index in the event stream."""
        return self._position

    def next(self, kind: EventKind) -> TraceEvent:
        """Advance cursor and return the next event if its kind matches.

        Raises DivergenceError if cassette is exhausted or if kind does not match.
        """
        if self._position >= len(self._events):
            raise DivergenceError(
                position=self._position,
                expected=None,
                actual=TraceEvent(kind=kind, timestamp=0.0),
                divergence_kind="cassette_exhausted",
                message=(
                    f"Expected event of kind '{kind}', but cassette is exhausted "
                    f"at step {self._position}."
                ),
            )

        recorded_event = self._events[self._position]
        if recorded_event.kind != kind:
            raise DivergenceError(
                position=self._position,
                expected=recorded_event,
                actual=TraceEvent(kind=kind, timestamp=0.0),
                divergence_kind="kind_mismatch",
            )

        self._position += 1
        return recorded_event

    def assert_exhausted(self) -> None:
        """Verify that all recorded events have been consumed.

        Raises DivergenceError if unconsumed events remain in the cassette.
        """
        if self._position < len(self._events):
            remaining_count = len(self._events) - self._position
            leftover_event = self._events[self._position]
            raise DivergenceError(
                position=self._position,
                expected=leftover_event,
                actual=None,
                divergence_kind="leftover_events",
                message=f"{remaining_count} unconsumed events remaining in cassette.",
            )
