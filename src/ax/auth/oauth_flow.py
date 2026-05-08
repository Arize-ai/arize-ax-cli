"""PKCE helpers and a one-shot loopback HTTP listener for the OAuth callback."""

import base64
import hashlib
import secrets
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse


def generate_pkce_pair() -> tuple[str, str, str]:
    """Return ``(code_verifier, code_challenge, method='S256')``.

    Per RFC 7636: verifier is 43-128 chars URL-safe base64, challenge is
    ``base64url(sha256(verifier))`` without padding.
    """
    verifier = (
        base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    )
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge, "S256"


def random_state() -> str:
    """Return a URL-safe random ``state`` token for CSRF protection."""
    return (
        base64.urlsafe_b64encode(secrets.token_bytes(16)).rstrip(b"=").decode()
    )


@dataclass
class AuthorizationResult:
    """Result of a successful OAuth authorization callback."""

    code: str
    state: str


class _CallbackHandler(BaseHTTPRequestHandler):
    """Loopback handler for the OAuth redirect.

    Captures the ``code`` (or error) and 302-redirects the browser to the
    Arize-hosted ``/auth/cli/callback`` page so users see Arize-branded
    UI rather than something rendered by a Python HTTP server bound to
    127.0.0.1. The redirect URL is set on the LoopbackServer up front by
    the login flow so the handler can build it from the user's profile
    routing config.
    """

    def do_GET(self) -> None:
        """Handle the OAuth provider's redirect to /callback."""
        server = self.server.loopback  # type: ignore[attr-defined]
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_error(404)
            return
        # Strip CRLF defensively — values flow into ValueError messages and
        # redirect reasons. Prevents log/header injection from a tampered
        # callback URL.
        params = {
            k: v[0].replace("\r", "").replace("\n", "")
            for k, v in parse_qs(parsed.query).items()
        }

        if "error" in params:
            self._redirect_error(
                server,
                f"{params.get('error')}: "
                f"{params.get('error_description', 'no description provided')}",
            )
            server._set_error(
                ValueError(
                    f"authorization server returned error={params.get('error')!r} "
                    f"error_description={params.get('error_description')!r}"
                )
            )
            return
        if params.get("state") != server.expected_state:
            self._redirect_error(
                server,
                "State parameter mismatch — possible CSRF, please retry from the CLI.",
            )
            server._set_error(
                ValueError(f"state mismatch: got {params.get('state')!r}")
            )
            return
        if "code" not in params:
            self._redirect_error(
                server,
                "The authorization server did not return an authorization code.",
            )
            server._set_error(ValueError("no code in redirect"))
            return

        self._redirect_success(server)
        server._set_result(
            AuthorizationResult(code=params["code"], state=params["state"])
        )

    def _redirect_success(self, server: "LoopbackServer") -> None:
        self._redirect(
            f"{server.callback_page_base_url}?{urlencode({'status': 'success'})}"
        )

    def _redirect_error(self, server: "LoopbackServer", reason: str) -> None:
        self._redirect(
            f"{server.callback_page_base_url}?"
            f"{urlencode({'status': 'error', 'reason': reason})}"
        )

    def _redirect(self, target: str) -> None:
        # Defense-in-depth against HTTP response splitting via the Location header.
        safe_target = target.replace("\r", "").replace("\n", "")
        self.send_response(302)
        self.send_header("Location", safe_target)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args: object, **kwargs: object) -> None:
        """Silence stdout access logging."""
        return


class LoopbackServer:
    """One-shot HTTP server bound to 127.0.0.1 on a random port for OAuth callback.

    On every request the handler 302-redirects the browser to
    ``callback_page_base_url`` so users land on the Arize-hosted, branded
    ``/auth/cli/callback`` page instead of seeing a page served by Python on
    127.0.0.1. ``callback_page_base_url`` should already include the
    ``/auth/cli/callback`` path (e.g. ``https://app-foo.arize.com/auth/cli/callback``);
    the handler appends ``?status=success`` or ``?status=error&reason=...``.
    """

    def __init__(
        self, expected_state: str, callback_page_base_url: str
    ) -> None:
        """Bind the loopback server on a free 127.0.0.1 port (not yet started)."""
        self.expected_state = expected_state
        self.callback_page_base_url = callback_page_base_url
        self._http = HTTPServer(("127.0.0.1", 0), _CallbackHandler)
        self._http.loopback = self  # type: ignore[attr-defined]
        self._thread: threading.Thread | None = None
        self._result: AuthorizationResult | None = None
        self._error: BaseException | None = None
        self._done = threading.Event()

    @property
    def port(self) -> int:
        """Return the loopback port the server is bound to."""
        return self._http.server_address[1]

    @property
    def address(self) -> tuple[str, int]:
        """Return the (host, port) tuple the server is bound to."""
        return self._http.server_address  # type: ignore[return-value]

    def start(self) -> None:
        """Start serving OAuth callbacks on a background daemon thread."""
        self._thread = threading.Thread(
            target=self._http.serve_forever, daemon=True
        )
        self._thread.start()

    def _set_result(self, r: AuthorizationResult) -> None:
        self._result = r
        self._done.set()

    def _set_error(self, e: BaseException) -> None:
        self._error = e
        self._done.set()

    def wait(self, timeout: float) -> AuthorizationResult:
        """Block until a callback arrives or ``timeout`` seconds elapse."""
        if not self._done.wait(timeout):
            self.stop()
            raise TimeoutError("timed out waiting for OAuth callback")
        self.stop()
        if self._error is not None:
            raise self._error
        assert self._result is not None  # noqa: S101  (invariant: _done set => result or error)
        return self._result

    def stop(self) -> None:
        """Shut the HTTP server down and release the bound port."""
        self._http.shutdown()
        self._http.server_close()
