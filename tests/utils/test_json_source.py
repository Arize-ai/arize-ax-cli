"""Tests for ax.utils.json_source."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest
import typer

if TYPE_CHECKING:
    from pathlib import Path

from ax.utils.json_source import load_json


@pytest.mark.unit
def test_load_json_raw_text_from_file(tmp_path: Path) -> None:
    """Existing file path returns parsed JSON."""
    p = tmp_path / "data.json"
    p.write_text('{"a": 1}', encoding="utf-8")
    assert load_json(str(p)) == {"a": 1}


@pytest.mark.unit
def test_load_json_raw_text_directory_raises(tmp_path: Path) -> None:
    """Existing directory path is rejected."""
    d = tmp_path / "dir"
    d.mkdir()
    with pytest.raises(typer.BadParameter, match="Not a file"):
        load_json(str(d))


@pytest.mark.unit
def test_load_json_raw_text_inline() -> None:
    """Inline JSON string is parsed and returned as a Python object."""
    assert load_json(json.dumps([{"role": "user"}])) == [{"role": "user"}]


@pytest.mark.unit
def test_load_json_raw_text_missing_file_raises(tmp_path: Path) -> None:
    """Path-like value with no file raises BadParameter."""
    missing = str(tmp_path / "nope.json")
    with pytest.raises(typer.BadParameter, match="File not found"):
        load_json(missing)


@pytest.mark.skipif(
    os.name == "nt", reason="chmod-based unreadable file not portable"
)
@pytest.mark.unit
def test_load_json_raw_text_unreadable_file(tmp_path: Path) -> None:
    """BadParameter when the path is a file but cannot be read."""
    p = tmp_path / "secret.json"
    p.write_text("{}", encoding="utf-8")
    p.chmod(0o000)
    try:
        with pytest.raises(
            typer.BadParameter, match="Could not read JSON file"
        ):
            load_json(str(p))
    finally:
        p.chmod(0o644)
