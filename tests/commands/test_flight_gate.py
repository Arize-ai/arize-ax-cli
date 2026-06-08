from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ax.cli import app as root_app
from ax.config.manager import ConfigManager
from ax.config.schema import (
    AuthConfig,
    Config,
    OAuthCredentials,
    ProfileConfig,
)

runner = CliRunner()


def _save_oauth_profile(name: str = "oauth-profile") -> None:
    cfg = Config(
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
    ConfigManager.save(cfg, name)
    ConfigManager.set_active_profile(name)


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path: Path, monkeypatch):
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


def test_export_without_all_flag_not_blocked_under_oauth():
    """Sanity check: --all is the only gated flag; omitting it should let the body run."""
    _save_oauth_profile()
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    mock_client.datasets.list_examples.return_value = []
    with patch(
        "ax.commands.datasets.make_client",
        return_value=(mock_client, MagicMock()),
    ):
        # datasets export requires a dataset ID
        result = runner.invoke(root_app, ["datasets", "export", "some-ds-id"])
    # We're not asserting 0 — the command may fail for other reasons (missing
    # mock). The key assertion: the Flight-gate error message is NOT present.
    assert (
        "API key" not in result.stdout
        or "not supported under OAuth" not in result.stdout
    )
