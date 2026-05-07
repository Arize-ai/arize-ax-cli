"""Tests for ax.utils.text_source."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ax.core.exceptions import UsageError
from ax.utils.text_source import load_text_source

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
def test_inline_value_passes_through() -> None:
    """Values without a leading '@' are returned unchanged."""
    source = "def evaluate(): return 1"
    assert load_text_source(source, "--code") == source


@pytest.mark.unit
def test_at_prefix_reads_utf8_file(tmp_path: Path) -> None:
    """'@path' reads the file as UTF-8."""
    path = tmp_path / "ev.py"
    path.write_text("class MyEval: ...\n", encoding="utf-8")
    assert load_text_source(f"@{path}", "--code") == "class MyEval: ...\n"


@pytest.mark.unit
def test_at_prefix_missing_file_raises(tmp_path: Path) -> None:
    """Missing '@path' file raises UsageError with the option name."""
    missing = tmp_path / "missing.py"
    with pytest.raises(UsageError, match="--code file not found"):
        load_text_source(f"@{missing}", "--code")


@pytest.mark.unit
def test_at_prefix_directory_raises(tmp_path: Path) -> None:
    """'@path' pointing at a directory raises UsageError."""
    with pytest.raises(UsageError, match="--imports path is not a file"):
        load_text_source(f"@{tmp_path}", "--imports")


@pytest.mark.unit
def test_inline_value_starting_with_at_not_supported() -> None:
    """Values with a leading '@' are always treated as file paths."""
    with pytest.raises(UsageError, match="file not found"):
        load_text_source("@this-is-definitely-not-a-real-path", "--code")
