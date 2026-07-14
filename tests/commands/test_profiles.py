"""Tests for profiles command."""

from pathlib import Path

import tomli_w
from typer.testing import CliRunner

from ax.cli import app
from ax.config.manager import ConfigManager
from ax.config.schema import AuthConfig, Config, ProfileConfig


class TestProfilesValidate:
    """Tests for 'ax profiles validate' command."""

    def test_validate_valid_profile_exits_cleanly(
        self, mock_config_dir: Path
    ) -> None:
        """Validate on a valid profile should report it's valid."""
        config = Config(
            profile=ProfileConfig(name="test"),
            auth=AuthConfig(api_key="ak-test123"),
        )
        ConfigManager.save(config, "test")
        ConfigManager.ACTIVE_PROFILE_FILE.write_text("test")

        runner = CliRunner()
        result = runner.invoke(app, ["profiles", "validate"])

        assert result.exit_code == 0
        assert "valid" in result.output

    def test_validate_missing_profile_raises_error(
        self, mock_config_dir: Path
    ) -> None:
        """Validate on a non-existent profile should report an error."""
        runner = CliRunner()
        result = runner.invoke(app, ["profiles", "validate", "ghost"])

        assert result.exit_code != 0

    def test_validate_invalid_profile_shows_error_and_hint(
        self, mock_config_dir: Path
    ) -> None:
        """Validate on an invalid profile should show validation errors and a hint."""
        bad_data = {"auth": {"api_key": ""}}  # empty key is invalid
        with open(ConfigManager.PROFILES_DIR / "test.toml", "wb") as f:
            tomli_w.dump(bad_data, f)
        ConfigManager.ACTIVE_PROFILE_FILE.write_text("test")

        runner = CliRunner()
        result = runner.invoke(app, ["profiles", "validate"])

        assert result.exit_code != 0
        assert "Invalid profile" in result.output
        assert "ax profiles create" in result.output
        assert "pydantic.dev" not in result.output


class TestProfilesShowRedaction:
    """`ax profiles show` must never echo credentials to the terminal."""

    def test_show_redacts_credentials_in_env_ref_default(
        self, mock_config_dir: Path
    ) -> None:
        """A ${VAR:default} default may embed a credentialed proxy URL."""
        from ax.config.schema import NetworkConfig

        config = Config(
            profile=ProfileConfig(name="proxied"),
            auth=AuthConfig(api_key="ak-test123"),
            network=NetworkConfig(
                proxy_mode="url",
                proxy_url="${CORP_PROXY:http://svc:hunter2@proxy.corp:8080}",
            ),
        )
        ConfigManager.save(config, "proxied")
        ConfigManager.ACTIVE_PROFILE_FILE.write_text("proxied")

        runner = CliRunner()
        result = runner.invoke(app, ["profiles", "show", "proxied"])

        assert result.exit_code == 0, result.output
        assert "hunter2" not in result.output
        assert "CORP_PROXY:***" in result.output

    def test_display_env_ref_keeps_plain_references(self) -> None:
        """References without a default stay readable as-is."""
        from ax.commands.profiles import _display_env_ref

        assert _display_env_ref("${ARIZE_PROXY_URL}") == "${ARIZE_PROXY_URL}"
        assert (
            _display_env_ref("${CORP_PROXY:http://u:p@h:1}")
            == "${CORP_PROXY:***}"
        )
