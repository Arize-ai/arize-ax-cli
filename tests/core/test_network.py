"""Tests for the shared proxy and TLS policy."""

import os

import pytest

from ax.config.schema import NetworkConfig, ProxyMode
from ax.core.exceptions import ConfigError
from ax.core.network import NetworkSettings

_GRPC_PROXY_ENV = "grpc_proxy"
_NO_GRPC_PROXY_ENV = "no_grpc_proxy"


@pytest.fixture(autouse=True)
def clear_proxy_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep host proxy variables from affecting proxy-resolution tests."""
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
    ):
        monkeypatch.delenv(name, raising=False)


def test_system_mode_prefers_arize_proxy_and_honors_no_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """System mode resolves standard variables with Arize's override first."""
    monkeypatch.setenv("ARIZE_PROXY_URL", "http://arize-proxy:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://ignored-proxy:8080")
    monkeypatch.setenv("NO_PROXY", ".internal.example.com,localhost")

    settings = NetworkSettings.from_config(NetworkConfig(), request_verify=True)

    assert (
        settings.proxy_for("https://api.arize.com") == "http://arize-proxy:8080"
    )
    assert settings.proxy_for("https://api.internal.example.com") == ""
    assert settings.proxy_for("https://localhost:8443") == ""


def test_arize_no_proxy_env_var_is_honored_at_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ARIZE_NO_PROXY works like ARIZE_PROXY_URL: detected AND applied.

    Profile creation detects it, so runtime resolution must read it too —
    with priority over the generic NO_PROXY.
    """
    monkeypatch.setenv("ARIZE_PROXY_URL", "http://arize-proxy:8080")
    monkeypatch.setenv("ARIZE_NO_PROXY", ".internal.example.com")
    monkeypatch.setenv("NO_PROXY", "ignored.example.com")

    settings = NetworkSettings.from_config(NetworkConfig(), request_verify=True)

    assert settings.no_proxy == ".internal.example.com"
    assert settings.proxy_for("https://api.internal.example.com") == ""


def test_explicit_proxy_mode_overrides_system_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A profile proxy URL wins over ambient proxy variables."""
    monkeypatch.setenv("HTTPS_PROXY", "http://system-proxy:8080")
    settings = NetworkSettings.from_config(
        NetworkConfig(
            proxy_mode=ProxyMode.URL,
            proxy_url="http://profile-proxy:3128",
            no_proxy="example.test",
        ),
        request_verify=True,
    )

    assert (
        settings.proxy_for("https://api.arize.com")
        == "http://profile-proxy:3128"
    )
    assert settings.proxy_for("https://example.test") == ""
    assert settings.requests_proxies("https://api.arize.com") == {
        "http": "http://profile-proxy:3128",
        "https": "http://profile-proxy:3128",
    }


def test_runtime_proxy_url_must_be_http_connect_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Environment-backed proxy URLs are checked before transport setup."""
    monkeypatch.setenv("CORP_PROXY", "socks5://proxy.example.com:1080")
    with pytest.raises(ConfigError, match="Proxy URL"):
        NetworkSettings.from_config(
            NetworkConfig(
                proxy_mode=ProxyMode.URL,
                proxy_url="${CORP_PROXY}",
            ),
            request_verify=True,
        )


def test_network_references_expand_for_raw_oauth_profiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OAuth paths can resolve profile env refs before a profile is saved."""
    monkeypatch.setenv("CORP_PROXY", "http://proxy.example.com:8080")
    settings = NetworkSettings.from_config(
        NetworkConfig(
            proxy_mode=ProxyMode.URL,
            proxy_url="${CORP_PROXY}",
        ),
        request_verify=True,
    )

    assert settings.proxy_url == "http://proxy.example.com:8080"


def test_system_mode_ignores_unsupported_ambient_proxy_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ambient socks5/https proxy variables must not break every command."""
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:1080")

    settings = NetworkSettings.from_environment()

    assert settings.proxy_url == ""


def test_system_mode_falls_back_past_unsupported_proxy_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A later usable env proxy wins over an earlier unsupported one."""
    monkeypatch.setenv("https_proxy", "socks5://127.0.0.1:1080")
    monkeypatch.setenv("http_proxy", "http://fallback-proxy:3128")

    settings = NetworkSettings.from_environment()

    assert settings.proxy_url == "http://fallback-proxy:3128"


def test_system_mode_ignores_missing_environment_ca_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale REQUESTS_CA_BUNDLE must not abort settings resolution."""
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", "/nonexistent/rotated-ca.pem")

    settings = NetworkSettings.from_environment()

    assert settings.ca_bundle == ""


def test_profile_ca_bundle_must_exist() -> None:
    """A profile-configured CA bundle path is still validated strictly."""
    with pytest.raises(ConfigError, match="CA bundle"):
        NetworkSettings.from_config(
            NetworkConfig(ca_bundle="/nonexistent/corporate-ca.pem"),
            request_verify=True,
        )


def test_configure_grpc_environment_normalizes_proxy_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flight and OTLP receive the same resolved proxy and bypass list."""
    monkeypatch.setenv(_GRPC_PROXY_ENV, "")
    monkeypatch.setenv(_NO_GRPC_PROXY_ENV, "")
    settings = NetworkSettings(
        proxy_url="http://proxy.example.com:8080",
        no_proxy="localhost,.internal.example.com",
    )

    settings.configure_grpc_environment()

    assert os.environ[_GRPC_PROXY_ENV] == "http://proxy.example.com:8080"
    assert os.environ[_NO_GRPC_PROXY_ENV] == "localhost,.internal.example.com"


def test_system_mode_exports_arize_proxy_to_grpc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flight and OTLP must see a proxy that only ARIZE_PROXY_URL provides.

    gRPC C-Core reads grpc_proxy/https_proxy/http_proxy but never
    ARIZE_PROXY_URL, so system mode must export the resolved proxy or
    Flight/OTLP silently bypass it.
    """
    monkeypatch.setenv("ARIZE_PROXY_URL", "http://arize-proxy:8080")
    monkeypatch.setenv("NO_PROXY", "localhost")

    settings = NetworkSettings.from_config(NetworkConfig(), request_verify=True)
    settings.configure_grpc_environment()

    assert os.environ[_GRPC_PROXY_ENV] == "http://arize-proxy:8080"
    assert os.environ[_NO_GRPC_PROXY_ENV] == "localhost"


def test_system_mode_preserves_existing_grpc_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AX system mode must not replace a deliberately distinct gRPC proxy."""
    monkeypatch.setenv(_GRPC_PROXY_ENV, "http://grpc-proxy.example.com:8080")
    monkeypatch.setenv(_NO_GRPC_PROXY_ENV, "grpc.internal.example.com")

    settings = NetworkSettings.from_config(NetworkConfig(), request_verify=True)
    settings.configure_grpc_environment()

    assert os.environ[_GRPC_PROXY_ENV] == "http://grpc-proxy.example.com:8080"
    assert os.environ[_NO_GRPC_PROXY_ENV] == "grpc.internal.example.com"


def test_no_proxy_supports_cidr_and_host_port() -> None:
    """HTTP transports honor normal NO_PROXY CIDR and host:port entries."""
    settings = NetworkSettings(
        proxy_url="http://proxy.example.com:8080",
        no_proxy="10.0.0.0/8,api.internal.example.com:8443",
    )

    assert settings.proxy_for("https://10.10.11.12:443") == ""
    assert settings.proxy_for("https://api.internal.example.com:8443") == ""
    assert (
        settings.proxy_for("https://api.internal.example.com:443")
        == "http://proxy.example.com:8080"
    )


def test_no_proxy_port_entry_matches_scheme_default_port() -> None:
    """A 'host:443' entry must bypass 'https://host' like curl and Go do."""
    settings = NetworkSettings(
        proxy_url="http://proxy.example.com:8080",
        no_proxy="api.internal.example.com:443",
    )

    assert settings.proxy_for("https://api.internal.example.com") == ""
    assert (
        settings.proxy_for("http://api.internal.example.com")
        == "http://proxy.example.com:8080"
    )


def test_bypasses_tolerates_out_of_range_url_port() -> None:
    """A malformed routing port must not crash proxy resolution."""
    settings = NetworkSettings(
        proxy_url="http://proxy.example.com:8080",
        no_proxy="localhost",
    )

    assert settings.bypasses("https://onprem.corp:99999") is False
    assert (
        settings.proxy_for("https://onprem.corp:99999")
        == "http://proxy.example.com:8080"
    )


def test_redacted_proxy_url_hides_password() -> None:
    """Profile output never reveals proxy credentials."""
    settings = NetworkSettings(
        proxy_url="http://user:super-secret@proxy.example.com:8080"
    )

    assert (
        settings.redacted_proxy_url()
        == "http://user:***@proxy.example.com:8080"
    )
