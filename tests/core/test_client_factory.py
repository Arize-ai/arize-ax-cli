"""Tests for building the authenticated SDK client."""

from pathlib import Path
from unittest.mock import patch

import pytest

from ax.config.manager import ConfigManager
from ax.config.schema import (
    AuthConfig,
    AuthMethod,
    Config,
    ProfileConfig,
    RoutingConfig,
    SecurityConfig,
)
from ax.core.client_factory import make_client
from ax.core.exceptions import ConfigError


def _config(security: SecurityConfig) -> Config:
    return Config(
        profile=ProfileConfig(name="p1"),
        auth=AuthConfig(api_key="ak-test123"),
        security=security,
    )


@pytest.mark.unit
class TestMakeClientClientCertificate:
    def test_sdk_client_and_token_refresh_both_get_cert(self, tmp_path: Path):
        cert = tmp_path / "client.crt"
        key = tmp_path / "client.key"
        cert.write_text("cert")
        key.write_text("key")
        key.chmod(0o600)
        config = _config(
            SecurityConfig(client_cert=str(cert), client_key=str(key))
        )
        with (
            patch(
                "ax.core.client_factory.ConfigManager.load",
                return_value=config,
            ),
            patch(
                "ax.core.client_factory.get_active_bearer",
                return_value="ak-test123",
            ) as bearer,
            patch("ax.core.client_factory.ArizeClient") as client_cls,
        ):
            make_client()

        kwargs = client_cls.call_args.kwargs
        assert kwargs["client_cert"] == str(cert)
        assert kwargs["client_key"] == str(key)
        assert bearer.call_args.kwargs["tls"].cert == (str(cert), str(key))

    def test_half_a_pair_raises_config_error(self, tmp_path: Path):
        cert = tmp_path / "client.crt"
        cert.write_text("cert")
        config = _config(SecurityConfig(client_cert=str(cert)))
        with (
            patch(
                "ax.core.client_factory.ConfigManager.load",
                return_value=config,
            ),
            patch("ax.core.client_factory.ArizeClient") as client_cls,
            pytest.raises(ConfigError, match="must be set together"),
        ):
            make_client()
        client_cls.assert_not_called()


@pytest.mark.parametrize(
    ("routing", "app_url", "api_host"),
    [
        (
            {"region": "${AX_TEST_REGION}"},
            "https://app.arize.com",
            "api.us-central-1a.arize.com",
        ),
        (
            {"region": "EU"},
            "https://app.eu-west-1a.arize.com",
            "api.eu-west-1a.arize.com",
        ),
        (
            {"region": "CA"},
            "https://app.ca-central-1a.arize.com",
            "api.ca-central-1a.arize.com",
        ),
        (
            {
                "single_host": "onprem.local",
                "single_port": "8443",
                "app_scheme": "http",
            },
            "http://onprem.local:8443",
            "onprem.local",
        ),
        (
            {"base_domain": "private.example.com"},
            "https://app.private.example.com",
            "api.private.example.com",
        ),
    ],
)
def test_client_factory_uses_account_routing(
    mock_config_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    routing: dict[str, str],
    app_url: str,
    api_host: str,
) -> None:
    monkeypatch.setenv("AX_TEST_REGION", "US")
    config = Config(
        profile=ProfileConfig(name="test"),
        auth=AuthConfig(auth_method=AuthMethod.OAUTH),
        routing=RoutingConfig(**routing),
    )
    ConfigManager.save(config, "test")
    ConfigManager.set_active_profile("test")
    with (
        patch(
            "ax.core.client_factory.get_active_bearer",
            return_value="test-token",
        ) as bearer,
        patch("ax.core.client_factory.ArizeClient") as sdk,
    ):
        client, _ = make_client()
    assert client is sdk.return_value
    assert bearer.call_args.kwargs["base_url"] == app_url
    assert sdk.call_args.kwargs["api_host"] == api_host
    assert ConfigManager.load("test", expand_env_vars=False).routing.model_dump(
        exclude_defaults=True
    ) == config.routing.model_dump(exclude_defaults=True)
