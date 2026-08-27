"""Tests for agentreplay pytest plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest


def test_fixture_available(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        def test_example(agentreplay):
            assert agentreplay is not None
            assert agentreplay.mode is None
            assert agentreplay.capability() is None
        """
    )
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(passed=1)


def test_record_flag_accepted(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        def test_example(agentreplay):
            assert agentreplay.mode == "record"
            cap = agentreplay.capability()
            assert cap is not None
            assert cap.mode == "record"
        """
    )
    result = pytester.runpytest_subprocess("--agentreplay=record")
    result.assert_outcomes(passed=1)


def test_replay_flag_accepted(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        def test_example(agentreplay):
            assert agentreplay.mode == "replay"
            cap = agentreplay.capability()
            assert cap is not None
            assert cap.mode == "replay"
        """
    )
    result = pytester.runpytest_subprocess("--agentreplay=replay")
    result.assert_outcomes(passed=1)


def test_cassette_path_derived_from_test_name(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        def test_custom_refund_flow(agentreplay):
            path = agentreplay.default_cassette_path
            assert "test_custom_refund_flow.jsonl" in str(path)
        """
    )
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(passed=1)
