"""Shared fixtures for command tests."""

from collections.abc import Generator
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ax.config.schema import AuthConfig, Config, ProfileConfig


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_config() -> Config:
    """Provide a minimal valid Config for testing."""
    return Config(
        profile=ProfileConfig(name="test"),
        auth=AuthConfig(api_key="ak-test-key"),
    )


@pytest.fixture
def mock_client() -> MagicMock:
    """Provide a MagicMock ArizeClient with sub-client stubs."""
    client = MagicMock()
    client.datasets = MagicMock()
    client.evaluators = MagicMock()
    client.experiments = MagicMock()
    client.spans = MagicMock()
    client.projects = MagicMock()
    client.tasks = MagicMock()
    client.spaces = MagicMock()
    client.users = MagicMock()
    client.organizations = MagicMock()
    return client


_MAKE_CLIENT_MODULES = (
    "ax.commands.datasets",
    "ax.commands.evaluators",
    "ax.commands.experiments",
    "ax.commands.spans",
    "ax.commands.traces",
    "ax.commands.projects",
    "ax.commands.tasks",
    "ax.commands.spaces",
    "ax.commands.users",
    "ax.commands.organizations",
)


@pytest.fixture
def patch_config_and_client(
    mock_config: Config,
    mock_client: MagicMock,
) -> Generator[tuple[MagicMock, MagicMock], None, None]:
    """Patch ``make_client`` in every command module so commands run without I/O.

    Each command module imports ``make_client`` from ``ax.core.client_factory``,
    binding a local name at import time, so we patch per-module. We also patch
    ``ConfigManager.load`` globally so guards that load config directly (e.g.
    ``auth_guards.require_api_key_auth``) see the same mock config.
    """
    with ExitStack() as stack:
        cfg_mock = stack.enter_context(
            patch(
                "ax.config.manager.ConfigManager.load", return_value=mock_config
            )
        )
        for mod in _MAKE_CLIENT_MODULES:
            stack.enter_context(
                patch(
                    f"{mod}.make_client",
                    return_value=(mock_client, mock_config),
                )
            )
        yield cfg_mock, mock_client
