from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import tomllib
from typer.testing import CliRunner

from ax.commands.auth import app
from ax.config.manager import ConfigManager
from ax.config.schema import (
    AuthConfig,
    Config,
    OAuthCredentials,
    ProfileConfig,
    RoutingConfig,
    SecurityConfig,
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


def _tls_files(tmp_path: Path) -> dict[str, str]:
    cert = tmp_path / "client.crt"
    key = tmp_path / "client.key"
    ca = tmp_path / "ca.pem"
    cert.write_text("cert")
    key.write_text("key")
    key.chmod(0o600)
    ca.write_text("ca")
    return {
        "client_cert": str(cert),
        "client_key": str(key),
        "ssl_ca_cert": str(ca),
    }


class TestClientCertificate:
    def test_login_presents_profile_cert(self, tmp_path: Path):
        files = _tls_files(tmp_path)
        cfg = _logged_out_oauth_config().model_copy(
            update={"security": SecurityConfig(**files)}
        )
        ConfigManager.save(cfg, "p1")
        ConfigManager.set_active_profile("p1")
        with (
            patch("ax.commands.auth.webbrowser.open"),
            patch("ax.commands.auth.LoopbackServer") as srv_cls,
            patch("ax.commands.auth.OAuthClient") as client_cls,
        ):
            srv_cls.return_value.port = 1234
            srv_cls.return_value.wait.return_value = MagicMock(
                code="c", state="s"
            )
            client_cls.return_value.exchange_code.return_value = MagicMock(
                access_token="new",
                refresh_token="new",
                expires_in=3600,
                user_email="user@example.com",
            )
            result = runner.invoke(app, ["login"])
        assert result.exit_code == 0, result.stdout
        tls = client_cls.call_args.kwargs["tls"]
        assert tls.cert == (files["client_cert"], files["client_key"])
        assert tls.verify == files["ssl_ca_cert"]

    def test_login_with_half_a_pair_fails_before_browser(self, tmp_path: Path):
        files = _tls_files(tmp_path)
        cfg = _logged_out_oauth_config().model_copy(
            update={
                "security": SecurityConfig(client_cert=files["client_cert"])
            }
        )
        ConfigManager.save(cfg, "p1")
        ConfigManager.set_active_profile("p1")
        with patch("ax.commands.auth.webbrowser.open") as wb:
            result = runner.invoke(app, ["login"])
        assert result.exit_code == 1
        assert "must be set together" in result.output
        assert "Unexpected error" not in result.output
        wb.assert_not_called()

    def test_logout_with_broken_cert_config_still_clears_profile(
        self, tmp_path: Path
    ):
        files = _tls_files(tmp_path)
        cfg = _oauth_config().model_copy(
            update={
                "security": SecurityConfig(client_cert=files["client_cert"])
            }
        )
        ConfigManager.save(cfg, "p1")
        ConfigManager.set_active_profile("p1")
        with patch("ax.commands.auth.OAuthClient") as client_cls:
            result = runner.invoke(app, ["logout"])
        assert result.exit_code == 0, result.output
        output = " ".join(result.output.split())
        assert "client certificate settings are invalid" in output
        assert "Local credentials are cleared." in output
        client_cls.assert_not_called()
        assert ConfigManager.load("p1").auth.oauth is None

    def test_logout_revokes_with_profile_cert(self, tmp_path: Path):
        files = _tls_files(tmp_path)
        cfg = _oauth_config().model_copy(
            update={"security": SecurityConfig(**files)}
        )
        ConfigManager.save(cfg, "p1")
        ConfigManager.set_active_profile("p1")
        with patch("ax.commands.auth.OAuthClient") as client_cls:
            result = runner.invoke(app, ["logout"])
        assert result.exit_code == 0, result.stdout
        tls = client_cls.call_args.kwargs["tls"]
        assert tls.cert == (files["client_cert"], files["client_key"])


@pytest.mark.parametrize("region", ["us-east-1b", "us-east-1"])
def test_login_rejects_aws_environment_before_browser(
    monkeypatch: pytest.MonkeyPatch, region: str
) -> None:
    config = _logged_out_oauth_config()
    config.routing = RoutingConfig(region="${ARIZE_REGION}")
    ConfigManager.save(config, "p1")
    ConfigManager.set_active_profile("p1")
    monkeypatch.setenv("ARIZE_REGION", region)
    with patch("ax.commands.auth.perform_oauth_login") as login:
        result = runner.invoke(app, ["login"])
    assert result.exit_code == 1, result.output
    assert "Unexpected error" not in result.output
    login.assert_not_called()


def test_login_resolves_us_environment_and_preserves_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _logged_out_oauth_config()
    config.routing = RoutingConfig(region="${ARIZE_REGION}")
    ConfigManager.save(config, "p1")
    ConfigManager.set_active_profile("p1")
    monkeypatch.setenv("ARIZE_REGION", "US")
    with patch("ax.commands.auth.perform_oauth_login") as login:
        login.return_value = _oauth_config().auth.oauth
        result = runner.invoke(app, ["login"])
    assert result.exit_code == 0, result.output
    assert login.call_args.kwargs["base_url"] == "https://app.arize.com"
    saved = ConfigManager.load("p1", expand_env_vars=False)
    assert saved.routing.region == "${ARIZE_REGION}"


@pytest.mark.parametrize("region", [None, "us-east-1b", "us-east-1"])
def test_logout_clears_tokens_when_environment_routing_is_invalid(
    monkeypatch: pytest.MonkeyPatch, region: str | None
) -> None:
    config = _oauth_config()
    config.routing = RoutingConfig(region="${ARIZE_REGION}")
    ConfigManager.save(config, "p1")
    ConfigManager.set_active_profile("p1")
    if region is None:
        monkeypatch.delenv("ARIZE_REGION", raising=False)
    else:
        monkeypatch.setenv("ARIZE_REGION", region)
    with patch("ax.commands.auth.OAuthClient") as client:
        result = runner.invoke(app, ["logout"])
    assert result.exit_code == 0, result.output
    assert "Remote tokens were not revoked" in result.output
    client.assert_not_called()
    saved = ConfigManager.load("p1", expand_env_vars=False)
    assert saved.auth.oauth is None
    assert saved.routing.region == "${ARIZE_REGION}"


@pytest.mark.parametrize("region", ["us-east-1b", "us-east-1"])
def test_logout_clears_literal_invalid_region_profile(
    region: str,
) -> None:
    config = _oauth_config()
    config.routing = RoutingConfig(region="US")
    ConfigManager.save(config, "p1")
    ConfigManager.set_active_profile("p1")
    path = ConfigManager.profile_path("p1")
    path.write_text(path.read_text().replace("us-central-1a", region))
    original = tomllib.loads(path.read_text())
    with patch("ax.commands.auth.OAuthClient") as client:
        result = runner.invoke(app, ["logout"])
    assert result.exit_code == 0, result.output
    assert "Remote tokens were not revoked" in result.output
    client.assert_not_called()
    expected = original
    del expected["auth"]["oauth"]
    assert tomllib.loads(path.read_text()) == expected
    assert ConfigManager.get_active_profile() == "p1"
