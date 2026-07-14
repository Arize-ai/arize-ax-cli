"""Tests for SDK client construction from AX configuration."""

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


@pytest.fixture(autouse=True)
def clear_grpc_proxy_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid leaking gRPC proxy configuration between unit tests."""
    monkeypatch.setenv("grpc_proxy", "")
    monkeypatch.setenv("no_grpc_proxy", "")


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
