"""Tests for resolving the TLS settings used by the CLI's own HTTP calls."""

import os
from pathlib import Path

import pytest

from ax.config.schema import SecurityConfig
from ax.config.tls import TLSSettings, resolve_tls
from ax.core.exceptions import ConfigError

_PEM_KEY = (
    "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n"
    "-----END PRIVATE KEY-----\n"
)
_TLS_ENV_VARS = (
    "ARIZE_CLIENT_CERT",
    "ARIZE_CLIENT_KEY",
    "ARIZE_SSL_CA_CERT",
    "REQUESTS_CA_BUNDLE",
    "SSL_CERT_FILE",
)


@pytest.fixture(autouse=True)
def _clear_tls_env(monkeypatch):
    for name in _TLS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def cert_pair(tmp_path: Path) -> tuple[str, str]:
    cert = tmp_path / "client.crt"
    key = tmp_path / "client.key"
    cert.write_text("-----BEGIN CERTIFICATE-----\nAA==\n")
    key.write_text(_PEM_KEY)
    os.chmod(key, 0o600)
    return str(cert), str(key)


@pytest.mark.unit
class TestResolveTls:
    def test_defaults_verify_with_system_roots_and_no_cert(self):
        assert resolve_tls(SecurityConfig()) == TLSSettings(
            verify=True, cert=None
        )

    def test_profile_cert_pair_is_presented(self, cert_pair):
        cert, key = cert_pair
        tls = resolve_tls(SecurityConfig(client_cert=cert, client_key=key))
        assert tls.cert == (cert, key)

    def test_env_var_references_are_expanded(self, cert_pair, monkeypatch):
        cert, key = cert_pair
        monkeypatch.setenv("MY_CERT", cert)
        monkeypatch.setenv("MY_KEY", key)
        tls = resolve_tls(
            SecurityConfig(client_cert="${MY_CERT}", client_key="${MY_KEY}")
        )
        assert tls.cert == (cert, key)

    def test_falls_back_to_sdk_env_vars(self, cert_pair, monkeypatch):
        cert, key = cert_pair
        monkeypatch.setenv("ARIZE_CLIENT_CERT", cert)
        monkeypatch.setenv("ARIZE_CLIENT_KEY", key)
        assert resolve_tls(SecurityConfig()).cert == (cert, key)

    def test_profile_pair_wins_over_env(self, cert_pair, tmp_path, monkeypatch):
        cert, key = cert_pair
        monkeypatch.setenv("ARIZE_CLIENT_CERT", str(tmp_path / "other.crt"))
        tls = resolve_tls(SecurityConfig(client_cert=cert, client_key=key))
        assert tls.cert == (cert, key)

    def test_tilde_is_expanded(self, cert_pair, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        tls = resolve_tls(
            SecurityConfig(
                client_cert="~/client.crt", client_key="~/client.key"
            )
        )
        assert tls.cert == cert_pair

    @pytest.mark.parametrize("missing", ["client_cert", "client_key"])
    def test_one_of_the_pair_raises(self, cert_pair, missing):
        cert, key = cert_pair
        values = {"client_cert": cert, "client_key": key}
        values[missing] = ""
        with pytest.raises(ConfigError, match=r"\[security\] section"):
            resolve_tls(SecurityConfig(**values))

    def test_pem_content_is_rejected_without_echo(self, cert_pair):
        cert, _ = cert_pair
        with pytest.raises(ConfigError) as exc:
            resolve_tls(SecurityConfig(client_cert=cert, client_key=_PEM_KEY))
        message = str(exc.value)
        assert "path to a PEM file" in message
        assert "MIIEvQ" not in message
        assert "BEGIN" not in message

    def test_pem_content_in_ssl_ca_cert_is_rejected_without_echo(self):
        with pytest.raises(ConfigError) as exc:
            resolve_tls(SecurityConfig(ssl_ca_cert=_PEM_KEY))
        message = str(exc.value)
        assert "ssl_ca_cert must be a path to a PEM file" in message
        assert "MIIEvQ" not in message

    def test_file_checks_are_left_to_the_sdk_and_requests(self, tmp_path):
        missing = (str(tmp_path / "nope.crt"), str(tmp_path / "nope.key"))
        tls = resolve_tls(
            SecurityConfig(client_cert=missing[0], client_key=missing[1])
        )
        assert tls.cert == missing

    def test_ca_cert_becomes_verify_path(self, tmp_path):
        ca = tmp_path / "ca.pem"
        ca.write_text("ca")
        tls = resolve_tls(SecurityConfig(ssl_ca_cert=str(ca)))
        assert tls.verify == str(ca)

    def test_ca_cert_falls_back_to_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(tmp_path / "ca.pem"))
        assert resolve_tls(SecurityConfig()).verify == str(tmp_path / "ca.pem")

    def test_request_verify_false_overrides_ca_cert(self, tmp_path):
        tls = resolve_tls(
            SecurityConfig(
                request_verify=False, ssl_ca_cert=str(tmp_path / "ca.pem")
            )
        )
        assert tls.verify is False

    def test_request_verify_env_reference_is_expanded(self, monkeypatch):
        monkeypatch.setenv("ARIZE_REQUEST_VERIFY", "false")
        tls = resolve_tls(
            SecurityConfig(request_verify="${ARIZE_REQUEST_VERIFY}")
        )
        assert tls.verify is False

    def test_unset_env_reference_raises_config_error(self):
        with pytest.raises(ConfigError, match="MY_UNSET_CERT"):
            resolve_tls(
                SecurityConfig(
                    client_cert="${MY_UNSET_CERT}", client_key="/k.pem"
                )
            )
