"""Tests for output formatters.

Regression tests for JSON/CSV output corruption caused by Rich's
console.print() wrapping long lines at the terminal width (default 80 cols).
"""

import json

import pytest
from pydantic import BaseModel

from ax.core.output import (
    BaseModelTableFormatter,
    CSVFormatter,
    JSONFormatter,
    TableFormatter,
)


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


class TestBaseModelTableFormatterFormatValue:
    """Tests for _format_value, focusing on generated OneOf union types."""

    def setup_method(self) -> None:
        self.formatter = BaseModelTableFormatter()

    def test_float_nan_shows_dash(self) -> None:
        """float('nan') from pandas numeric columns must render as em-dash."""
        import math

        result = self.formatter._format_value(float("nan"))
        assert "—" in result
        assert str(math.nan) not in result

    def test_pandas_na_shows_dash(self) -> None:
        """pd.NA from pandas nullable columns must render as em-dash."""
        import pandas as pd

        result = self.formatter._format_value(pd.NA)
        assert "—" in result

    def test_oneof_predefined_role_shows_name(self) -> None:
        """OneOf wrapper with a predefined role should display just the role name."""
        value = {
            "oneof_schema_1_validator": None,
            "oneof_schema_2_validator": None,
            "actual_instance": {"type": "predefined", "name": "member"},
            "one_of_schemas": {
                "OrganizationPredefinedRoleAssignment",
                "OrganizationCustomRoleAssignment",
            },
            "discriminator_value_class_map": {},
        }
        result = self.formatter._format_value(value)
        assert result == "member"

    def test_oneof_custom_role_shows_id(self) -> None:
        """OneOf wrapper with a custom role should display just the role ID."""
        value = {
            "oneof_schema_1_validator": None,
            "oneof_schema_2_validator": None,
            "actual_instance": {"type": "custom", "id": "role-abc-123"},
            "one_of_schemas": {
                "OrganizationPredefinedRoleAssignment",
                "OrganizationCustomRoleAssignment",
            },
            "discriminator_value_class_map": {},
        }
        result = self.formatter._format_value(value)
        assert result == "role-abc-123"

    def test_plain_dict_formatted_as_key_value_pairs(self) -> None:
        """Plain dicts are formatted as 'key=value, ...' skipping None/empty values."""
        value = {"temperature": 0.7, "max_tokens": 100, "top_p": None}
        result = self.formatter._format_value(value)
        assert "temperature=0.7" in result
        assert "max_tokens=100" in result
        assert "top_p" not in result  # None skipped

    def test_plain_dict_skips_empty_containers(self) -> None:
        """Empty dicts and lists inside a value are silently skipped."""
        value = {"model": "gpt-4", "additional_properties": {}, "stop": []}
        result = self.formatter._format_value(value)
        assert "model=gpt-4" in result
        assert "additional_properties" not in result
        assert "stop" not in result

    def test_nested_dict_expanded(self) -> None:
        """Dicts nested inside a dict are recursively expanded."""
        value = {"response_format": {"type": "json_object"}}
        result = self.formatter._format_value(value)
        assert "response_format=" in result
        assert "type=json_object" in result

    def test_list_items_joined(self) -> None:
        """Non-empty lists are joined with ' | ' rather than showing 'N items'."""
        result = self.formatter._format_value(["production", "staging"])
        assert "production" in result
        assert "staging" in result
        assert "items" not in result

    def test_empty_list_shows_dash(self) -> None:
        """Empty lists render as an em-dash placeholder."""
        result = self.formatter._format_value([])
        assert "—" in result

    def test_list_of_dicts_expanded(self) -> None:
        """Lists of dicts (e.g. messages from model_dump) expand each entry."""
        from enum import Enum

        class Role(Enum):
            USER = "user"

        value = [{"role": Role.USER, "content": "Hello", "tool_calls": None}]
        result = self.formatter._format_value(value)
        assert "role=user" in result
        assert "content=Hello" in result
        assert "tool_calls" not in result  # None skipped


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


# ---------------------------------------------------------------------------
# Regression tests: PromptWithVersion and PromptVersion display cleanly
#
# These tests use the real SDK types (arize.prompts.types) which define
# PromptVersion.__str__ and InvocationParams.__str__ to avoid leaking
# internal Python repr strings (LLMMessage repr, raw enum repr, etc.).
# The generic BaseModelTableFormatter calls str() on nested BaseModel
# fields, so the fix lives entirely in the SDK types.
# ---------------------------------------------------------------------------


def _make_prompt_version(**kwargs):  # type: ignore[no-untyped-def]
    """Build a minimal PromptVersion using real SDK types."""
    from datetime import datetime, timezone

    from arize._generated.api_client.models.input_variable_format import (
        InputVariableFormat,
    )
    from arize._generated.api_client.models.llm_message import LLMMessage
    from arize._generated.api_client.models.llm_provider import LlmProvider
    from arize._generated.api_client.models.message_role import MessageRole
    from arize.prompts.types import PromptVersion

    defaults: dict = {
        "id": "pv_1",
        "prompt_id": "pr_1",
        "commit_hash": "abc123",
        "commit_message": "Add greeting",
        "messages": [
            LLMMessage(role=MessageRole.SYSTEM, content="You are helpful."),
            LLMMessage(role=MessageRole.USER, content="Hello, {name}!"),
        ],
        "input_variable_format": InputVariableFormat.F_STRING,
        "provider": LlmProvider.OPEN_AI,
        "model": "gpt-4",
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "created_by_user_id": "u_1",
    }
    defaults.update(kwargs)
    return PromptVersion(**defaults)


def _make_prompt_with_version(**kwargs):  # type: ignore[no-untyped-def]
    """Build a minimal PromptWithVersion using real SDK types."""
    from datetime import datetime, timezone

    from arize.prompts.types import PromptWithVersion

    version = _make_prompt_version()
    defaults: dict = {
        "id": "pr_1",
        "name": "My Prompt",
        "space_id": "sp_1",
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "created_by_user_id": "u_1",
        "version": version,
    }
    defaults.update(kwargs)
    return PromptWithVersion(**defaults)


class TestPromptVersionStr:
    """PromptVersion.__str__ must produce clean output — no internal repr."""

    def test_shows_commit_message(self) -> None:
        pv = _make_prompt_version(commit_message="My commit")
        assert "My commit" in str(pv)

    def test_enum_values_not_repr(self) -> None:
        pv = _make_prompt_version()
        s = str(pv)
        assert "open_ai" in s
        assert "f_string" in s
        assert "<LlmProvider" not in s
        assert "<InputVariableFormat" not in s

    def test_message_role_and_content(self) -> None:
        pv = _make_prompt_version()
        s = str(pv)
        assert "system" in s
        assert "user" in s
        assert "You are helpful." in s
        assert "Hello, {name}!" in s
        assert "LLMMessage(" not in s
        assert "<MessageRole" not in s

    def test_labels_shown(self) -> None:
        pv = _make_prompt_version(labels=["production", "staging"])
        s = str(pv)
        assert "production" in s
        assert "staging" in s

    def test_empty_content_message_still_shows_role(self) -> None:
        from arize._generated.api_client.models.llm_message import LLMMessage
        from arize._generated.api_client.models.message_role import MessageRole

        pv = _make_prompt_version(
            messages=[LLMMessage(role=MessageRole.USER, content="")]
        )
        assert "user" in str(pv)


class TestInvocationParamsStr:
    """InvocationParams.__str__ omits None fields."""

    def test_all_none_returns_empty(self) -> None:
        from arize.prompts.types import InvocationParams

        assert str(InvocationParams()) == ""

    def test_non_none_fields_shown(self) -> None:
        from arize.prompts.types import InvocationParams

        ip = InvocationParams(temperature=0.7, max_tokens=1000)
        s = str(ip)
        assert "temperature=0.7" in s
        assert "max_tokens=1000" in s
        assert "max_completion_tokens" not in s  # None → omitted


class TestPromptWithVersionTableRendering:
    """TableFormatter renders PromptWithVersion cleanly via SDK __str__."""

    def test_no_internal_repr_in_panel(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """The version row must not contain Python class repr strings."""
        model = _make_prompt_with_version()
        TableFormatter().format(model)
        out = capsys.readouterr().out
        assert "LLMMessage(" not in out
        assert "<MessageRole" not in out
        assert "<LlmProvider" not in out
        assert "<InputVariableFormat" not in out
        assert "InvocationParams(" not in out

    def test_messages_content_visible(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        model = _make_prompt_with_version()
        TableFormatter().format(model)
        out = capsys.readouterr().out
        assert "You are helpful." in out
        assert "Hello, {name}!" in out
        assert "system" in out
        assert "user" in out

    def test_enum_values_not_repr(self, capsys: pytest.CaptureFixture) -> None:
        model = _make_prompt_with_version()
        TableFormatter().format(model)
        out = capsys.readouterr().out
        assert "open_ai" in out
        assert "f_string" in out
