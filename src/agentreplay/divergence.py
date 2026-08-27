"""Structured divergence error raised when replay diverges from cassette."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from agentreplay.trace import TraceEvent

DivergenceKind = Literal[
    "kind_mismatch",
    "cassette_exhausted",
    "leftover_events",
    "argument_mismatch",
]


def _format_event_summary(event: TraceEvent) -> str:
    """Format a TraceEvent into a concise single-line representation."""
    if event.kind == "tool_call":
        if event.arguments:
            args_str = ", ".join(f"{k}={v!r}" for k, v in sorted(event.arguments.items()))
            return f"tool_call: {event.name}({args_str})"
        return f"tool_call: {event.name}()"
    if event.kind == "tool_result":
        return f"tool_result: {event.name}"
    if event.kind == "model_response":
        res_preview = str(event.result) if event.result is not None else ""
        if len(res_preview) > 60:
            res_preview = res_preview[:57] + "..."
        return f'model_response → "{res_preview}"' if res_preview else "model_response"
    if event.kind == "model_request":
        return "model_request"
    if event.name:
        return f"{event.kind}: {event.name}"
    return event.kind


class DivergenceError(AssertionError):
    """Raised when replay execution diverges from the recorded cassette."""

    def __init__(
        self,
        position: int,
        expected: TraceEvent | None,
        actual: TraceEvent | None,
        divergence_kind: DivergenceKind,
        message: str | None = None,
    ) -> None:
        self.position = position
        self.expected = expected
        self.actual = actual
        self.divergence_kind = divergence_kind

        if message is not None:
            self.message = message
        elif divergence_kind == "cassette_exhausted":
            self.message = "Cassette exhausted, but agent requested further interaction."
        elif divergence_kind == "leftover_events":
            self.message = (
                "Agent completed execution with unconsumed events remaining in cassette."
            )
        elif divergence_kind == "kind_mismatch":
            exp = expected.kind if expected else "None"
            act = actual.kind if actual else "None"
            self.message = f"Event kind mismatch: expected {exp}, got {act}."
        elif divergence_kind == "argument_mismatch":
            self.message = "Tool arguments did not match cassette."
        else:
            self.message = f"Divergence ({divergence_kind})"

        super().__init__(self._build_str())

    def _build_str(self) -> str:
        lines = [f"Divergence at step {self.position}:"]
        if self.expected is not None:
            lines.append(f"  Expected: {_format_event_summary(self.expected)}")
        if self.actual is not None:
            lines.append(f"  Actual:   {_format_event_summary(self.actual)}")
        if self.message:
            lines.append(f"  Note: {self.message}")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self._build_str()
