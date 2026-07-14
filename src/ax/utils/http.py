"""HTTP download utilities."""

import ssl
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import BinaryIO, cast
from urllib.parse import urlparse

from ax.core.exceptions import FileIOError
from ax.core.network import NetworkSettings


def unverified_ssl_context() -> ssl.SSLContext:
    """Return an SSLContext with certificate verification disabled."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def open_url(
    url: str,
    *,
    timeout: int | float,
    network: NetworkSettings | None = None,
) -> BinaryIO:
    """Open an HTTP(S) URL with the shared proxy and TLS policy."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise FileIOError(
            f"URL scheme must be http or https, got {parsed.scheme!r}"
        )
    settings = network or NetworkSettings.from_environment()
    handlers: list[urllib.request.BaseHandler] = [
        urllib.request.HTTPSHandler(context=settings.ssl_context()),
    ]
    if proxy_url := settings.proxy_for(url):
        handlers.append(
            urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        )
    elif settings.proxy_url or settings.bypasses(url):
        # A proxy is configured but this URL must not use it: force a
        # direct connection instead of falling back to system discovery.
        handlers.append(urllib.request.ProxyHandler({}))
    # Otherwise install no ProxyHandler so build_opener keeps urllib's
    # default discovery (env vars plus macOS/Windows OS proxy settings).
    opener = urllib.request.build_opener(*handlers)
    return cast("BinaryIO", opener.open(url, timeout=timeout))


def download_url(
    url: str,
    dest: Path,
    *,
    timeout: int = 30,
    verify: bool | None = None,
    network: NetworkSettings | None = None,
) -> Path:
    """Download a URL to a local file.

    Args:
        url: URL to download
        dest: Destination file path
        timeout: Request timeout in seconds
        verify: Explicit TLS-verification override. When None, the policy
          carried by *network* applies unchanged.
        network: Resolved proxy and TLS settings. When omitted, uses system env.

    Returns:
        Path to the downloaded file

    Raises:
        FileIOError: If the download fails
    """
    try:
        settings = network or NetworkSettings.from_environment()
        if verify is not None and settings.request_verify != verify:
            settings = replace(settings, request_verify=verify)
        with open_url(url, timeout=timeout, network=settings) as response:
            dest.write_bytes(response.read())
    except Exception as e:
        raise FileIOError(f"Failed to download {url}: {e}") from e
    return dest
