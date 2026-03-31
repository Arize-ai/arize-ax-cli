"""AI integration management commands."""

from dataclasses import asdict
from typing import Annotated, Any, overload

import typer
from arize import ArizeClient
from arize._generated.api_client.models.ai_integration_auth_type import (
    AiIntegrationAuthType,
)
from arize._generated.api_client.models.ai_integration_provider import (
    AiIntegrationProvider,
)
from arize._generated.api_client.models.ai_integration_scoping import (
    AiIntegrationScoping,
)

from ax.config.manager import ConfigManager
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError, UsageError
from ax.core.output import output_data
from ax.utils.console import (
    confirm,
    info,
    setup_logging,
    spinner,
    warning,
)
from ax.utils.file_io import parse_output_option
from ax.utils.json_source import load_json

# Create ai-integrations subcommand app
app = typer.Typer(
    name="ai-integrations",
    help="Manage AI integrations",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


@overload
def _parse_json_option(
    value: str, option_name: str, expected: type[dict]
) -> dict[str, Any]: ...


@overload
def _parse_json_option(
    value: str, option_name: str, expected: type[list]
) -> list[dict[str, Any]]: ...


def _parse_json_option(
    value: str, option_name: str, expected: type
) -> dict[str, Any] | list[dict[str, Any]]:
    """Parse a JSON CLI option and validate its top-level type."""
    parsed = load_json(value)
    if not isinstance(parsed, expected):
        raise typer.BadParameter(
            f"{option_name} must be a JSON {expected.__name__}"
        )
    return parsed


@app.command("list")
@handle_errors
def list_ai_integrations(
    space_id: Annotated[
        str | None,
        typer.Option(
            "--space-id",
            help="Space ID to filter integrations",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of integrations to return",
        ),
    ] = 15,
    cursor: Annotated[
        str | None,
        typer.Option(
            "--cursor",
            help="Pagination cursor for next page",
        ),
    ] = None,
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help="Configuration profile to use",
        ),
    ] = "",
    output: Annotated[
        str,
        typer.Option(
            "--output",
            "-o",
            help="Output format (table, json, csv, parquet) or file path",
        ),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
) -> None:
    """List AI integrations."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching AI integrations"):
            response = client.ai_integrations.list(
                space=space_id,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list AI integrations: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("get")
@handle_errors
def get_ai_integration(
    id: Annotated[
        str,
        typer.Argument(help="AI integration ID"),
    ],
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help="Configuration profile to use",
        ),
    ] = "",
    output: Annotated[
        str,
        typer.Option(
            "--output",
            "-o",
            help="Output format (table, json, csv, parquet) or file path",
        ),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
) -> None:
    """Get an AI integration by ID."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching AI integration"):
            integration = client.ai_integrations.get(integration=id)
    except Exception as e:
        raise APIError(f"Failed to get AI integration: {e}") from e
    else:
        output_data(
            integration,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("create")
@handle_errors
def create_ai_integration(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Integration name (must be unique within the account)",
        ),
    ],
    provider: Annotated[
        AiIntegrationProvider,
        typer.Option(
            "--provider",
            help=(
                "LLM provider: openAI, azureOpenAI, awsBedrock, vertexAI, "
                "anthropic, custom, nvidiaNim, gemini"
            ),
        ),
    ],
    api_key: Annotated[
        str | None,
        typer.Option(
            "--api-key",
            help="API key for the provider (write-only, never returned)",
        ),
    ] = None,
    base_url: Annotated[
        str | None,
        typer.Option(
            "--base-url",
            help="Custom base URL for the provider",
        ),
    ] = None,
    model_names: Annotated[
        list[str] | None,
        typer.Option(
            "--model-name",
            help=(
                "Supported model name (repeat for multiple, "
                "e.g. --model-name gpt-4o --model-name gpt-4o-mini)"
            ),
        ),
    ] = None,
    enable_default_models: Annotated[
        bool,
        typer.Option(
            "--enable-default-models",
            is_flag=True,
            help="Enable the provider's default model list",
        ),
    ] = False,
    function_calling_enabled: Annotated[
        bool,
        typer.Option(
            "--function-calling-enabled",
            is_flag=True,
            help="Enable function/tool calling",
        ),
    ] = False,
    auth_type: Annotated[
        AiIntegrationAuthType | None,
        typer.Option(
            "--auth-type",
            help=(
                "Authentication type: default, proxy_with_headers, bearer_token"
            ),
        ),
    ] = None,
    headers: Annotated[
        str | None,
        typer.Option(
            "--headers",
            help=(
                "Custom headers as a JSON object or path to a JSON file, "
                'e.g. \'{"X-Custom-Header": "value"}\' or headers.json'
            ),
        ),
    ] = None,
    provider_metadata: Annotated[
        str | None,
        typer.Option(
            "--provider-metadata",
            help=(
                "Provider-specific metadata as a JSON object or path to a JSON file. "
                "Required for awsBedrock (role_arn) and vertexAI "
                "(project_id, location, project_access_label)."
            ),
        ),
    ] = None,
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help="Configuration profile to use",
        ),
    ] = "",
    output: Annotated[
        str,
        typer.Option(
            "--output",
            "-o",
            help="Output format (table, json, csv, parquet) or file path",
        ),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
) -> None:
    r"""Create a new AI integration.

    Provider-specific requirements:

    \b
    - awsBedrock:  --provider-metadata '{"role_arn": "..."}'
    - vertexAI:    --provider-metadata '{"project_id": "...",
                       "location": "...", "project_access_label": "..."}'
    """
    parsed_headers = (
        _parse_json_option(headers, "--headers", dict) if headers else None
    )
    parsed_provider_metadata = (
        _parse_json_option(provider_metadata, "--provider-metadata", dict)
        if provider_metadata
        else None
    )

    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Creating AI integration",
            success_msg="AI integration created successfully",
        ):
            integration = client.ai_integrations.create(
                name=name,
                provider=provider,
                api_key=api_key,
                base_url=base_url,
                model_names=model_names,
                headers=parsed_headers,
                enable_default_models=enable_default_models,
                function_calling_enabled=function_calling_enabled,
                auth_type=auth_type,
                provider_metadata=parsed_provider_metadata,
            )
    except Exception as e:
        raise APIError(f"Failed to create AI integration: {e}") from e
    else:
        output_data(
            integration,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("update")
@handle_errors
def update_ai_integration(
    id: Annotated[
        str,
        typer.Argument(help="AI integration ID"),
    ],
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Updated integration name",
        ),
    ] = None,
    provider: Annotated[
        AiIntegrationProvider | None,
        typer.Option(
            "--provider",
            help=(
                "Updated LLM provider: openAI, azureOpenAI, awsBedrock, vertexAI, "
                "anthropic, custom, nvidiaNim, gemini"
            ),
        ),
    ] = None,
    api_key: Annotated[
        str | None,
        typer.Option(
            "--api-key",
            help="New API key for the provider (write only, never returned)",
        ),
    ] = None,
    base_url: Annotated[
        str | None,
        typer.Option(
            "--base-url",
            help="Updated custom base URL",
        ),
    ] = None,
    model_names: Annotated[
        list[str] | None,
        typer.Option(
            "--model-name",
            help=(
                "Supported model name (repeat for multiple). "
                "Replaces all existing model names."
            ),
        ),
    ] = None,
    enable_default_models: Annotated[
        bool | None,
        typer.Option(
            "--enable-default-models/--no-enable-default-models",
            help="Enable the provider's default model list (omit to leave unchanged)",
        ),
    ] = None,
    function_calling_enabled: Annotated[
        bool | None,
        typer.Option(
            "--function-calling-enabled/--no-function-calling-enabled",
            help="Enable function/tool calling (omit to leave unchanged)",
        ),
    ] = None,
    auth_type: Annotated[
        AiIntegrationAuthType | None,
        typer.Option(
            "--auth-type",
            help=(
                "Updated authentication type: default, proxy_with_headers, bearer_token"
            ),
        ),
    ] = None,
    headers: Annotated[
        str | None,
        typer.Option(
            "--headers",
            help=(
                "Custom headers as a JSON object or path to a JSON file, "
                'e.g. \'{"X-Custom-Header": "value"}\' or headers.json. '
                "Pass 'null' to clear existing headers."
            ),
        ),
    ] = None,
    provider_metadata: Annotated[
        str | None,
        typer.Option(
            "--provider-metadata",
            help=(
                "Provider-specific metadata as a JSON object or path to a JSON file. "
                "Pass 'null' to clear existing metadata."
            ),
        ),
    ] = None,
    scopings: Annotated[
        str | None,
        typer.Option(
            "--scopings",
            help=(
                "Visibility scoping rules as a JSON array or path to a JSON file. "
                "Replaces all existing scopings. "
                'e.g. \'[{"space_id": "sp_abc"}]\' or scopings.json'
            ),
        ),
    ] = None,
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help="Configuration profile to use",
        ),
    ] = "",
    output: Annotated[
        str,
        typer.Option(
            "--output",
            "-o",
            help="Output format (table, json, csv, parquet) or file path",
        ),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
) -> None:
    """Update an AI integration by ID.

    Only the fields you provide are sent to the server.
    At least one option must be specified.
    """
    # Build a dict of explicitly provided fields to detect "nothing given"
    provided = {
        k: v
        for k, v in (
            ("name", name),
            ("provider", provider),
            ("api_key", api_key),
            ("base_url", base_url),
            ("model_names", model_names),
            ("enable_default_models", enable_default_models),
            ("function_calling_enabled", function_calling_enabled),
            ("auth_type", auth_type),
            ("headers", headers),
            ("provider_metadata", provider_metadata),
            ("scopings", scopings),
        )
        if v is not None
    }

    if not provided:
        raise UsageError(
            "At least one option must be provided to update the integration."
        )

    parsed_headers = (
        _parse_json_option(headers, "--headers", dict) if headers else None
    )
    parsed_provider_metadata = (
        _parse_json_option(provider_metadata, "--provider-metadata", dict)
        if provider_metadata
        else None
    )
    parsed_scopings: list[AiIntegrationScoping] | None = (
        [
            AiIntegrationScoping(**item)
            for item in _parse_json_option(scopings, "--scopings", list)
        ]
        if scopings
        else None
    )

    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    # Build kwargs with only the explicitly provided fields so the SDK's
    # _UNSET sentinel logic correctly skips omitted ones.
    update_kwargs: dict[str, Any] = {"integration": id}
    if name is not None:
        update_kwargs["name"] = name
    if provider is not None:
        update_kwargs["provider"] = provider
    if api_key is not None:
        update_kwargs["api_key"] = api_key
    if base_url is not None:
        update_kwargs["base_url"] = base_url
    if model_names is not None:
        update_kwargs["model_names"] = model_names
    if enable_default_models is not None:
        update_kwargs["enable_default_models"] = enable_default_models
    if function_calling_enabled is not None:
        update_kwargs["function_calling_enabled"] = function_calling_enabled
    if auth_type is not None:
        update_kwargs["auth_type"] = auth_type
    if headers is not None:
        update_kwargs["headers"] = parsed_headers
    if provider_metadata is not None:
        update_kwargs["provider_metadata"] = parsed_provider_metadata
    if scopings is not None:
        update_kwargs["scopings"] = parsed_scopings

    try:
        with spinner(
            "Updating AI integration",
            success_msg="AI integration updated successfully",
        ):
            integration = client.ai_integrations.update(**update_kwargs)
    except Exception as e:
        raise APIError(f"Failed to update AI integration: {e}") from e
    else:
        output_data(
            integration,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("delete")
@handle_errors
def delete_ai_integration(
    id: Annotated[
        str,
        typer.Argument(help="AI integration ID"),
    ],
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Skip confirmation prompt",
        ),
    ] = False,
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help="Configuration profile to use",
        ),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
) -> None:
    """Delete an AI integration by ID.

    This operation is irreversible.
    """
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    if not force:
        warning("This will permanently delete the AI integration")

        if not confirm("Are you sure?", default=False):
            info("AI integration not deleted")
            raise typer.Exit()

    try:
        with spinner(
            "Deleting AI integration",
            success_msg=f"AI integration with ID '{id}' deleted successfully",
        ):
            client.ai_integrations.delete(integration=id)
    except Exception as e:
        raise APIError(f"Failed to delete AI integration: {e}") from e
