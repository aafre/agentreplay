"""Unit tests for OpenAI client adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice

import agentreplay

if TYPE_CHECKING:
    from pathlib import Path


def _make_mock_completion(content: str = "Hello from mock model") -> ChatCompletion:
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
        model="gpt-4o",
        object="chat.completion",
    )


def test_openai_sync_record_and_replay(tmp_path: Path) -> None:
    cassette_file = tmp_path / "openai_sync.jsonl"

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_mock_completion("42")

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

    # 2. Replay with empty client that would raise if called
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
        # Verified: Reconstructed typed ChatCompletion offline
        assert isinstance(replay_resp, ChatCompletion)
        assert replay_resp.choices[0].message.content == "42"

    # Failing client was never called
    assert failing_client.chat.completions.create.call_count == 0


@pytest.mark.asyncio
async def test_openai_async_record_and_replay(tmp_path: Path) -> None:
    from unittest.mock import AsyncMock

    cassette_file = tmp_path / "openai_async.jsonl"

    mock_async_client = MagicMock()
    mock_async_client.chat.completions.create = AsyncMock(
        return_value=_make_mock_completion("Async answer")
    )

    # 1. Record
    wrapped_record = agentreplay.openai(
        mock_async_client, mode="record", cassette_path=cassette_file
    )
    with agentreplay.session(mode="record", cassette_path=cassette_file):
        resp = await wrapped_record.chat.completions.create(
            model="gpt-4o",
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
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert replay_resp.choices[0].message.content == "Async answer"
