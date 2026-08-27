"""Tests for Vanilla OpenAI Agent Loop showing recording and offline replay."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)

import agentreplay
from examples.raw_openai_agent.agent import run_vanilla_agent

if TYPE_CHECKING:
    from pathlib import Path


def _make_tool_call_response() -> ChatCompletion:
    return ChatCompletion(
        id="chatcmpl-turn-1",
        choices=[
            Choice(
                finish_reason="tool_calls",
                index=0,
                message=ChatCompletionMessage(
                    role="assistant",
                    tool_calls=[
                        ChatCompletionMessageToolCall(
                            id="call_user_sub",
                            type="function",
                            function=Function(
                                name="get_user_subscription",
                                arguments=json.dumps({"user_id": "usr_99"}),
                            ),
                        )
                    ],
                ),
            )
        ],
        created=1724747400,
        model="gpt-4o",
        object="chat.completion",
    )


def _make_final_response() -> ChatCompletion:
    return ChatCompletion(
        id="chatcmpl-turn-2",
        choices=[
            Choice(
                finish_reason="stop",
                index=0,
                message=ChatCompletionMessage(
                    role="assistant",
                    content="Customer is on Enterprise tier with 50 seats.",
                ),
            )
        ],
        created=1724747405,
        model="gpt-4o",
        object="chat.completion",
    )


def test_vanilla_openai_record_and_replay(tmp_path: Path) -> None:
    cassette_file = tmp_path / "vanilla_openai_agent.jsonl"

    # Step 1: Record using mock client
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = [
        _make_tool_call_response(),
        _make_final_response(),
    ]

    with agentreplay.session(mode="record", cassette_path=cassette_file) as sess:
        wrapped_record_client = sess.wrap_openai(mock_client)
        result = run_vanilla_agent(wrapped_record_client, "Check status for usr_99")
        assert "Enterprise tier" in result

    assert cassette_file.exists()

    # Step 2: Replay offline with a client that throws if called
    failing_client = MagicMock()
    failing_client.chat.completions.create.side_effect = RuntimeError(
        "Live network call attempted during replay!"
    )

    with agentreplay.session(mode="replay", cassette_path=cassette_file) as sess:
        wrapped_replay_client = sess.wrap_openai(failing_client)
        replay_result = run_vanilla_agent(wrapped_replay_client, "Check status for usr_99")
        assert replay_result == result

    # Verified: Zero live API calls occurred during replay
    assert failing_client.chat.completions.create.call_count == 0
