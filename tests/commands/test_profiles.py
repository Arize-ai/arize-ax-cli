"""Tests for profiles command."""

from pathlib import Path

import tomli_w
from typer.testing import CliRunner

from ax.cli import app
from ax.config.manager import ConfigManager
from ax.config.schema import AuthConfig, Config


class TestProfilesValidate:
    """Tests for 'ax profiles validate' command."""

    def test_validate_valid_profile_exits_cleanly(
        self, mock_config_dir: Path
    ) -> None:
        """Validate on a valid profile should report it's valid."""
        config = Config(auth=AuthConfig(api_key="ak-test123"))
        ConfigManager.save(config, "default")

        runner = CliRunner()
        result = runner.invoke(app, ["profiles", "validate"])

        assert result.exit_code == 0
        assert "valid" in result.output

    def test_validate_missing_profile_raises_error(
        self, mock_config_dir: Path
    ) -> None:
        """Validate on a non-existent profile should report an error."""
        runner = CliRunner()
        result = runner.invoke(
            app, ["profiles", "validate", "--profile", "ghost"]
        )

        assert result.exit_code != 0

    def test_validate_invalid_profile_shows_error_and_hint(
        self, mock_config_dir: Path
    ) -> None:
        """Validate on an invalid profile should show validation errors and a hint."""
        bad_data = {"auth": {"api_key": ""}}  # empty key is invalid
        with open(ConfigManager.DEFAULT_CONFIG_FILE, "wb") as f:
            tomli_w.dump(bad_data, f)

        runner = CliRunner()
        result = runner.invoke(app, ["profiles", "validate"])

        assert result.exit_code != 0
        assert "Invalid profile" in result.output
        assert "ax profiles create" in result.output
