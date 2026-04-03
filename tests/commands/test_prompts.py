"""Tests for prompts CLI commands."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from arize._generated.api_client.models import LLMMessage
from arize._generated.api_client.models.input_variable_format import (
    InputVariableFormat,
)
from arize._generated.api_client.models.llm_provider import LlmProvider
from arize._generated.api_client.models.message_role import MessageRole
from arize._generated.api_client.models.tool_call_type import ToolCallType
from typer.testing import CliRunner, Result

from ax.cli import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers to build realistic SDK response objects
# ---------------------------------------------------------------------------

_CREATED_AT = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

_PROMPT_ID = "pr_test_1"
_VERSION_ID = "pv_test_1"


def _make_prompt_with_version(
    prompt_id: str = _PROMPT_ID,
    name: str = "My Prompt",
    version_id: str = _VERSION_ID,
) -> MagicMock:
    """Build a realistic PromptWithVersion mock."""
    mock = MagicMock()
    mock.prompt.id = prompt_id
    mock.prompt.name = name
    mock.version.id = version_id
    return mock


def _make_prompt(
    prompt_id: str = _PROMPT_ID,
    name: str = "My Prompt",
) -> MagicMock:
    """Build a realistic Prompt mock."""
    mock = MagicMock()
    mock.id = prompt_id
    mock.name = name
    return mock


def _make_prompt_version(
    version_id: str = _VERSION_ID,
) -> MagicMock:
    """Build a realistic PromptVersion mock."""
    mock = MagicMock()
    mock.id = version_id
    return mock


def _make_list_response(*prompts: MagicMock) -> MagicMock:
    """Build a PromptsList200Response mock."""
    mock = MagicMock()
    mock.prompts = list(prompts)
    mock.pagination.has_more = False
    return mock


def _make_versions_response(*versions: MagicMock) -> MagicMock:
    """Build a PromptVersionsList200Response mock."""
    mock = MagicMock()
    mock.versions = list(versions)
    mock.pagination.has_more = False
    return mock


def _make_set_labels_response() -> MagicMock:
    """Build a PromptVersionLabelsSet200Response mock."""
    mock = MagicMock()
    mock.labels = ["production"]
    return mock


def _large_inline_messages_payload() -> list[dict[str, object]]:
    """Multi-turn messages with tool calls — exercises a sizable inline JSON blob."""
    return [
        {
            "role": "system",
            "content": (
                "You are Acme Corp's support copilot. Policies:\n"
                + "\n".join(
                    f"{i}. Be accurate, cite internal docs, and stay on brand."
                    for i in range(1, 26)
                )
                + "\nAddress the customer as {customer_alias}."
            ),
        },
        {
            "role": "user",
            "content": (
                "Ticket #{ticket_id}: triage and suggest next steps.\n"
                "Context:\n"
                + "\n".join(
                    f"line {n}: incident detail snippet for correlation."
                    for n in range(1, 41)
                )
            ),
        },
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_7f3a2",
                    "type": "function",
                    "function": {
                        "name": "lookup_ticket",
                        "arguments": json.dumps(
                            {
                                "ticket_id": "INC-2048",
                                "fields": ["status", "priority", "assignee"],
                            }
                        ),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_7f3a2",
            "content": json.dumps(
                {
                    "status": "open",
                    "priority": "P2",
                    "notes": "x" * 400,
                }
            ),
        },
        {
            "role": "assistant",
            "content": (
                "Based on the ticket metadata, recommend escalation to on-call "
                "and attach runbook {runbook_id}."
            ),
        },
    ]


# ---------------------------------------------------------------------------
# Shared mock setup
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a mock ArizeClient with prompts subclient pre-wired."""
    return MagicMock()


@pytest.fixture
def mock_config() -> MagicMock:
    """Return a mock Config whose output.format is 'json'."""
    config = MagicMock()
    config.output.format = "json"
    return config


def _invoke(
    args: list[str],
    mock_config: MagicMock,
    mock_client: MagicMock,
    cli_input: str | None = None,
) -> Result:
    """Invoke the CLI app with standard mocks."""
    with (
        patch(
            "ax.commands.prompts.ConfigManager.load",
            return_value=mock_config,
        ),
        patch("ax.commands.prompts.asdict", return_value={}),
        patch(
            "ax.commands.prompts.ArizeClient",
            return_value=mock_client,
        ),
    ):
        return runner.invoke(app, args, input=cli_input)


# ---------------------------------------------------------------------------
# ax prompts list
# ---------------------------------------------------------------------------


class TestListPrompts:
    """Tests for `ax prompts list`."""

    def test_list_returns_prompts_in_output(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that listed prompts appear in the JSON output."""
        mock_client.prompts.list.return_value = _make_list_response(
            _make_prompt_with_version(name="Alpha"),
            _make_prompt_with_version(name="Beta"),
        )

        result = _invoke(
            ["prompts", "list", "--output", "json"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output

    def test_list_passes_options_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --space, --limit, --cursor are forwarded."""
        mock_client.prompts.list.return_value = _make_list_response()

        _invoke(
            [
                "prompts",
                "list",
                "--space",
                "sp_abc",
                "--limit",
                "5",
                "--cursor",
                "tok",
            ],
            mock_config,
            mock_client,
        )

        mock_client.prompts.list.assert_called_once_with(
            name=None,
            space="sp_abc",
            limit=5,
            cursor="tok",
        )

    def test_list_name_filter_forwarded(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --name is forwarded to the SDK."""
        mock_client.prompts.list.return_value = _make_list_response()

        _invoke(
            ["prompts", "list", "--name", "my-prompt"],
            mock_config,
            mock_client,
        )

        mock_client.prompts.list.assert_called_once_with(
            name="my-prompt",
            space=None,
            limit=15,
            cursor=None,
        )

    def test_list_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error results in a non-zero exit code."""
        mock_client.prompts.list.side_effect = RuntimeError("API error")
        result = _invoke(["prompts", "list"], mock_config, mock_client)
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax prompts get
# ---------------------------------------------------------------------------


class TestGetPrompt:
    """Tests for `ax prompts get <id>`."""

    def test_get_calls_sdk_with_correct_id(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that the positional ID is forwarded to the SDK."""
        mock_client.prompts.get.return_value = _make_prompt_with_version()

        _invoke(
            ["prompts", "get", _PROMPT_ID],
            mock_config,
            mock_client,
        )

        mock_client.prompts.get.assert_called_once_with(
            prompt=_PROMPT_ID,
            space=None,
            version_id=None,
            label=None,
        )

    def test_get_passes_version_id_and_label(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --version-id and --label are forwarded."""
        mock_client.prompts.get.return_value = _make_prompt_with_version()

        _invoke(
            [
                "prompts",
                "get",
                _PROMPT_ID,
                "--version-id",
                "pv_xyz",
                "--label",
                "production",
            ],
            mock_config,
            mock_client,
        )

        mock_client.prompts.get.assert_called_once_with(
            prompt=_PROMPT_ID,
            space=None,
            version_id="pv_xyz",
            label="production",
        )

    def test_get_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error results in a non-zero exit."""
        mock_client.prompts.get.side_effect = RuntimeError("Not found")
        result = _invoke(["prompts", "get", "pr_999"], mock_config, mock_client)
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax prompts create
# ---------------------------------------------------------------------------


class TestCreatePrompt:
    """Tests for `ax prompts create`."""

    def test_create_calls_sdk_correctly(
        self,
        mock_config: MagicMock,
        mock_client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that create passes all required arguments to the SDK."""
        messages_file = tmp_path / "messages.json"
        messages_file.write_text(
            json.dumps([{"role": "user", "content": "Hello"}])
        )

        mock_client.prompts.create.return_value = _make_prompt_with_version(
            name="My Prompt"
        )

        result = _invoke(
            [
                "prompts",
                "create",
                "--name",
                "My Prompt",
                "--space",
                "sp_abc",
                "--provider",
                "openAI",
                "--input-variable-format",
                "f_string",
                "--messages",
                str(messages_file),
                "--commit-message",
                "Initial",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.prompts.create.call_args.kwargs
        assert call_kwargs["name"] == "My Prompt"
        assert call_kwargs["space"] == "sp_abc"
        assert call_kwargs["provider"] == LlmProvider.OPENAI
        assert (
            call_kwargs["input_variable_format"] == InputVariableFormat.F_STRING
        )
        assert call_kwargs["commit_message"] == "Initial"
        msgs = call_kwargs["messages"]
        assert len(msgs) == 1
        assert isinstance(msgs[0], LLMMessage)
        assert msgs[0].role == MessageRole.USER
        assert msgs[0].content == "Hello"

    def test_create_with_inline_messages_json(
        self,
        mock_config: MagicMock,
        mock_client: MagicMock,
    ) -> None:
        """Test that --messages accepts a large inline JSON array."""
        mock_client.prompts.create.return_value = _make_prompt_with_version(
            name="P"
        )
        payload = _large_inline_messages_payload()
        inline = json.dumps(payload)
        assert len(inline) > 2_000, (
            "fixture should stress a non-trivial argv payload"
        )

        result = _invoke(
            [
                "prompts",
                "create",
                "--name",
                "P",
                "--space",
                "sp_abc",
                "--provider",
                "openAI",
                "--input-variable-format",
                "f_string",
                "--messages",
                inline,
                "--commit-message",
                "Init",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output
        mock_client.prompts.create.assert_called_once()
        msgs = mock_client.prompts.create.call_args.kwargs["messages"]
        assert len(msgs) == 5
        assert msgs[0].role == MessageRole.SYSTEM
        assert msgs[0].content is not None
        assert "{customer_alias}" in msgs[0].content
        assert msgs[1].role == MessageRole.USER
        assert "{ticket_id}" in (msgs[1].content or "")
        assert msgs[2].role == MessageRole.ASSISTANT
        assert msgs[2].tool_calls is not None
        assert len(msgs[2].tool_calls) == 1
        assert msgs[2].tool_calls[0].type == ToolCallType.FUNCTION
        assert msgs[2].tool_calls[0].function.name == "lookup_ticket"
        assert "INC-2048" in msgs[2].tool_calls[0].function.arguments
        assert msgs[3].role == MessageRole.TOOL
        assert msgs[3].tool_call_id == "call_7f3a2"
        assert msgs[3].content is not None
        assert "P2" in msgs[3].content
        assert msgs[4].role == MessageRole.ASSISTANT
        assert "{runbook_id}" in (msgs[4].content or "")

    def test_create_invalid_messages_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that invalid messages (not a file, not JSON) exit non-zero."""
        result = _invoke(
            [
                "prompts",
                "create",
                "--name",
                "P",
                "--space",
                "sp_abc",
                "--provider",
                "openAI",
                "--input-variable-format",
                "f_string",
                "--messages",
                "/nonexistent/path.json",
                "--commit-message",
                "Init",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0

    def test_create_sdk_error_exits_nonzero(
        self,
        mock_config: MagicMock,
        mock_client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that an SDK error during create causes a non-zero exit."""
        messages_file = tmp_path / "messages.json"
        messages_file.write_text(
            json.dumps([{"role": "user", "content": "Hello"}])
        )
        mock_client.prompts.create.side_effect = RuntimeError("Conflict")

        result = _invoke(
            [
                "prompts",
                "create",
                "--name",
                "P",
                "--space",
                "sp_abc",
                "--provider",
                "openAI",
                "--input-variable-format",
                "f_string",
                "--messages",
                str(messages_file),
                "--commit-message",
                "Init",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax prompts update
# ---------------------------------------------------------------------------


class TestUpdatePrompt:
    """Tests for `ax prompts update <id>`."""

    def test_update_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that update passes prompt_id and description to the SDK."""
        mock_client.prompts.update.return_value = _make_prompt()

        result = _invoke(
            [
                "prompts",
                "update",
                _PROMPT_ID,
                "--description",
                "New description",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.prompts.update.assert_called_once_with(
            prompt=_PROMPT_ID,
            space=None,
            description="New description",
        )

    def test_update_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error during update causes a non-zero exit."""
        mock_client.prompts.update.side_effect = RuntimeError("Not found")
        result = _invoke(
            ["prompts", "update", _PROMPT_ID, "--description", "X"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax prompts delete
# ---------------------------------------------------------------------------


class TestDeletePrompt:
    """Tests for `ax prompts delete <id>`."""

    def test_delete_force_skips_confirmation(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --force bypasses the prompt and deletes."""
        mock_client.prompts.delete.return_value = None

        result = _invoke(
            ["prompts", "delete", _PROMPT_ID, "--force"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.prompts.delete.assert_called_once_with(
            prompt=_PROMPT_ID, space=None
        )

    def test_delete_confirms_yes_calls_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that confirming the prompt proceeds with deletion."""
        mock_client.prompts.delete.return_value = None

        result = _invoke(
            ["prompts", "delete", _PROMPT_ID],
            mock_config,
            mock_client,
            cli_input="y\n",
        )

        assert result.exit_code == 0, result.output
        mock_client.prompts.delete.assert_called_once_with(
            prompt=_PROMPT_ID, space=None
        )

    def test_delete_declines_does_not_call_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that declining the confirmation leaves the prompt untouched."""
        result = _invoke(
            ["prompts", "delete", _PROMPT_ID],
            mock_config,
            mock_client,
            cli_input="n\n",
        )

        assert result.exit_code == 0
        mock_client.prompts.delete.assert_not_called()

    def test_delete_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error during delete causes a non-zero exit."""
        mock_client.prompts.delete.side_effect = RuntimeError("Not found")
        result = _invoke(
            ["prompts", "delete", _PROMPT_ID, "--force"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax prompts list-versions
# ---------------------------------------------------------------------------


class TestListVersions:
    """Tests for `ax prompts list-versions <id>`."""

    def test_list_versions_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that list-versions passes prompt_id, limit, and cursor."""
        mock_client.prompts.list_versions.return_value = (
            _make_versions_response(_make_prompt_version())
        )

        _invoke(
            [
                "prompts",
                "list-versions",
                _PROMPT_ID,
                "--limit",
                "5",
                "--cursor",
                "tok",
            ],
            mock_config,
            mock_client,
        )

        mock_client.prompts.list_versions.assert_called_once_with(
            prompt=_PROMPT_ID,
            space=None,
            limit=5,
            cursor="tok",
        )

    def test_list_versions_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error causes a non-zero exit."""
        mock_client.prompts.list_versions.side_effect = RuntimeError("error")
        result = _invoke(
            ["prompts", "list-versions", _PROMPT_ID],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax prompts create-version
# ---------------------------------------------------------------------------


class TestCreateVersion:
    """Tests for `ax prompts create-version <id>`."""

    def test_create_version_calls_sdk_correctly(
        self,
        mock_config: MagicMock,
        mock_client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that create-version forwards all args to the SDK."""
        messages_file = tmp_path / "messages.json"
        messages_file.write_text(
            json.dumps([{"role": "user", "content": "Hello"}])
        )
        mock_client.prompts.create_version.return_value = _make_prompt_version()

        result = _invoke(
            [
                "prompts",
                "create-version",
                _PROMPT_ID,
                "--provider",
                "openAI",
                "--input-variable-format",
                "f_string",
                "--messages",
                str(messages_file),
                "--commit-message",
                "v2",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.prompts.create_version.call_args.kwargs
        assert call_kwargs["prompt"] == _PROMPT_ID
        assert call_kwargs["commit_message"] == "v2"

    def test_create_version_with_inline_messages_json(
        self,
        mock_config: MagicMock,
        mock_client: MagicMock,
    ) -> None:
        """Test create-version with the same large inline JSON as create."""
        mock_client.prompts.create_version.return_value = _make_prompt_version()
        inline = json.dumps(_large_inline_messages_payload())

        result = _invoke(
            [
                "prompts",
                "create-version",
                _PROMPT_ID,
                "--provider",
                "openAI",
                "--input-variable-format",
                "f_string",
                "--messages",
                inline,
                "--commit-message",
                "v3-big-inline",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.prompts.create_version.call_args.kwargs
        assert call_kwargs["prompt"] == _PROMPT_ID
        assert call_kwargs["commit_message"] == "v3-big-inline"
        assert len(call_kwargs["messages"]) == 5

    def test_create_version_sdk_error_exits_nonzero(
        self,
        mock_config: MagicMock,
        mock_client: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test that an SDK error causes a non-zero exit."""
        messages_file = tmp_path / "messages.json"
        messages_file.write_text(
            json.dumps([{"role": "user", "content": "Hello"}])
        )
        mock_client.prompts.create_version.side_effect = RuntimeError("err")

        result = _invoke(
            [
                "prompts",
                "create-version",
                _PROMPT_ID,
                "--provider",
                "openAI",
                "--input-variable-format",
                "f_string",
                "--messages",
                str(messages_file),
                "--commit-message",
                "v2",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax prompts get-version-by-label
# ---------------------------------------------------------------------------


class TestGetVersionByLabel:
    """Tests for `ax prompts get-version-by-label <id>`."""

    def test_get_version_by_label_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that get-version-by-label forwards prompt_id and label_name."""
        mock_client.prompts.get_label.return_value = _make_prompt_version()

        _invoke(
            [
                "prompts",
                "get-version-by-label",
                _PROMPT_ID,
                "--label",
                "production",
            ],
            mock_config,
            mock_client,
        )

        mock_client.prompts.get_label.assert_called_once_with(
            prompt=_PROMPT_ID,
            space=None,
            label_name="production",
        )

    def test_get_version_by_label_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error causes a non-zero exit."""
        mock_client.prompts.get_label.side_effect = RuntimeError("Not found")
        result = _invoke(
            [
                "prompts",
                "get-version-by-label",
                _PROMPT_ID,
                "--label",
                "production",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax prompts set-version-labels
# ---------------------------------------------------------------------------


class TestSetVersionLabels:
    """Tests for `ax prompts set-version-labels <version-id>`."""

    def test_set_version_labels_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that set-version-labels forwards version_id and labels list."""
        mock_client.prompts.set_labels.return_value = (
            _make_set_labels_response()
        )

        _invoke(
            [
                "prompts",
                "set-version-labels",
                _VERSION_ID,
                "--label",
                "production",
                "--label",
                "staging",
            ],
            mock_config,
            mock_client,
        )

        mock_client.prompts.set_labels.assert_called_once_with(
            version_id=_VERSION_ID,
            labels=["production", "staging"],
        )

    def test_set_version_labels_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error causes a non-zero exit."""
        mock_client.prompts.set_labels.side_effect = RuntimeError("error")
        result = _invoke(
            [
                "prompts",
                "set-version-labels",
                _VERSION_ID,
                "--label",
                "production",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax prompts remove-version-label
# ---------------------------------------------------------------------------


class TestRemoveVersionLabel:
    """Tests for `ax prompts remove-version-label <version-id>`."""

    def test_remove_version_label_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that remove-version-label forwards version_id and label_name."""
        mock_client.prompts.delete_label.return_value = None

        result = _invoke(
            [
                "prompts",
                "remove-version-label",
                _VERSION_ID,
                "--label",
                "production",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.prompts.delete_label.assert_called_once_with(
            version_id=_VERSION_ID,
            label_name="production",
        )

    def test_remove_version_label_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error causes a non-zero exit."""
        mock_client.prompts.delete_label.side_effect = RuntimeError("error")
        result = _invoke(
            [
                "prompts",
                "remove-version-label",
                _VERSION_ID,
                "--label",
                "production",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
