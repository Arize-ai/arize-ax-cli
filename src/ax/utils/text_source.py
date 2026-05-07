"""Load UTF-8 text from an inline value or an ``@path`` file reference."""

from pathlib import Path

from ax.core.exceptions import UsageError


def load_text_source(value: str, option_name: str) -> str:
    """Resolve a text value that may reference a file on disk.

    If ``value`` starts with ``@``, the remainder is treated as a filesystem
    path and its UTF-8 contents are returned. Otherwise ``value`` is returned
    unchanged (inline text).

    Args:
        value: Inline text, or ``@path/to/file`` to load from disk.
        option_name: Human-readable option name for error messages
            (e.g. ``"--code"``).

    Returns:
        The resolved text content.

    Raises:
        UsageError: If ``@path`` does not exist, is not a regular file, or
            cannot be read as UTF-8.
    """
    if not value.startswith("@"):
        return value
    path = Path(value[1:])
    if not path.exists():
        raise UsageError(f"{option_name} file not found: {path}")
    if not path.is_file():
        raise UsageError(f"{option_name} path is not a file: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise UsageError(
            f"Could not read {option_name} file '{path}': {exc}"
        ) from exc
