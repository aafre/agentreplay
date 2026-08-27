"""agentreplay pytest plugin — CLI options and fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

import pytest

if TYPE_CHECKING:
    from agentreplay.adapters.pydantic_ai import AgentReplayCapability


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add CLI flags for agentreplay."""
    group = parser.getgroup("agentreplay", "agentreplay regression testing")
    group.addoption(
        "--agentreplay",
        action="store",
        dest="agentreplay",
        choices=["record", "replay"],
        default=None,
        help="Record or replay agent interactions (choices: 'record', 'replay')",
    )


class AgentReplayFixture:
    """Helper fixture object providing access to agentreplay configuration and capabilities."""

    def __init__(
        self,
        mode: Literal["record", "replay"] | None,
        test_name: str,
        test_module: str,
        cassettes_dir: Path,
    ) -> None:
        self._mode = mode
        self._test_name = test_name
        self._test_module = test_module
        self._cassettes_dir = cassettes_dir

    @property
    def mode(self) -> Literal["record", "replay"] | None:
        """Current agentreplay execution mode ('record', 'replay', or None)."""
        return self._mode

    @property
    def default_cassette_path(self) -> Path:
        """Auto-derived cassette file path based on test module and name."""
        mod_part = self._test_module.replace(".", "/")
        return self._cassettes_dir / mod_part / f"{self._test_name}.jsonl"

    def capability(
        self,
        cassette_path: str | Path | None = None,
    ) -> AgentReplayCapability | None:
        """Return an AgentReplayCapability configured for this test, or None if flag not set."""
        if self._mode is None:
            return None

        target_path = (
            Path(cassette_path) if cassette_path is not None else self.default_cassette_path
        )
        from agentreplay.adapters.pydantic_ai import AgentReplayCapability

        return AgentReplayCapability(mode=self._mode, cassette_path=target_path)


@pytest.fixture
def agentreplay(request: pytest.FixtureRequest) -> AgentReplayFixture:
    """Fixture providing agentreplay integration in pytest tests."""
    raw_mode = request.config.getoption("agentreplay")
    mode: Literal["record", "replay"] | None
    if raw_mode == "record":
        mode = "record"
    elif raw_mode == "replay":
        mode = "replay"
    else:
        mode = None

    test_name = request.node.name
    mod = getattr(request.node, "module", None)
    module_name = getattr(mod, "__name__", "tests")
    root_dir = Path(str(request.config.rootpath))
    cassettes_dir = root_dir / "tests" / "cassettes"

    return AgentReplayFixture(
        mode=mode,
        test_name=test_name,
        test_module=module_name,
        cassettes_dir=cassettes_dir,
    )
