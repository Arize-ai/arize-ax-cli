import base64
import json
from unittest.mock import MagicMock, patch

from ax.auth.oauth_client import (
    OAuthClient,
    _decode_email_from_id_token,
)
from ax.core.network import NetworkSettings


def _fake_id_token(email: str) -> str:
    """Build a JWT-shaped string with the given email; header and signature
    are dummy (we don't verify).
    """
    header = (
        base64.urlsafe_b64encode(b'{"alg":"RS256","typ":"JWT"}')
        .rstrip(b"=")
        .decode()
    )
    payload = (
        base64.urlsafe_b64encode(json.dumps({"email": email}).encode())
        .rstrip(b"=")
        .decode()
    )
    return f"{header}.{payload}.signature"


def _mock_response(status: int, json_body: dict) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = json_body
    if status >= 400:
        import requests

        def _raise():
            raise requests.HTTPError(f"HTTP {status}")

        m.raise_for_status = _raise
    else:
        m.raise_for_status = lambda: None
    return m


class TestDecodeEmailFromIdToken:
    def test_returns_email_from_valid_token(self):
        tok = _fake_id_token("user@example.com")
        assert _decode_email_from_id_token(tok) == "user@example.com"

    def test_returns_none_for_malformed_token(self):
        assert _decode_email_from_id_token("not-a-jwt") is None
        assert _decode_email_from_id_token("") is None
        assert _decode_email_from_id_token("a.b") is None

    def test_returns_none_when_payload_has_no_email(self):
        header = (
            base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=").decode()
        )
        payload = (
            base64.urlsafe_b64encode(b'{"sub":"42"}').rstrip(b"=").decode()
        )
        assert _decode_email_from_id_token(f"{header}.{payload}.sig") is None


class TestExchangeCode:
    def test_uses_explicit_proxy_and_ca_bundle(self):
        """OAuth token exchange follows the same profile policy as API calls."""
        client = OAuthClient(
            base_url="https://app.arize.com",
            client_id="arize-cli",
            network=NetworkSettings(
                proxy_url="http://proxy.example.com:8080",
                ca_bundle="/tmp/corporate-ca.pem",
            ),
        )
        with patch("ax.auth.oauth_client.requests.post") as post:
            post.return_value = _mock_response(
                200,
                {
                    "access_token": "a",
                    "refresh_token": "r",
                    "expires_in": 60,
                },
            )
            client.exchange_code(
                code="abc", code_verifier="v", redirect_uri="u"
            )

        assert post.call_args.kwargs["proxies"] == {
            "http": "http://proxy.example.com:8080",
            "https": "http://proxy.example.com:8080",
        }
        assert post.call_args.kwargs["verify"] == "/tmp/corporate-ca.pem"

    def test_happy_path_parses_response_with_id_token_email(self):
        client = OAuthClient(
            base_url="https://app.arize.com", client_id="arize-cli"
        )
        id_tok = _fake_id_token("user@example.com")
        with patch("ax.auth.oauth_client.requests.post") as post:
            post.return_value = _mock_response(
                200,
                {
                    "access_token": "arz_at_x",
                    "refresh_token": "arz_rt_x",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                    "id_token": id_tok,
                },
            )
            resp = client.exchange_code(
                code="abc",
                code_verifier="v",
                redirect_uri="http://127.0.0.1:1234/callback",
            )
        assert resp.access_token == "arz_at_x"
        assert resp.refresh_token == "arz_rt_x"
        assert resp.expires_in == 3600
        assert resp.user_email == "user@example.com"
        # Verify request shape
        post.assert_called_once()
        assert post.call_args.args[0] == "https://app.arize.com/oauth2/token"
        body = post.call_args.kwargs["data"]
        assert body["grant_type"] == "authorization_code"
        assert body["code"] == "abc"
        assert body["code_verifier"] == "v"
        assert body["client_id"] == "arize-cli"
        assert body["redirect_uri"] == "http://127.0.0.1:1234/callback"

    def test_no_id_token_returns_none_email(self):
        client = OAuthClient(
            base_url="https://app.arize.com", client_id="arize-cli"
        )
        with patch("ax.auth.oauth_client.requests.post") as post:
            post.return_value = _mock_response(
                200,
                {
                    "access_token": "a",
                    "refresh_token": "r",
                    "expires_in": 60,
                    "token_type": "Bearer",
                },
            )
            resp = client.exchange_code(
                code="abc", code_verifier="v", redirect_uri="u"
            )
        assert resp.user_email is None

    def test_http_error_propagates(self):
        import pytest
        import requests

        client = OAuthClient(
            base_url="https://app.arize.com", client_id="arize-cli"
        )
        with patch("ax.auth.oauth_client.requests.post") as post:
            post.return_value = _mock_response(400, {"error": "invalid_grant"})
            with pytest.raises(requests.HTTPError):
                client.exchange_code(
                    code="bad", code_verifier="v", redirect_uri="u"
                )


class TestRefresh:
    def test_sends_refresh_grant(self):
        client = OAuthClient(
            base_url="https://app.arize.com", client_id="arize-cli"
        )
        with patch("ax.auth.oauth_client.requests.post") as post:
            post.return_value = _mock_response(
                200,
                {
                    "access_token": "arz_at_new",
                    "refresh_token": "arz_rt_new",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            )
            resp = client.refresh(refresh_token="arz_rt_old")
        body = post.call_args.kwargs["data"]
        assert body["grant_type"] == "refresh_token"
        assert body["refresh_token"] == "arz_rt_old"
        assert body["client_id"] == "arize-cli"
        assert resp.access_token == "arz_at_new"
        assert resp.refresh_token == "arz_rt_new"


class TestRevoke:
    def test_swallows_network_errors(self):
        client = OAuthClient(
            base_url="https://app.arize.com", client_id="arize-cli"
        )
        with patch(
            "ax.auth.oauth_client.requests.post",
            side_effect=Exception("network down"),
        ):
            # Must NOT raise
            client.revoke(token="arz_rt_x")

    def test_swallows_non_200_without_raising(self):
        """RFC 7009 says revoke always returns 200, but if the server returns
        an error, we still don't raise — the local profile is cleared regardless.
        """
        client = OAuthClient(
            base_url="https://app.arize.com", client_id="arize-cli"
        )
        with patch("ax.auth.oauth_client.requests.post") as post:
            # Don't call raise_for_status in revoke — we want it to swallow.
            post.return_value = _mock_response(500, {"error": "server_error"})
            client.revoke(token="arz_rt_x")  # MUST NOT RAISE

    def test_sends_expected_body(self):
        client = OAuthClient(
            base_url="https://app.arize.com", client_id="arize-cli"
        )
        with patch("ax.auth.oauth_client.requests.post") as post:
            post.return_value = _mock_response(200, {})
            client.revoke(token="arz_rt_x")
        body = post.call_args.kwargs["data"]
        assert body["token"] == "arz_rt_x"
        assert body["client_id"] == "arize-cli"


class TestParseTokenResponseValidation:
    """Cover _parse_token_response failure modes via the public API."""

    def _bad_resp(self, *, json_side_effect=None, json_body=None, text=""):
        m = MagicMock()
        m.status_code = 200
        m.raise_for_status = lambda: None
        m.text = text
        if json_side_effect is not None:
            m.json.side_effect = json_side_effect
        else:
            m.json.return_value = json_body
        return m

    def test_non_json_response_raises_authentication_error(self):
        import pytest

        from ax.core.exceptions import AuthenticationError

        client = OAuthClient(
            base_url="https://app.arize.com", client_id="arize-cli"
        )
        with patch("ax.auth.oauth_client.requests.post") as post:
            post.return_value = self._bad_resp(
                json_side_effect=ValueError("not json"), text="<html>500</html>"
            )
            with pytest.raises(AuthenticationError, match="non-JSON response"):
                client.exchange_code(
                    code="c", code_verifier="v", redirect_uri="u"
                )

    def test_non_object_json_raises_authentication_error(self):
        import pytest

        from ax.core.exceptions import AuthenticationError

        client = OAuthClient(
            base_url="https://app.arize.com", client_id="arize-cli"
        )
        with patch("ax.auth.oauth_client.requests.post") as post:
            post.return_value = self._bad_resp(
                json_body=["not", "an", "object"]
            )
            with pytest.raises(AuthenticationError, match="not a JSON object"):
                client.refresh(refresh_token="rt")

    def test_missing_required_field_raises(self):
        import pytest

        from ax.core.exceptions import AuthenticationError

        client = OAuthClient(
            base_url="https://app.arize.com", client_id="arize-cli"
        )
        with patch("ax.auth.oauth_client.requests.post") as post:
            # Missing refresh_token
            post.return_value = self._bad_resp(
                json_body={"access_token": "a", "expires_in": 60}
            )
            with pytest.raises(
                AuthenticationError,
                match="missing required field 'refresh_token'",
            ):
                client.exchange_code(
                    code="c", code_verifier="v", redirect_uri="u"
                )

    def test_wrong_type_field_raises(self):
        import pytest

        from ax.core.exceptions import AuthenticationError

        client = OAuthClient(
            base_url="https://app.arize.com", client_id="arize-cli"
        )
        with patch("ax.auth.oauth_client.requests.post") as post:
            post.return_value = self._bad_resp(
                json_body={
                    "access_token": 123,
                    "refresh_token": "r",
                    "expires_in": 60,
                }
            )
            with pytest.raises(
                AuthenticationError, match="'access_token' has wrong type"
            ):
                client.refresh(refresh_token="rt")

    def test_non_integer_expires_in_raises(self):
        import pytest

        from ax.core.exceptions import AuthenticationError

        client = OAuthClient(
            base_url="https://app.arize.com", client_id="arize-cli"
        )
        with patch("ax.auth.oauth_client.requests.post") as post:
            post.return_value = self._bad_resp(
                json_body={
                    "access_token": "a",
                    "refresh_token": "r",
                    "expires_in": "soon",
                }
            )
            with pytest.raises(
                AuthenticationError, match="'expires_in' is not an integer"
            ):
                client.exchange_code(
                    code="c", code_verifier="v", redirect_uri="u"
                )

    def test_string_expires_in_is_accepted(self):
        """Some IdPs return expires_in as a string — coerce, don't reject."""
        client = OAuthClient(
            base_url="https://app.arize.com", client_id="arize-cli"
        )
        with patch("ax.auth.oauth_client.requests.post") as post:
            post.return_value = _mock_response(
                200,
                {
                    "access_token": "a",
                    "refresh_token": "r",
                    "expires_in": "3600",
                },
            )
            resp = client.refresh(refresh_token="rt")
        assert resp.expires_in == 3600
