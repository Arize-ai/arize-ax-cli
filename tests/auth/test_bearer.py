from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
import tomli_w
import tomllib

from ax.auth.bearer import get_active_bearer
from ax.auth.oauth_client import TokenResponse
from ax.config.schema import AuthConfig, OAuthCredentials
from ax.config.tls import TLSSettings
from ax.core.exceptions import ConfigError, MfaRequiredError


def _fresh_oauth() -> OAuthCredentials:
    return OAuthCredentials(
        access_token="arz_at_cur",
        refresh_token="arz_rt_cur",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        user_email="user@example.com",
    )


def _expiring_oauth() -> OAuthCredentials:
    return OAuthCredentials(
        access_token="arz_at_cur",
        refresh_token="arz_rt_cur",
        expires_at=datetime.now(timezone.utc)
        + timedelta(seconds=30),  # within 60s
        user_email="user@example.com",
    )


def _write_profile(p: Path, oauth: OAuthCredentials) -> None:
    data = {
        "auth": {
            "oauth": {
                "access_token": oauth.access_token,
                "refresh_token": oauth.refresh_token,
                "expires_at": oauth.expires_at,
                "user_email": oauth.user_email,
            }
        }
    }
    with p.open("wb") as f:
        tomli_w.dump(data, f)


class TestGetActiveBearer:
    def test_mfa_refresh_clears_tokens_and_preserves_profile(
        self, tmp_path: Path
    ):
        profile_path = tmp_path / "p.toml"
        oauth = _expiring_oauth()
        _write_profile(profile_path, oauth)
        with profile_path.open("rb") as f:
            data = tomllib.load(f)
        data["profile"] = {"name": "test-profile"}
        data["api"] = {"base_url": "https://api.arize.com"}
        with profile_path.open("wb") as f:
            tomli_w.dump(data, f)
        with patch("ax.auth.bearer.OAuthClient") as client:
            client.return_value.refresh.side_effect = MfaRequiredError(
                "Run 'ax auth login' to sign in again."
            )
            with pytest.raises(MfaRequiredError, match="ax auth login"):
                get_active_bearer(
                    AuthConfig(oauth=oauth),
                    profile_path=profile_path,
                    base_url="https://app.arize.com",
                )
        with profile_path.open("rb") as f:
            saved = tomllib.load(f)
        assert saved["profile"] == data["profile"]
        assert saved["api"] == data["api"]
        assert saved["auth"] == {"auth_method": "oauth"}
        with pytest.raises(ConfigError, match="ax auth login"):
            get_active_bearer(
                AuthConfig(**saved["auth"]),
                profile_path=profile_path,
                base_url="https://app.arize.com",
            )

    def test_temporary_refresh_failure_keeps_tokens(self, tmp_path: Path):
        profile_path = tmp_path / "p.toml"
        oauth = _expiring_oauth()
        _write_profile(profile_path, oauth)
        before = profile_path.read_bytes()
        with patch("ax.auth.bearer.OAuthClient") as client:
            client.return_value.refresh.side_effect = requests.HTTPError(
                "HTTP 503"
            )
            with pytest.raises(requests.HTTPError):
                get_active_bearer(
                    AuthConfig(oauth=oauth),
                    profile_path=profile_path,
                    base_url="https://app.arize.com",
                )
        assert profile_path.read_bytes() == before

    def test_api_key_returns_api_key(self, tmp_path: Path):
        cfg = AuthConfig(api_key="ak-abc")
        assert (
            get_active_bearer(
                cfg,
                profile_path=tmp_path / "p.toml",
                base_url="https://app.arize.com",
            )
            == "ak-abc"
        )

    def test_fresh_oauth_returns_access_token_unchanged(self, tmp_path: Path):
        cfg = AuthConfig(oauth=_fresh_oauth())
        bearer = get_active_bearer(
            cfg,
            profile_path=tmp_path / "p.toml",
            base_url="https://app.arize.com",
        )
        assert bearer == "arz_at_cur"

    def test_near_expiry_triggers_refresh(self, tmp_path: Path):
        profile_path = tmp_path / "p.toml"
        _write_profile(profile_path, _expiring_oauth())
        cfg = AuthConfig(oauth=_expiring_oauth())

        with patch("ax.auth.bearer.OAuthClient") as ClientCls:
            inst = ClientCls.return_value
            inst.refresh.return_value = TokenResponse(
                access_token="arz_at_new",
                refresh_token="arz_rt_new",
                expires_in=3600,
            )
            bearer = get_active_bearer(
                cfg, profile_path=profile_path, base_url="https://app.arize.com"
            )
        assert bearer == "arz_at_new"
        inst.refresh.assert_called_once_with(refresh_token="arz_rt_cur")

    def test_refresh_persists_new_tokens_to_file(self, tmp_path: Path):
        profile_path = tmp_path / "p.toml"
        _write_profile(profile_path, _expiring_oauth())
        cfg = AuthConfig(oauth=_expiring_oauth())

        with patch("ax.auth.bearer.OAuthClient") as ClientCls:
            ClientCls.return_value.refresh.return_value = TokenResponse(
                access_token="arz_at_new",
                refresh_token="arz_rt_new",
                expires_in=3600,
            )
            get_active_bearer(
                cfg, profile_path=profile_path, base_url="https://app.arize.com"
            )

        import tomllib

        with profile_path.open("rb") as f:
            data = tomllib.load(f)
        assert data["auth"]["oauth"]["access_token"] == "arz_at_new"
        assert data["auth"]["oauth"]["refresh_token"] == "arz_rt_new"

    def test_concurrent_refresh_sees_updated_disk_state(self, tmp_path: Path):
        """If a concurrent process just refreshed, the second caller should
        return the new access_token from disk without issuing its own refresh.
        """
        profile_path = tmp_path / "p.toml"
        # Write a "fresh" profile to disk (another process already refreshed)
        fresh = _fresh_oauth()
        _write_profile(profile_path, fresh)

        # But our in-memory cfg still has the stale, near-expiry version
        stale_cfg = AuthConfig(oauth=_expiring_oauth())

        with patch("ax.auth.bearer.OAuthClient") as ClientCls:
            bearer = get_active_bearer(
                stale_cfg,
                profile_path=profile_path,
                base_url="https://app.arize.com",
            )

        # Should have picked up the fresh token from disk, NOT called refresh
        assert bearer == fresh.access_token
        ClientCls.return_value.refresh.assert_not_called()


class TestRefreshPresentsClientCertificate:
    def test_refresh_client_uses_given_tls(self, tmp_path: Path):
        profile_path = tmp_path / "p.toml"
        _write_profile(profile_path, _expiring_oauth())
        tls = TLSSettings(verify="/ca.pem", cert=("/c.crt", "/c.key"))

        with patch("ax.auth.bearer.OAuthClient") as ClientCls:
            ClientCls.return_value.refresh.return_value = TokenResponse(
                access_token="arz_at_new",
                refresh_token="arz_rt_new",
                expires_in=3600,
            )
            get_active_bearer(
                AuthConfig(oauth=_expiring_oauth()),
                profile_path=profile_path,
                base_url="https://app.arize.com",
                tls=tls,
            )
        assert ClientCls.call_args.kwargs["tls"] == tls
