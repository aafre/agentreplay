"""TraceDiff — human-readable trajectory comparison between event sequences."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from agentreplay.trace import TraceEvent


def format_event(event: TraceEvent) -> str:
    """Produce a single-line human-readable representation of a TraceEvent."""
    if event.kind == "tool_call":
        name = event.name or "unknown"
        if event.arguments is not None:
            args_str = ", ".join(f"{k}={v!r}" for k, v in sorted(event.arguments.items()))
            return f"tool_call: {name}({args_str})"
        return f"tool_call: {name}()"

    if event.kind == "tool_result":
        name = event.name or "unknown"
        if event.result is not None:
            res_str = str(event.result)
            if len(res_str) > 60:
                res_str = res_str[:57] + "..."
            return f"tool_result: {name} → {res_str}"
        return f"tool_result: {name}"

    if event.kind == "model_response":
        if event.result is not None:
            res_str = str(event.result)
            if len(res_str) > 60:
                res_str = res_str[:57] + "..."
            return f'model_response → "{res_str}"'
        return "model_response"

    if event.kind == "model_request":
        return "model_request"

    if event.kind == "run_start":
        return "run_start"

    if event.kind == "run_end":
        return "run_end"

    if event.kind == "error":
        msg = str(event.result) if event.result is not None else (event.name or "")
        return f"error: {msg}" if msg else "error"

    if event.name:
        return f"{event.kind}: {event.name}"
    return event.kind


def events_match(e1: TraceEvent | None, e2: TraceEvent | None) -> bool:
    """Check if two events match semantically, ignoring timestamp and event_id."""
    if e1 is None or e2 is None:
        return e1 is e2
    return (
        e1.kind == e2.kind
        and e1.name == e2.name
        and e1.arguments == e2.arguments
        and e1.result == e2.result
        and e1.tool_calls == e2.tool_calls
    )


def format_trace_diff(
    expected: Sequence[TraceEvent],
    actual: Sequence[TraceEvent],
) -> str:
    """Format the difference between expected and actual trace events.

    Returns a human-readable diff highlighting the first point of divergence.
    """
    if len(expected) == len(actual) and all(
        events_match(e, a) for e, a in zip(expected, actual, strict=True)
    ):
        return "Traces are identical"

    div_idx = 0
    max_len = max(len(expected), len(actual))
    for i in range(max_len):
        e = expected[i] if i < len(expected) else None
        a = actual[i] if i < len(actual) else None
        if not events_match(e, a):
            div_idx = i
            break

    lines: list[str] = [
        "Agent trajectory changed",
        "",
        "Expected:",
    ]

    if not expected:
        lines.append("  (empty)")
    else:
        for idx, ev in enumerate(expected, 1):
            lines.append(f"  {idx}. {format_event(ev)}")

    lines.extend(["", "Actual:"])

    if not actual:
        lines.append("  (empty)")
    else:
        for idx, ev in enumerate(actual, 1):
            lines.append(f"  {idx}. {format_event(ev)}")

    lines.extend(["", f"Divergence at step {div_idx + 1}:"])

    e_div = expected[div_idx] if div_idx < len(expected) else None
    a_div = actual[div_idx] if div_idx < len(actual) else None

    if e_div is not None:
        lines.append(f"  - {format_event(e_div)}")
    else:
        lines.append("  - (end of trace)")

    if a_div is not None:
        lines.append(f"  + {format_event(a_div)}")
    else:
        lines.append("  + (end of trace)")

    return "\n".join(lines)
