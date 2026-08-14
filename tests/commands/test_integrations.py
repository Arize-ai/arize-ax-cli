"""Tests for integrations CLI commands."""

import json
from unittest.mock import MagicMock, patch

import pytest
from arize.integrations.types import (
    CreateAnthropicConfig,
    CreateAwsBedrockAuth,
    CreateAwsBedrockConfig,
    CreateCustomConfig,
    CreateLlmConfig,
    CreateNvidiaNimConfig,
    CreateOpenAiConfig,
    CreateVertexAiConfig,
    IntegrationScoping,
    IntegrationType,
    UpdateAgentRequestPresetInput,
)
from typer.testing import CliRunner, Result

from ax.cli import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers to build realistic SDK response objects
# ---------------------------------------------------------------------------

_INTEGRATION_ID = "int_test_1"


def _make_integration(
    integration_id: str = _INTEGRATION_ID,
    name: str = "My Integration",
    integration_type: str = "LLM",
) -> MagicMock:
    """Build an LlmIntegration/AgentIntegration mock."""
    mock = MagicMock()
    mock.id = integration_id
    mock.name = name
    mock.type = integration_type
    return mock


def _make_list_response(*integrations: MagicMock) -> MagicMock:
    """Build a ListIntegrationsResponse mock."""
    mock = MagicMock()
    mock.integrations = list(integrations)
    mock.pagination.has_more = False
    return mock


# ---------------------------------------------------------------------------
# Shared mock setup
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a mock ArizeClient with the integrations subclient pre-wired."""
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
            "ax.commands.integrations.make_client",
            return_value=(mock_client, mock_config),
        ),
    ):
        return runner.invoke(app, args, input=cli_input)


# ---------------------------------------------------------------------------
# ax integrations list
# ---------------------------------------------------------------------------


class TestListIntegrations:
    """Tests for `ax integrations list`."""

    def test_list_returns_integrations_in_output(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that listed integrations appear in the output."""
        mock_client.integrations.list.return_value = _make_list_response(
            _make_integration(name="Alpha"),
            _make_integration(name="Beta", integration_type="AGENT"),
        )

        result = _invoke(
            ["integrations", "list", "--output", "json"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.integrations.list.assert_called_once()

    def test_list_passes_options_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --type, --name, --space, --limit, --cursor forward."""
        mock_client.integrations.list.return_value = _make_list_response()

        _invoke(
            [
                "integrations",
                "list",
                "--type",
                "AGENT",
                "--name",
                "openai",
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

        mock_client.integrations.list.assert_called_once_with(
            integration_type=IntegrationType.AGENT,
            name="openai",
            space="sp_abc",
            limit=5,
            cursor="tok",
        )

    def test_list_defaults_omit_type(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that omitting --type requests the merged multi-type list."""
        mock_client.integrations.list.return_value = _make_list_response()

        _invoke(["integrations", "list"], mock_config, mock_client)

        mock_client.integrations.list.assert_called_once_with(
            integration_type=None,
            name=None,
            space=None,
            limit=15,
            cursor=None,
        )

    def test_list_rejects_invalid_type(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an unknown --type value fails argument parsing."""
        result = _invoke(
            ["integrations", "list", "--type", "WEBHOOK"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.integrations.list.assert_not_called()

    def test_list_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error results in a non-zero exit."""
        mock_client.integrations.list.side_effect = RuntimeError("error")
        result = _invoke(["integrations", "list"], mock_config, mock_client)
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax integrations get
# ---------------------------------------------------------------------------


class TestGetIntegration:
    """Tests for `ax integrations get <id>`."""

    def test_get_calls_sdk_with_correct_id(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that the positional ID is forwarded to the SDK."""
        mock_client.integrations.get.return_value = _make_integration()

        _invoke(
            ["integrations", "get", _INTEGRATION_ID],
            mock_config,
            mock_client,
        )

        mock_client.integrations.get.assert_called_once_with(
            integration=_INTEGRATION_ID,
            integration_type=None,
            space=None,
        )

    def test_get_forwards_type_and_space(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --type and --space are forwarded for name resolution."""
        mock_client.integrations.get.return_value = _make_integration()

        _invoke(
            [
                "integrations",
                "get",
                "my-integration",
                "--type",
                "LLM",
                "--space",
                "sp_abc",
            ],
            mock_config,
            mock_client,
        )

        mock_client.integrations.get.assert_called_once_with(
            integration="my-integration",
            integration_type=IntegrationType.LLM,
            space="sp_abc",
        )

    def test_get_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error (e.g. 404) results in a non-zero exit."""
        mock_client.integrations.get.side_effect = RuntimeError("Not found")
        result = _invoke(
            ["integrations", "get", _INTEGRATION_ID],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax integrations create llm
# ---------------------------------------------------------------------------


class TestCreateLlmIntegration:
    """Tests for `ax integrations create llm`."""

    def test_create_llm_builds_provider_config(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that flags build the provider config oneOf."""
        mock_client.integrations.create_llm.return_value = _make_integration()

        result = _invoke(
            [
                "integrations",
                "create",
                "llm",
                "--name",
                "my-openai",
                "--provider",
                "OPEN_AI",
                "--api-key",
                "sk-test",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.integrations.create_llm.assert_called_once_with(
            name="my-openai",
            config=CreateLlmConfig(
                actual_instance=CreateOpenAiConfig(
                    provider="OPEN_AI", api_key="sk-test"
                )
            ),
            scopings=None,
        )

    def test_create_llm_function_calling_flag(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --no-function-calling-enabled reaches the config."""
        mock_client.integrations.create_llm.return_value = _make_integration()

        result = _invoke(
            [
                "integrations",
                "create",
                "llm",
                "--name",
                "my-anthropic",
                "--provider",
                "ANTHROPIC",
                "--api-key",
                "sk-test",
                "--no-function-calling-enabled",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        config = mock_client.integrations.create_llm.call_args.kwargs["config"]
        assert config == CreateLlmConfig(
            actual_instance=CreateAnthropicConfig(
                provider="ANTHROPIC",
                api_key="sk-test",
                is_function_calling_enabled=False,
            )
        )

    def test_create_llm_custom_provider(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that CUSTOM builds the config from --base-url and --headers."""
        mock_client.integrations.create_llm.return_value = _make_integration()

        result = _invoke(
            [
                "integrations",
                "create",
                "llm",
                "--name",
                "my-custom",
                "--provider",
                "CUSTOM",
                "--base-url",
                "https://llm.example.com",
                "--model-name",
                "my-model",
                "--headers",
                json.dumps({"X-Api-Key": "secret"}),
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        config = mock_client.integrations.create_llm.call_args.kwargs["config"]
        assert config == CreateLlmConfig(
            actual_instance=CreateCustomConfig(
                provider="CUSTOM",
                base_url="https://llm.example.com",
                headers={"X-Api-Key": "secret"},
                model_names=["my-model"],
            )
        )

    def test_create_llm_vertex_provider(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that VERTEX_AI builds the config from its required flags."""
        mock_client.integrations.create_llm.return_value = _make_integration()

        result = _invoke(
            [
                "integrations",
                "create",
                "llm",
                "--name",
                "my-vertex",
                "--provider",
                "VERTEX_AI",
                "--gcp-project-id",
                "proj-1",
                "--gcp-location",
                "us-central1",
                "--project-access-label",
                "label-1",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        config = mock_client.integrations.create_llm.call_args.kwargs["config"]
        assert config == CreateLlmConfig(
            actual_instance=CreateVertexAiConfig(
                provider="VERTEX_AI",
                project_id="proj-1",
                location="us-central1",
                project_access_label="label-1",
            )
        )

    def test_create_llm_nvidia_nim_optional_fields(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that NVIDIA_NIM builds a config with only optional fields."""
        mock_client.integrations.create_llm.return_value = _make_integration()

        result = _invoke(
            [
                "integrations",
                "create",
                "llm",
                "--name",
                "my-nim",
                "--provider",
                "NVIDIA_NIM",
                "--base-url",
                "https://nim.example.com",
                "--enable-default-models",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        config = mock_client.integrations.create_llm.call_args.kwargs["config"]
        assert config == CreateLlmConfig(
            actual_instance=CreateNvidiaNimConfig(
                provider="NVIDIA_NIM",
                base_url="https://nim.example.com",
                is_default_models_enabled=True,
            )
        )

    def test_create_llm_bedrock_parses_auth(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that AWS_BEDROCK parses --auth into the auth oneOf."""
        mock_client.integrations.create_llm.return_value = _make_integration()

        result = _invoke(
            [
                "integrations",
                "create",
                "llm",
                "--name",
                "my-bedrock",
                "--provider",
                "AWS_BEDROCK",
                "--auth",
                json.dumps(
                    {
                        "auth_type": "DEFAULT",
                        "role_arn": "arn:aws:iam::123:role/arize",
                    }
                ),
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        config = mock_client.integrations.create_llm.call_args.kwargs["config"]
        assert isinstance(config.actual_instance, CreateAwsBedrockConfig)
        assert isinstance(config.actual_instance.auth, CreateAwsBedrockAuth)

    def test_create_llm_forwards_scopings(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --scopings pass through to the SDK."""
        mock_client.integrations.create_llm.return_value = _make_integration()

        result = _invoke(
            [
                "integrations",
                "create",
                "llm",
                "--name",
                "my-openai",
                "--provider",
                "OPEN_AI",
                "--api-key",
                "sk-test",
                "--scopings",
                json.dumps([{"organization_id": "org_1", "space_id": "sp_1"}]),
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        scopings = mock_client.integrations.create_llm.call_args.kwargs[
            "scopings"
        ]
        assert len(scopings) == 1
        assert isinstance(scopings[0], IntegrationScoping)
        assert scopings[0].organization_id == "org_1"
        assert scopings[0].space_id == "sp_1"

    def test_create_llm_missing_required_flag_is_usage_error(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that a missing provider-required flag fails cleanly."""
        result = _invoke(
            [
                "integrations",
                "create",
                "llm",
                "--name",
                "x",
                "--provider",
                "OPEN_AI",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 2
        assert "--api-key" in result.output
        mock_client.integrations.create_llm.assert_not_called()

    def test_create_llm_invalid_auth_does_not_leak_generated_errors(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that a bad auth oneOf fails without generated parser dumps."""
        result = _invoke(
            [
                "integrations",
                "create",
                "llm",
                "--name",
                "x",
                "--provider",
                "AWS_BEDROCK",
                "--auth",
                json.dumps({"auth_type": "NOT_A_REAL_AUTH"}),
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 2
        assert "pydantic.dev" not in result.output
        assert "oneof_schema" not in result.output
        mock_client.integrations.create_llm.assert_not_called()

    def test_create_llm_non_array_scopings_is_usage_error(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that a non-array scopings value fails cleanly."""
        result = _invoke(
            [
                "integrations",
                "create",
                "llm",
                "--name",
                "x",
                "--provider",
                "OPEN_AI",
                "--api-key",
                "sk-test",
                "--scopings",
                json.dumps({"space_id": "sp_1"}),
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 2
        assert "JSON array" in result.output
        mock_client.integrations.create_llm.assert_not_called()

    def test_create_llm_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error (e.g. 409) results in a non-zero exit."""
        mock_client.integrations.create_llm.side_effect = RuntimeError("409")
        result = _invoke(
            [
                "integrations",
                "create",
                "llm",
                "--name",
                "x",
                "--provider",
                "OPEN_AI",
                "--api-key",
                "sk-test",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax integrations create agent
# ---------------------------------------------------------------------------


class TestCreateAgentIntegration:
    """Tests for `ax integrations create agent`."""

    def test_create_agent_maps_flags_to_kwargs(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that agent flags map to the SDK kwargs."""
        mock_client.integrations.create_agent.return_value = _make_integration(
            integration_type="AGENT"
        )

        result = _invoke(
            [
                "integrations",
                "create",
                "agent",
                "--name",
                "my-agent",
                "--endpoint",
                "https://agent.example.com/run",
                "--input-schema",
                json.dumps({"type": "object"}),
                "--description",
                "test agent",
                "--headers",
                json.dumps({"X-Auth": "secret"}),
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.integrations.create_agent.assert_called_once_with(
            name="my-agent",
            endpoint="https://agent.example.com/run",
            input_schema={"type": "object"},
            description="test agent",
            headers={"X-Auth": "secret"},
            request_presets=None,
            scopings=None,
        )

    def test_create_agent_parses_request_presets(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that request presets are parsed into typed inputs."""
        mock_client.integrations.create_agent.return_value = _make_integration(
            integration_type="AGENT"
        )

        result = _invoke(
            [
                "integrations",
                "create",
                "agent",
                "--name",
                "my-agent",
                "--endpoint",
                "https://agent.example.com/run",
                "--input-schema",
                json.dumps({"type": "object"}),
                "--request-presets",
                json.dumps(
                    [{"name": "default", "config": {"model": "gpt-4o"}}]
                ),
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        presets = mock_client.integrations.create_agent.call_args.kwargs[
            "request_presets"
        ]
        assert len(presets) == 1
        assert presets[0].name == "default"
        assert presets[0].config == {"model": "gpt-4o"}

    def test_create_agent_requires_input_schema(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that omitting --input-schema fails argument parsing."""
        result = _invoke(
            [
                "integrations",
                "create",
                "agent",
                "--name",
                "my-agent",
                "--endpoint",
                "https://agent.example.com/run",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 2
        mock_client.integrations.create_agent.assert_not_called()

    def test_create_agent_non_array_request_presets_is_usage_error(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that a non-array request_presets fails cleanly."""
        result = _invoke(
            [
                "integrations",
                "create",
                "agent",
                "--name",
                "my-agent",
                "--endpoint",
                "https://agent.example.com/run",
                "--input-schema",
                json.dumps({"type": "object"}),
                "--request-presets",
                json.dumps({"name": "default"}),
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 2
        assert "JSON array" in result.output
        mock_client.integrations.create_agent.assert_not_called()


# ---------------------------------------------------------------------------
# ax integrations update llm
# ---------------------------------------------------------------------------


class TestUpdateLlmIntegration:
    """Tests for `ax integrations update llm <id>`."""

    def test_update_llm_sends_only_present_fields(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that only provided flags become SDK kwargs."""
        mock_client.integrations.update_llm.return_value = _make_integration()

        result = _invoke(
            [
                "integrations",
                "update",
                "llm",
                _INTEGRATION_ID,
                "--api-key",
                "sk-new",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.integrations.update_llm.assert_called_once_with(
            integration=_INTEGRATION_ID,
            space=None,
            api_key="sk-new",
        )

    def test_update_llm_maps_name_and_function_calling(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --name and function-calling map to SDK kwargs."""
        mock_client.integrations.update_llm.return_value = _make_integration()

        _invoke(
            [
                "integrations",
                "update",
                "llm",
                _INTEGRATION_ID,
                "--name",
                "renamed",
                "--no-function-calling-enabled",
            ],
            mock_config,
            mock_client,
        )

        mock_client.integrations.update_llm.assert_called_once_with(
            integration=_INTEGRATION_ID,
            space=None,
            name="renamed",
            function_calling_enabled=False,
        )

    def test_update_llm_null_headers_clears(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --headers null is forwarded as None to clear."""
        mock_client.integrations.update_llm.return_value = _make_integration()

        _invoke(
            [
                "integrations",
                "update",
                "llm",
                _INTEGRATION_ID,
                "--headers",
                "null",
            ],
            mock_config,
            mock_client,
        )

        mock_client.integrations.update_llm.assert_called_once_with(
            integration=_INTEGRATION_ID,
            space=None,
            headers=None,
        )

    def test_update_llm_parses_bedrock_auth(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --auth is parsed into the auth oneOf."""
        mock_client.integrations.update_llm.return_value = _make_integration()

        result = _invoke(
            [
                "integrations",
                "update",
                "llm",
                _INTEGRATION_ID,
                "--auth",
                json.dumps(
                    {
                        "auth_type": "DEFAULT",
                        "role_arn": "arn:aws:iam::123:role/arize",
                    }
                ),
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        auth = mock_client.integrations.update_llm.call_args.kwargs["auth"]
        assert isinstance(auth, CreateAwsBedrockAuth)
        assert auth.actual_instance.role_arn == "arn:aws:iam::123:role/arize"

    def test_update_llm_invalid_auth_does_not_leak_generated_errors(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that a bad auth oneOf fails without generated parser dumps."""
        result = _invoke(
            [
                "integrations",
                "update",
                "llm",
                _INTEGRATION_ID,
                "--auth",
                json.dumps({"auth_type": "NOT_A_REAL_AUTH"}),
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 2
        assert "pydantic.dev" not in result.output
        assert "oneof_schema" not in result.output
        mock_client.integrations.update_llm.assert_not_called()

    def test_update_llm_rejects_provider_flag(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that provider is immutable — no --provider flag exists."""
        result = _invoke(
            [
                "integrations",
                "update",
                "llm",
                _INTEGRATION_ID,
                "--provider",
                "ANTHROPIC",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 2
        assert "provider" in result.output.lower()
        mock_client.integrations.update_llm.assert_not_called()

    def test_update_llm_empty_is_usage_error(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that a no-field update fails without calling the SDK."""
        result = _invoke(
            ["integrations", "update", "llm", _INTEGRATION_ID],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 2
        mock_client.integrations.update_llm.assert_not_called()

    def test_update_llm_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error results in a non-zero exit."""
        mock_client.integrations.update_llm.side_effect = RuntimeError("422")
        result = _invoke(
            [
                "integrations",
                "update",
                "llm",
                _INTEGRATION_ID,
                "--name",
                "x",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax integrations update agent
# ---------------------------------------------------------------------------


class TestUpdateAgentIntegration:
    """Tests for `ax integrations update agent <id>`."""

    def test_update_agent_sends_only_present_fields(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test agent updates map only provided flags to kwargs."""
        mock_client.integrations.update_agent.return_value = _make_integration(
            integration_type="AGENT"
        )

        result = _invoke(
            [
                "integrations",
                "update",
                "agent",
                "my-agent",
                "--endpoint",
                "https://agent.example.com/v2/run",
                "--space",
                "sp_abc",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.integrations.update_agent.assert_called_once_with(
            integration="my-agent",
            space="sp_abc",
            endpoint="https://agent.example.com/v2/run",
        )

    def test_update_agent_parses_request_presets(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that replacement presets are parsed into typed inputs."""
        mock_client.integrations.update_agent.return_value = _make_integration(
            integration_type="AGENT"
        )

        result = _invoke(
            [
                "integrations",
                "update",
                "agent",
                _INTEGRATION_ID,
                "--request-presets",
                json.dumps(
                    [{"name": "default", "config": {"model": "gpt-4o"}}]
                ),
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        presets = mock_client.integrations.update_agent.call_args.kwargs[
            "request_presets"
        ]
        assert len(presets) == 1
        assert isinstance(presets[0], UpdateAgentRequestPresetInput)
        assert presets[0].name == "default"

    def test_update_agent_input_schema_parsed(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --input-schema is parsed into a dict kwarg."""
        mock_client.integrations.update_agent.return_value = _make_integration(
            integration_type="AGENT"
        )

        _invoke(
            [
                "integrations",
                "update",
                "agent",
                _INTEGRATION_ID,
                "--input-schema",
                json.dumps({"type": "object"}),
            ],
            mock_config,
            mock_client,
        )

        mock_client.integrations.update_agent.assert_called_once_with(
            integration=_INTEGRATION_ID,
            space=None,
            input_schema={"type": "object"},
        )

    def test_update_agent_non_array_request_presets_is_usage_error(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that a non-array request_presets fails cleanly on update."""
        result = _invoke(
            [
                "integrations",
                "update",
                "agent",
                _INTEGRATION_ID,
                "--request-presets",
                json.dumps({"name": "default"}),
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 2
        assert "JSON array" in result.output
        mock_client.integrations.update_agent.assert_not_called()

    def test_update_agent_unknown_flag_is_usage_error(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an unknown flag fails loudly."""
        result = _invoke(
            [
                "integrations",
                "update",
                "agent",
                _INTEGRATION_ID,
                "--endpont",
                "https://x",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 2
        mock_client.integrations.update_agent.assert_not_called()

    def test_update_agent_empty_is_usage_error(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that a no-field update fails without calling the SDK."""
        result = _invoke(
            ["integrations", "update", "agent", _INTEGRATION_ID],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 2
        mock_client.integrations.update_agent.assert_not_called()


# ---------------------------------------------------------------------------
# ax integrations delete
# ---------------------------------------------------------------------------


class TestDeleteIntegration:
    """Tests for `ax integrations delete <id>`."""

    def test_delete_with_force_skips_confirmation(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --force deletes without prompting."""
        result = _invoke(
            ["integrations", "delete", _INTEGRATION_ID, "--force"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.integrations.delete.assert_called_once_with(
            integration=_INTEGRATION_ID,
            integration_type=None,
            space=None,
        )

    def test_delete_forwards_type_and_space(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --type and --space are forwarded for name resolution."""
        _invoke(
            [
                "integrations",
                "delete",
                "my-agent",
                "--type",
                "AGENT",
                "--space",
                "sp_abc",
                "--force",
            ],
            mock_config,
            mock_client,
        )

        mock_client.integrations.delete.assert_called_once_with(
            integration="my-agent",
            integration_type=IntegrationType.AGENT,
            space="sp_abc",
        )

    def test_delete_confirmation_yes_deletes(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that answering yes at the prompt deletes."""
        result = _invoke(
            ["integrations", "delete", _INTEGRATION_ID],
            mock_config,
            mock_client,
            cli_input="y\n",
        )

        assert result.exit_code == 0, result.output
        mock_client.integrations.delete.assert_called_once()

    def test_delete_confirmation_no_aborts(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that answering no at the prompt aborts the deletion."""
        result = _invoke(
            ["integrations", "delete", _INTEGRATION_ID],
            mock_config,
            mock_client,
            cli_input="n\n",
        )

        assert result.exit_code == 0, result.output
        mock_client.integrations.delete.assert_not_called()

    def test_delete_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error results in a non-zero exit."""
        mock_client.integrations.delete.side_effect = RuntimeError("404")
        result = _invoke(
            ["integrations", "delete", _INTEGRATION_ID, "--force"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
