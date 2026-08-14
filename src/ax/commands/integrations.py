"""Integration management commands (LLM and agent)."""

from collections.abc import Callable
from typing import Annotated, Any, TypeVar, cast

import typer
from arize.integrations.types import (
    AgentIntegration,
    CreateAgentRequestPresetInput,
    CreateAnthropicConfig,
    CreateAwsBedrockAuth,
    CreateAwsBedrockConfig,
    CreateCustomConfig,
    CreateGeminiConfig,
    CreateLlmConfig,
    CreateNvidiaNimConfig,
    CreateOpenAiConfig,
    CreateVertexAiConfig,
    IntegrationScoping,
    IntegrationType,
    LlmIntegration,
    LlmIntegrationProvider,
    UpdateAgentRequestPresetInput,
)
from pydantic import ValidationError as PydanticValidationError

from ax.core.client_factory import make_client
from ax.core.decorators import handle_errors
from ax.core.error_formatter import format_validation_error
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

# Create integrations subcommand app
app = typer.Typer(
    name="integrations",
    help="Manage integrations (LLM and agent)",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)

_T = TypeVar("_T")

# ---------------------------------------------------------------------------
# Shared option types
# ---------------------------------------------------------------------------

NameOrIdArg = Annotated[str, typer.Argument(help="Integration name or ID")]
SpaceOpt = Annotated[
    str | None,
    typer.Option(
        "--space",
        "-s",
        help="Space name or ID (optional visibility filter)",
    ),
]
ScopingsOpt = Annotated[
    str | None,
    typer.Option(
        "--scopings",
        help=(
            "Visibility scoping rules as a JSON array or path to a JSON file. "
            "Replaces all existing scopings. "
            'e.g. \'[{"organization_id": "org_1", "space_id": "sp_1"}]\''
        ),
    ),
]
HeadersOpt = Annotated[
    str | None,
    typer.Option(
        "--headers",
        help=(
            "Custom headers as a JSON object or path to a JSON file, "
            "e.g. '{\"X-Api-Key\": \"secret\"}'. Pass 'null' to clear."
        ),
    ),
]
OutputOpt = Annotated[
    str,
    typer.Option(
        "--output",
        "-o",
        help="Output format (table, json, csv, parquet) or file path",
    ),
]
VerboseOpt = Annotated[
    bool,
    typer.Option("--verbose", "-v", help="Enable verbose logs"),
]


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------


def _parse_json_object(value: str, option: str) -> dict[str, Any]:
    """Parse a JSON option and require a top-level object."""
    parsed = load_json(value)
    if not isinstance(parsed, dict):
        raise typer.BadParameter(f"{option} must be a JSON object")
    return parsed


def _parse_json_array(value: str, option: str) -> list[Any]:
    """Parse a JSON option and require a top-level array."""
    parsed = load_json(value)
    if not isinstance(parsed, list):
        raise typer.BadParameter(f"{option} must be a JSON array")
    return parsed


def _from_dict(
    parse: Callable[..., _T | None], value: object, where: str
) -> _T:
    """Build a generated model from a dict, mapping failures to UsageError.

    Generated oneOf ``from_dict`` helpers raise ``ValueError`` whose message
    concatenates every variant's pydantic error (class names,
    ``errors.pydantic.dev`` links). Do not interpolate that dump into the
    user-facing message; ``format_validation_error`` is safe for a real
    ``ValidationError``.
    """
    try:
        result = parse(value)
    except PydanticValidationError as exc:
        raise UsageError(
            f"Invalid {where}: {format_validation_error(exc)}"
        ) from exc
    except Exception as exc:
        raise UsageError(f"Invalid {where}") from exc
    if result is None:
        raise UsageError(f"Invalid {where}: could not parse")
    return result


def _parse_scopings(value: str | None) -> list[IntegrationScoping] | None:
    """Parse the --scopings option into typed IntegrationScoping models."""
    if value is None:
        return None
    items = _parse_json_array(value, "--scopings")
    return [
        _from_dict(IntegrationScoping.from_dict, item, "scoping")
        for item in items
    ]


def _parse_headers(value: str | None) -> dict[str, str] | None:
    """Parse the --headers option; the literal ``null`` clears (returns None)."""
    if value is None or value.strip().lower() == "null":
        return None
    parsed = load_json(value)
    if not isinstance(parsed, dict):
        raise typer.BadParameter("--headers must be a JSON object or null")
    return parsed


def _parse_request_presets(
    value: str, parse: Callable[..., _T | None]
) -> list[_T]:
    """Parse --request-presets into typed inputs; reject non-arrays."""
    items = _parse_json_array(value, "--request-presets")
    return [_from_dict(parse, item, "request preset") for item in items]


def _parse_bedrock_auth(value: str) -> CreateAwsBedrockAuth:
    """Parse the --auth option into the AWS Bedrock auth oneOf."""
    obj = _parse_json_object(value, "--auth")
    return _from_dict(CreateAwsBedrockAuth.from_dict, obj, "auth")


def _require_provider_flag(
    value: _T | None, flag: str, provider: LlmIntegrationProvider
) -> _T:
    """Return a provider-required flag value or fail cleanly when missing."""
    if value is None:
        raise UsageError(f"{flag} is required for provider {provider.value}")
    return value


# ---------------------------------------------------------------------------
# ax integrations list / get
# ---------------------------------------------------------------------------


@app.command("list")
@handle_errors
def list_integrations(
    integration_type: Annotated[
        IntegrationType | None,
        typer.Option(
            "--type",
            "-t",
            help="Filter by integration type: LLM or AGENT",
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Case-insensitive substring filter on integration name",
        ),
    ] = None,
    space: SpaceOpt = None,
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
            "-c",
            help="Pagination cursor for next page",
        ),
    ] = None,
    output: OutputOpt = "",
    verbose: VerboseOpt = False,
) -> None:
    """List integrations.

    When --type is omitted, integrations of every type are returned in one
    merged list; each item carries its type.
    """
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching integrations"):
            response = client.integrations.list(
                integration_type=integration_type,
                name=name,
                space=space,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list integrations: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("get")
@handle_errors
def get_integration(
    name_or_id: NameOrIdArg,
    integration_type: Annotated[
        IntegrationType | None,
        typer.Option(
            "--type",
            "-t",
            help=(
                "Integration type (LLM or AGENT). Required when using a "
                "name instead of an ID — names are only unique per type"
            ),
        ),
    ] = None,
    space: SpaceOpt = None,
    output: OutputOpt = "",
    verbose: VerboseOpt = False,
) -> None:
    """Get an integration by name or ID."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching integration"):
            integration = client.integrations.get(
                integration=name_or_id,
                integration_type=integration_type,
                space=space,
            )
    except Exception as e:
        raise APIError(f"Failed to get integration: {e}") from e
    else:
        output_data(
            integration,
            format_type=output_format,
            output_file=output_file,
        )


# ---------------------------------------------------------------------------
# ax integrations create <type>
# ---------------------------------------------------------------------------

create_app = typer.Typer(
    name="create",
    help="Create an integration (choose the subcommand for its type)",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)
app.add_typer(create_app)


def _build_create_llm_config(
    *,
    provider: LlmIntegrationProvider,
    api_key: str | None,
    base_url: str | None,
    model_names: list[str] | None,
    enable_default_models: bool | None,
    function_calling_enabled: bool | None,
    headers: dict[str, str] | None,
    auth: CreateAwsBedrockAuth | None,
    project_id: str | None,
    location: str | None,
    project_access_label: str | None,
) -> CreateLlmConfig:
    """Build the provider-specific create config from individual flags.

    Required flags are validated per provider so a missing one surfaces as a
    clean usage error instead of a generated pydantic dump.
    """
    provider_value = provider.value
    fc: dict[str, Any] = (
        {}
        if function_calling_enabled is None
        else {"is_function_calling_enabled": function_calling_enabled}
    )
    dm: dict[str, Any] = (
        {}
        if enable_default_models is None
        else {"is_default_models_enabled": enable_default_models}
    )

    inner: (
        CreateOpenAiConfig
        | CreateAnthropicConfig
        | CreateGeminiConfig
        | CreateAwsBedrockConfig
        | CreateCustomConfig
        | CreateVertexAiConfig
        | CreateNvidiaNimConfig
    )

    try:
        if provider is LlmIntegrationProvider.OPEN_AI:
            inner = CreateOpenAiConfig(
                provider=provider_value,
                api_key=_require_provider_flag(api_key, "--api-key", provider),
                **fc,
            )
        elif provider is LlmIntegrationProvider.ANTHROPIC:
            inner = CreateAnthropicConfig(
                provider=provider_value,
                api_key=_require_provider_flag(api_key, "--api-key", provider),
                **fc,
            )
        elif provider is LlmIntegrationProvider.GEMINI:
            inner = CreateGeminiConfig(
                provider=provider_value,
                api_key=_require_provider_flag(api_key, "--api-key", provider),
                **fc,
            )
        elif provider is LlmIntegrationProvider.AWS_BEDROCK:
            inner = CreateAwsBedrockConfig(
                provider=provider_value,
                auth=_require_provider_flag(auth, "--auth", provider),
                model_names=model_names,
                **dm,
            )
        elif provider is LlmIntegrationProvider.CUSTOM:
            inner = CreateCustomConfig(
                provider=provider_value,
                base_url=_require_provider_flag(
                    base_url, "--base-url", provider
                ),
                api_key=api_key,
                headers=headers,
                model_names=model_names,
                **fc,
                **dm,
            )
        elif provider is LlmIntegrationProvider.VERTEX_AI:
            inner = CreateVertexAiConfig(
                provider=provider_value,
                project_id=_require_provider_flag(
                    project_id, "--gcp-project-id", provider
                ),
                location=_require_provider_flag(
                    location, "--gcp-location", provider
                ),
                project_access_label=_require_provider_flag(
                    project_access_label, "--project-access-label", provider
                ),
            )
        elif provider is LlmIntegrationProvider.NVIDIA_NIM:
            # Every connection field is optional for NVIDIA NIM.
            inner = CreateNvidiaNimConfig(
                provider=provider_value,
                base_url=base_url,
                api_key=api_key,
                headers=headers,
                model_names=model_names,
                **fc,
                **dm,
            )
        else:
            # Fail loudly rather than silently misroute a provider variant
            # added to the SDK enum after this command was written.
            raise UsageError(f"Unsupported provider: {provider.value}")
    except PydanticValidationError as exc:
        raise UsageError(
            f"Invalid LLM config: {format_validation_error(exc)}"
        ) from exc

    return CreateLlmConfig(actual_instance=inner)


@create_app.command("llm")
@handle_errors
def create_llm_integration(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Integration name (must be unique within the account)",
        ),
    ],
    provider: Annotated[
        LlmIntegrationProvider,
        typer.Option(
            "--provider",
            help=(
                "Model provider: OPEN_AI, ANTHROPIC, GEMINI, AWS_BEDROCK, "
                "CUSTOM, VERTEX_AI, NVIDIA_NIM"
            ),
        ),
    ],
    api_key: Annotated[
        str | None,
        typer.Option(
            "--api-key",
            help=(
                "API key (write-only). Required for OPEN_AI, ANTHROPIC, "
                "GEMINI; optional for CUSTOM and NVIDIA_NIM"
            ),
        ),
    ] = None,
    base_url: Annotated[
        str | None,
        typer.Option(
            "--base-url",
            help=(
                "Endpoint URL (HTTPS). Required for CUSTOM; optional for "
                "NVIDIA_NIM"
            ),
        ),
    ] = None,
    model_names: Annotated[
        list[str] | None,
        typer.Option(
            "--model-name",
            help=(
                "Custom model name (repeat for multiple). "
                "AWS_BEDROCK, CUSTOM, and NVIDIA_NIM only"
            ),
        ),
    ] = None,
    enable_default_models: Annotated[
        bool | None,
        typer.Option(
            "--enable-default-models/--no-enable-default-models",
            help=(
                "Enable Arize's default model catalog. "
                "AWS_BEDROCK, CUSTOM, and NVIDIA_NIM only"
            ),
        ),
    ] = None,
    function_calling_enabled: Annotated[
        bool | None,
        typer.Option(
            "--function-calling-enabled/--no-function-calling-enabled",
            help=(
                "Enable function/tool calling. Not valid for AWS_BEDROCK "
                "or VERTEX_AI"
            ),
        ),
    ] = None,
    headers: HeadersOpt = None,
    auth: Annotated[
        str | None,
        typer.Option(
            "--auth",
            help=(
                "AWS Bedrock auth as a JSON object or path to a JSON file "
                "(required for AWS_BEDROCK), "
                'e.g. \'{"auth_type": "DEFAULT", "role_arn": "arn:..."}\''
            ),
        ),
    ] = None,
    project_id: Annotated[
        str | None,
        typer.Option(
            "--gcp-project-id", help="GCP project ID (VERTEX_AI only)"
        ),
    ] = None,
    location: Annotated[
        str | None,
        typer.Option("--gcp-location", help="GCP region (VERTEX_AI only)"),
    ] = None,
    project_access_label: Annotated[
        str | None,
        typer.Option(
            "--project-access-label",
            help="Vertex AI project-access label (VERTEX_AI only)",
        ),
    ] = None,
    scopings: ScopingsOpt = None,
    output: OutputOpt = "",
    verbose: VerboseOpt = False,
) -> None:
    """Create an LLM integration.

    Provider-specific requirements:

    - OPEN_AI / ANTHROPIC / GEMINI: --api-key
    - AWS_BEDROCK: --auth
    - CUSTOM: --base-url
    - VERTEX_AI: --gcp-project-id, --gcp-location, --project-access-label
    - NVIDIA_NIM: none (needs at least one model source: --model-name or
      --enable-default-models)
    """
    parsed_headers = _parse_headers(headers) if headers is not None else None
    parsed_auth = _parse_bedrock_auth(auth) if auth is not None else None
    config_obj = _build_create_llm_config(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model_names=model_names,
        enable_default_models=enable_default_models,
        function_calling_enabled=function_calling_enabled,
        headers=parsed_headers,
        auth=parsed_auth,
        project_id=project_id,
        location=location,
        project_access_label=project_access_label,
    )
    parsed_scopings = _parse_scopings(scopings)

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Creating integration",
            success_msg="Integration created successfully",
        ):
            integration = client.integrations.create_llm(
                name=name,
                config=config_obj,
                # IntegrationScopingRequest is not exported from
                # arize.integrations.types in the pinned SDK; pydantic
                # coerces the IntegrationScoping models we build.
                scopings=cast("Any", parsed_scopings),
            )
    except Exception as e:
        raise APIError(f"Failed to create integration: {e}") from e
    else:
        output_data(
            integration,
            format_type=output_format,
            output_file=output_file,
        )


@create_app.command("agent")
@handle_errors
def create_agent_integration(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Integration name (must be unique within the account)",
        ),
    ],
    endpoint: Annotated[
        str,
        typer.Option(
            "--endpoint",
            help="HTTPS endpoint Arize calls for replay",
        ),
    ],
    input_schema: Annotated[
        str,
        typer.Option(
            "--input-schema",
            help=(
                "JSON Schema (Draft-07) for the request body, as a JSON "
                "object or path to a JSON file"
            ),
        ),
    ],
    description: Annotated[
        str | None,
        typer.Option("--description", help="Human-readable description"),
    ] = None,
    headers: HeadersOpt = None,
    request_presets: Annotated[
        str | None,
        typer.Option(
            "--request-presets",
            help=(
                "Initial named request presets as a JSON array or path to a "
                "JSON file"
            ),
        ),
    ] = None,
    scopings: ScopingsOpt = None,
    output: OutputOpt = "",
    verbose: VerboseOpt = False,
) -> None:
    """Create an agent integration.

    Connects a customer-hosted agent exposed at an HTTPS endpoint.
    """
    parsed_input_schema = _parse_json_object(input_schema, "--input-schema")
    parsed_headers = _parse_headers(headers) if headers is not None else None
    parsed_presets = (
        _parse_request_presets(
            request_presets, CreateAgentRequestPresetInput.from_dict
        )
        if request_presets is not None
        else None
    )
    parsed_scopings = _parse_scopings(scopings)

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Creating integration",
            success_msg="Integration created successfully",
        ):
            integration = client.integrations.create_agent(
                name=name,
                endpoint=endpoint,
                input_schema=parsed_input_schema,
                description=description,
                headers=parsed_headers,
                request_presets=parsed_presets,
                # See create_llm note: scopings are coerced by pydantic.
                scopings=cast("Any", parsed_scopings),
            )
    except Exception as e:
        raise APIError(f"Failed to create integration: {e}") from e
    else:
        output_data(
            integration,
            format_type=output_format,
            output_file=output_file,
        )


# ---------------------------------------------------------------------------
# ax integrations update <type>
# ---------------------------------------------------------------------------

update_app = typer.Typer(
    name="update",
    help="Update an integration (choose the subcommand for its type)",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)
app.add_typer(update_app)


def _emit_updated(
    integration: LlmIntegration | AgentIntegration,
    output: str,
    default_format: str,
) -> None:
    """Render an updated integration using the configured output format."""
    output_format, output_file = parse_output_option(
        output if output else default_format
    )
    output_data(
        integration,
        format_type=output_format,
        output_file=output_file,
    )


@update_app.command("llm")
@handle_errors
def update_llm_integration(
    name_or_id: NameOrIdArg,
    space: SpaceOpt = None,
    new_name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="New integration name"),
    ] = None,
    api_key: Annotated[
        str | None,
        typer.Option(
            "--api-key",
            help=(
                "Rotate the API key. Not valid for AWS_BEDROCK "
                "(use --auth) or VERTEX_AI"
            ),
        ),
    ] = None,
    function_calling_enabled: Annotated[
        bool | None,
        typer.Option(
            "--function-calling-enabled/--no-function-calling-enabled",
            help=(
                "Enable function/tool calling (omit to leave unchanged). "
                "Not valid for AWS_BEDROCK or VERTEX_AI"
            ),
        ),
    ] = None,
    auth: Annotated[
        str | None,
        typer.Option(
            "--auth",
            help=(
                "Replacement AWS Bedrock auth as a JSON object or path to a "
                "JSON file (AWS_BEDROCK only)"
            ),
        ),
    ] = None,
    base_url: Annotated[
        str | None,
        typer.Option(
            "--base-url",
            help="New endpoint URL (CUSTOM and NVIDIA_NIM only)",
        ),
    ] = None,
    headers: HeadersOpt = None,
    enable_default_models: Annotated[
        bool | None,
        typer.Option(
            "--enable-default-models/--no-enable-default-models",
            help=(
                "Toggle Arize's default model catalog (omit to leave "
                "unchanged). AWS_BEDROCK, CUSTOM, and NVIDIA_NIM only"
            ),
        ),
    ] = None,
    model_names: Annotated[
        list[str] | None,
        typer.Option(
            "--model-name",
            help=(
                "Replacement custom model name (repeat for multiple). "
                "AWS_BEDROCK, CUSTOM, and NVIDIA_NIM only"
            ),
        ),
    ] = None,
    project_id: Annotated[
        str | None,
        typer.Option("--gcp-project-id", help="New GCP project ID (VERTEX_AI)"),
    ] = None,
    location: Annotated[
        str | None,
        typer.Option("--gcp-location", help="New GCP region (VERTEX_AI)"),
    ] = None,
    project_access_label: Annotated[
        str | None,
        typer.Option(
            "--project-access-label",
            help="New Vertex AI project-access label (VERTEX_AI)",
        ),
    ] = None,
    scopings: ScopingsOpt = None,
    output: OutputOpt = "",
    verbose: VerboseOpt = False,
) -> None:
    """Update an LLM integration by name or ID.

    Only the fields you pass are changed; omitted fields are left unchanged.
    The provider is immutable. Config fields are provider-conditional; the
    server rejects fields that do not apply to the stored provider.
    """
    kwargs: dict[str, Any] = {}
    if new_name is not None:
        kwargs["name"] = new_name
    if api_key is not None:
        kwargs["api_key"] = api_key
    if function_calling_enabled is not None:
        kwargs["function_calling_enabled"] = function_calling_enabled
    if auth is not None:
        kwargs["auth"] = _parse_bedrock_auth(auth)
    if base_url is not None:
        kwargs["base_url"] = base_url
    if headers is not None:
        kwargs["headers"] = _parse_headers(headers)
    if enable_default_models is not None:
        kwargs["is_default_models_enabled"] = enable_default_models
    if model_names is not None:
        kwargs["model_names"] = model_names
    if project_id is not None:
        kwargs["project_id"] = project_id
    if location is not None:
        kwargs["location"] = location
    if project_access_label is not None:
        kwargs["project_access_label"] = project_access_label
    if scopings is not None:
        kwargs["scopings"] = _parse_scopings(scopings)

    if not kwargs:
        raise UsageError(
            "Provide at least one field to update "
            "(--name, --scopings, or a config field)."
        )

    setup_logging(verbose)
    client, config = make_client()

    try:
        with spinner(
            "Updating integration",
            success_msg="Integration updated successfully",
        ):
            integration = client.integrations.update_llm(
                integration=name_or_id,
                space=space,
                **kwargs,
            )
    except Exception as e:
        raise APIError(f"Failed to update integration: {e}") from e
    else:
        _emit_updated(integration, output, config.output.format)


@update_app.command("agent")
@handle_errors
def update_agent_integration(
    name_or_id: NameOrIdArg,
    space: SpaceOpt = None,
    new_name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="New integration name"),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="New description"),
    ] = None,
    endpoint: Annotated[
        str | None,
        typer.Option("--endpoint", help="New HTTPS endpoint URL"),
    ] = None,
    input_schema: Annotated[
        str | None,
        typer.Option(
            "--input-schema",
            help=(
                "New JSON Schema for the request body, as a JSON object or "
                "path to a JSON file"
            ),
        ),
    ] = None,
    headers: HeadersOpt = None,
    request_presets: Annotated[
        str | None,
        typer.Option(
            "--request-presets",
            help=(
                "Replacement request presets as a JSON array or path to a "
                "JSON file (matched by name)"
            ),
        ),
    ] = None,
    scopings: ScopingsOpt = None,
    output: OutputOpt = "",
    verbose: VerboseOpt = False,
) -> None:
    """Update an agent integration by name or ID.

    Only the fields you pass are changed; omitted fields are left unchanged.
    Collection fields (headers, request_presets, scopings) replace the
    existing values when provided.
    """
    kwargs: dict[str, Any] = {}
    if new_name is not None:
        kwargs["name"] = new_name
    if description is not None:
        kwargs["description"] = description
    if endpoint is not None:
        kwargs["endpoint"] = endpoint
    if input_schema is not None:
        kwargs["input_schema"] = _parse_json_object(
            input_schema, "--input-schema"
        )
    if headers is not None:
        kwargs["headers"] = _parse_headers(headers)
    if request_presets is not None:
        kwargs["request_presets"] = _parse_request_presets(
            request_presets, UpdateAgentRequestPresetInput.from_dict
        )
    if scopings is not None:
        kwargs["scopings"] = _parse_scopings(scopings)

    if not kwargs:
        raise UsageError(
            "Provide at least one field to update "
            "(--name, --description, --scopings, or a config field)."
        )

    setup_logging(verbose)
    client, config = make_client()

    try:
        with spinner(
            "Updating integration",
            success_msg="Integration updated successfully",
        ):
            integration = client.integrations.update_agent(
                integration=name_or_id,
                space=space,
                **kwargs,
            )
    except Exception as e:
        raise APIError(f"Failed to update integration: {e}") from e
    else:
        _emit_updated(integration, output, config.output.format)


# ---------------------------------------------------------------------------
# ax integrations delete
# ---------------------------------------------------------------------------


@app.command("delete")
@handle_errors
def delete_integration(
    name_or_id: NameOrIdArg,
    integration_type: Annotated[
        IntegrationType | None,
        typer.Option(
            "--type",
            "-t",
            help=(
                "Integration type (LLM or AGENT). Required when using a "
                "name instead of an ID — names are only unique per type"
            ),
        ),
    ] = None,
    space: SpaceOpt = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Skip confirmation prompt",
        ),
    ] = False,
    verbose: VerboseOpt = False,
) -> None:
    """Delete an integration by name or ID.

    This operation is irreversible.
    """
    setup_logging(verbose)
    client, _ = make_client()

    if not force:
        warning("This will permanently delete the integration")

        if not confirm("Are you sure?", default=False):
            info("Integration not deleted")
            raise typer.Exit()

    try:
        with spinner(
            "Deleting integration",
            success_msg=f"Integration '{name_or_id}' deleted successfully",
        ):
            client.integrations.delete(
                integration=name_or_id,
                integration_type=integration_type,
                space=space,
            )
    except Exception as e:
        raise APIError(f"Failed to delete integration: {e}") from e
