"""Integration tests for the `ax profiles create` command."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

import pytest
from typer.testing import CliRunner

from ax.commands.profiles import app
from ax.config.manager import ConfigManager
from ax.config.schema import (
    AuthConfig,
    Config,
    OAuthCredentials,
    ProfileConfig,
    RoutingConfig,
)


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

    def test_set_active_profile_called_after_create(
        self, runner: CliRunner
    ) -> None:
        """set_active_profile is called after a profile is created."""
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
        existing_config = Config(
            profile=ProfileConfig(name="onprem-profile"),
            auth=AuthConfig(api_key="existing-key"),
        )
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


# ---------------------------------------------------------------------------
# OAuth auth-method tests
# ---------------------------------------------------------------------------


def _fake_oauth_creds(email: str = "user@example.com") -> OAuthCredentials:
    return OAuthCredentials(
        access_token="arz_at_x",
        refresh_token="arz_rt_x",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        user_email=email,
    )


class TestProfilesCreateOAuth:
    """Tests for --auth-method oauth on the create command."""

    def test_auth_method_oauth_triggers_inline_login(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """--auth-method oauth calls perform_oauth_login and saves OAuth credentials."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(ConfigManager, "CONFIG_DIR", tmp_path / ".arize")
        monkeypatch.setattr(
            ConfigManager, "PROFILES_DIR", tmp_path / ".arize" / "profiles"
        )
        monkeypatch.setattr(
            ConfigManager,
            "ACTIVE_PROFILE_FILE",
            tmp_path / ".arize" / ".active_profile",
        )
        (tmp_path / ".arize" / "profiles").mkdir(parents=True, exist_ok=True)

        fake_creds = _fake_oauth_creds()

        with patch(
            "ax.commands.profiles.perform_oauth_login", return_value=fake_creds
        ) as mock_login:
            local_runner = CliRunner()
            result = local_runner.invoke(
                app,
                [
                    "create",
                    "my-oauth-profile",
                    "--auth-method",
                    "oauth",
                    "--region",
                    "eu-west-1a",
                ],
            )

        assert result.exit_code == 0, result.output
        mock_login.assert_called_once()
        call_url = (
            mock_login.call_args.kwargs.get("base_url")
            or mock_login.call_args.args[0]
        )
        assert call_url == "https://app.eu-west-1a.arize.com"

        loaded = ConfigManager.load("my-oauth-profile")
        assert loaded.auth.uses_oauth
        assert loaded.auth.oauth.access_token == "arz_at_x"
        assert loaded.routing.region == "eu-west-1a"

    def test_auth_method_oauth_default_routing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """--auth-method oauth with no routing flags uses the default app URL."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(ConfigManager, "CONFIG_DIR", tmp_path / ".arize")
        monkeypatch.setattr(
            ConfigManager, "PROFILES_DIR", tmp_path / ".arize" / "profiles"
        )
        monkeypatch.setattr(
            ConfigManager,
            "ACTIVE_PROFILE_FILE",
            tmp_path / ".arize" / ".active_profile",
        )
        (tmp_path / ".arize" / "profiles").mkdir(parents=True, exist_ok=True)

        fake_creds = _fake_oauth_creds()

        with patch(
            "ax.commands.profiles.perform_oauth_login", return_value=fake_creds
        ) as mock_login:
            local_runner = CliRunner()
            result = local_runner.invoke(
                app,
                ["create", "oauth-default", "--auth-method", "oauth"],
            )

        assert result.exit_code == 0, result.output
        mock_login.assert_called_once()
        call_url = (
            mock_login.call_args.kwargs.get("base_url")
            or mock_login.call_args.args[0]
        )
        assert call_url == "https://app.arize.com"

        loaded = ConfigManager.load("oauth-default")
        assert loaded.auth.uses_oauth
        assert loaded.auth.oauth.user_email == "user@example.com"

    def test_api_key_and_oauth_mutually_exclusive(
        self, runner: CliRunner
    ) -> None:
        """Passing both --auth-method oauth and --api-key exits non-zero."""
        result = runner.invoke(
            app,
            [
                "create",
                "p",
                "--auth-method",
                "oauth",
                "--api-key",
                "ak-xxx",
            ],
        )
        assert result.exit_code != 0

    def test_invalid_auth_method_exits_nonzero(self, runner: CliRunner) -> None:
        """An unrecognized --auth-method value exits with an error."""
        result = runner.invoke(
            app,
            ["create", "p", "--auth-method", "magic-link"],
        )
        assert result.exit_code != 0

    def test_oauth_profile_saved_with_single_host_routing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """--auth-method oauth with --single-host saves on-prem routing and uses correct URL."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(ConfigManager, "CONFIG_DIR", tmp_path / ".arize")
        monkeypatch.setattr(
            ConfigManager, "PROFILES_DIR", tmp_path / ".arize" / "profiles"
        )
        monkeypatch.setattr(
            ConfigManager,
            "ACTIVE_PROFILE_FILE",
            tmp_path / ".arize" / ".active_profile",
        )
        (tmp_path / ".arize" / "profiles").mkdir(parents=True, exist_ok=True)

        fake_creds = _fake_oauth_creds()

        with patch(
            "ax.commands.profiles.perform_oauth_login", return_value=fake_creds
        ) as mock_login:
            local_runner = CliRunner()
            result = local_runner.invoke(
                app,
                [
                    "create",
                    "onprem-oauth",
                    "--auth-method",
                    "oauth",
                    "--single-host",
                    "arize.mycompany.internal",
                ],
            )

        assert result.exit_code == 0, result.output
        mock_login.assert_called_once()
        call_url = (
            mock_login.call_args.kwargs.get("base_url")
            or mock_login.call_args.args[0]
        )
        assert call_url == "https://arize.mycompany.internal"

        loaded = ConfigManager.load("onprem-oauth")
        assert loaded.routing.single_host == "arize.mycompany.internal"
        assert loaded.auth.uses_oauth

    def test_oauth_with_single_host_flag(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """--auth-method oauth --single-host saves on-prem routing and derives correct login URL."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(ConfigManager, "CONFIG_DIR", tmp_path / ".arize")
        monkeypatch.setattr(
            ConfigManager, "PROFILES_DIR", tmp_path / ".arize" / "profiles"
        )
        monkeypatch.setattr(
            ConfigManager,
            "ACTIVE_PROFILE_FILE",
            tmp_path / ".arize" / ".active_profile",
        )
        (tmp_path / ".arize" / "profiles").mkdir(parents=True, exist_ok=True)

        fake_creds = _fake_oauth_creds()

        with patch(
            "ax.commands.profiles.perform_oauth_login", return_value=fake_creds
        ) as mock_login:
            local_runner = CliRunner()
            result = local_runner.invoke(
                app,
                [
                    "create",
                    "onprem-oauth",
                    "--auth-method",
                    "oauth",
                    "--single-host",
                    "arize.my-company.com",
                    "--single-port",
                    "443",
                ],
            )

        assert result.exit_code == 0, result.output
        mock_login.assert_called_once()
        called_url = (
            mock_login.call_args.kwargs.get("base_url")
            or mock_login.call_args.args[0]
        )
        assert urlparse(called_url).netloc == "arize.my-company.com:443"

        loaded = ConfigManager.load("onprem-oauth")
        assert loaded.routing.single_host == "arize.my-company.com"
        assert loaded.routing.region == ""
        assert loaded.auth.uses_oauth

    def test_oauth_interactive_supports_single_host(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Interactive OAuth profile creation must allow on-prem single_host routing via read_routing()."""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(ConfigManager, "CONFIG_DIR", tmp_path / ".arize")
        monkeypatch.setattr(
            ConfigManager, "PROFILES_DIR", tmp_path / ".arize" / "profiles"
        )
        monkeypatch.setattr(
            ConfigManager,
            "ACTIVE_PROFILE_FILE",
            tmp_path / ".arize" / ".active_profile",
        )
        (tmp_path / ".arize" / "profiles").mkdir(parents=True, exist_ok=True)

        fake_creds = _fake_oauth_creds()
        single_host_routing = RoutingConfig(
            single_host="arize.my-company.com", single_port="443"
        )

        from ax.config.schema import SecurityConfig, TransportConfig

        with (
            patch(
                "ax.commands.profiles.perform_oauth_login",
                return_value=fake_creds,
            ) as mock_login,
            patch(
                "ax.config.setup.read_routing",
                return_value=single_host_routing,
            ),
            patch(
                "ax.config.setup.read_transport",
                return_value=TransportConfig(),
            ),
            patch(
                "ax.config.setup.read_security",
                return_value=SecurityConfig(),
            ),
            patch("ax.config.setup.read_output_format", return_value="table"),
            patch("questionary.select") as mock_select,
        ):
            # Two questionary.select prompts: auth method, then Simple/Advanced
            # mode (Advanced is required to reach read_routing()).
            mock_select.return_value.ask.side_effect = ["oauth", "Advanced"]

            local_runner = CliRunner()
            result = local_runner.invoke(
                app,
                ["create", "onprem-oauth-interactive"],
            )

        assert result.exit_code == 0, result.output
        mock_login.assert_called_once()
        called_url = (
            mock_login.call_args.kwargs.get("base_url")
            or mock_login.call_args.args[0]
        )
        assert urlparse(called_url).netloc == "arize.my-company.com:443"

        loaded = ConfigManager.load("onprem-oauth-interactive")
        assert loaded.routing.single_host == "arize.my-company.com"
        assert loaded.routing.region == ""
        assert loaded.auth.uses_oauth
