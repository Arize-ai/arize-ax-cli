import base64
import contextlib
import hashlib
import http.client
import threading
import urllib.error
import urllib.request

import pytest

from ax.auth.oauth_flow import LoopbackServer, generate_pkce_pair, random_state

# Any URL — the loopback redirects there but tests don't follow the redirect.
_CALLBACK_PAGE = "https://app.arize.com/auth/cli/callback"


def _new_server(expected_state: str = "xyz") -> LoopbackServer:
    return LoopbackServer(
        expected_state=expected_state,
        callback_page_base_url=_CALLBACK_PAGE,
    )


def _fire(url: str) -> None:
    """Hit the loopback in a daemon thread, swallowing any redirect-follow errors.

    The loopback responds with a 302 to a non-127.0.0.1 host the test
    process can't reach; we only care that the server captured state, not
    that the browser successfully followed the redirect.
    """

    def run() -> None:
        with contextlib.suppress(
            urllib.error.URLError, urllib.error.HTTPError, OSError
        ):
            urllib.request.urlopen(url).read()  # noqa: S310 (test scaffolding)

    threading.Thread(target=run, daemon=True).start()


def test_generate_pkce_pair_is_s256_compatible():
    verifier, challenge, method = generate_pkce_pair()
    assert method == "S256"
    assert 43 <= len(verifier) <= 128  # RFC 7636 §4.1
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert challenge == expected


def test_pkce_pair_is_fresh_every_call():
    a, _, _ = generate_pkce_pair()
    b, _, _ = generate_pkce_pair()
    assert a != b


def test_random_state_is_fresh():
    assert random_state() != random_state()


def test_loopback_server_only_binds_127_0_0_1():
    server = _new_server()
    server.start()
    try:
        host, port = server.address
        assert host == "127.0.0.1"
        assert port > 0
    finally:
        server.stop()


def test_loopback_server_captures_code_and_state():
    server = _new_server()
    server.start()
    _fire(f"http://127.0.0.1:{server.port}/callback?code=the-code&state=xyz")
    result = server.wait(timeout=5.0)
    assert result.code == "the-code"
    assert result.state == "xyz"


def test_loopback_server_rejects_state_mismatch():
    server = _new_server("expected")
    server.start()
    _fire(f"http://127.0.0.1:{server.port}/callback?code=x&state=wrong")
    with pytest.raises(ValueError, match="state"):
        server.wait(timeout=5.0)


def test_loopback_server_rejects_missing_code():
    server = _new_server()
    server.start()
    _fire(f"http://127.0.0.1:{server.port}/callback?state=xyz")
    with pytest.raises(ValueError, match="no code"):
        server.wait(timeout=5.0)


def test_loopback_server_rejects_wrong_path():
    """Browsers that land on a non-/callback URL (e.g., /favicon.ico) should get 404
    and the server should keep waiting for a proper callback.
    """
    server = _new_server()
    server.start()
    try:
        # Fire a bogus request; it shouldn't terminate wait()
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{server.port}/favicon.ico"
            ).read()
        except urllib.error.HTTPError as e:
            assert e.code == 404
        # Server should still be waiting; we terminate via stop()
        assert not server._done.is_set()
    finally:
        server.stop()


def test_loopback_redirects_success_to_callback_page():
    """Successful callback should 302-redirect to {callback_page_base_url}?status=success."""
    server = _new_server()
    server.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.port)
        conn.request("GET", "/callback?code=the-code&state=xyz")
        resp = conn.getresponse()
        assert resp.status == 302, resp.status
        location = resp.getheader("Location") or ""
        assert location.startswith(_CALLBACK_PAGE), location
        assert "status=success" in location
        # Make sure no token material leaked into the redirect target.
        assert "the-code" not in location
        assert "code=" not in location
    finally:
        server.stop()


def test_loopback_redirects_error_to_callback_page_with_reason():
    """State mismatch should redirect with status=error and a reason."""
    server = _new_server("expected")
    server.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.port)
        conn.request("GET", "/callback?code=x&state=wrong")
        resp = conn.getresponse()
        assert resp.status == 302
        location = resp.getheader("Location") or ""
        assert location.startswith(_CALLBACK_PAGE)
        assert "status=error" in location
        assert "reason=" in location
    finally:
        server.stop()
