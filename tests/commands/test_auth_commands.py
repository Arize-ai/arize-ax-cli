from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from typer.testing import CliRunner

from ax.commands.auth import app
from ax.config.manager import ConfigManager
from ax.config.schema import (
    AuthConfig,
    Config,
    OAuthCredentials,
    ProfileConfig,
    RoutingConfig,
)

runner = CliRunner()


def _oauth_config(email: str = "user@example.com", name: str = "p1") -> Config:
    """OAuth profile with valid (non-expired) tokens — i.e. signed in."""
    return Config(
        profile=ProfileConfig(name=name),
        auth=AuthConfig(
            oauth=OAuthCredentials(
                access_token="arz_at_x",
                refresh_token="arz_rt_x",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                user_email=email,
            )
        ),
    )


def _logged_out_oauth_config(name: str = "p1") -> Config:
    """OAuth profile with cleared tokens — the post-logout state. This is
    the typical state for `ax auth login` because already-signed-in profiles
    short-circuit with 'You are already logged in'.
    """
    return Config(
        profile=ProfileConfig(name=name),
        auth=AuthConfig(auth_method="oauth"),
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
    monkeypatch.setenv("HOME", str(tmp_path))
    # Re-evaluate class-level paths that were already computed from Path.home()
    monkeypatch.setattr(ConfigManager, "CONFIG_DIR", tmp_path / ".arize")
    monkeypatch.setattr(
        ConfigManager, "PROFILES_DIR", tmp_path / ".arize" / "profiles"
    )
    monkeypatch.setattr(
        ConfigManager,
        "ACTIVE_PROFILE_FILE",
        tmp_path / ".arize" / ".active_profile",
    )
    yield


class TestLogin:
    def test_forwards_hidden_utm_params_to_oauth_authorize_url(self):
        ConfigManager.save(_logged_out_oauth_config(), "p1")
        ConfigManager.set_active_profile("p1")
        captured_url: dict[str, str] = {}

        def _capture_open(url):
            captured_url["url"] = url

        with (
            patch(
                "ax.commands.auth.webbrowser.open", side_effect=_capture_open
            ),
            patch("ax.commands.auth.LoopbackServer") as srv_cls,
            patch("ax.commands.auth.OAuthClient") as client_cls,
        ):
            srv = srv_cls.return_value
            srv.port = 53682
            srv.wait.return_value = MagicMock(code="the-code", state="state")
            client_cls.return_value.exchange_code.return_value = MagicMock(
                access_token="arz_at_new",
                refresh_token="arz_rt_new",
                expires_in=3600,
                user_email="user@example.com",
            )
            result = runner.invoke(
                app,
                [
                    "login",
                    "--utm-params",
                    "utm_source=ax&utm_medium=cli&utm_campaign=signup&utm_content=cli&unknown=drop",
                ],
            )

        assert result.exit_code == 0, result.stdout
        query = parse_qs(urlparse(captured_url["url"]).query)
        assert query["utm_source"] == ["ax"]
        assert query["utm_medium"] == ["cli"]
        assert query["utm_campaign"] == ["signup"]
        assert query["utm_content"] == ["cli"]
        assert "unknown" not in query

    def test_hides_utm_params_from_login_help(self):
        result = runner.invoke(app, ["login", "--help"])

        assert result.exit_code == 0, result.stdout
        assert "--utm-params" not in result.stdout

    def test_runs_full_flow_on_active_oauth_profile(self):
        # Logged-out OAuth profile — `ax auth login` should run the browser flow.
        ConfigManager.save(_logged_out_oauth_config(), "p1")
        ConfigManager.set_active_profile("p1")
        with (
            patch("ax.commands.auth.webbrowser.open"),
            patch("ax.commands.auth.LoopbackServer") as srv_cls,
            patch("ax.commands.auth.OAuthClient") as client_cls,
        ):
            srv = srv_cls.return_value
            srv.port = 53682
            srv.wait.return_value = MagicMock(
                code="the-code", state="state-xyz"
            )
            client_cls.return_value.exchange_code.return_value = MagicMock(
                access_token="arz_at_new",
                refresh_token="arz_rt_new",
                expires_in=3600,
                user_email="user@example.com",
            )
            result = runner.invoke(app, ["login"])
        assert result.exit_code == 0, result.stdout
        loaded = ConfigManager.load("p1")
        assert loaded.auth.uses_oauth
        assert loaded.auth.oauth.user_email == "user@example.com"
        assert loaded.auth.oauth.access_token == "arz_at_new"

    def test_skips_when_already_logged_in(self):
        # Pre-existing OAuth profile with non-expired tokens → no browser flow.
        ConfigManager.save(_oauth_config("user@example.com"), "p1")
        ConfigManager.set_active_profile("p1")
        with (
            patch("ax.commands.auth.webbrowser.open") as wb,
            patch("ax.commands.auth.LoopbackServer") as srv_cls,
            patch("ax.commands.auth.OAuthClient") as client_cls,
        ):
            result = runner.invoke(app, ["login"])
        assert result.exit_code == 0, result.stdout
        assert "already logged in" in result.stdout
        assert "user@example.com" in result.stdout
        wb.assert_not_called()
        srv_cls.assert_not_called()
        client_cls.assert_not_called()

    def test_runs_when_access_token_expired(self):
        # Same shape as _oauth_config but with expires_at in the past.
        cfg = Config(
            profile=ProfileConfig(name="p1"),
            auth=AuthConfig(
                oauth=OAuthCredentials(
                    access_token="old",
                    refresh_token="old",
                    expires_at=datetime.now(timezone.utc)
                    - timedelta(minutes=5),
                    user_email="user@example.com",
                )
            ),
        )
        ConfigManager.save(cfg, "p1")
        ConfigManager.set_active_profile("p1")
        with (
            patch("ax.commands.auth.webbrowser.open"),
            patch("ax.commands.auth.LoopbackServer") as srv_cls,
            patch("ax.commands.auth.OAuthClient") as client_cls,
        ):
            srv = srv_cls.return_value
            srv.port = 1234
            srv.wait.return_value = MagicMock(code="c", state="s")
            client_cls.return_value.exchange_code.return_value = MagicMock(
                access_token="new",
                refresh_token="new",
                expires_in=3600,
                user_email="user@example.com",
            )
            result = runner.invoke(app, ["login"])
        assert result.exit_code == 0, result.stdout
        loaded = ConfigManager.load("p1")
        assert loaded.auth.oauth.access_token == "new"

    def test_login_errors_when_no_active_profile(self):
        result = runner.invoke(app, ["login"])
        assert result.exit_code == 1, result.output
        assert "No active profile" in result.output

    def test_login_errors_when_active_profile_is_api_key(self):
        ConfigManager.save(_api_key_config(), "p1")
        ConfigManager.set_active_profile("p1")
        result = runner.invoke(app, ["login"])
        assert result.exit_code == 1
        assert "API-key authentication" in result.stdout

    def test_login_rejects_profile_flag(self):
        # --profile is intentionally not exposed.
        ConfigManager.save(_oauth_config(), "p1")
        ConfigManager.set_active_profile("p1")
        result = runner.invoke(app, ["login", "--profile", "other"])
        assert result.exit_code != 0


class TestLoginRouting:
    def test_login_uses_profile_routing_for_base_url(self):
        # Logged-out OAuth profile with explicit app_host override; the login
        # flow must resolve its base URL from this routing config.
        cfg = Config(
            profile=ProfileConfig(name="staging"),
            auth=AuthConfig(auth_method="oauth"),
            routing=RoutingConfig(app_host="app.staging.arize.com"),
        )
        ConfigManager.save(cfg, "staging")
        ConfigManager.set_active_profile("staging")

        captured_url = {}

        def _capture_open(url):
            captured_url["url"] = url

        with (
            patch(
                "ax.commands.auth.webbrowser.open", side_effect=_capture_open
            ),
            patch("ax.commands.auth.LoopbackServer") as srv_cls,
            patch("ax.commands.auth.OAuthClient") as client_cls,
        ):
            srv = srv_cls.return_value
            srv.port = 53682
            srv.wait.return_value = MagicMock(code="c", state="s")
            client_cls.return_value.exchange_code.return_value = MagicMock(
                access_token="a",
                refresh_token="r",
                expires_in=3600,
                user_email="k@x.com",
            )
            result = runner.invoke(app, ["login"])

        assert result.exit_code == 0, result.stdout
        assert urlparse(captured_url["url"]).netloc == "app.staging.arize.com"
        # And the OAuthClient was constructed with the resolved URL, not the default
        construct_kwargs = client_cls.call_args.kwargs
        assert construct_kwargs["base_url"] == "https://app.staging.arize.com"


class TestLogout:
    def test_revokes_both_tokens_and_clears(self):
        ConfigManager.save(_oauth_config(), "p1")
        ConfigManager.set_active_profile("p1")
        with patch("ax.commands.auth.OAuthClient") as client_cls:
            result = runner.invoke(app, ["logout"])
        assert result.exit_code == 0, result.stdout
        # Both tokens must be revoked server-side, otherwise a copy of the
        # [auth.oauth] block could be re-pasted and the access token would
        # still work for up to 1h.
        revoke_calls = client_cls.return_value.revoke.call_args_list
        assert len(revoke_calls) == 2, revoke_calls
        revoked_tokens = {c.kwargs["token"] for c in revoke_calls}
        assert revoked_tokens == {"arz_at_x", "arz_rt_x"}
        # Profile is preserved but credentials are cleared.
        cleared = ConfigManager.load("p1", expand_env_vars=False)
        assert cleared.auth.is_logged_out
        assert cleared.auth.oauth is None
        assert cleared.auth.api_key is None

    def test_errors_on_api_key_profile(self):
        ConfigManager.save(_api_key_config(), "p1")
        ConfigManager.set_active_profile("p1")
        with patch("ax.commands.auth.OAuthClient") as client_cls:
            result = runner.invoke(app, ["logout"])
        # API-key profiles can't be logged out — must create a new profile.
        assert result.exit_code == 1, result.stdout
        assert "API-key authentication" in result.stdout
        client_cls.return_value.revoke.assert_not_called()
        # Profile is left untouched.
        assert ConfigManager.load("p1").auth.api_key is not None

    def test_noop_when_already_logged_out(self):
        # OAuth profile already cleared — logout should be a friendly no-op.
        from ax.config.schema import AuthConfig as _Auth

        cfg = Config(
            profile=ProfileConfig(name="p1"),
            auth=_Auth(auth_method="oauth"),
        )
        ConfigManager.save(cfg, "p1")
        ConfigManager.set_active_profile("p1")
        with patch("ax.commands.auth.OAuthClient") as client_cls:
            result = runner.invoke(app, ["logout"])
        assert result.exit_code == 0
        assert "already logged out" in result.stdout
        client_cls.return_value.revoke.assert_not_called()
