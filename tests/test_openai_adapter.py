"""Unit tests for OpenAI client adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from openai.types.chat import ChatCompletion, ChatCompletionMessage, ParsedChatCompletion
from openai.types.chat.chat_completion import Choice
from openai.types.chat.parsed_chat_completion import ParsedChatCompletionMessage, ParsedChoice
from pydantic import BaseModel

import agentreplay

if TYPE_CHECKING:
    from pathlib import Path


class AnalysisResult(BaseModel):
    summary: str
    confidence: float


def _make_mock_completion(
    content: str = "Hello from mock model", model: str = "gpt-4o"
) -> ChatCompletion:
    return ChatCompletion(
        id="chatcmpl-test-123",
        choices=[
            Choice(
                finish_reason="stop",
                index=0,
                message=ChatCompletionMessage(
                    content=content,
                    role="assistant",
                ),
            )
        ],
        created=1724747400,
        model=model,
        object="chat.completion",
    )


def test_openai_sync_record_and_replay(tmp_path: Path) -> None:
    cassette_file = tmp_path / "openai_sync.jsonl"

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_mock_completion("42", model="gpt-4o")

    # 1. Record
    wrapped_record = agentreplay.openai(mock_client, mode="record", cassette_path=cassette_file)
    with agentreplay.session(mode="record", cassette_path=cassette_file):
        resp = wrapped_record.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "What is the answer?"}],
        )
        assert resp.choices[0].message.content == "42"

    assert mock_client.chat.completions.create.call_count == 1
    assert cassette_file.exists()

    # 2. Replay with failing client
    failing_client = MagicMock()
    failing_client.chat.completions.create.side_effect = RuntimeError(
        "Live API called during replay!"
    )

    wrapped_replay = agentreplay.openai(failing_client, mode="replay", cassette_path=cassette_file)
    with agentreplay.session(mode="replay", cassette_path=cassette_file):
        replay_resp = wrapped_replay.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "What is the answer?"}],
        )
        assert isinstance(replay_resp, ChatCompletion)
        assert replay_resp.choices[0].message.content == "42"

    assert failing_client.chat.completions.create.call_count == 0


@pytest.mark.asyncio
async def test_openai_async_record_and_replay(tmp_path: Path) -> None:
    from unittest.mock import AsyncMock

    cassette_file = tmp_path / "openai_async.jsonl"

    mock_async_client = MagicMock()
    mock_async_client.chat.completions.create = AsyncMock(
        return_value=_make_mock_completion("Async answer", model="o3-mini")
    )

    # 1. Record
    wrapped_record = agentreplay.openai(
        mock_async_client, mode="record", cassette_path=cassette_file
    )
    with agentreplay.session(mode="record", cassette_path=cassette_file):
        resp = await wrapped_record.chat.completions.create(
            model="o3-mini",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert resp.choices[0].message.content == "Async answer"

    # 2. Replay
    failing_async_client = MagicMock()
    failing_async_client.chat.completions.create = AsyncMock(
        side_effect=RuntimeError("Live API called!")
    )

    wrapped_replay = agentreplay.openai(
        failing_async_client, mode="replay", cassette_path=cassette_file
    )
    with agentreplay.session(mode="replay", cassette_path=cassette_file):
        replay_resp = await wrapped_replay.chat.completions.create(
            model="o3-mini",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert replay_resp.choices[0].message.content == "Async answer"


def test_openai_structured_outputs_parse(tmp_path: Path) -> None:
    cassette_file = tmp_path / "openai_structured.jsonl"

    parsed_obj = AnalysisResult(summary="Healthy system", confidence=0.98)
    mock_parsed_completion = ParsedChatCompletion[AnalysisResult](
        id="chatcmpl-parse-1",
        choices=[
            ParsedChoice[AnalysisResult](
                finish_reason="stop",
                index=0,
                message=ParsedChatCompletionMessage[AnalysisResult](
                    content=parsed_obj.model_dump_json(),
                    parsed=parsed_obj,
                    role="assistant",
                ),
            )
        ],
        created=1724747410,
        model="gpt-4o-mini",
        object="chat.completion",
    )

    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse.return_value = mock_parsed_completion

    # 1. Record
    wrapped_record = agentreplay.openai(mock_client, mode="record", cassette_path=cassette_file)
    with agentreplay.session(mode="record", cassette_path=cassette_file):
        resp = wrapped_record.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Analyze cluster"}],
            response_format=AnalysisResult,
        )
        assert resp.choices[0].message.content is not None

    # 2. Replay
    failing_client = MagicMock()
    failing_client.beta.chat.completions.parse.side_effect = RuntimeError("Live API called!")

    wrapped_replay = agentreplay.openai(failing_client, mode="replay", cassette_path=cassette_file)
    with agentreplay.session(mode="replay", cassette_path=cassette_file):
        replay_resp = wrapped_replay.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Analyze cluster"}],
            response_format=AnalysisResult,
        )
        assert replay_resp.choices[0].message.parsed is not None
        assert replay_resp.choices[0].message.parsed.summary == "Healthy system"
        assert replay_resp.choices[0].message.parsed.confidence == 0.98
