"""Tests for AuthConfig and OAuthCredentials schema models."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from ax.config.schema import AuthConfig, OAuthCredentials


def _oauth(**overrides: object) -> OAuthCredentials:
    defaults: dict[str, object] = {
        "access_token": "arz_at_abc",
        "refresh_token": "arz_rt_abc",
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "user_email": "user@example.com",
    }
    defaults.update(overrides)
    return OAuthCredentials(**defaults)


class TestAuthConfig:
    def test_api_key_only_is_valid(self) -> None:
        cfg = AuthConfig(
            api_key="ak-00000000-0000-0000-0000-000000000000-AAAAA"
        )
        assert cfg.auth_method == "api-key"
        assert cfg.api_key.startswith("ak-")
        assert cfg.oauth is None
        assert not cfg.uses_oauth
        assert not cfg.is_logged_out

    def test_oauth_signed_in_is_valid(self) -> None:
        cfg = AuthConfig(oauth=_oauth())
        assert cfg.auth_method == "oauth"
        assert cfg.api_key is None
        assert cfg.oauth is not None
        assert cfg.uses_oauth
        assert not cfg.is_logged_out
        assert cfg.oauth.user_email == "user@example.com"

    def test_oauth_logged_out_is_valid(self) -> None:
        # OAuth profiles can have oauth=None (after `ax logout`); the profile
        # remembers its auth_method so re-login is one command.
        cfg = AuthConfig(auth_method="oauth")
        assert cfg.auth_method == "oauth"
        assert cfg.uses_oauth
        assert cfg.is_logged_out
        assert cfg.api_key is None
        assert cfg.oauth is None

    def test_api_key_method_requires_api_key(self) -> None:
        with pytest.raises(ValidationError, match="non-empty api_key"):
            AuthConfig(auth_method="api-key")

    def test_api_key_method_forbids_oauth(self) -> None:
        with pytest.raises(ValidationError, match="must not have an oauth"):
            AuthConfig(auth_method="api-key", api_key="ak-xxx", oauth=_oauth())

    def test_oauth_method_forbids_api_key(self) -> None:
        with pytest.raises(ValidationError, match="must not have an api_key"):
            AuthConfig(auth_method="oauth", api_key="ak-xxx")

    def test_legacy_profile_with_only_api_key_infers_method(self) -> None:
        # Backwards-compat: profile written before auth_method existed
        cfg = AuthConfig(api_key="ak-xxx")
        assert cfg.auth_method == "api-key"

    def test_legacy_profile_with_only_oauth_infers_method(self) -> None:
        cfg = AuthConfig(oauth=_oauth())
        assert cfg.auth_method == "oauth"

    def test_empty_oauth_access_token_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AuthConfig(oauth=_oauth(access_token=""))

    def test_api_key_whitespace_stripped(self) -> None:
        cfg = AuthConfig(api_key="  ak-abc  ")
        assert cfg.api_key == "ak-abc"

    def test_empty_api_key_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AuthConfig(api_key="   ")
