"""HTTP client for the Arize app's /oauth2/* endpoints."""

import base64
import json
import logging
from dataclasses import dataclass

import requests

from ax.core.exceptions import AuthenticationError
from ax.core.network import NetworkSettings

_log = logging.getLogger(__name__)


@dataclass
class TokenResponse:
    """Parsed /oauth2/token response."""

    access_token: str
    refresh_token: str
    expires_in: int  # seconds
    user_email: str | None = None


def _parse_token_response(resp: requests.Response) -> dict:
    """Validate /oauth2/token response shape and return its JSON body.

    Surfaces a descriptive AuthenticationError on bad JSON or missing/wrong-typed
    required fields, instead of an opaque KeyError or JSONDecodeError.
    """
    try:
        body = resp.json()
    except ValueError as e:
        raise AuthenticationError(
            f"OAuth token endpoint returned non-JSON response: {resp.text[:200]!r}"
        ) from e
    if not isinstance(body, dict):
        raise AuthenticationError(
            f"OAuth token response was not a JSON object: {body!r}"
        )
    required: dict[str, type | tuple[type, ...]] = {
        "access_token": str,
        "refresh_token": str,
        "expires_in": (int, str),  # spec says int; some IdPs return string
    }
    for key, expected_type in required.items():
        if key not in body:
            raise AuthenticationError(
                f"OAuth token response missing required field {key!r}"
            )
        if not isinstance(body[key], expected_type):
            raise AuthenticationError(
                f"OAuth token response field {key!r} has wrong type: "
                f"expected {expected_type}, got {type(body[key]).__name__}"
            )
    try:
        int(body["expires_in"])
    except (TypeError, ValueError) as e:
        raise AuthenticationError(
            f"OAuth token response field 'expires_in' is not an integer: "
            f"{body['expires_in']!r}"
        ) from e
    return body


def _decode_email_from_id_token(id_token: str) -> str | None:
    """Best-effort extraction of the ``email`` claim from an id_token JWT.

    Does NOT verify the JWT signature, issuer, audience, or nonce. This is
    safe under the current threat model because:

    1. The id_token arrived over TLS directly from the Arize app's
       /oauth2/token endpoint — there is no third-party hop.
    2. The extracted email is *display-only*: it is written to the profile
       as ``user_email`` and shown in "Signed in as ..." messages.
       Authorization always uses the ``access_token``, which the API server
       validates server-side.
    3. A spoofed email would be cosmetic and visible to the user.

    TODO: If we ever start using this email for anything beyond display
    (authorization, audit logs, account routing), promote this to full OIDC
    verification: PyJWKClient + ``jwt.decode(... audience=, issuer=,
    options={'require': ['exp','iat','iss','aud','nonce']})``, plus a
    ``nonce`` threaded through the PKCE auth-request and the loopback
    callback server.
    """
    try:
        parts = id_token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        pad = "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + pad))
        email = payload.get("email")
        return email if isinstance(email, str) and email else None
    except Exception as e:
        _log.debug("id_token email extraction failed: %s", e)
        return None


class OAuthClient:
    """HTTP client for the Arize app's /oauth2/{token,revoke} endpoints."""

    def __init__(
        self,
        base_url: str,
        client_id: str,
        timeout: float = 10.0,
        network: NetworkSettings | None = None,
    ) -> None:
        """Pin the base URL and OAuth client_id used by every request."""
        self._base = base_url.rstrip("/")
        self._client_id = client_id
        self._timeout = timeout
        self._network = network or NetworkSettings.from_environment()

    def _post(self, path: str, data: dict[str, str]) -> requests.Response:
        """POST an OAuth form using the shared proxy and TLS policy."""
        url = f"{self._base}{path}"
        # Always use an env-free session. Passing ``proxies={}`` to requests.post
        # still allows ambient proxy discovery, which can disagree with the
        # validated policy (for example ALL_PROXY=socks5://...).
        with requests.Session() as session:
            session.trust_env = False
            return session.post(
                url,
                data=data,
                timeout=self._timeout,
                proxies=self._network.requests_proxies(url),
                verify=self._network.verify_value,
            )

    def exchange_code(
        self, *, code: str, code_verifier: str, redirect_uri: str
    ) -> TokenResponse:
        """POST /oauth2/token with grant_type=authorization_code."""
        resp = self._post(
            "/oauth2/token",
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": self._client_id,
                "code_verifier": code_verifier,
            },
        )
        resp.raise_for_status()
        body = _parse_token_response(resp)
        email = (
            _decode_email_from_id_token(body["id_token"])
            if body.get("id_token")
            else None
        )
        return TokenResponse(
            access_token=body["access_token"],
            refresh_token=body["refresh_token"],
            expires_in=int(body["expires_in"]),
            user_email=email,
        )

    def refresh(self, *, refresh_token: str) -> TokenResponse:
        """POST /oauth2/token with grant_type=refresh_token."""
        resp = self._post(
            "/oauth2/token",
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self._client_id,
            },
        )
        resp.raise_for_status()
        body = _parse_token_response(resp)
        return TokenResponse(
            access_token=body["access_token"],
            refresh_token=body["refresh_token"],
            expires_in=int(body["expires_in"]),
        )

    def revoke(self, *, token: str) -> None:
        """POST /oauth2/revoke. Best-effort — never raises.

        RFC 7009 §2.2: revocation endpoints always return 200 for invalid
        tokens too, so we swallow both network errors and server-side errors.
        The local profile gets cleared regardless (ax auth logout).

        A non-200 response means the server is genuinely misbehaving — surface
        it as a warning so the user can see their token may not have been
        revoked. Network errors are logged at debug level since the local
        profile clear honors the user's intent regardless.
        """
        try:
            resp = self._post(
                "/oauth2/revoke",
                {"token": token, "client_id": self._client_id},
            )
            if resp.status_code != 200:
                _log.warning(
                    "revoke returned non-200 status=%s body=%s — token may NOT be revoked",
                    resp.status_code,
                    resp.text[:200],
                )
        except Exception as e:
            _log.debug("revoke best-effort failed: %s", e)
