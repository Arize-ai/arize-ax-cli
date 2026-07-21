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

_GRPC_PROXY_ENV = "grpc_proxy"


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
    """REST follows the configured no_proxy policy."""
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


def test_make_client_does_not_change_grpc_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP(S)-only proxy configuration leaves gRPC settings untouched."""
    monkeypatch.setenv(_GRPC_PROXY_ENV, "http://caller-proxy.example.com:8080")
    config = Config(
        profile=ProfileConfig(name="proxy"),
        auth=AuthConfig(auth_method="api-key", api_key="ak-test"),
        network=NetworkConfig(
            proxy_mode=ProxyMode.URL,
            proxy_url="http://profile-proxy.example.com:8080",
        ),
    )

    with (
        patch("ax.core.client_factory.ConfigManager.load", return_value=config),
        patch("ax.core.client_factory.ArizeClient"),
    ):
        make_client()

    assert os.environ[_GRPC_PROXY_ENV] == "http://caller-proxy.example.com:8080"
