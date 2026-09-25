"""HTTP download utilities."""

import ssl
import urllib.request
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

from ax.core.exceptions import FileIOError


def unverified_ssl_context() -> ssl.SSLContext:
    """Return an SSLContext with certificate verification disabled."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def verified_ssl_context() -> ssl.SSLContext:
    """Return an SSLContext trusting both the platform store and certifi.

    The two sources are additive on purpose, because either can be the only one
    that works:

    * truststore makes the Windows and macOS certificate stores available to
      Python, where a corporate root can be installed.
    * certifi provides the public roots required by standalone Python builds.

    Loading both means a download works whether the certificate chains to a
    public root or an internal one.
    """
    try:
        import truststore

        ctx = cast(
            "ssl.SSLContext",
            truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
        )
    except ImportError:
        ctx = ssl.create_default_context()
    try:
        import certifi

        ctx.load_verify_locations(cafile=certifi.where())
    # Swallowed deliberately: certifi is an addition to whatever the platform
    # already trusts, so failing to load it must not stop a download that the
    # platform store alone can verify.
    except Exception:  # noqa: S110
        pass
    return ctx


def download_url(
    url: str,
    dest: Path,
    *,
    timeout: int = 30,
    verify: bool = True,
) -> Path:
    """Download a URL to a local file.

    Args:
        url: URL to download
        dest: Destination file path
        timeout: Request timeout in seconds
        verify: Whether to verify SSL certificates

    Returns:
        Path to the downloaded file

    Raises:
        FileIOError: If the download fails
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise FileIOError(
            f"URL scheme must be http or https, got {parsed.scheme!r}"
        )
    try:
        context = verified_ssl_context() if verify else unverified_ssl_context()
        with urllib.request.urlopen(  # noqa: S310
            url, timeout=timeout, context=context
        ) as response:
            dest.write_bytes(response.read())
    except Exception as e:
        raise FileIOError(f"Failed to download {url}: {e}") from e
    return dest
