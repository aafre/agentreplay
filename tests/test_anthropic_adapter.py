"""Unit tests for Anthropic client adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from anthropic.types import Message, TextBlock, Usage

import agentreplay

if TYPE_CHECKING:
    from pathlib import Path


def _make_mock_message(
    content: str = "Hello from Claude",
    model: str = "claude-3-7-sonnet-latest",
) -> Message:
    return Message(
        id="msg_test_123",
        content=[TextBlock(text=content, type="text")],
        model=model,
        role="assistant",
        type="message",
        usage=Usage(input_tokens=10, output_tokens=20),
    )


def test_anthropic_sync_record_and_replay(tmp_path: Path) -> None:
    cassette_file = tmp_path / "anthropic_sync.jsonl"

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_mock_message(
        "Claude response", model="claude-3-7-sonnet-latest"
    )

    # 1. Record
    wrapped_record = agentreplay.anthropic(mock_client, mode="record", cassette_path=cassette_file)
    with agentreplay.session(mode="record", cassette_path=cassette_file):
        resp = wrapped_record.messages.create(
            model="claude-3-7-sonnet-latest",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert resp.content and isinstance(resp.content[0], TextBlock)
        assert resp.content[0].text == "Claude response"

    assert mock_client.messages.create.call_count == 1
    assert cassette_file.exists()

    # 2. Replay with failing client
    failing_client = MagicMock()
    failing_client.messages.create.side_effect = RuntimeError("Live Anthropic API called!")

    wrapped_replay = agentreplay.anthropic(
        failing_client, mode="replay", cassette_path=cassette_file
    )
    with agentreplay.session(mode="replay", cassette_path=cassette_file):
        replay_resp = wrapped_replay.messages.create(
            model="claude-3-7-sonnet-latest",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert isinstance(replay_resp, Message)
        assert replay_resp.content and isinstance(replay_resp.content[0], TextBlock)
        assert replay_resp.content[0].text == "Claude response"

    assert failing_client.messages.create.call_count == 0


@pytest.mark.asyncio
async def test_anthropic_async_record_and_replay(tmp_path: Path) -> None:
    from unittest.mock import AsyncMock

    cassette_file = tmp_path / "anthropic_async.jsonl"

    mock_async_client = MagicMock()
    mock_async_client.messages.create = AsyncMock(
        return_value=_make_mock_message("Async Claude response", model="claude-3-5-haiku-latest")
    )

    # 1. Record
    wrapped_record = agentreplay.anthropic(
        mock_async_client, mode="record", cassette_path=cassette_file
    )
    with agentreplay.session(mode="record", cassette_path=cassette_file):
        resp = await wrapped_record.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert resp.content and isinstance(resp.content[0], TextBlock)
        assert resp.content[0].text == "Async Claude response"

    # 2. Replay
    failing_async_client = MagicMock()
    failing_async_client.messages.create = AsyncMock(side_effect=RuntimeError("Live API called!"))

    wrapped_replay = agentreplay.anthropic(
        failing_async_client, mode="replay", cassette_path=cassette_file
    )
    with agentreplay.session(mode="replay", cassette_path=cassette_file):
        replay_resp = await wrapped_replay.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert replay_resp.content and isinstance(replay_resp.content[0], TextBlock)
        assert replay_resp.content[0].text == "Async Claude response"
