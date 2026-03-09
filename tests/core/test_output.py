"""Tests for output formatters.

Regression tests for JSON/CSV output corruption caused by Rich's
console.print() wrapping long lines at the terminal width (default 80 cols).
"""

import json

import pytest
from pydantic import BaseModel

from ax.core.output import CSVFormatter, JSONFormatter


class SpanAttributes(BaseModel):
    """Minimal span-like model for testing."""

    name: str
    status_code: str = "OK"
    attributes: dict | None = None


class SpanListResponse(BaseModel):
    """Minimal list response wrapper."""

    spans: list[SpanAttributes]


class TestJSONFormatterProducesValidJSON:
    """Verify JSONFormatter stdout output is always parseable by json.loads().

    Rich's console.print() wraps long lines to fit the terminal width,
    inserting literal newlines into JSON string values. This makes the
    output invalid JSON. These tests ensure we bypass Rich for
    machine-readable formats.
    """

    def test_short_content(self, capsys: pytest.CaptureFixture) -> None:
        """Short content roundtrips through JSON without corruption."""
        data = SpanListResponse(
            spans=[SpanAttributes(name="short", attributes={"key": "val"})]
        )
        JSONFormatter().format(data)
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["spans"][0]["name"] == "short"

    def test_long_nested_json_strings(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Span attributes with long nested JSON strings must not be line-wrapped.

        This is the exact pattern that triggered the bug:
        input.value containing a serialized JSON object > 80 chars wide.
        """
        long_inner_json = json.dumps(
            {
                "type": "user_input",
                "question": "can you create an eval on rag",
                "input_context": {
                    "evaluator_hub_state": {
                        "name": "Q&A\n",
                        "display_name": "Telecoms Compliance",
                        "template": (
                            "You are a helpful AI bot that checks for the "
                            "accuracy and completeness of telecommunications "
                            "compliance remediation guidance."
                        ),
                    }
                },
            }
        )
        data = SpanListResponse(
            spans=[
                SpanAttributes(
                    name="eval_agent",
                    status_code="ERROR",
                    attributes={"input.value": long_inner_json},
                )
            ]
        )
        JSONFormatter().format(data)
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        inner = json.loads(parsed["spans"][0]["attributes"]["input.value"])
        assert inner["input_context"]["evaluator_hub_state"]["name"] == "Q&A\n"

    def test_multiline_user_input(self, capsys: pytest.CaptureFixture) -> None:
        """Literal newlines in string values must be escaped, not rendered as raw breaks."""
        data = SpanListResponse(
            spans=[
                SpanAttributes(
                    name="test",
                    attributes={
                        "input.value": "line one\nline two\nline three"
                    },
                )
            ]
        )
        JSONFormatter().format(data)
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert (
            parsed["spans"][0]["attributes"]["input.value"]
            == "line one\nline two\nline three"
        )

    def test_writes_to_file(self, tmp_path: object) -> None:
        """File output must also produce valid JSON."""
        data = SpanListResponse(
            spans=[SpanAttributes(name="test", attributes={"k": "v" * 200})]
        )
        out = str(tmp_path / "out.json")  # type: ignore[operator]
        JSONFormatter().format(data, output_file=out)
        with open(out) as f:
            parsed = json.loads(f.read())
        assert parsed["spans"][0]["name"] == "test"


class TestCSVFormatterProducesValidOutput:
    """Verify CSVFormatter stdout output is not corrupted by Rich wrapping."""

    def test_csv_no_rich_wrapping(self, capsys: pytest.CaptureFixture) -> None:
        """CSV output is not corrupted by Rich line wrapping."""
        data = SpanListResponse(
            spans=[
                SpanAttributes(
                    name="span_with_long_attribute_value",
                    attributes={"detail": "x" * 200},
                )
            ]
        )
        CSVFormatter().format(data)
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert len(lines) == 2, "CSV should have exactly header + 1 data row"
