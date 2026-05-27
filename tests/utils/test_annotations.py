"""Tests for the parse_annotations() helper."""

import json
from pathlib import Path

import pytest
import typer
from arize.datasets.types import AnnotateRecordInput

from ax.utils.annotations import parse_annotations

_VALID_ITEM = {
    "record_id": "rec-1",
    "values": [{"name": "quality", "score": 0.9}],
}


class TestParseAnnotations:
    """Tests for parse_annotations()."""

    def test_no_file_raises(self) -> None:
        """Providing no file raises BadParameter."""
        with pytest.raises(typer.BadParameter, match="--file"):
            parse_annotations(None)

    def test_valid_file_returns_list(self, tmp_path: Path) -> None:
        """A valid JSON file is parsed into AnnotateRecordInput objects."""
        f = tmp_path / "annotations.json"
        f.write_text(json.dumps([_VALID_ITEM]))
        result = parse_annotations(str(f))
        assert len(result) == 1
        assert isinstance(result[0], AnnotateRecordInput)
        assert result[0].record_id == "rec-1"

    def test_multiple_records(self, tmp_path: Path) -> None:
        """Multiple records are all parsed."""
        items = [
            {"record_id": f"r{i}", "values": [{"name": "q"}]} for i in range(3)
        ]
        f = tmp_path / "annotations.json"
        f.write_text(json.dumps(items))
        result = parse_annotations(str(f))
        assert len(result) == 3
        assert result[1].record_id == "r1"
