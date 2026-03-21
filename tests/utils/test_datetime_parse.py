"""Tests for ISO 8601 datetime parsing helpers."""

from datetime import datetime, timezone

import pytest
import typer

from ax.utils.datetime_parse import parse_optional_iso8601


class TestParseOptionalIso8601:
    """Tests for parse_optional_iso8601."""

    def test_none_returns_none(self) -> None:
        """Omitted optional value stays None."""
        assert parse_optional_iso8601(None) is None

    def test_date_only(self) -> None:
        """Date-only string parses to midnight naive datetime."""
        result = parse_optional_iso8601("2025-12-31")
        assert result == datetime(2025, 12, 31, 0, 0, 0)

    def test_datetime_with_t_separator(self) -> None:
        """Common CLI example with T separator parses."""
        result = parse_optional_iso8601("2025-12-31T23:59:59")
        assert result == datetime(2025, 12, 31, 23, 59, 59)

    def test_zulu_suffix(self) -> None:
        """Z suffix is accepted (Python 3.11+ fromisoformat)."""
        result = parse_optional_iso8601("2024-01-01T00:00:00Z")
        assert result == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_invalid_raises_bad_parameter(self) -> None:
        """Garbage input raises typer.BadParameter with a helpful message."""
        with pytest.raises(typer.BadParameter) as exc_info:
            parse_optional_iso8601("not-a-date")
        message = str(exc_info.value)
        assert "Invalid datetime format" in message
        assert "not-a-date" in message
        assert "ISO 8601" in message
