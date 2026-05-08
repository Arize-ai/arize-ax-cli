from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from ax.auth.auth_guards import require_api_key_auth
from ax.config.manager import ConfigManager
from ax.config.schema import (
    AuthConfig,
    Config,
    OAuthCredentials,
    ProfileConfig,
)

runner = CliRunner()


def _oauth_config(name: str = "p1") -> Config:
    return Config(
        profile=ProfileConfig(name=name),
        auth=AuthConfig(
            oauth=OAuthCredentials(
                access_token="arz_at_x",
                refresh_token="arz_rt_x",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                user_email="user@example.com",
            )
        ),
    )


def _api_key_config(name: str = "p1") -> Config:
    return Config(
        profile=ProfileConfig(name=name),
        auth=AuthConfig(
            api_key="ak-00000000-0000-0000-0000-000000000000-AAAAA"
        ),
    )


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path: Path, monkeypatch):
    """Same fixture as used in test_auth_commands — monkeypatch class attrs so
    ConfigManager uses the tmp_path.
    """
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
    yield


def _build_test_app() -> typer.Typer:
    """Build a tiny Typer app with a single decorated command, for isolated testing."""
    app = typer.Typer()

    @app.command()
    @require_api_key_auth("--all")
    def export(
        use_all: bool = typer.Option(False, "--all"),
    ) -> None:
        typer.echo(f"ran use_all={use_all}")

    return app


class TestRequireApiKeyAuth:
    def test_blocks_all_flag_under_oauth(self):
        ConfigManager.save(_oauth_config(), "p1")
        ConfigManager.set_active_profile("p1")
        result = runner.invoke(_build_test_app(), ["--all"])
        assert result.exit_code == 2
        assert "API key" in result.stdout
        assert "ran " not in result.stdout  # body never ran

    def test_allows_all_flag_under_api_key(self):
        ConfigManager.save(_api_key_config(), "p1")
        ConfigManager.set_active_profile("p1")
        result = runner.invoke(_build_test_app(), ["--all"])
        assert result.exit_code == 0
        assert "ran use_all=True" in result.stdout

    def test_passthrough_without_all_flag_on_oauth(self):
        ConfigManager.save(_oauth_config(), "p1")
        ConfigManager.set_active_profile("p1")
        result = runner.invoke(_build_test_app(), [])
        assert result.exit_code == 0
        assert "ran use_all=False" in result.stdout

    def test_passthrough_without_all_flag_on_api_key(self):
        ConfigManager.save(_api_key_config(), "p1")
        ConfigManager.set_active_profile("p1")
        result = runner.invoke(_build_test_app(), [])
        assert result.exit_code == 0
        assert "ran use_all=False" in result.stdout

    def test_missing_profile_falls_through_to_underlying_command(self):
        """If the profile can't be loaded, the decorator shouldn't mask the error."""
        # No profile saved at all
        result = runner.invoke(_build_test_app(), ["--all"])
        # Decorator's job is to gate OAuth, not mask missing-profile errors:
        # body must run successfully, exit 0.
        assert result.exit_code == 0, result.stdout
        assert "ran use_all=True" in result.stdout
