"""Tests for proxy-aware urllib helpers."""

import io
import urllib.request

import pytest

from ax.core.network import NetworkSettings
from ax.utils.http import open_url


@pytest.fixture
def captured_handlers(monkeypatch: pytest.MonkeyPatch) -> list:
    """Capture the handlers open_url installs instead of hitting the network."""
    handlers: list = []

    def fake_build_opener(*args):
        handlers.extend(args)

        class _FakeOpener:
            def open(self, url, timeout=None):
                return io.BytesIO(b"")

        return _FakeOpener()

    monkeypatch.setattr(
        "ax.utils.http.urllib.request.build_opener", fake_build_opener
    )
    return handlers


def _proxy_handlers(handlers: list) -> list[urllib.request.ProxyHandler]:
    return [h for h in handlers if isinstance(h, urllib.request.ProxyHandler)]


def test_open_url_uses_explicit_proxy(captured_handlers: list) -> None:
    """A resolved proxy is installed for both schemes."""
    settings = NetworkSettings(proxy_url="http://proxy.example.com:8080")

    open_url("https://api.arize.com", timeout=5, network=settings)

    (handler,) = _proxy_handlers(captured_handlers)
    assert handler.proxies == {
        "http": "http://proxy.example.com:8080",
        "https": "http://proxy.example.com:8080",
    }


def test_open_url_forces_direct_connection_for_bypassed_host(
    captured_handlers: list,
) -> None:
    """A no_proxy match must not fall back to OS-level proxy discovery."""
    settings = NetworkSettings(
        proxy_url="http://proxy.example.com:8080",
        no_proxy="api.internal.example.com",
    )

    open_url("https://api.internal.example.com", timeout=5, network=settings)

    (handler,) = _proxy_handlers(captured_handlers)
    assert handler.proxies == {}


def test_open_url_defers_to_system_proxy_discovery(
    captured_handlers: list,
) -> None:
    """With nothing configured, urllib's default discovery must stay active.

    Passing an explicit empty ProxyHandler would disable the macOS System
    Configuration / Windows registry proxy lookup the default opener does.
    """
    open_url(
        "https://pypi.org/pypi/arize-ax-cli/json",
        timeout=5,
        network=NetworkSettings(),
    )

    assert _proxy_handlers(captured_handlers) == []
