"""Tests for output formatters.

Regression tests for JSON/CSV output corruption caused by Rich's
console.print() wrapping long lines at the terminal width (default 80 cols).
"""

import json
from enum import Enum
from typing import Optional

import pytest
from pydantic import BaseModel

from ax.core.output import (
    BaseModelTableFormatter,
    CSVFormatter,
    JSONFormatter,
    PromptFormatter,
    TableFormatter,
    _all_none,
    _is_prompt_version,
    _is_prompt_with_version,
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

    def test_plain_dict_not_affected(self) -> None:
        """Plain dicts without the OneOf marker keys are not unwrapped."""
        value = {"foo": "bar", "baz": 1}
        result = self.formatter._format_value(value)
        assert "foo" in result  # rendered as str(dict)


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
# Minimal Pydantic models that duck-type as PromptWithVersion / PromptVersion
# ---------------------------------------------------------------------------


class _FakeRole(str, Enum):
    SYSTEM = "system"
    USER = "user"


class _FakeMessage(BaseModel):
    role: _FakeRole
    content: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list] = None


class _FakeProvider(str, Enum):
    OPEN_AI = "open_ai"


class _FakeIVF(str, Enum):
    F_STRING = "f_string"


class _FakeInvocationParams(BaseModel):
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class _FakeVersion(BaseModel):
    id: str = "pv_1"
    prompt_id: str = "pr_1"
    commit_hash: str = "abc123"
    commit_message: str = "Add greeting"
    messages: list[_FakeMessage] = []
    input_variable_format: _FakeIVF = _FakeIVF.F_STRING
    provider: _FakeProvider = _FakeProvider.OPEN_AI
    model: str = "gpt-4"
    invocation_params: Optional[_FakeInvocationParams] = None
    labels: Optional[list[str]] = None


class _FakePromptWithVersion(BaseModel):
    id: str = "pr_1"
    name: str = "My Prompt"
    description: Optional[str] = None
    space_id: str = "sp_1"
    version: _FakeVersion


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAllNone:
    def test_none_returns_true(self) -> None:
        assert _all_none(None) is True

    def test_all_none_basemodel_returns_true(self) -> None:
        assert _all_none(_FakeInvocationParams()) is True

    def test_partial_basemodel_returns_false(self) -> None:
        assert _all_none(_FakeInvocationParams(temperature=0.7)) is False

    def test_non_basemodel_returns_false(self) -> None:
        assert _all_none("value") is False


class TestDuckTypeDetection:
    def test_prompt_with_version_detected(self) -> None:
        model = _FakePromptWithVersion(version=_FakeVersion())
        assert _is_prompt_with_version(model) is True
        assert _is_prompt_version(model) is False

    def test_prompt_version_detected(self) -> None:
        model = _FakeVersion()
        assert _is_prompt_version(model) is True
        assert _is_prompt_with_version(model) is False

    def test_unrelated_model_not_detected(self) -> None:
        model = SpanAttributes(name="x")
        assert _is_prompt_with_version(model) is False
        assert _is_prompt_version(model) is False


class TestPromptFormatter:
    """PromptFormatter renders cleanly — no LLMMessage repr, no raw enum repr."""

    def test_format_with_version_shows_name_and_commit(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        version = _FakeVersion(commit_message="Update greeting")
        model = _FakePromptWithVersion(name="Greeter", version=version)
        PromptFormatter().format_with_version(model)
        out = capsys.readouterr().out
        assert "Greeter" in out
        assert "Update greeting" in out
        # Must not leak class names
        assert "FakeVersion" not in out
        assert "FakeMessage" not in out

    def test_format_with_version_shows_message_role_and_content(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        messages = [
            _FakeMessage(role=_FakeRole.SYSTEM, content="You are helpful."),
            _FakeMessage(role=_FakeRole.USER, content="Hello, {name}!"),
        ]
        version = _FakeVersion(messages=messages)
        model = _FakePromptWithVersion(version=version)
        PromptFormatter().format_with_version(model)
        out = capsys.readouterr().out
        assert "system" in out
        assert "user" in out
        assert "You are helpful." in out
        assert "Hello, {name}!" in out
        # Must not leak Python repr
        assert "FakeRole" not in out
        assert "FakeMessage(" not in out

    def test_format_with_version_enum_values_not_repr(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        version = _FakeVersion()
        model = _FakePromptWithVersion(version=version)
        PromptFormatter().format_with_version(model)
        out = capsys.readouterr().out
        # Enum value strings, not repr
        assert "open_ai" in out
        assert "f_string" in out
        assert "OPEN_AI" not in out
        assert "F_STRING" not in out
        assert "<" not in out  # no <EnumClass.VALUE: 'value'> pattern

    def test_format_with_version_omits_all_none_invocation_params(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        version = _FakeVersion(invocation_params=_FakeInvocationParams())
        model = _FakePromptWithVersion(version=version)
        PromptFormatter().format_with_version(model)
        out = capsys.readouterr().out
        assert "InvocationParams" not in out
        assert "Invocation Parameters" not in out

    def test_format_with_version_shows_non_none_invocation_params(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        version = _FakeVersion(
            invocation_params=_FakeInvocationParams(temperature=0.5)
        )
        model = _FakePromptWithVersion(version=version)
        PromptFormatter().format_with_version(model)
        out = capsys.readouterr().out
        assert "temperature" in out
        assert "0.5" in out

    def test_format_with_version_shows_labels(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        version = _FakeVersion(labels=["production", "staging"])
        model = _FakePromptWithVersion(version=version)
        PromptFormatter().format_with_version(model)
        out = capsys.readouterr().out
        assert "production" in out
        assert "staging" in out

    def test_format_version_standalone(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        messages = [_FakeMessage(role=_FakeRole.USER, content="Hi")]
        version = _FakeVersion(messages=messages, labels=["v1"])
        PromptFormatter().format_version(version)
        out = capsys.readouterr().out
        assert "user" in out
        assert "Hi" in out
        assert "v1" in out
        assert "FakeMessage(" not in out

    def test_table_formatter_dispatches_prompt_with_version(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """TableFormatter must delegate PromptWithVersion to PromptFormatter."""
        version = _FakeVersion(
            messages=[_FakeMessage(role=_FakeRole.SYSTEM, content="sys")]
        )
        model = _FakePromptWithVersion(version=version)
        TableFormatter().format(model)
        out = capsys.readouterr().out
        assert "sys" in out
        assert "FakeVersion(" not in out

    def test_table_formatter_dispatches_prompt_version(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """TableFormatter must delegate standalone PromptVersion to PromptFormatter."""
        version = _FakeVersion(
            messages=[_FakeMessage(role=_FakeRole.USER, content="hello")]
        )
        TableFormatter().format(version)
        out = capsys.readouterr().out
        assert "hello" in out
        assert "FakeMessage(" not in out

    def test_empty_string_content_still_renders_role(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """A message with content='' must still render the role line (not be dropped)."""
        messages = [_FakeMessage(role=_FakeRole.USER, content="")]
        version = _FakeVersion(messages=messages)
        model = _FakePromptWithVersion(version=version)
        PromptFormatter().format_with_version(model)
        out = capsys.readouterr().out
        assert "user" in out

    def test_tool_calls_message_renders_function_name(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """An assistant message with tool_calls renders the function name."""
        from unittest.mock import MagicMock

        fn = MagicMock()
        fn.name = "lookup_ticket"
        tc = MagicMock()
        tc.function = fn
        msg = _FakeMessage(role=_FakeRole.USER, tool_calls=[tc])
        version = _FakeVersion(messages=[msg])
        model = _FakePromptWithVersion(version=version)
        PromptFormatter().format_with_version(model)
        out = capsys.readouterr().out
        assert "lookup_ticket" in out
        assert "→" in out

    def test_tool_call_id_message_renders_response(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """A tool-response message with tool_call_id renders the response line."""
        msg = _FakeMessage(role=_FakeRole.USER, tool_call_id="call_abc")
        version = _FakeVersion(messages=[msg])
        model = _FakePromptWithVersion(version=version)
        PromptFormatter().format_with_version(model)
        out = capsys.readouterr().out
        assert "call_abc" in out
