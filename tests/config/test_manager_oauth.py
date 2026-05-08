"""Tests for ConfigManager OAuth profile round-trip and env-var skip."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from ax.config.manager import ConfigManager
from ax.config.schema import (
    AuthConfig,
    Config,
    OAuthCredentials,
    ProfileConfig,
)


def _oauth_config(
    email: str = "user@example.com",
    expires_at: datetime | None = None,
    name: str = "test-profile",
) -> Config:
    return Config(
        profile=ProfileConfig(name=name),
        auth=AuthConfig(
            oauth=OAuthCredentials(
                access_token="arz_at_abc",
                refresh_token="arz_rt_abc",
                expires_at=expires_at
                or datetime(2099, 1, 1, tzinfo=timezone.utc),
                user_email=email,
            )
        ),
    )


def test_oauth_profile_roundtrip(mock_config_dir: Path) -> None:
    """Save an OAuth profile then load it back — all fields must survive."""
    expires = datetime(2099, 1, 1, tzinfo=timezone.utc)
    cfg = _oauth_config(expires_at=expires)

    ConfigManager.save(cfg, profile="test-profile")
    loaded = ConfigManager.load("test-profile", expand_env_vars=True)

    assert loaded.auth.uses_oauth is True
    assert loaded.auth.oauth is not None
    assert loaded.auth.oauth.access_token == "arz_at_abc"
    assert loaded.auth.oauth.refresh_token == "arz_rt_abc"
    assert loaded.auth.oauth.user_email == "user@example.com"
    # expires_at must round-trip; accept naive UTC or aware UTC equality
    loaded_exp = loaded.auth.oauth.expires_at
    if loaded_exp.tzinfo is None:
        loaded_exp = loaded_exp.replace(tzinfo=timezone.utc)
    assert loaded_exp == expires


def test_api_key_profile_still_expands_env_vars(
    mock_config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The api_key env-expansion path must keep working — regression guard."""
    monkeypatch.setenv("MY_API_KEY", "ak-from-env")

    # Write a profile TOML by hand that uses a ${...} reference
    profile_dir = ConfigManager.PROFILES_DIR
    (profile_dir / "env-ref.toml").write_text(
        '[profile]\nname = "env-ref"\n\n[auth]\napi_key = "${MY_API_KEY}"\n'
    )

    loaded = ConfigManager.load("env-ref", expand_env_vars=True)
    assert loaded.auth.api_key == "ak-from-env"
