"""Tests for SDK client construction from AX configuration."""

import os
from unittest.mock import patch

import pytest

from ax.config.schema import (
    AuthConfig,
    Config,
    NetworkConfig,
    ProfileConfig,
    ProxyMode,
)
from ax.core.client_factory import make_client
from ax.core.network import _GRPC_PROXY_ENV


@pytest.fixture(autouse=True)
def clear_network_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the host's proxy settings from changing client construction."""
    for name in (
        "ARIZE_PROXY_URL",
        "ARIZE_NO_PROXY",
        "https_proxy",
        "HTTPS_PROXY",
        "http_proxy",
        "HTTP_PROXY",
        "all_proxy",
        "ALL_PROXY",
        "no_proxy",
        "NO_PROXY",
        "grpc_proxy",
        "no_grpc_proxy",
        "ARIZE_SSL_CA_CERT",
        "REQUESTS_CA_BUNDLE",
        "SSL_CERT_FILE",
    ):
        monkeypatch.delenv(name, raising=False)


def test_make_client_passes_proxy_and_ca_bundle_to_sdk() -> None:
    """The REST client receives the resolved proxy and CA bundle."""
    config = Config(
        profile=ProfileConfig(name="proxy"),
        auth=AuthConfig(auth_method="api-key", api_key="ak-test"),
        network=NetworkConfig(
            proxy_mode=ProxyMode.URL,
            proxy_url="http://proxy.example.com:8080",
            ca_bundle="",
        ),
    )

    with (
        patch("ax.core.client_factory.ConfigManager.load", return_value=config),
        patch("ax.core.client_factory.ArizeClient") as arize_client,
    ):
        make_client()

    assert (
        arize_client.call_args.kwargs["proxy_url"]
        == "http://proxy.example.com:8080"
    )
    assert arize_client.call_args.kwargs["ssl_ca_cert"] == ""


def test_make_client_bypasses_rest_proxy_for_no_proxy_host() -> None:
    """REST follows the same no_proxy policy as gRPC and OAuth."""
    config = Config(
        profile=ProfileConfig(name="proxy"),
        auth=AuthConfig(auth_method="api-key", api_key="ak-test"),
        network=NetworkConfig(
            proxy_mode=ProxyMode.URL,
            proxy_url="http://proxy.example.com:8080",
            no_proxy="api.arize.com",
        ),
    )

    with (
        patch("ax.core.client_factory.ConfigManager.load", return_value=config),
        patch("ax.core.client_factory.ArizeClient") as arize_client,
    ):
        make_client()

    assert arize_client.call_args.kwargs["proxy_url"] == ""


def test_make_client_restores_grpc_environment_after_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SDK construction sees the profile policy without retaining it globally."""
    monkeypatch.setenv("grpc_proxy", "http://caller-proxy.example.com:8080")
    config = Config(
        profile=ProfileConfig(name="proxy"),
        auth=AuthConfig(auth_method="api-key", api_key="ak-test"),
        network=NetworkConfig(
            proxy_mode=ProxyMode.URL,
            proxy_url="http://profile-proxy.example.com:8080",
        ),
    )

    def assert_grpc_proxy_is_scoped(**kwargs):
        assert kwargs["proxy_url"] == "http://profile-proxy.example.com:8080"
        assert (
            os.environ.get(_GRPC_PROXY_ENV)
            == "http://profile-proxy.example.com:8080"
        )
        return object()

    with (
        patch("ax.core.client_factory.ConfigManager.load", return_value=config),
        patch(
            "ax.core.client_factory.ArizeClient",
            side_effect=assert_grpc_proxy_is_scoped,
        ),
    ):
        make_client()

    assert (
        os.environ.get(_GRPC_PROXY_ENV)
        == "http://caller-proxy.example.com:8080"
    )
