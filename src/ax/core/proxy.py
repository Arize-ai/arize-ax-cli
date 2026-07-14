"""Small, transport-independent helpers for HTTP CONNECT proxy URLs."""

from urllib.parse import urlparse


def is_http_connect_proxy_url(value: str) -> bool:
    """Return whether *value* is a usable ``http://host:port`` proxy URL."""
    parsed = urlparse(value)
    if parsed.scheme != "http" or not parsed.hostname:
        return False
    try:
        port = parsed.port
    except ValueError:
        return False
    return port is not None and 1 <= port <= 65535
