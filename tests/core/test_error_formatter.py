"""Tests for the pydantic ValidationError parsing path in error_formatter."""

import io
import json
from typing import Annotated

import pytest
from arize._generated.api_client import ApiClient
from pydantic import BaseModel, Field
from rich.console import Console

from ax.core.error_formatter import (
    format_error_message,
    parse_exception,
    parse_pydantic_validation_error,
)
from ax.core.exceptions import ConfigError


class _LimitModel(BaseModel):
    """Mirrors the generated SDK's ``limit`` param constraint (le=500)."""

    limit: Annotated[int, Field(le=500, ge=1)]


class _MultiFieldModel(BaseModel):
    """A model with two independently-invalid fields."""

    limit: Annotated[int, Field(le=500, ge=1)]
    name: Annotated[str, Field(min_length=1)]


def _make_validation_error() -> Exception:
    """Return the same shape of ValidationError the generated SDK raises."""
    try:
        _LimitModel(limit=99999)
    except Exception as e:
        return e
    raise AssertionError("expected a ValidationError")


def _make_multi_field_validation_error() -> Exception:
    """Return a ValidationError with two independently-failing fields."""
    try:
        _MultiFieldModel(limit=99999, name="")
    except Exception as e:
        return e
    raise AssertionError("expected a ValidationError")


class TestParsePydanticValidationError:
    """Unit tests for parse_pydantic_validation_error."""

    def test_returns_none_for_unrelated_exception(self) -> None:
        """A plain exception with no ValidationError in its chain yields None."""
        assert parse_pydantic_validation_error(RuntimeError("boom")) is None

    def test_returns_none_for_unrelated_cause(self) -> None:
        """An exception chain without a ValidationError yields None."""
        try:
            raise RuntimeError("wrapper") from ValueError(
                "not a validation error"
            )
        except RuntimeError as e:
            assert parse_pydantic_validation_error(e) is None

    def test_extracts_field_and_message(self) -> None:
        """A ValidationError's field name and message are surfaced cleanly."""
        parsed = parse_pydantic_validation_error(_make_validation_error())

        assert parsed is not None
        assert parsed.status == 422
        assert parsed.reason == "Validation Error"
        assert "limit" in parsed.detail
        assert "less than or equal to 500" in parsed.detail

    def test_finds_validation_error_via_cause_chain(self) -> None:
        """A ValidationError wrapped by an outer exception is still found."""
        inner = _make_validation_error()
        try:
            raise RuntimeError("Failed to list traces") from inner
        except RuntimeError as outer:
            parsed = parse_pydantic_validation_error(outer)

        assert parsed is not None
        assert "limit" in parsed.detail

    def test_does_not_leak_pydantic_internals_in_detail(self) -> None:
        """The clean detail message omits pydantic's doc-site URL."""
        parsed = parse_pydantic_validation_error(_make_validation_error())

        assert parsed is not None
        assert "pydantic.dev" not in parsed.detail
        assert "type=less_than_equal" not in parsed.detail

    def test_raw_message_preserved_in_body_for_verbose_mode(self) -> None:
        """The raw pydantic message is kept in body for --verbose output."""
        parsed = parse_pydantic_validation_error(_make_validation_error())

        assert parsed is not None
        assert "pydantic.dev" in parsed.body

    def test_returns_none_for_config_error(self) -> None:
        """A ValidationError wrapped by ConfigError (e.g. a malformed profile
        TOML) is not mistaken for SDK request validation, so ConfigError's
        own actionable message is left for the caller to print instead.
        """
        inner = _make_validation_error()
        try:
            raise ConfigError(
                "Profile 'default' has an invalid configuration:\n\n"
                f"{inner}\n\n"
                "Run 'ax profiles create' to recreate it."
            ) from inner
        except ConfigError as outer:
            assert parse_pydantic_validation_error(outer) is None

    def test_multiple_field_errors_are_semicolon_joined(self) -> None:
        """Two independently-invalid fields are joined into one detail
        string, each with its own field name and message.
        """
        parsed = parse_pydantic_validation_error(
            _make_multi_field_validation_error()
        )

        assert parsed is not None
        assert (
            parsed.detail
            == "limit: Input should be less than or equal to 500; "
            "name: String should have at least 1 character"
        )


class TestParseExceptionIntegration:
    """parse_exception must reach the pydantic path when nothing else matches."""

    def test_parse_exception_returns_pydantic_result(self) -> None:
        """parse_exception falls through to pydantic parsing for AxError-wrapped
        ValidationErrors (the actual shape raised by CLI commands).
        """
        inner = _make_validation_error()
        try:
            raise RuntimeError(
                "Failed to list traces: " + str(inner)
            ) from inner
        except RuntimeError as wrapped:
            parsed = parse_exception(wrapped)

        assert parsed is not None
        assert parsed.status == 422
        assert "limit" in parsed.detail

    @pytest.mark.parametrize(
        "exc", [RuntimeError("plain"), ValueError("plain")]
    )
    def test_parse_exception_returns_none_when_nothing_matches(
        self, exc: Exception
    ) -> None:
        """Exceptions with no ApiException, gRPC, or pydantic error yield None."""
        assert parse_exception(exc) is None

    def test_parse_exception_returns_none_for_config_error(self) -> None:
        """ConfigError wrapping a ValidationError does not get reformatted --
        parse_exception should return None so the decorator prints
        ConfigError's own message.
        """
        inner = _make_validation_error()
        try:
            raise ConfigError(
                "Profile 'default' has an invalid configuration:\n\n"
                f"{inner}\n\n"
                "Run 'ax profiles create' to recreate it."
            ) from inner
        except ConfigError as outer:
            assert parse_exception(outer) is None


def _make_response_validation_error(kind: str) -> Exception:
    """Return the ValidationError the SDK raises when parsing a response."""
    span = {
        "name": "span",
        "context": {"trace_id": "t1", "span_id": "s1"},
        "kind": kind,
        "start_time": "2026-01-01T00:00:00Z",
        "end_time": "2026-01-01T00:00:01Z",
    }
    try:
        ApiClient().deserialize(
            json.dumps({"spans": [span]}),
            "ListSpansResponse",
            "application/json",
        )
    except Exception as e:
        return e
    raise AssertionError("expected a ValidationError")


class TestResponseValidationError:
    """Response parse failures are not reported as 422 input errors."""

    def test_not_reported_as_422(self) -> None:
        """A server value the SDK rejects is not shown as an input error."""
        parsed = parse_pydantic_validation_error(
            _make_response_validation_error("tool")
        )
        assert parsed is not None
        assert parsed.status is None
        assert parsed.detail is not None
        assert "Server response could not be parsed" in parsed.detail
        assert "kind = 'tool'" in parsed.detail
        assert "not a problem with your input" in parsed.detail

    def test_formatted_message_has_no_422(self) -> None:
        """The clean error output omits the 422 status and suggestion."""
        parsed = parse_pydantic_validation_error(
            _make_response_validation_error("tool")
        )
        assert parsed is not None
        message = format_error_message(parsed)
        assert "422" not in message
        assert "Check the error details" not in message

    def test_server_values_are_markup_escaped(self) -> None:
        """Server-sent values cannot inject Rich markup in either mode."""
        parsed = parse_pydantic_validation_error(
            _make_response_validation_error("[/bold] x")
        )
        assert parsed is not None
        for verbose in (False, True):
            Console(file=io.StringIO()).print(
                format_error_message(parsed, verbose=verbose)
            )

    def test_request_errors_still_422(self) -> None:
        """Errors raised outside response parsing keep the 422 status."""
        parsed = parse_pydantic_validation_error(_make_validation_error())
        assert parsed is not None
        assert parsed.status == 422
