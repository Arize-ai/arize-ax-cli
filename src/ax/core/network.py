"""Shared outbound-network configuration for every AX CLI transport."""

from __future__ import annotations

import os
import ssl
from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from pathlib import Path
from urllib.parse import urlparse

from ax.config.schema import NetworkConfig, ProxyMode
from ax.core.exceptions import ConfigError

_PROXY_ENV_VARS = (
    "ARIZE_PROXY_URL",
    "https_proxy",
    "HTTPS_PROXY",
    "http_proxy",
    "HTTP_PROXY",
    "all_proxy",
    "ALL_PROXY",
)
_NO_PROXY_ENV_VARS = ("no_proxy", "NO_PROXY")
_CA_BUNDLE_ENV_VARS = (
    "ARIZE_SSL_CA_CERT",
    "REQUESTS_CA_BUNDLE",
    "SSL_CERT_FILE",
)
_GRPC_PROXY_ENV = "grpc_proxy"
_NO_GRPC_PROXY_ENV = "no_grpc_proxy"


def _split_no_proxy_host_port(entry: str) -> tuple[str, int | None]:
    """Split a no_proxy entry into host/CIDR and an optional numeric port."""
    if entry.startswith("["):
        closing = entry.find("]")
        if closing != -1:
            host = entry[1:closing]
            remainder = entry[closing + 1 :]
            if remainder.startswith(":") and remainder[1:].isdigit():
                return host, int(remainder[1:])
            return host, None
    if entry.count(":") == 1:
        host, possible_port = entry.rsplit(":", maxsplit=1)
        if possible_port.isdigit():
            return host, int(possible_port)
    return entry, None


def _expand_environment_reference(value: str) -> str:
    """Expand a profile ``${NAME}`` value when a raw profile is in use."""
    if not (value.startswith("${") and value.endswith("}")):
        return value
    name = value[2:-1]
    if ":" in name:
        name, default = name.split(":", maxsplit=1)
    else:
        default = ""
    resolved = os.environ.get(name, default).strip()
    if not resolved:
        raise ConfigError(f"Environment variable {name!r} is not set.")
    return resolved


def _first_environment_value(names: tuple[str, ...]) -> str:
    """Return the first non-empty value among *names*."""
    for name in names:
        if value := os.environ.get(name, "").strip():
            return value
    return ""


def _validate_proxy_url(proxy_url: str) -> str:
    """Validate and return an HTTP CONNECT proxy URL.

    gRPC supports HTTP CONNECT proxies and urllib3 supports the same URL form.
    Limiting the shared setting to ``http://`` keeps Flight, OTLP, and REST
    behavior identical.
    """
    if not proxy_url:
        return ""
    parsed = urlparse(proxy_url)
    if parsed.scheme != "http" or not parsed.hostname:
        raise ConfigError(
            "Proxy URL must use the form 'http://[user:password@]host:port'."
        )
    return proxy_url


@dataclass(frozen=True)
class NetworkSettings:
    """Resolved proxy, bypass, and TLS settings for one CLI invocation."""

    proxy_url: str = ""
    no_proxy: str = ""
    ca_bundle: str = ""
    request_verify: bool = True
    override_grpc_proxy: bool = True
    override_grpc_no_proxy: bool = True

    @classmethod
    def from_config(
        cls, config: NetworkConfig, *, request_verify: bool
    ) -> NetworkSettings:
        """Resolve profile settings and supported system environment variables."""
        if config.proxy_mode == ProxyMode.URL:
            proxy_url = _expand_environment_reference(config.proxy_url)
            if not proxy_url:
                raise ConfigError(
                    "network.proxy_mode='url' requires network.proxy_url."
                )
        else:
            proxy_url = _first_environment_value(_PROXY_ENV_VARS)

        configured_no_proxy = _expand_environment_reference(config.no_proxy)
        no_proxy = configured_no_proxy or _first_environment_value(
            _NO_PROXY_ENV_VARS
        )
        ca_bundle = _expand_environment_reference(config.ca_bundle)
        ca_bundle = ca_bundle or _first_environment_value(_CA_BUNDLE_ENV_VARS)
        if ca_bundle and not Path(ca_bundle).is_file():
            raise ConfigError(
                "Configured CA bundle path does not exist or is not a file."
            )

        return cls(
            proxy_url=_validate_proxy_url(proxy_url),
            no_proxy=no_proxy,
            ca_bundle=ca_bundle,
            request_verify=request_verify,
            override_grpc_proxy=config.proxy_mode == ProxyMode.URL,
            override_grpc_no_proxy=bool(configured_no_proxy),
        )

    @classmethod
    def from_environment(cls) -> NetworkSettings:
        """Resolve system proxy settings when no AX profile is available."""
        return cls.from_config(NetworkConfig(), request_verify=True)

    @property
    def verify_value(self) -> bool | str:
        """Return the value accepted by requests for TLS verification."""
        if not self.request_verify:
            return False
        return self.ca_bundle or True

    def bypasses(self, url: str) -> bool:
        """Return whether *url* must avoid the configured proxy."""
        parsed = urlparse(url)
        if not parsed.hostname or not self.no_proxy:
            return False
        host = parsed.hostname.lower().rstrip(".")
        if self.no_proxy.strip() == "*":
            return True

        try:
            host_ip = ip_address(host)
        except ValueError:
            host_ip = None

        host_port = f"{host}:{parsed.port}" if parsed.port else host
        for entry in self.no_proxy.split(","):
            candidate = entry.strip().lower()
            if not candidate:
                continue
            candidate, candidate_port = _split_no_proxy_host_port(candidate)
            if candidate_port is not None and candidate_port != parsed.port:
                continue
            if host_ip is not None:
                try:
                    if host_ip in ip_network(candidate, strict=False):
                        return True
                    continue
                except ValueError:
                    if candidate.strip("[]") == host:
                        return True

            candidate = candidate.lstrip(".").rstrip(".")
            if (
                host == candidate
                or host_port == candidate
                or host.endswith(f".{candidate}")
                or host_port.endswith(f".{candidate}")
            ):
                return True
        return False

    def proxy_for(self, url: str) -> str:
        """Return the proxy URL for *url*, or an empty string for direct access."""
        if not self.proxy_url or self.bypasses(url):
            return ""
        return self.proxy_url

    def requests_proxies(self, url: str) -> dict[str, str]:
        """Return explicit Requests proxies for *url* without env inheritance."""
        if not (proxy_url := self.proxy_for(url)):
            return {}
        return {"http": proxy_url, "https": proxy_url}

    def ssl_context(self) -> ssl.SSLContext:
        """Create the SSL context for urllib-based downloads."""
        if not self.request_verify:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            return context
        return ssl.create_default_context(cafile=self.ca_bundle or None)

    def configure_grpc_environment(self) -> None:
        """Normalize the proxy settings consumed by gRPC C-Core transports.

        The SDK creates Arrow Flight and OTLP channels internally. Those native
        transports honor ``grpc_proxy`` and ``no_grpc_proxy`` at channel creation,
        so set their process-local values before constructing the SDK client.
        """
        if self.override_grpc_proxy:
            if self.proxy_url:
                os.environ[_GRPC_PROXY_ENV] = self.proxy_url
            else:
                os.environ.pop(_GRPC_PROXY_ENV, None)

        if self.override_grpc_no_proxy:
            if self.no_proxy:
                os.environ[_NO_GRPC_PROXY_ENV] = self.no_proxy
            else:
                os.environ.pop(_NO_GRPC_PROXY_ENV, None)

        if self.ca_bundle:
            os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = self.ca_bundle
            os.environ["OTEL_EXPORTER_OTLP_CERTIFICATE"] = self.ca_bundle
            os.environ["OTEL_EXPORTER_OTLP_TRACES_CERTIFICATE"] = self.ca_bundle

    def redacted_proxy_url(self) -> str:
        """Return a display-safe representation of the configured proxy URL."""
        if not self.proxy_url:
            return ""
        parsed = urlparse(self.proxy_url)
        if parsed.password is None:
            return self.proxy_url
        username = parsed.username or ""
        host = parsed.hostname or ""
        try:
            port = f":{parsed.port}" if parsed.port else ""
        except ValueError:
            authority = parsed.netloc.rsplit("@", maxsplit=1)[-1]
            return f"{parsed.scheme}://{username}:***@{authority}"
        return f"{parsed.scheme}://{username}:***@{host}{port}"
