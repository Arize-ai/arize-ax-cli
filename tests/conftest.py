"""Shared pytest fixtures and configuration for all tests."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from ax.config.manager import ConfigManager


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory for testing.

    Args:
        tmp_path: pytest's built-in temporary directory fixture

    Returns:
        Path to temporary .arize config directory
    """
    config_dir = tmp_path / ".arize"
    config_dir.mkdir()
    (config_dir / "profiles").mkdir()
    return config_dir


@pytest.fixture
def mock_config_dir(temp_config_dir: Path) -> Generator[Path, None, None]:
    """Mock ConfigManager directories to use temporary directory.

    This fixture patches all ConfigManager directory paths to use a
    temporary directory, ensuring tests don't affect real config files.

    Args:
        temp_config_dir: Temporary config directory fixture

    Yields:
        Path to mocked config directory
    """
    with (
        patch.object(ConfigManager, "CONFIG_DIR", temp_config_dir),
        patch.object(
            ConfigManager,
            "PROFILES_DIR",
            temp_config_dir / "profiles",
        ),
        patch.object(
            ConfigManager,
            "DEFAULT_CONFIG_FILE",
            temp_config_dir / "config.toml",
        ),
        patch.object(
            ConfigManager,
            "ACTIVE_PROFILE_FILE",
            temp_config_dir / ".active_profile",
        ),
    ):
        yield temp_config_dir


@pytest.fixture
def sample_config_data() -> dict[str, object]:
    """Provide sample configuration data for testing.

    Returns:
        Dictionary with valid configuration data
    """
    return {
        "profile": {"name": "test"},
        "auth": {"api_key": "ak-test123"},
        "routing": {"region": "us-east-1b"},
        "transport": {
            "stream_max_workers": 8,
            "stream_max_queue_bound": 5000,
            "pyarrow_max_chunksize": 10000,
            "max_http_payload_size_mb": 8,
        },
        "security": {"request_verify": True},
        "storage": {"directory": "~/.arize", "cache_enabled": True},
        "output": {"format": "table"},
    }
