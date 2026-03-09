"""Tests for export utility functions."""

import json
from pathlib import Path

from pydantic import BaseModel

from ax.utils.export import (
    _ensure_gitignored,
    make_export_dir,
    print_json_array,
    write_json_array,
)


class _FakeModel(BaseModel):
    """Minimal Pydantic model for testing serialization."""

    id: str
    value: int
    optional: str | None = None


class TestMakeExportDir:
    """Tests for make_export_dir."""

    def test_creates_directory(self, tmp_path: Path) -> None:
        """Test that the directory is created."""
        result = make_export_dir(str(tmp_path), "trace", "abc123")
        assert result.exists()
        assert result.is_dir()

    def test_directory_name_contains_prefix_and_id(
        self, tmp_path: Path
    ) -> None:
        """Test that the directory name includes prefix and sanitised ID."""
        result = make_export_dir(str(tmp_path), "trace", "abc123")
        assert result.name.startswith("trace_abc123_")

    def test_slashes_in_id_are_replaced(self, tmp_path: Path) -> None:
        """Test that forward slashes in the ID are replaced with underscores."""
        result = make_export_dir(str(tmp_path), "session", "a/b/c")
        assert "/" not in result.name
        assert "a_b_c" in result.name

    def test_long_id_is_truncated(self, tmp_path: Path) -> None:
        """Test that IDs longer than 50 chars are truncated."""
        long_id = "x" * 100
        result = make_export_dir(str(tmp_path), "span", long_id)
        # prefix + underscore + truncated id + underscore + timestamp
        id_part = result.name.split("_", 1)[1].rsplit("_", 2)[0]
        assert len(id_part) <= 50

    def test_creates_nested_parents(self, tmp_path: Path) -> None:
        """Test that intermediate directories are created."""
        deep = tmp_path / "a" / "b" / "c"
        result = make_export_dir(str(deep), "trace", "id1")
        assert result.exists()

    def test_exist_ok_on_same_timestamp(self, tmp_path: Path) -> None:
        """Test that calling twice in the same second does not raise (exist_ok=True)."""
        result1 = make_export_dir(str(tmp_path), "trace", "same")
        result2 = make_export_dir(str(tmp_path), "trace", "same")
        assert result1.exists()
        assert result2.exists()


class TestEnsureGitignored:
    """Tests for _ensure_gitignored."""

    def test_adds_entry_when_missing(self, tmp_path: Path) -> None:
        """Creates .gitignore with the traces entry when none exists."""
        (tmp_path / ".git").mkdir()
        traces_dir = tmp_path / ".arize-tmp-traces" / "sub"
        traces_dir.mkdir(parents=True)
        _ensure_gitignored(traces_dir)
        gitignore = tmp_path / ".gitignore"
        assert ".arize-tmp-traces/" in gitignore.read_text().splitlines()

    def test_does_not_duplicate_entry(self, tmp_path: Path) -> None:
        """Skips adding the entry if .gitignore already contains it."""
        (tmp_path / ".git").mkdir()
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\n.arize-tmp-traces/\n")
        traces_dir = tmp_path / ".arize-tmp-traces" / "sub"
        traces_dir.mkdir(parents=True)
        _ensure_gitignored(traces_dir)
        assert gitignore.read_text().count(".arize-tmp-traces/") == 1

    def test_no_op_for_unrelated_dir(self, tmp_path: Path) -> None:
        """Does nothing when the directory is not under .arize-tmp-traces."""
        (tmp_path / ".git").mkdir()
        other_dir = tmp_path / "other-output" / "sub"
        other_dir.mkdir(parents=True)
        _ensure_gitignored(other_dir)
        assert not (tmp_path / ".gitignore").exists()

    def test_appends_newline_if_file_lacks_trailing_newline(
        self, tmp_path: Path
    ) -> None:
        """Inserts a newline before the entry if file has no trailing newline."""
        (tmp_path / ".git").mkdir()
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/")  # no trailing newline
        traces_dir = tmp_path / ".arize-tmp-traces"
        traces_dir.mkdir()
        _ensure_gitignored(traces_dir)
        lines = gitignore.read_text().splitlines()
        assert lines == ["node_modules/", ".arize-tmp-traces/"]

    def test_make_export_dir_triggers_gitignore(self, tmp_path: Path) -> None:
        """make_export_dir auto-creates the .gitignore entry."""
        (tmp_path / ".git").mkdir()
        traces_dir = tmp_path / ".arize-tmp-traces"
        make_export_dir(str(traces_dir), "trace", "abc123")
        gitignore = tmp_path / ".gitignore"
        assert gitignore.exists()
        assert ".arize-tmp-traces/" in gitignore.read_text().splitlines()


class TestWriteJsonArray:
    """Tests for write_json_array."""

    def test_writes_json_file(self, tmp_path: Path) -> None:
        """Test that a valid JSON file is written."""
        items = [_FakeModel(id="a", value=1), _FakeModel(id="b", value=2)]
        file_path = write_json_array(tmp_path, "out.json", items)

        assert file_path.exists()
        data = json.loads(file_path.read_text())
        assert len(data) == 2
        assert data[0] == {"id": "a", "value": 1}
        assert data[1] == {"id": "b", "value": 2}

    def test_excludes_none_fields(self, tmp_path: Path) -> None:
        """Test that None fields are excluded from output."""
        items = [_FakeModel(id="c", value=3, optional=None)]
        file_path = write_json_array(tmp_path, "out.json", items)
        data = json.loads(file_path.read_text())
        assert "optional" not in data[0]

    def test_includes_set_optional_fields(self, tmp_path: Path) -> None:
        """Test that explicitly set optional fields are included."""
        items = [_FakeModel(id="d", value=4, optional="yes")]
        file_path = write_json_array(tmp_path, "out.json", items)
        data = json.loads(file_path.read_text())
        assert data[0]["optional"] == "yes"

    def test_empty_list_writes_empty_array(self, tmp_path: Path) -> None:
        """Test that an empty list produces an empty JSON array."""
        file_path = write_json_array(tmp_path, "empty.json", [])
        data = json.loads(file_path.read_text())
        assert data == []

    def test_returns_correct_path(self, tmp_path: Path) -> None:
        """Test that the returned path points to the written file."""
        file_path = write_json_array(tmp_path, "check.json", [])
        assert file_path == tmp_path / "check.json"


class TestPrintJsonArray:
    """Tests for print_json_array."""

    def test_prints_json_to_stdout(self, capsys: object) -> None:
        """Test that JSON is printed to stdout."""
        items = [_FakeModel(id="e", value=5)]
        print_json_array(items)
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        data = json.loads(captured.out)
        assert data == [{"id": "e", "value": 5}]

    def test_empty_list_prints_empty_array(self, capsys: object) -> None:
        """Test that an empty list prints []."""
        print_json_array([])
        captured = capsys.readouterr()  # type: ignore[attr-defined]
        data = json.loads(captured.out)
        assert data == []
