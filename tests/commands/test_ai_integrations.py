"""Tests for ai-integrations CLI commands."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from arize.ai_integrations.types import (
    AiIntegrationAuthType,
    AiIntegrationProvider,
    AiIntegrationScoping,
    AwsProviderMetadataKind,
    AwsProviderMetadataRequest,
)
from typer.testing import CliRunner, Result

from ax.cli import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers to build realistic SDK response objects
# ---------------------------------------------------------------------------

_INTEGRATION_ID = "ai_int_test_1"
_CREATED_AT = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_integration(
    integration_id: str = _INTEGRATION_ID,
    name: str = "My Integration",
    provider: str = "OPEN_AI",
) -> MagicMock:
    """Build an AiIntegration mock."""
    mock = MagicMock()
    mock.id = integration_id
    mock.name = name
    mock.provider = provider
    return mock


def _make_list_response(*integrations: MagicMock) -> MagicMock:
    """Build an AiIntegrationsList200Response mock."""
    mock = MagicMock()
    mock.ai_integrations = list(integrations)
    mock.pagination.has_more = False
    return mock


# ---------------------------------------------------------------------------
# Shared mock setup
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a mock ArizeClient with ai_integrations subclient pre-wired."""
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
            "ax.commands.ai_integrations.make_client",
            return_value=(mock_client, mock_config),
        ),
    ):
        return runner.invoke(app, args, input=cli_input)


# ---------------------------------------------------------------------------
# ax ai-integrations list
# ---------------------------------------------------------------------------


class TestListAiIntegrations:
    """Tests for `ax ai-integrations list`."""

    def test_list_returns_integrations_in_output(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that listed integrations appear in the output."""
        mock_client.ai_integrations.list.return_value = _make_list_response(
            _make_integration(name="Alpha"),
            _make_integration(name="Beta"),
        )

        result = _invoke(
            ["ai-integrations", "list", "--output", "json"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.ai_integrations.list.assert_called_once()

    def test_list_passes_options_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --space-id, --limit, --cursor are forwarded."""
        mock_client.ai_integrations.list.return_value = _make_list_response()

        _invoke(
            [
                "ai-integrations",
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

        mock_client.ai_integrations.list.assert_called_once_with(
            name=None,
            space="sp_abc",
            limit=5,
            cursor="tok",
        )

    def test_list_name_filter_forwarded(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --name is forwarded to the SDK."""
        mock_client.ai_integrations.list.return_value = _make_list_response()

        _invoke(
            ["ai-integrations", "list", "--name", "openai"],
            mock_config,
            mock_client,
        )

        mock_client.ai_integrations.list.assert_called_once_with(
            name="openai",
            space=None,
            limit=15,
            cursor=None,
        )

    def test_list_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error results in a non-zero exit."""
        mock_client.ai_integrations.list.side_effect = RuntimeError("error")
        result = _invoke(["ai-integrations", "list"], mock_config, mock_client)
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax ai-integrations get
# ---------------------------------------------------------------------------


class TestGetAiIntegration:
    """Tests for `ax ai-integrations get <id>`."""

    def test_get_calls_sdk_with_correct_id(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that the positional ID is forwarded to the SDK."""
        mock_client.ai_integrations.get.return_value = _make_integration()

        _invoke(
            ["ai-integrations", "get", _INTEGRATION_ID],
            mock_config,
            mock_client,
        )

        mock_client.ai_integrations.get.assert_called_once_with(
            integration=_INTEGRATION_ID, space=None
        )

    def test_get_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error (e.g. 404) results in a non-zero exit."""
        mock_client.ai_integrations.get.side_effect = RuntimeError("Not found")
        result = _invoke(
            ["ai-integrations", "get", _INTEGRATION_ID],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax ai-integrations create
# ---------------------------------------------------------------------------


class TestCreateAiIntegration:
    """Tests for `ax ai-integrations create`."""

    def test_create_calls_sdk_with_required_args(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that create passes name and provider to the SDK."""
        mock_client.ai_integrations.create.return_value = _make_integration(
            name="OpenAI Prod"
        )

        result = _invoke(
            [
                "ai-integrations",
                "create",
                "--name",
                "OpenAI Prod",
                "--provider",
                "OPEN_AI",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.ai_integrations.create.call_args.kwargs
        assert call_kwargs["name"] == "OpenAI Prod"
        assert call_kwargs["provider"] == AiIntegrationProvider.OPEN_AI
        assert call_kwargs["enable_default_models"] is False
        assert call_kwargs["function_calling_enabled"] is False

    def test_create_enable_flags_forwarded_when_passed(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Passing --enable-default-models / --function-calling-enabled sets True."""
        mock_client.ai_integrations.create.return_value = _make_integration()

        _invoke(
            [
                "ai-integrations",
                "create",
                "--name",
                "X",
                "--provider",
                "OPEN_AI",
                "--enable-default-models",
                "--function-calling-enabled",
            ],
            mock_config,
            mock_client,
        )

        call_kwargs = mock_client.ai_integrations.create.call_args.kwargs
        assert call_kwargs["enable_default_models"] is True
        assert call_kwargs["function_calling_enabled"] is True

    def test_create_passes_optional_model_names(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --model-name (repeatable) is forwarded as a list."""
        mock_client.ai_integrations.create.return_value = _make_integration()

        _invoke(
            [
                "ai-integrations",
                "create",
                "--name",
                "My Integration",
                "--provider",
                "OPEN_AI",
                "--model-name",
                "gpt-4o",
                "--model-name",
                "gpt-4o-mini",
            ],
            mock_config,
            mock_client,
        )

        call_kwargs = mock_client.ai_integrations.create.call_args.kwargs
        assert call_kwargs["model_names"] == ["gpt-4o", "gpt-4o-mini"]

    def test_create_parses_headers_json(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --headers is parsed from JSON string."""
        mock_client.ai_integrations.create.return_value = _make_integration()

        _invoke(
            [
                "ai-integrations",
                "create",
                "--name",
                "Custom",
                "--provider",
                "CUSTOM",
                "--headers",
                '{"X-Custom": "value"}',
            ],
            mock_config,
            mock_client,
        )

        call_kwargs = mock_client.ai_integrations.create.call_args.kwargs
        assert call_kwargs["headers"] == {"X-Custom": "value"}

    def test_create_invalid_headers_json_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that invalid JSON for --headers causes a non-zero exit."""
        result = _invoke(
            [
                "ai-integrations",
                "create",
                "--name",
                "Bad",
                "--provider",
                "CUSTOM",
                "--headers",
                "not-json",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0

    def test_create_parses_provider_metadata(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --provider-metadata is parsed from JSON string."""
        mock_client.ai_integrations.create.return_value = _make_integration()

        _invoke(
            [
                "ai-integrations",
                "create",
                "--name",
                "Bedrock",
                "--provider",
                "AWS_BEDROCK",
                "--provider-metadata",
                '{"role_arn": "arn:aws:iam::123:role/MyRole"}',
            ],
            mock_config,
            mock_client,
        )

        call_kwargs = mock_client.ai_integrations.create.call_args.kwargs
        assert call_kwargs["provider_metadata"] == AwsProviderMetadataRequest(
            kind=AwsProviderMetadataKind.AWS,
            role_arn="arn:aws:iam::123:role/MyRole",
        )

    def test_create_invalid_provider_metadata_json_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that invalid JSON for --provider-metadata causes a non-zero exit."""
        result = _invoke(
            [
                "ai-integrations",
                "create",
                "--name",
                "Bad",
                "--provider",
                "AWS_BEDROCK",
                "--provider-metadata",
                "not-json",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0

    def test_create_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error during create causes a non-zero exit."""
        mock_client.ai_integrations.create.side_effect = RuntimeError(
            "Conflict"
        )
        result = _invoke(
            [
                "ai-integrations",
                "create",
                "--name",
                "Test",
                "--provider",
                "OPEN_AI",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax ai-integrations update
# ---------------------------------------------------------------------------


class TestUpdateAiIntegration:
    """Tests for `ax ai-integrations update <id>`."""

    def test_update_name_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that update passes integration_id and name."""
        mock_client.ai_integrations.update.return_value = _make_integration(
            name="Renamed"
        )

        result = _invoke(
            [
                "ai-integrations",
                "update",
                _INTEGRATION_ID,
                "--name",
                "Renamed",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.ai_integrations.update.call_args.kwargs
        assert call_kwargs["integration"] == _INTEGRATION_ID
        assert call_kwargs["space"] is None
        assert call_kwargs["name"] == "Renamed"

    def test_update_space_forwarded(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --space is forwarded to the SDK."""
        mock_client.ai_integrations.update.return_value = _make_integration(
            name="Renamed"
        )

        result = _invoke(
            [
                "ai-integrations",
                "update",
                _INTEGRATION_ID,
                "--name",
                "Renamed",
                "--space",
                "sp_xyz",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.ai_integrations.update.call_args.kwargs
        assert call_kwargs["space"] == "sp_xyz"

    def test_update_no_options_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that calling update with no options causes a non-zero exit."""
        result = _invoke(
            ["ai-integrations", "update", _INTEGRATION_ID],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0

    def test_update_provider_forwarded(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --provider is forwarded to the SDK."""
        mock_client.ai_integrations.update.return_value = _make_integration()

        result = _invoke(
            [
                "ai-integrations",
                "update",
                _INTEGRATION_ID,
                "--provider",
                "ANTHROPIC",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.ai_integrations.update.call_args.kwargs
        assert call_kwargs["provider"] == AiIntegrationProvider.ANTHROPIC

    def test_update_auth_type_forwarded(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --auth-type is forwarded to the SDK."""
        mock_client.ai_integrations.update.return_value = _make_integration()

        result = _invoke(
            [
                "ai-integrations",
                "update",
                _INTEGRATION_ID,
                "--auth-type",
                "BEARER_TOKEN",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.ai_integrations.update.call_args.kwargs
        assert call_kwargs["auth_type"] == AiIntegrationAuthType.BEARER_TOKEN

    def test_update_base_url_forwarded(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --base-url is forwarded to the SDK."""
        mock_client.ai_integrations.update.return_value = _make_integration()

        result = _invoke(
            [
                "ai-integrations",
                "update",
                _INTEGRATION_ID,
                "--base-url",
                "https://my-proxy.example.com",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.ai_integrations.update.call_args.kwargs
        assert call_kwargs["base_url"] == "https://my-proxy.example.com"

    def test_update_api_key_forwarded(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --api-key is forwarded to the SDK."""
        mock_client.ai_integrations.update.return_value = _make_integration()

        result = _invoke(
            [
                "ai-integrations",
                "update",
                _INTEGRATION_ID,
                "--api-key",
                "sk-new-key",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.ai_integrations.update.call_args.kwargs
        assert call_kwargs["api_key"] == "sk-new-key"

    def test_update_model_names_forwarded(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --model-name (repeatable) is forwarded as a list."""
        mock_client.ai_integrations.update.return_value = _make_integration()

        result = _invoke(
            [
                "ai-integrations",
                "update",
                _INTEGRATION_ID,
                "--model-name",
                "gpt-4o",
                "--model-name",
                "gpt-4o-mini",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.ai_integrations.update.call_args.kwargs
        assert call_kwargs["model_names"] == ["gpt-4o", "gpt-4o-mini"]

    def test_update_enable_default_models_true(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --enable-default-models sets the flag to True."""
        mock_client.ai_integrations.update.return_value = _make_integration()

        result = _invoke(
            [
                "ai-integrations",
                "update",
                _INTEGRATION_ID,
                "--enable-default-models",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.ai_integrations.update.call_args.kwargs
        assert call_kwargs["enable_default_models"] is True

    def test_update_no_enable_default_models_false(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --no-enable-default-models sets the flag to False."""
        mock_client.ai_integrations.update.return_value = _make_integration()

        result = _invoke(
            [
                "ai-integrations",
                "update",
                _INTEGRATION_ID,
                "--no-enable-default-models",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.ai_integrations.update.call_args.kwargs
        assert call_kwargs["enable_default_models"] is False

    def test_update_function_calling_enabled_true(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --function-calling-enabled sets the flag to True."""
        mock_client.ai_integrations.update.return_value = _make_integration()

        result = _invoke(
            [
                "ai-integrations",
                "update",
                _INTEGRATION_ID,
                "--function-calling-enabled",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.ai_integrations.update.call_args.kwargs
        assert call_kwargs["function_calling_enabled"] is True

    def test_update_headers_forwarded(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --headers is parsed and forwarded to the SDK."""
        mock_client.ai_integrations.update.return_value = _make_integration()

        result = _invoke(
            [
                "ai-integrations",
                "update",
                _INTEGRATION_ID,
                "--headers",
                '{"X-Custom": "value"}',
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.ai_integrations.update.call_args.kwargs
        assert call_kwargs["headers"] == {"X-Custom": "value"}

    def test_update_invalid_headers_json_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that invalid JSON for --headers causes a non-zero exit."""
        result = _invoke(
            [
                "ai-integrations",
                "update",
                _INTEGRATION_ID,
                "--headers",
                "not-json",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0

    def test_update_provider_metadata_forwarded(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --provider-metadata is parsed and forwarded to the SDK."""
        mock_client.ai_integrations.update.return_value = _make_integration()

        result = _invoke(
            [
                "ai-integrations",
                "update",
                _INTEGRATION_ID,
                "--provider-metadata",
                '{"role_arn": "arn:aws:iam::123:role/MyRole"}',
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.ai_integrations.update.call_args.kwargs
        assert call_kwargs["provider_metadata"] == {
            "role_arn": "arn:aws:iam::123:role/MyRole"
        }

    def test_update_invalid_provider_metadata_json_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that invalid JSON for --provider-metadata causes a non-zero exit."""
        result = _invoke(
            [
                "ai-integrations",
                "update",
                _INTEGRATION_ID,
                "--provider-metadata",
                "not-json",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0

    def test_update_scopings_forwarded(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --scopings is parsed into AiIntegrationScoping objects."""
        mock_client.ai_integrations.update.return_value = _make_integration()

        result = _invoke(
            [
                "ai-integrations",
                "update",
                _INTEGRATION_ID,
                "--scopings",
                '[{"space_id": "sp_abc"}]',
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.ai_integrations.update.call_args.kwargs
        assert call_kwargs["scopings"] == [
            AiIntegrationScoping(space_id="sp_abc")
        ]

    def test_update_invalid_scopings_json_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that invalid JSON for --scopings causes a non-zero exit."""
        result = _invoke(
            [
                "ai-integrations",
                "update",
                _INTEGRATION_ID,
                "--scopings",
                "not-json",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0

    def test_update_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error during update causes a non-zero exit."""
        mock_client.ai_integrations.update.side_effect = RuntimeError(
            "Not found"
        )
        result = _invoke(
            [
                "ai-integrations",
                "update",
                _INTEGRATION_ID,
                "--name",
                "New",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax ai-integrations delete
# ---------------------------------------------------------------------------


class TestDeleteAiIntegration:
    """Tests for `ax ai-integrations delete <id>`."""

    def test_delete_force_skips_confirmation(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --force bypasses the prompt and deletes."""
        mock_client.ai_integrations.delete.return_value = None

        result = _invoke(
            ["ai-integrations", "delete", _INTEGRATION_ID, "--force"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.ai_integrations.delete.assert_called_once_with(
            integration=_INTEGRATION_ID, space=None
        )

    def test_delete_confirms_yes_calls_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that confirming the prompt proceeds with deletion."""
        mock_client.ai_integrations.delete.return_value = None

        result = _invoke(
            ["ai-integrations", "delete", _INTEGRATION_ID],
            mock_config,
            mock_client,
            cli_input="y\n",
        )

        assert result.exit_code == 0, result.output
        mock_client.ai_integrations.delete.assert_called_once_with(
            integration=_INTEGRATION_ID, space=None
        )

    def test_delete_declines_does_not_call_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that declining the confirmation leaves the integration untouched."""
        result = _invoke(
            ["ai-integrations", "delete", _INTEGRATION_ID],
            mock_config,
            mock_client,
            cli_input="n\n",
        )

        assert result.exit_code == 0
        mock_client.ai_integrations.delete.assert_not_called()

    def test_delete_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error during delete causes a non-zero exit."""
        mock_client.ai_integrations.delete.side_effect = RuntimeError(
            "Not found"
        )
        result = _invoke(
            ["ai-integrations", "delete", _INTEGRATION_ID, "--force"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
