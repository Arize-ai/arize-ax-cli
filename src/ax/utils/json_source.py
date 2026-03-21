"""Load JSON text from a file path or an inline string."""

import json
from pathlib import Path
from typing import Any

import typer


def load_json(source: str) -> dict[str, Any] | list[dict[str, Any]]:
    """Parse JSON from a filesystem path or an inline string.

    If ``source``, after stripping whitespace, starts with ``[`` or ``{``,
    it is treated as an inline JSON document. Otherwise it is treated as a
    filesystem path: the file must exist and be a regular file.

    Args:
        source: Path to a ``.json`` file or a JSON document as a string.

    Returns:
        Parsed JSON value — a ``dict`` or ``list``.

    Raises:
        typer.BadParameter: If a path is invalid, missing, not a file,
            cannot be read, or the content is not valid JSON.
    """
    text = source.strip()
    json_string = text if text.startswith(("[", "{")) else _read_json_file(text)
    try:
        return json.loads(json_string)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Not valid JSON: {exc}") from exc


def _read_json_file(filepath: str) -> str:
    """Return the contents of a JSON file as a string."""
    path = Path(filepath)
    if path.is_file():
        try:
            return path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise typer.BadParameter(
                f"Could not read JSON file '{filepath}': {exc}"
            ) from exc

    if path.exists():
        raise typer.BadParameter(f"Not a file: {filepath}")

    raise typer.BadParameter(f"File not found: {filepath}")
