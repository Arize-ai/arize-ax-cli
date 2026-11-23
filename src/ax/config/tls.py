"""TLS settings for the HTTP calls the CLI makes to Arize itself."""

import os
from dataclasses import dataclass

from arize.constants.config import (
    ENV_CLIENT_CERT,
    ENV_CLIENT_KEY,
    ENV_SSL_CA_CERT,
)

from ax.config.manager import _expand_env_var
from ax.config.schema import SecurityConfig, _str_to_bool
from ax.core.exceptions import ConfigError

_PEM_MARKER = "-----BEGIN"
_CA_ENV_VARS = (ENV_SSL_CA_CERT, "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE")


@dataclass(frozen=True)
class TLSSettings:
    """The ``verify`` and ``cert`` arguments for ``requests`` calls."""

    verify: bool | str = True
    cert: tuple[str, str] | None = None


def redact_pem(value: str) -> str:
    """Return ``value`` for display, hiding it when it holds PEM content."""
    if _PEM_MARKER in value:
        return "(PEM content; must be a file path)"
    return value


def _expand(value: str) -> str:
    try:
        return _expand_env_var(value)
    except ValueError as e:
        raise ConfigError(str(e)) from e


def _path(value: str) -> str:
    return os.path.expanduser(_expand(value).strip())


def resolve_tls(security: SecurityConfig) -> TLSSettings:
    """Resolve the profile's TLS settings, falling back to the SDK env vars.

    The precedence and validation match the SDK, so the CLI's own OAuth calls
    and the SDK client present the same certificate and trust the same CAs.

    Args:
        security: The profile's security section. ``${VAR}`` references are
            expanded.

    Returns:
        The resolved settings.

    Raises:
        ConfigError: If only one of client_cert/client_key is set, a value
            holds PEM content instead of a path, or a referenced env var is
            not set. File checks are left to the SDK and to ``requests``.
    """
    if security.client_cert or security.client_key:
        cert = _path(security.client_cert)
        key = _path(security.client_key)
    else:
        cert = _path(os.environ.get(ENV_CLIENT_CERT, ""))
        key = _path(os.environ.get(ENV_CLIENT_KEY, ""))
    if bool(cert) != bool(key):
        raise ConfigError(
            "client_cert and client_key must be set together (in the "
            f"profile's [security] section or as {ENV_CLIENT_CERT} and "
            f"{ENV_CLIENT_KEY})"
        )
    for field, value in (("client_cert", cert), ("client_key", key)):
        if _PEM_MARKER in value:
            raise ConfigError(
                f"{field} must be a path to a PEM file, not the PEM content"
            )

    ca = _path(security.ssl_ca_cert) or next(
        (
            os.environ[name].strip()
            for name in _CA_ENV_VARS
            if os.environ.get(name, "").strip()
        ),
        "",
    )
    if _PEM_MARKER in ca:
        raise ConfigError(
            "ssl_ca_cert must be a path to a PEM file, not the PEM content"
        )
    request_verify = security.request_verify
    if isinstance(request_verify, str):
        request_verify = _expand(request_verify)
    verify: bool | str = (ca or True) if _str_to_bool(request_verify) else False
    return TLSSettings(verify=verify, cert=(cert, key) if cert else None)
