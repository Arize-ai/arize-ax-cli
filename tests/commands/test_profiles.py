"""Tests for profiles command."""

from pathlib import Path

import tomli_w
from typer.testing import CliRunner

from ax.cli import app
from ax.commands.profiles import _display_detected_env_value
from ax.config.manager import ConfigManager
from ax.config.schema import AuthConfig, Config, ProfileConfig, SecurityConfig


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


class TestProfilesShowClientCertificate:
    """'ax profiles show' displays TLS paths but never PEM content."""

    def _save(self, security: SecurityConfig) -> None:
        config = Config(
            profile=ProfileConfig(name="test"),
            auth=AuthConfig(api_key="ak-test123"),
            security=security,
        )
        ConfigManager.save(config, "test")
        ConfigManager.ACTIVE_PROFILE_FILE.write_text("test")

    def test_shows_cert_paths(self, mock_config_dir: Path) -> None:
        self._save(
            SecurityConfig(
                client_cert="/etc/arize/client.crt",
                client_key="/etc/arize/client.key",
                ssl_ca_cert="/etc/arize/ca.pem",
            )
        )
        result = CliRunner().invoke(app, ["profiles", "show"])

        assert result.exit_code == 0, result.output
        assert "/etc/arize/client.crt" in result.output
        assert "/etc/arize/client.key" in result.output
        assert "/etc/arize/ca.pem" in result.output

    def test_expanded_pem_content_is_not_echoed(
        self, mock_config_dir: Path, monkeypatch
    ) -> None:
        monkeypatch.setenv(
            "MY_KEY",
            "-----BEGIN PRIVATE KEY-----\nSECRETKEYBODY\n"
            "-----END PRIVATE KEY-----",
        )
        self._save(SecurityConfig(client_cert="/c.crt", client_key="${MY_KEY}"))
        result = CliRunner().invoke(app, ["profiles", "show", "--expand"])

        assert result.exit_code == 0, result.output
        assert "SECRETKEYBODY" not in result.output
        assert "PEM content" in result.output


class TestDetectedEnvValueDisplay:
    def test_pem_content_is_redacted(self) -> None:
        shown = _display_detected_env_value(
            "client_key",
            "-----BEGIN PRIVATE KEY-----\nSECRETKEYBODY\n",
        )
        assert "SECRETKEYBODY" not in shown

    def test_paths_are_shown(self) -> None:
        assert _display_detected_env_value("client_cert", "/c.crt") == "/c.crt"

    def test_api_key_is_masked(self) -> None:
        shown = _display_detected_env_value(
            "api_key", "ak-1234567890abcdefghij"
        )
        assert "abcdefghij" not in shown
