"""HTTP download utilities."""

import ssl
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from ax.core.exceptions import FileIOError


def unverified_ssl_context() -> ssl.SSLContext:
    """Return an SSLContext with certificate verification disabled."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
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
        context = unverified_ssl_context() if not verify else None
        with urllib.request.urlopen(  # noqa: S310
            url, timeout=timeout, context=context
        ) as response:
            dest.write_bytes(response.read())
    except Exception as e:
        raise FileIOError(f"Failed to download {url}: {e}") from e
    return dest
