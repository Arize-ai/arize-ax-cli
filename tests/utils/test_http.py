"""Tests for proxy-aware urllib helpers."""

import http.client
import io
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import ClassVar
from urllib.parse import urlsplit

import pytest

from ax.core.network import NetworkSettings
from ax.utils.http import open_url


@contextmanager
def _serve(
    handler: type[BaseHTTPRequestHandler],
) -> Iterator[ThreadingHTTPServer]:
    """Run a local HTTP server for a transport-level proxy test."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class _OriginHandler(BaseHTTPRequestHandler):
    """Small HTTP origin that records direct and forwarded requests."""

    paths: ClassVar[list[str]] = []

    def do_GET(self) -> None:
        """Return a fixed body for proxy tests."""
        type(self).paths.append(self.path)
        body = b"origin response"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        """Keep expected local-server traffic out of test output."""


class _ProxyHandler(BaseHTTPRequestHandler):
    """Minimal forward proxy that records HTTP and CONNECT requests."""

    proxied_urls: ClassVar[list[str]] = []
    connect_targets: ClassVar[list[str]] = []

    def do_GET(self) -> None:
        """Forward an HTTP request sent with an absolute proxy URL."""
        type(self).proxied_urls.append(self.path)
        target = urlsplit(self.path)
        assert target.hostname is not None
        connection = http.client.HTTPConnection(
            target.hostname, target.port or 80, timeout=5
        )
        request_path = target.path or "/"
        if target.query:
            request_path = f"{request_path}?{target.query}"
        headers = {
            name: value
            for name, value in self.headers.items()
            if name.lower() not in {"connection", "proxy-connection"}
        }
        connection.request("GET", request_path, headers=headers)
        response = connection.getresponse()
        body = response.read()
        self.send_response(response.status)
        for name, value in response.getheaders():
            if name.lower() not in {"connection", "transfer-encoding"}:
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)
        connection.close()

    def do_CONNECT(self) -> None:
        """Acknowledge a tunnel so the test can observe CONNECT selection."""
        type(self).connect_targets.append(self.path)
        self.send_response(200, "Connection Established")
        self.end_headers()
        self.close_connection = True

    def log_message(self, _format: str, *_args: object) -> None:
        """Keep expected local-server traffic out of test output."""


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


def test_open_url_forces_direct_connection_without_a_resolved_proxy(
    captured_handlers: list,
) -> None:
    """Unsupported ambient proxies cannot bypass the resolved policy."""
    open_url(
        "https://pypi.org/pypi/arize-ax-cli/json",
        timeout=5,
        network=NetworkSettings(),
    )

    (handler,) = _proxy_handlers(captured_handlers)
    assert handler.proxies == {}


def test_open_url_forwards_http_through_a_running_proxy() -> None:
    """The resolved proxy is used for a real HTTP(S)-transport request."""
    _OriginHandler.paths.clear()
    _ProxyHandler.proxied_urls.clear()
    with _serve(_OriginHandler) as origin, _serve(_ProxyHandler) as proxy:
        origin_url = f"http://127.0.0.1:{origin.server_port}/resource"
        settings = NetworkSettings(
            proxy_url=f"http://127.0.0.1:{proxy.server_port}"
        )

        with open_url(origin_url, timeout=5, network=settings) as response:
            assert response.read() == b"origin response"

    assert _ProxyHandler.proxied_urls == [origin_url]
    assert _OriginHandler.paths == ["/resource"]


def test_open_url_uses_connect_for_https_proxy_requests() -> None:
    """HTTPS requests negotiate an HTTP CONNECT tunnel through the proxy."""
    _ProxyHandler.connect_targets.clear()
    with _serve(_ProxyHandler) as proxy:
        settings = NetworkSettings(
            proxy_url=f"http://127.0.0.1:{proxy.server_port}"
        )

        with pytest.raises(urllib.error.URLError):
            open_url(
                "https://example.test/resource", timeout=5, network=settings
            )

    assert _ProxyHandler.connect_targets == ["example.test:443"]


def test_open_url_bypasses_running_proxy_for_no_proxy_host() -> None:
    """A no_proxy match connects directly even when a proxy is configured."""
    _OriginHandler.paths.clear()
    _ProxyHandler.proxied_urls.clear()
    with _serve(_OriginHandler) as origin, _serve(_ProxyHandler) as proxy:
        origin_url = f"http://127.0.0.1:{origin.server_port}/bypass"
        settings = NetworkSettings(
            proxy_url=f"http://127.0.0.1:{proxy.server_port}",
            no_proxy="127.0.0.1",
        )

        with open_url(origin_url, timeout=5, network=settings) as response:
            assert response.read() == b"origin response"

    assert _ProxyHandler.proxied_urls == []
    assert _OriginHandler.paths == ["/bypass"]
