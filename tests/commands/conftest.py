"""Shared fixtures for command tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ax.config.schema import AuthConfig, Config


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_config() -> Config:
    """Provide a minimal valid Config for testing."""
    return Config(auth=AuthConfig(api_key="ak-test-key"))


@pytest.fixture
def mock_client() -> MagicMock:
    """Provide a MagicMock ArizeClient with sub-client stubs."""
    client = MagicMock()
    client.datasets = MagicMock()
    client.evaluators = MagicMock()
    client.experiments = MagicMock()
    client.spans = MagicMock()
    client.projects = MagicMock()
    return client


@pytest.fixture
def patch_config_and_client(
    mock_config: Config,
    mock_client: MagicMock,
) -> Generator[tuple[MagicMock, MagicMock], None, None]:
    """Patch ConfigManager.load and ArizeClient so commands run without I/O.

    ArizeClient must be patched in every command module because each does
    ``from arize import ArizeClient``, binding a local name at import time.
    """
    with (
        patch(
            "ax.config.manager.ConfigManager.load",
            return_value=mock_config,
        ) as cfg_mock,
        patch(
            "ax.commands.datasets.ArizeClient",
            return_value=mock_client,
        ),
        patch(
            "ax.commands.evaluators.ArizeClient",
            return_value=mock_client,
        ),
        patch(
            "ax.commands.experiments.ArizeClient",
            return_value=mock_client,
        ),
        patch(
            "ax.commands.spans.ArizeClient",
            return_value=mock_client,
        ),
        patch(
            "ax.commands.traces.ArizeClient",
            return_value=mock_client,
        ),
        patch(
            "ax.commands.projects.ArizeClient",
            return_value=mock_client,
        ),
    ):
        yield cfg_mock, mock_client
