"""URL helpers for instrumentation onboarding."""

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

UTM_SOURCE = "axcli"


def with_utm(url: str) -> str:
    """Add AX's source parameter to an HTTP(S) URL, idempotently."""
    try:
        parts = urlparse(url)
    except ValueError:
        return url
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return url

    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("utm_source", UTM_SOURCE)
    return urlunparse(parts._replace(query=urlencode(query)))
