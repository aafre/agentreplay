"""PydanticAI capability adapter for recording and replaying agent interactions."""

from __future__ import annotations

import copy
import dataclasses
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic_ai.capabilities.abstract import AbstractCapability
from pydantic_ai.exceptions import SkipModelRequest, SkipToolExecution
from pydantic_ai.messages import (
    ModelResponse,
    ModelResponsePart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
)
from pydantic_ai.usage import RequestUsage

from agentreplay._cursor import CassetteCursor
from agentreplay.cassette import Cassette, CassetteHeader
from agentreplay.divergence import DivergenceError
from agentreplay.trace import TraceEvent

if TYPE_CHECKING:
    from pydantic_ai.agent import AgentRunResult
    from pydantic_ai.models import ModelRequestContext
    from pydantic_ai.tools import RunContext, ToolDefinition


def _reconstruct_model_response(data: dict[str, Any] | None) -> ModelResponse:
    """Reconstruct a ModelResponse dataclass from a dictionary."""
    if data is None:
        return ModelResponse(parts=[])

    parts_data = data.get("parts", [])
    parts: list[ModelResponsePart] = []
    for p in parts_data:
        kind = p.get("part_kind")
        if kind == "text":
            parts.append(
                TextPart(
                    content=p.get("content", ""),
                    id=p.get("id"),
                    provider_name=p.get("provider_name"),
                    provider_details=p.get("provider_details"),
                )
            )
        elif kind == "tool-call":
            parts.append(
                ToolCallPart(
                    tool_name=p.get("tool_name", ""),
                    args=p.get("args", {}),
                    tool_call_id=p.get("tool_call_id"),
                    id=p.get("id"),
                    provider_name=p.get("provider_name"),
                    provider_details=p.get("provider_details"),
                )
            )
        elif kind == "thinking":
            parts.append(
                ThinkingPart(
                    content=p.get("content", ""),
                    id=p.get("id"),
                    signature=p.get("signature"),
                    provider_name=p.get("provider_name"),
                    provider_details=p.get("provider_details"),
                )
            )
        else:
            parts.append(TextPart(content=str(p.get("content", ""))))

    usage_data = data.get("usage")
    if usage_data:
        usage = RequestUsage(
            input_tokens=usage_data.get("input_tokens", 0),
            cache_write_tokens=usage_data.get("cache_write_tokens", 0),
            cache_read_tokens=usage_data.get("cache_read_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            input_audio_tokens=usage_data.get("input_audio_tokens", 0),
            cache_audio_read_tokens=usage_data.get("cache_audio_read_tokens", 0),
            output_audio_tokens=usage_data.get("output_audio_tokens", 0),
            details=usage_data.get("details", {}),
        )
    else:
        usage = RequestUsage()

    ts_data = data.get("timestamp")
    if isinstance(ts_data, str):
        try:
            ts = datetime.fromisoformat(ts_data)
        except Exception:
            ts = datetime.now(UTC)
    elif isinstance(ts_data, datetime):
        ts = ts_data
    else:
        ts = datetime.now(UTC)

    return ModelResponse(
        parts=parts,
        usage=usage,
        model_name=data.get("model_name"),
        timestamp=ts,
        provider_name=data.get("provider_name"),
        provider_url=data.get("provider_url"),
        provider_details=data.get("provider_details"),
        provider_response_id=data.get("provider_response_id"),
        finish_reason=data.get("finish_reason"),
        run_id=data.get("run_id"),
        conversation_id=data.get("conversation_id"),
        metadata=data.get("metadata"),
    )


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively convert datetime objects to ISO format strings for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    return obj


class AgentReplayCapability(AbstractCapability[Any]):
    """Capability for recording and replaying PydanticAI agent executions."""

    def __init__(
        self,
        *,
        mode: Literal["record", "replay"],
        cassette_path: str | Path,
        cassette: Cassette | None = None,
        cursor: CassetteCursor | None = None,
    ) -> None:
        super().__init__()
        self.mode: Literal["record", "replay"] = mode
        self.cassette_path: Path = Path(cassette_path)
        self._cassette: Cassette | None = cassette
        self._cursor: CassetteCursor | None = cursor

    async def for_run(self, ctx: RunContext[Any]) -> AgentReplayCapability:
        """Return a fresh capability instance isolated to this run."""
        if self.mode == "record":
            cassette = Cassette(
                header=CassetteHeader(
                    framework="pydantic-ai",
                )
            )
            return AgentReplayCapability(
                mode="record",
                cassette_path=self.cassette_path,
                cassette=cassette,
            )

        loaded_cassette = Cassette.load(self.cassette_path)
        cursor = CassetteCursor(loaded_cassette.events)
        return AgentReplayCapability(
            mode="replay",
            cassette_path=self.cassette_path,
            cassette=loaded_cassette,
            cursor=cursor,
        )

    async def before_run(self, ctx: RunContext[Any]) -> None:
        if self.mode == "record" and self._cassette is not None:
            self._cassette.append(TraceEvent(kind="run_start", timestamp=time.time()))
        elif self.mode == "replay" and self._cursor is not None:
            self._cursor.next("run_start")

    async def before_model_request(
        self,
        ctx: RunContext[Any],
        request_context: ModelRequestContext,
    ) -> ModelRequestContext:
        if self.mode == "record" and self._cassette is not None:
            model_id = getattr(request_context, "model_id", None)
            self._cassette.append(
                TraceEvent(kind="model_request", timestamp=time.time(), name=model_id)
            )
            return request_context

        if self.mode == "replay" and self._cursor is not None:
            self._cursor.next("model_request")
            resp_event = self._cursor.next("model_response")
            response = _reconstruct_model_response(resp_event.result)
            raise SkipModelRequest(response=response)

        return request_context

    async def after_model_request(
        self,
        ctx: RunContext[Any],
        *,
        request_context: ModelRequestContext,
        response: ModelResponse,
    ) -> ModelResponse:
        if self.mode == "record" and self._cassette is not None:
            resp_dict = _sanitize_for_json(dataclasses.asdict(response))
            self._cassette.append(
                TraceEvent(
                    kind="model_response",
                    timestamp=time.time(),
                    result=copy.deepcopy(resp_dict),
                )
            )
        return response

    async def before_tool_execute(
        self,
        ctx: RunContext[Any],
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: Any,
    ) -> Any:
        if self.mode == "replay" and self._cursor is not None:
            event = self._cursor.next("tool_result")
            if event.name != call.tool_name:
                raise DivergenceError(
                    position=self._cursor.position - 1,
                    expected=event,
                    actual=TraceEvent(
                        kind="tool_result",
                        timestamp=time.time(),
                        name=call.tool_name,
                    ),
                    divergence_kind="kind_mismatch",
                    message=(f"Tool mismatch: expected '{event.name}', got '{call.tool_name}'."),
                )
            raise SkipToolExecution(result=copy.deepcopy(event.result))

        return args

    async def after_tool_execute(
        self,
        ctx: RunContext[Any],
        *,
        call: ToolCallPart,
        tool_def: ToolDefinition,
        args: Any,
        result: Any,
    ) -> Any:
        if self.mode == "record" and self._cassette is not None:
            if isinstance(args, dict):
                safe_args: dict[str, Any] = copy.deepcopy(args)
            elif hasattr(args, "model_dump"):
                safe_args = copy.deepcopy(args.model_dump())
            elif hasattr(args, "__dataclass_fields__"):
                safe_args = copy.deepcopy(dataclasses.asdict(args))
            else:
                try:
                    safe_args = copy.deepcopy(dict(args))
                except Exception:
                    safe_args = {"raw": repr(args)}

            self._cassette.append(
                TraceEvent(
                    kind="tool_result",
                    timestamp=time.time(),
                    name=call.tool_name,
                    arguments=_sanitize_for_json(safe_args),
                    result=copy.deepcopy(_sanitize_for_json(result)),
                )
            )
        return result

    async def after_run(
        self,
        ctx: RunContext[Any],
        *,
        result: AgentRunResult[Any],
    ) -> AgentRunResult[Any]:
        if self.mode == "record" and self._cassette is not None:
            self._cassette.append(TraceEvent(kind="run_end", timestamp=time.time()))
            self._cassette.save(self.cassette_path)
        elif self.mode == "replay" and self._cursor is not None:
            self._cursor.next("run_end")
            self._cursor.assert_exhausted()

        return result
