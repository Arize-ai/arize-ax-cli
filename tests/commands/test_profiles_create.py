"""Integration tests for the `ax profiles create` command."""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ax.commands.profiles import app
from ax.config.schema import AuthConfig, Config


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Typer CliRunner."""
    return CliRunner()


# ---------------------------------------------------------------------------
# --from-file tests
# ---------------------------------------------------------------------------


class TestFromFile:
    """Tests for the --from-file option."""

    def test_happy_path_creates_profile(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """--from-file with a valid TOML creates a profile non-interactively."""
        toml_file = tmp_path / "profile.toml"
        toml_file.write_bytes(
            b'[auth]\napi_key = "test-key-123"\n\n[output]\nformat = "json"\n'
        )

        with (
            patch("ax.commands.profiles.ConfigManager") as mock_cm,
        ):
            mock_cm.list_profiles.return_value = []
            mock_cm.exists.return_value = False

            result = runner.invoke(
                app,
                [
                    "create",
                    "ci-profile",
                    "--from-file",
                    str(toml_file),
                ],
            )

        assert result.exit_code == 0, result.output
        mock_cm.save.assert_called_once()

    def test_nonexistent_file_shows_error(self, runner: CliRunner) -> None:
        """--from-file with a nonexistent path exits with a non-zero code."""
        with patch("ax.commands.profiles.ConfigManager") as mock_cm:
            mock_cm.list_profiles.return_value = []
            mock_cm.exists.return_value = False

            result = runner.invoke(
                app,
                [
                    "create",
                    "bad-profile",
                    "--from-file",
                    "/nonexistent/path/config.toml",
                ],
            )

        assert result.exit_code != 0

    def test_from_file_uses_toml_region(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """--from-file uses the region value from the TOML file."""
        toml_file = tmp_path / "profile.toml"
        toml_file.write_bytes(
            b'[auth]\napi_key = "toml-key"\n\n[routing]\nregion = "us-east-1b"\n'
        )

        saved_configs: list[Config] = []

        def capture_save(config: Config, _profile: str) -> None:
            saved_configs.append(config)

        with patch("ax.commands.profiles.ConfigManager") as mock_cm:
            mock_cm.list_profiles.return_value = []
            mock_cm.exists.return_value = False
            mock_cm.save.side_effect = capture_save

            result = runner.invoke(
                app,
                [
                    "create",
                    "file-profile",
                    "--from-file",
                    str(toml_file),
                ],
            )

        assert result.exit_code == 0, result.output
        assert saved_configs[0].routing.region == "us-east-1b"
        assert saved_configs[0].auth.api_key == "toml-key"

    def test_from_file_cli_flags_override_file(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """CLI flags are applied after TOML (flags override file)."""
        toml_file = tmp_path / "profile.toml"
        toml_file.write_bytes(
            b'[auth]\napi_key = "from-toml"\n\n[routing]\nregion = "us-east-1b"\n'
        )

        saved_configs: list[Config] = []

        def capture_save(config: Config, _profile: str) -> None:
            saved_configs.append(config)

        with patch("ax.commands.profiles.ConfigManager") as mock_cm:
            mock_cm.list_profiles.return_value = []
            mock_cm.exists.return_value = False
            mock_cm.save.side_effect = capture_save

            result = runner.invoke(
                app,
                [
                    "create",
                    "merged-profile",
                    "--from-file",
                    str(toml_file),
                    "--api-key",
                    "from-flag",
                    "--region",
                    "eu-west-1a",
                ],
            )

        assert result.exit_code == 0, result.output
        assert saved_configs[0].auth.api_key == "from-flag"
        assert saved_configs[0].routing.region == "eu-west-1a"


# ---------------------------------------------------------------------------
# Flag tests
# ---------------------------------------------------------------------------


class TestFlags:
    """Tests for individual CLI flags."""

    def test_api_key_flag_skips_interactive_prompt(
        self, runner: CliRunner
    ) -> None:
        """--api-key flag prevents read_api_key from being called."""
        with (
            patch("ax.commands.profiles.ConfigManager") as mock_cm,
            patch("ax.config.setup.read_api_key") as mock_read_key,
        ):
            mock_cm.list_profiles.return_value = []
            mock_cm.exists.return_value = False

            result = runner.invoke(
                app,
                [
                    "create",
                    "flagged-profile",
                    "--api-key",
                    "test-key-456",
                ],
            )

        assert result.exit_code == 0, result.output
        mock_read_key.assert_not_called()

    def test_missing_api_key_with_flags_fails(self, runner: CliRunner) -> None:
        """Providing flags without --api-key fails validation."""
        with patch("ax.commands.profiles.ConfigManager") as mock_cm:
            mock_cm.list_profiles.return_value = []
            mock_cm.exists.return_value = False

            result = runner.invoke(
                app,
                ["create", "bad-profile", "--output-format", "json"],
            )

        assert result.exit_code != 0

    def test_flags_succeed_with_all_required_fields(
        self, runner: CliRunner
    ) -> None:
        """Providing all required fields via flags creates the profile."""
        with patch("ax.commands.profiles.ConfigManager") as mock_cm:
            mock_cm.list_profiles.return_value = []
            mock_cm.exists.return_value = False

            result = runner.invoke(
                app,
                [
                    "create",
                    "ci-profile",
                    "--api-key",
                    "ci-key",
                    "--output-format",
                    "json",
                ],
            )

        assert result.exit_code == 0, result.output
        mock_cm.save.assert_called_once()

    def test_single_host_and_port_flags_set_routing(
        self, runner: CliRunner
    ) -> None:
        """--single-host and --single-port flags set on-prem routing config."""
        saved_configs: list[Config] = []

        def capture_save(config: Config, _profile: str) -> None:
            saved_configs.append(config)

        with patch("ax.commands.profiles.ConfigManager") as mock_cm:
            mock_cm.list_profiles.return_value = []
            mock_cm.exists.return_value = False
            mock_cm.save.side_effect = capture_save

            result = runner.invoke(
                app,
                [
                    "create",
                    "onprem-profile",
                    "--api-key",
                    "onprem-key",
                    "--single-host",
                    "arize.yourcompany.com",
                    "--single-port",
                    "443",
                ],
            )

        assert result.exit_code == 0, result.output
        assert saved_configs[0].routing.single_host == "arize.yourcompany.com"
        assert saved_configs[0].routing.single_port == "443"

    def test_env_var_detection_skipped_when_flag_provided(
        self, runner: CliRunner
    ) -> None:
        """Env var detection flow is skipped when any flag is provided."""
        with (
            patch("ax.commands.profiles.ConfigManager") as mock_cm,
            patch("ax.commands.profiles.detect_env_vars") as mock_detect,
        ):
            mock_cm.list_profiles.return_value = []
            mock_cm.exists.return_value = False

            result = runner.invoke(
                app,
                [
                    "create",
                    "flagged-profile",
                    "--api-key",
                    "k",
                ],
            )

        assert result.exit_code == 0, result.output
        mock_detect.assert_not_called()


# ---------------------------------------------------------------------------
# Profile name, overwrite, and active-profile behavior
# ---------------------------------------------------------------------------


class TestCreateProfileNameOverwriteAndActive:
    """Tests for profile naming, duplicate handling, and active profile."""

    def test_positional_profile_name_used(self, runner: CliRunner) -> None:
        """A positional profile_name argument sets the saved profile name."""
        saved_profile_names: list[str] = []

        def capture_save(_config: Config, profile: str) -> None:
            saved_profile_names.append(profile)

        with patch("ax.commands.profiles.ConfigManager") as mock_cm:
            mock_cm.list_profiles.return_value = []
            mock_cm.exists.return_value = False
            mock_cm.save.side_effect = capture_save

            result = runner.invoke(
                app,
                [
                    "create",
                    "my-named-profile",
                    "--api-key",
                    "k",
                ],
            )

        assert result.exit_code == 0, result.output
        assert saved_profile_names == ["my-named-profile"]

    def test_invalid_profile_name_raises_error(self, runner: CliRunner) -> None:
        """A profile name with invalid characters exits non-zero."""
        with patch("ax.commands.profiles.ConfigManager") as mock_cm:
            mock_cm.list_profiles.return_value = []
            mock_cm.exists.return_value = False

            result = runner.invoke(
                app,
                [
                    "create",
                    "bad name!",
                    "--api-key",
                    "k",
                ],
            )

        assert result.exit_code != 0

    def test_existing_profile_prompts_overwrite(
        self, runner: CliRunner
    ) -> None:
        """When the profile exists without flags, user is asked to confirm."""
        with patch("ax.commands.profiles.ConfigManager") as mock_cm:
            mock_cm.list_profiles.return_value = ["existing-profile"]
            mock_cm.exists.return_value = True

            # Provide "n" to decline overwrite
            runner.invoke(
                app,
                [
                    "create",
                    "existing-profile",
                    "--api-key",
                    "k",
                ],
                input="n\n",
            )

        # User declined — config should not be saved
        mock_cm.save.assert_not_called()

    def test_set_active_profile_called_for_non_default(
        self, runner: CliRunner
    ) -> None:
        """set_active_profile is called when a non-default profile is created."""
        with patch("ax.commands.profiles.ConfigManager") as mock_cm:
            mock_cm.list_profiles.return_value = []
            mock_cm.exists.return_value = False

            result = runner.invoke(
                app,
                [
                    "create",
                    "my-profile",
                    "--api-key",
                    "k",
                ],
            )

        assert result.exit_code == 0, result.output
        mock_cm.set_active_profile.assert_called_once_with("my-profile")

    def test_set_active_profile_not_called_for_default(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """set_active_profile is NOT called when the profile name is 'default'."""
        toml_file = tmp_path / "c.toml"
        toml_file.write_bytes(b'[auth]\napi_key = "k"\n')

        with patch("ax.commands.profiles.ConfigManager") as mock_cm:
            mock_cm.list_profiles.return_value = []
            mock_cm.exists.return_value = False

            # No positional arg → defaults to "default"
            result = runner.invoke(
                app,
                [
                    "create",
                    "--from-file",
                    str(toml_file),
                ],
            )

        assert result.exit_code == 0, result.output
        mock_cm.set_active_profile.assert_not_called()

    def test_flags_on_existing_profile_raises_error(
        self, runner: CliRunner
    ) -> None:
        """Using flags on an existing profile raises an error directing to update."""
        with patch("ax.commands.profiles.ConfigManager") as mock_cm:
            mock_cm.list_profiles.return_value = ["existing-profile"]
            mock_cm.exists.return_value = True

            result = runner.invoke(
                app,
                [
                    "create",
                    "existing-profile",
                    "--api-key",
                    "k",
                ],
            )

        assert result.exit_code != 0
        mock_cm.save.assert_not_called()

    def test_existing_profile_from_file_raises_without_prompt(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Duplicate profile with only --from-file raises; no overwrite prompt."""
        toml_file = tmp_path / "profile.toml"
        toml_file.write_bytes(b'[auth]\napi_key = "k"\n')

        with patch("ax.commands.profiles.ConfigManager") as mock_cm:
            mock_cm.list_profiles.return_value = ["existing-profile"]
            mock_cm.exists.return_value = True

            result = runner.invoke(
                app,
                [
                    "create",
                    "existing-profile",
                    "--from-file",
                    str(toml_file),
                ],
            )

        assert result.exit_code != 0
        mock_cm.save.assert_not_called()


# ---------------------------------------------------------------------------
# Update command flag tests
# ---------------------------------------------------------------------------


class TestUpdateFlags:
    """Tests for --single-host and --single-port flags on the update command."""

    def test_single_host_and_port_flags_update_routing(
        self, runner: CliRunner
    ) -> None:
        """--single-host and --single-port flags update on-prem routing via merge."""
        existing_config = Config(auth=AuthConfig(api_key="existing-key"))
        saved_configs: list[Config] = []

        def capture_save(config: Config, _profile: str) -> None:
            saved_configs.append(config)

        with patch("ax.commands.profiles.ConfigManager") as mock_cm:
            mock_cm.get_active_profile.return_value = "onprem-profile"
            mock_cm.exists.return_value = True
            mock_cm.load.return_value = existing_config
            mock_cm.save.side_effect = capture_save

            result = runner.invoke(
                app,
                [
                    "update",
                    "onprem-profile",
                    "--single-host",
                    "arize.yourcompany.com",
                    "--single-port",
                    "443",
                ],
            )

        assert result.exit_code == 0, result.output
        assert saved_configs[0].routing.single_host == "arize.yourcompany.com"
        assert saved_configs[0].routing.single_port == "443"
