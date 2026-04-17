"""Tests for ax.utils.upgrade_check."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

import pytest

import ax.utils.upgrade_check as uc


@pytest.fixture(autouse=True)
def reset_upgrade_state() -> Generator[None, None, None]:
    """Reset module-level upgrade flag before and after each test."""
    with uc._lock:
        uc._should_upgrade = False
    yield
    with uc._lock:
        uc._should_upgrade = False


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_read_cache_missing(tmp_path: Path) -> None:
    """Missing cache file returns None."""
    assert uc._read_cache(tmp_path / ".upgrade_check") is None


@pytest.mark.unit
def test_read_cache_valid(tmp_path: Path) -> None:
    """Valid cache file is parsed correctly."""
    p = tmp_path / ".upgrade_check"
    p.write_text(
        json.dumps({"last_check": 1000.0, "latest_version": "0.14.0"}),
        encoding="utf-8",
    )
    result = uc._read_cache(p)
    assert result == {"last_check": 1000.0, "latest_version": "0.14.0"}


@pytest.mark.unit
def test_read_cache_corrupt_deletes_file(tmp_path: Path) -> None:
    """Corrupt cache file is deleted; None is returned."""
    p = tmp_path / ".upgrade_check"
    p.write_text("not-valid-json", encoding="utf-8")
    result = uc._read_cache(p)
    assert result is None
    assert not p.exists()


@pytest.mark.unit
def test_write_cache_creates_file_and_dirs(tmp_path: Path) -> None:
    """Cache file is created with correct content, including missing parent dirs."""
    p = tmp_path / "subdir" / ".upgrade_check"
    uc._write_cache(p, {"last_check": 9999.0, "latest_version": "1.0.0"})
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["last_check"] == 9999.0
    assert data["latest_version"] == "1.0.0"


# ---------------------------------------------------------------------------
# _run_check logic
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fresh_cache_skips_pypi_fetch(tmp_path: Path) -> None:
    """Cache younger than interval does not trigger a PyPI fetch."""
    p = tmp_path / ".upgrade_check"
    uc._write_cache(p, {"last_check": time.time(), "latest_version": "0.13.0"})

    with patch("ax.utils.upgrade_check.fetch_pypi_version") as mock_fetch:
        uc._run_check(interval_hours=6.0, cache_path=p)

    mock_fetch.assert_not_called()


@pytest.mark.unit
def test_stale_cache_triggers_pypi_fetch(tmp_path: Path) -> None:
    """Cache older than interval triggers a fresh PyPI fetch and updates file."""
    p = tmp_path / ".upgrade_check"
    uc._write_cache(
        p, {"last_check": time.time() - 7 * 3600, "latest_version": "0.13.0"}
    )

    with patch(
        "ax.utils.upgrade_check.fetch_pypi_version", return_value="0.14.0"
    ):
        uc._run_check(interval_hours=6.0, cache_path=p)

    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["latest_version"] == "0.14.0"


@pytest.mark.unit
def test_newer_version_sets_pending_warning(tmp_path: Path) -> None:
    """When PyPI has a newer version, _pending_warning is set."""
    p = tmp_path / ".upgrade_check"
    with (
        patch("ax.utils.upgrade_check.__version__", "0.13.0"),
        patch(
            "ax.utils.upgrade_check.fetch_pypi_version", return_value="0.14.0"
        ),
    ):
        uc._run_check(interval_hours=0.0, cache_path=p)

    assert uc.should_upgrade() is True


@pytest.mark.unit
def test_current_version_no_warning(tmp_path: Path) -> None:
    """When already on the latest version, no upgrade flag is set."""
    p = tmp_path / ".upgrade_check"
    with (
        patch("ax.utils.upgrade_check.__version__", "0.14.0"),
        patch(
            "ax.utils.upgrade_check.fetch_pypi_version", return_value="0.14.0"
        ),
    ):
        uc._run_check(interval_hours=0.0, cache_path=p)

    assert uc.should_upgrade() is False


@pytest.mark.unit
def test_network_failure_leaves_cache_unchanged(tmp_path: Path) -> None:
    """PyPI fetch failure does not update cache and does not raise."""
    p = tmp_path / ".upgrade_check"
    with patch("ax.utils.upgrade_check.fetch_pypi_version", return_value=None):
        uc._run_check(interval_hours=0.0, cache_path=p)

    assert not p.exists()
    assert uc.should_upgrade() is False


@pytest.mark.unit
def test_cached_newer_version_warns_without_fetch(tmp_path: Path) -> None:
    """A cached newer version sets warning even when no fetch is needed."""
    p = tmp_path / ".upgrade_check"
    uc._write_cache(p, {"last_check": time.time(), "latest_version": "0.14.0"})
    with (
        patch("ax.utils.upgrade_check.__version__", "0.13.0"),
        patch("ax.utils.upgrade_check.fetch_pypi_version") as mock_fetch,
    ):
        uc._run_check(interval_hours=6.0, cache_path=p)

    mock_fetch.assert_not_called()
    assert uc.should_upgrade() is True
