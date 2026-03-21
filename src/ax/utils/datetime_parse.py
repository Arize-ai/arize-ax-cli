"""Parse ISO 8601 datetime strings for CLI options."""

from datetime import datetime
from typing import overload

import typer


@overload
def parse_optional_iso8601(value: None) -> None: ...


@overload
def parse_optional_iso8601(value: str) -> datetime: ...


def parse_optional_iso8601(value: str | None) -> datetime | None:
    """Parse an optional ISO 8601 datetime string.

    Args:
        value: ISO 8601 datetime string, or ``None``.

    Returns:
        A :class:`datetime` object, or ``None`` if *value* is ``None``.

    Raises:
        typer.BadParameter: If the string cannot be parsed as ISO 8601.
    """
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(
            f"Invalid datetime format: '{value}'. "
            "Use ISO 8601 (e.g. '2025-12-31T23:59:59' or '2025-12-31')."
        ) from exc
