"""Background version check for the ax CLI."""

from __future__ import annotations

import contextlib
import json
import threading
import time
import urllib.request
from typing import TYPE_CHECKING

from packaging.version import Version

from ax.config.manager import ConfigManager
from ax.utils.http import unverified_ssl_context
from ax.version import __version__

if TYPE_CHECKING:
    import ssl
    from pathlib import Path

PYPI_TIMEOUT = 3
_PYPI_URL = "https://pypi.org/pypi/arize-ax-cli/json"
_DEFAULT_CACHE_PATH = ConfigManager.CONFIG_DIR / ".upgrade_check"

_lock = threading.Lock()
_should_upgrade: bool = False


def start_background_check(
    enabled: bool,
    interval_hours: float,
    request_verify: bool = True,
) -> threading.Thread | None:
    """Start a daemon thread to check PyPI for a newer ax version.

    Args:
        enabled: Whether to run the check at all.
        interval_hours: Minimum hours between PyPI fetches.
        request_verify: Whether to verify SSL certificates.

    Returns:
        The started thread, or None if the check is disabled.
    """
    if not enabled:
        return None

    thread = threading.Thread(
        target=_run_check,
        kwargs={
            "interval_hours": interval_hours,
            "cache_path": _DEFAULT_CACHE_PATH,
            "request_verify": request_verify,
        },
        daemon=True,
        name="ax-upgrade-check",
    )
    thread.start()
    return thread


def should_upgrade() -> bool:
    """Return True if a newer version of ax is available on PyPI.

    Returns:
        True if an upgrade is available, False otherwise.
    """
    with _lock:
        return _should_upgrade


def _make_ssl_context(verify: bool) -> ssl.SSLContext | None:
    """Return an unverified SSL context when verify is False, else None.

    Args:
        verify: Whether SSL certificates should be verified.

    Returns:
        An unverified SSLContext, or None to use the default verified context.
    """
    return None if verify else unverified_ssl_context()


def fetch_pypi_version(request_verify: bool = True) -> str | None:
    """Fetch the latest arize-ax-cli version from PyPI.

    Args:
        request_verify: Whether to verify SSL certificates.

    Returns:
        Version string from PyPI, or None on any failure.
    """
    try:
        with urllib.request.urlopen(  # noqa: S310
            _PYPI_URL,
            timeout=PYPI_TIMEOUT,
            context=_make_ssl_context(request_verify),
        ) as resp:
            data = json.loads(resp.read())
            return str(data["info"]["version"])
    except Exception:
        return None


def _run_check(
    interval_hours: float,
    cache_path: Path,
    request_verify: bool = True,
) -> None:
    """Thread target: read cache, set upgrade flag if newer version known, fetch if stale.

    Args:
        interval_hours: Minimum hours between PyPI fetches.
        cache_path: Path to the JSON cache file.
        request_verify: Whether to verify SSL certificates.
    """
    global _should_upgrade
    try:
        cache = _read_cache(cache_path)
        now = time.time()

        # Warn immediately from cached result if already known
        cached_latest = cache.get("latest_version") if cache else None
        if cached_latest and Version(str(cached_latest)) > Version(__version__):
            with _lock:
                _should_upgrade = True

        # Skip fetch if cache is fresh
        last_check = float(cache.get("last_check", 0.0)) if cache else 0.0  # type: ignore[arg-type]
        stale = now - last_check > interval_hours * 3600
        if not stale:
            return

        # Fetch and update cache
        latest = fetch_pypi_version(request_verify)
        if latest is None:
            return

        _write_cache(cache_path, {"last_check": now, "latest_version": latest})
        if Version(latest) > Version(__version__):
            with _lock:
                _should_upgrade = True

    except Exception:  # noqa: S110
        pass


def _read_cache(path: Path) -> dict[str, object] | None:
    """Read JSON cache file; delete and return None if missing or corrupt.

    Args:
        path: Path to the cache file.

    Returns:
        Parsed cache dict, or None.
    """
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[return-value]
    except (json.JSONDecodeError, OSError):
        with contextlib.suppress(OSError):
            path.unlink()
        return None


def _write_cache(path: Path, data: dict[str, object]) -> None:
    """Write JSON cache file, creating parent directories as needed.

    Args:
        path: Path to the cache file.
        data: Data to serialize.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass
