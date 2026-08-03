"""Tests for dotenv API-key output utilities."""

from pathlib import Path
from unittest.mock import patch

import pytest

from ax.core.exceptions import FileIOError
from ax.utils.dotenv import write_api_key_to_dotenv


@pytest.mark.parametrize(
    "filename",
    [".env", ".env.local", ".env.development", ".env.production.local"],
)
def test_write_api_key_accepts_dotenv_filename_variants(
    tmp_path: Path, filename: str
) -> None:
    """Common dotenv filename variants are supported."""
    dotenv_path = tmp_path / filename

    write_api_key_to_dotenv(str(dotenv_path), "new-key")

    assert dotenv_path.read_text() == "ARIZE_API_KEY=new-key\n"


def test_write_api_key_appends_exported_quoted_assignment_for_envrc(
    tmp_path: Path,
) -> None:
    """A new .envrc assignment is exported and single-quoted for direnv."""
    envrc_path = tmp_path / ".envrc"

    write_api_key_to_dotenv(str(envrc_path), "new-key")

    assert envrc_path.read_text() == "export ARIZE_API_KEY='new-key'\n"


def test_write_api_key_appends_export_to_existing_envrc(
    tmp_path: Path,
) -> None:
    """An appended .envrc assignment is exported alongside other content."""
    envrc_path = tmp_path / ".envrc"
    envrc_path.write_text('export OTHER="value"\n')

    write_api_key_to_dotenv(str(envrc_path), "new-key")

    assert envrc_path.read_text() == (
        "export OTHER=\"value\"\nexport ARIZE_API_KEY='new-key'\n"
    )


def test_write_api_key_replaces_envrc_assignment_preserving_export(
    tmp_path: Path,
) -> None:
    """Replacing an exported .envrc assignment keeps export and quotes it."""
    envrc_path = tmp_path / ".envrc"
    envrc_path.write_text("export ARIZE_API_KEY='old-key'\n")

    write_api_key_to_dotenv(str(envrc_path), "new-key")

    assert envrc_path.read_text() == "export ARIZE_API_KEY='new-key'\n"


def test_write_api_key_upgrades_bare_envrc_assignment_to_export(
    tmp_path: Path,
) -> None:
    """A bare .envrc assignment is upgraded to export so direnv loads it."""
    envrc_path = tmp_path / ".envrc"
    envrc_path.write_text("ARIZE_API_KEY=old-key\n")

    write_api_key_to_dotenv(str(envrc_path), "new-key")

    assert envrc_path.read_text() == "export ARIZE_API_KEY='new-key'\n"


def test_write_api_key_normalizes_double_quoted_envrc_value(
    tmp_path: Path,
) -> None:
    """A double-quoted .envrc value is re-quoted with safe single quotes."""
    envrc_path = tmp_path / ".envrc"
    envrc_path.write_text('ARIZE_API_KEY="old"\n')

    write_api_key_to_dotenv(str(envrc_path), "$(touch pwned)")

    assert envrc_path.read_text() == ("export ARIZE_API_KEY='$(touch pwned)'\n")


def test_write_api_key_shell_escapes_envrc_value(
    tmp_path: Path,
) -> None:
    """Shell metacharacters in an .envrc value are quoted, never evaluated."""
    envrc_path = tmp_path / ".envrc"

    write_api_key_to_dotenv(str(envrc_path), "ab`touch pwned` cd")

    assert envrc_path.read_text() == (
        "export ARIZE_API_KEY='ab`touch pwned` cd'\n"
    )


def test_write_api_key_escapes_single_quote_in_envrc_value(
    tmp_path: Path,
) -> None:
    """An embedded single quote is escaped for a shell-sourced .envrc."""
    envrc_path = tmp_path / ".envrc"

    write_api_key_to_dotenv(str(envrc_path), "a'b")

    assert envrc_path.read_text() == "export ARIZE_API_KEY='a'\\''b'\n"


def test_write_api_key_replaces_assignment_without_changing_formatting(
    tmp_path: Path,
) -> None:
    """Replacement preserves export, quote style, comments, and CRLF lines."""
    dotenv_path = tmp_path / ".env.local"
    dotenv_path.write_bytes(
        b"# local settings\r\n"
        b"export ARIZE_API_KEY = 'old-value'  # rotate me\r\n"
        b"OTHER=value\r\n"
    )

    write_api_key_to_dotenv(str(dotenv_path), "new-key")

    assert dotenv_path.read_bytes() == (
        b"# local settings\r\n"
        b"export ARIZE_API_KEY = 'new-key'  # rotate me\r\n"
        b"OTHER=value\r\n"
    )


def test_write_api_key_replaces_all_duplicate_assignments(
    tmp_path: Path,
) -> None:
    """All active assignments are updated so a later one cannot override it."""
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "ARIZE_API_KEY=old-first\nOTHER=value\nARIZE_API_KEY=old-last\n"
    )

    write_api_key_to_dotenv(str(dotenv_path), "new-key")

    assert dotenv_path.read_text() == (
        "ARIZE_API_KEY=new-key\nOTHER=value\nARIZE_API_KEY=new-key\n"
    )


@pytest.mark.parametrize(
    ("initial", "expected"),
    [
        ("ARIZE_API_KEY=old  \n", "ARIZE_API_KEY=new-key  \n"),
        (
            'ARIZE_API_KEY="old"  \n',
            'ARIZE_API_KEY="new-key"  \n',
        ),
        (
            "ARIZE_API_KEY= # populated by deployment\n",
            "ARIZE_API_KEY= new-key # populated by deployment\n",
        ),
        (
            "ARIZE_API_KEY=old#not-a-comment\n",
            "ARIZE_API_KEY=new-key\n",
        ),
    ],
)
def test_write_api_key_preserves_trailing_whitespace_and_parses_comments(
    tmp_path: Path, initial: str, expected: str
) -> None:
    """Only whitespace-prefixed hashes are comments; other formatting remains."""
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(initial)

    write_api_key_to_dotenv(str(dotenv_path), "new-key")

    assert dotenv_path.read_text() == expected


@pytest.mark.parametrize(
    ("initial", "expected"),
    [
        ("", "ARIZE_API_KEY=new-key\n"),
        ("OTHER=value\n", "OTHER=value\nARIZE_API_KEY=new-key\n"),
        ("OTHER=value", "OTHER=value\nARIZE_API_KEY=new-key\n"),
    ],
)
def test_write_api_key_appends_with_correct_newlines(
    tmp_path: Path, initial: str, expected: str
) -> None:
    """An absent assignment is appended for empty and non-final-newline files."""
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(initial, newline="")

    write_api_key_to_dotenv(str(dotenv_path), "new-key")

    assert dotenv_path.read_text() == expected


def test_write_api_key_rejects_non_dotenv_file(tmp_path: Path) -> None:
    """Only dotenv filename patterns are accepted."""
    with pytest.raises(FileIOError, match="dotenv filename"):
        write_api_key_to_dotenv(str(tmp_path / "settings.txt"), "new-key")


def test_write_api_key_rejects_missing_parent(tmp_path: Path) -> None:
    """The target parent directory must already exist."""
    with pytest.raises(FileIOError, match="Parent directory does not exist"):
        write_api_key_to_dotenv(str(tmp_path / "missing" / ".env"), "new-key")


def test_write_api_key_rejects_symlink_target(tmp_path: Path) -> None:
    """A symlinked target is rejected and left intact, not clobbered."""
    real_target = tmp_path / "secrets.env"
    real_target.write_text("ARIZE_API_KEY=old-key\n")
    symlink_path = tmp_path / ".env"
    symlink_path.symlink_to(real_target)

    with pytest.raises(FileIOError, match="symlink"):
        write_api_key_to_dotenv(str(symlink_path), "new-key")

    assert symlink_path.is_symlink()
    assert symlink_path.readlink() == real_target
    assert real_target.read_text() == "ARIZE_API_KEY=old-key\n"


def test_write_api_key_rejects_broken_symlink(tmp_path: Path) -> None:
    """A dangling symlink is rejected rather than silently clobbered."""
    symlink_path = tmp_path / ".env"
    symlink_path.symlink_to(tmp_path / "does-not-exist.env")

    with pytest.raises(FileIOError, match="symlink"):
        write_api_key_to_dotenv(str(symlink_path), "new-key")

    assert symlink_path.is_symlink()


def test_write_api_key_is_atomic_when_replace_fails(tmp_path: Path) -> None:
    """A failed atomic replacement leaves the original file unchanged."""
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("ARIZE_API_KEY=old-key\n")

    with (
        patch("ax.utils.dotenv.os.replace", side_effect=OSError("disk error")),
        pytest.raises(FileIOError, match="Failed to update dotenv file"),
    ):
        write_api_key_to_dotenv(str(dotenv_path), "new-key")

    assert dotenv_path.read_text() == "ARIZE_API_KEY=old-key\n"


def test_write_api_key_cleans_up_temporary_file_when_interrupted(
    tmp_path: Path,
) -> None:
    """An interrupted write leaves neither the secret nor a temporary file."""
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("ARIZE_API_KEY=old-key\n")

    with (
        patch("ax.utils.dotenv.os.fsync", side_effect=KeyboardInterrupt),
        pytest.raises(KeyboardInterrupt),
    ):
        write_api_key_to_dotenv(str(dotenv_path), "new-key")

    assert dotenv_path.read_text() == "ARIZE_API_KEY=old-key\n"
    assert list(tmp_path.iterdir()) == [dotenv_path]
