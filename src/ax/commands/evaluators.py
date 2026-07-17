"""Evaluator management commands."""

from typing import Annotated

import typer
from arize._generated.api_client.models.invocation_params import (
    InvocationParams,
)
from arize._generated.api_client.models.provider_params import ProviderParams
from arize.evaluators.types import (
    CodeConfig,
    CustomCodeConfig,
    DataGranularity,
    EvaluatorLlmConfig,
    ManagedCodeConfig,
    ManagedCodeEvaluator,
    OptimizationDirection,
    StaticParam,
    TemplateConfig,
)

from ax.core.client_factory import make_client
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
from ax.utils.text_source import load_text_source

app = typer.Typer(
    name="evaluators",
    help="Manage evaluators",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


def _parse_optional_classification_choices(
    source: str | None,
) -> dict[str, int | float] | None:
    """Parse label→score map for structured classification output.

    Returns:
        Parsed map, or None when omitted or empty (freeform evaluator output).
    """
    if source is None or not source.strip():
        return None
    parsed = load_json(source.strip())
    if not isinstance(parsed, dict):
        raise UsageError("--classification-choices must be a JSON object")
    result: dict[str, int | float] = {}
    for key, value in parsed.items():
        if isinstance(value, bool) or type(value) not in (int, float):
            raise UsageError("--classification-choices values must be numbers")
        result[key] = value
    if not result:
        return None
    return result


def _build_template_config(
    template_name: str,
    template: str,
    ai_integration_id: str,
    model_name: str,
    include_explanations: bool,
    use_function_calling: bool,
    invocation_params_str: str,
    provider_params_str: str,
    classification_choices_str: str | None = None,
    direction: OptimizationDirection | None = None,
    data_granularity: DataGranularity | None = None,
) -> TemplateConfig:
    r"""Build a TemplateConfig from individual CLI option values."""
    invocation_params = load_json(invocation_params_str)
    if not isinstance(invocation_params, dict):
        raise UsageError("--invocation-params must be a JSON object")

    provider_params = load_json(provider_params_str)
    if not isinstance(provider_params, dict):
        raise UsageError("--provider-params must be a JSON object")

    typed_invocation_params = InvocationParams.from_dict(invocation_params)
    if typed_invocation_params is None:
        raise UsageError("--invocation-params is missing or invalid")

    typed_provider_params = ProviderParams.from_dict(provider_params)
    if typed_provider_params is None:
        raise UsageError("--provider-params is missing or invalid")

    llm_config = EvaluatorLlmConfig(
        ai_integration_id=ai_integration_id,
        model_name=model_name,
        invocation_parameters=typed_invocation_params,
        provider_parameters=typed_provider_params,
    )
    return TemplateConfig(
        name=template_name,
        template=template,
        include_explanations=include_explanations,
        use_function_calling_if_available=use_function_calling,
        llm_config=llm_config,
        classification_choices=_parse_optional_classification_choices(
            classification_choices_str
        ),
        direction=direction,
        data_granularity=data_granularity,
    )


def _parse_variables(source: str) -> list[str]:
    """Parse the --variables option into a list of strings."""
    parsed = load_json(source)
    if not isinstance(parsed, list) or not all(
        isinstance(v, str) for v in parsed
    ):
        raise UsageError("--variables must be a JSON array of strings")
    return parsed  # type: ignore[return-value]


def _parse_static_params(source: str | None) -> list[StaticParam] | None:
    """Parse the --static-params option into a list of StaticParam objects.

    Each item must be an object with ``name``, ``type``, and ``default_value``
    (string for ``STRING``/``REGEX``; array of strings for ``STRING_ARRAY``).
    Returns ``None`` when the option is omitted.
    """
    if source is None or not source.strip():
        return None
    parsed = load_json(source)
    if not isinstance(parsed, list):
        raise UsageError("--static-params must be a JSON array of objects")
    try:
        params = [StaticParam.from_dict(item) for item in parsed]
    except Exception as exc:
        raise UsageError(f"Failed to parse --static-params: {exc}") from exc
    none_indices = [i for i, p in enumerate(params) if p is None]
    if none_indices:
        raise UsageError(
            f"Failed to parse --static-params at index(es): {none_indices}"
        )
    return params  # type: ignore[return-value]


# Discriminator values for the code_config `type` field (ManagedCodeConfig /
# CustomCodeConfig). The OpenAPI schema models these as single-value inline
# enums, so no generated enum class exists — keep one source of truth here.
_CODE_TYPE_MANAGED = "MANAGED"
_CODE_TYPE_CUSTOM = "CUSTOM"
_CODE_TYPES = (_CODE_TYPE_MANAGED, _CODE_TYPE_CUSTOM)


def _build_managed_code_config(
    *,
    code_name: str,
    managed_evaluator: ManagedCodeEvaluator,
    variables: str,
    static_params: str | None,
    query_filter: str | None,
    data_granularity: DataGranularity | None,
) -> CodeConfig:
    """Build a CodeConfig wrapping a ManagedCodeConfig from CLI option values."""
    managed = ManagedCodeConfig(
        type=_CODE_TYPE_MANAGED,
        name=code_name,
        managed_evaluator=managed_evaluator,
        variables=_parse_variables(variables),
        static_params=_parse_static_params(static_params),
        query_filter=query_filter if query_filter else None,
        data_granularity=data_granularity,
    )
    return CodeConfig(managed)


def _build_custom_code_config(
    *,
    code_name: str,
    code: str,
    imports: str | None,
    variables: str,
    static_params: str | None,
    query_filter: str | None,
    data_granularity: DataGranularity | None,
) -> CodeConfig:
    """Build a CodeConfig wrapping a CustomCodeConfig from CLI option values."""
    custom = CustomCodeConfig(
        type=_CODE_TYPE_CUSTOM,
        name=code_name,
        code=load_text_source(code, "--code"),
        imports=(
            load_text_source(imports, "--imports")
            if imports is not None
            else None
        ),
        variables=_parse_variables(variables),
        static_params=_parse_static_params(static_params),
        query_filter=query_filter if query_filter else None,
        data_granularity=data_granularity,
    )
    return CodeConfig(custom)


@app.command("list")
@handle_errors
def list_evaluators(
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Case-insensitive substring filter on evaluator name",
        ),
    ] = None,
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of evaluators to return",
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
    """List evaluators, optionally filtered by space."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching evaluators"):
            response = client.evaluators.list(
                name=name,
                space=space,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list evaluators: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("get")
@handle_errors
def get_evaluator(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Evaluator name or ID"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using evaluator name instead of ID)",
        ),
    ] = None,
    version_id: Annotated[
        str | None,
        typer.Option(
            "--version-id",
            help="Version ID to retrieve (default: latest version)",
        ),
    ] = None,
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
    """Get an evaluator by name or ID, with its resolved version."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching evaluator"):
            evaluator = client.evaluators.get(
                evaluator=name_or_id,
                space=space,
                version_id=version_id,
            )
    except Exception as e:
        raise APIError(f"Failed to get evaluator: {e}") from e
    else:
        output_data(
            evaluator,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("create-template-evaluator")
@handle_errors
def template_create_evaluator(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Evaluator name (must be unique within the space)",
            prompt=True,
        ),
    ],
    space: Annotated[
        str,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID to create the evaluator in",
            prompt=True,
        ),
    ],
    commit_message: Annotated[
        str,
        typer.Option(
            "--commit-message",
            help="Commit message for the initial version",
        ),
    ],
    template_name: Annotated[
        str,
        typer.Option(
            "--template-name",
            help="Eval column name (alphanumeric, spaces, hyphens, underscores)",
            prompt=True,
        ),
    ],
    template: Annotated[
        str,
        typer.Option(
            "--template",
            help="Prompt template string with {{variable}} placeholders",
            prompt=True,
        ),
    ],
    ai_integration_id: Annotated[
        str,
        typer.Option(
            "--ai-integration-id",
            help="AI integration identifier (base64)",
            prompt=True,
        ),
    ],
    model_name: Annotated[
        str,
        typer.Option(
            "--model-name",
            help="Model name (e.g. gpt-4o)",
            prompt=True,
        ),
    ],
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            help="Optional evaluator description",
        ),
    ] = None,
    include_explanations: Annotated[
        bool,
        typer.Option(
            "--include-explanations",
            help="Include reasoning explanation alongside the score",
        ),
    ] = False,
    use_function_calling: Annotated[
        bool,
        typer.Option(
            "--use-function-calling",
            help="Prefer structured function-call output when supported",
        ),
    ] = False,
    invocation_params: Annotated[
        str,
        typer.Option(
            "--invocation-params",
            help="JSON object of model invocation parameters (e.g. '{\"temperature\": 0.7}')",
        ),
    ] = "{}",
    provider_params: Annotated[
        str,
        typer.Option(
            "--provider-params",
            help="JSON object of provider-specific parameters",
        ),
    ] = "{}",
    classification_choices: Annotated[
        str | None,
        typer.Option(
            "--classification-choices",
            help=(
                "JSON object mapping choice labels to numeric scores "
                '(e.g. \'{"relevant":1,"irrelevant":0}\'). '
                "Omit for freeform (non-classification) output."
            ),
        ),
    ] = None,
    direction: Annotated[
        OptimizationDirection | None,
        typer.Option(
            "--direction",
            help="Optimization direction: MAXIMIZE, MINIMIZE, or NONE",
        ),
    ] = None,
    data_granularity: Annotated[
        DataGranularity | None,
        typer.Option(
            "--data-granularity",
            help="Data granularity: SPAN, TRACE, or SESSION",
            case_sensitive=False,
        ),
    ] = None,
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
    """Create a new LLM template evaluator with an initial version."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    template_config = _build_template_config(
        template_name=template_name,
        template=template,
        ai_integration_id=ai_integration_id,
        model_name=model_name,
        include_explanations=include_explanations,
        use_function_calling=use_function_calling,
        invocation_params_str=invocation_params,
        provider_params_str=provider_params,
        classification_choices_str=classification_choices,
        direction=direction,
        data_granularity=data_granularity,
    )

    try:
        with spinner(
            "Creating evaluator",
            success_msg="Evaluator created successfully",
        ):
            evaluator = client.evaluators.create_template_evaluator(
                name=name,
                space=space,
                commit_message=commit_message,
                template_config=template_config,
                description=description,
            )
    except Exception as e:
        raise APIError(f"Failed to create evaluator: {e}") from e
    else:
        output_data(
            evaluator,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("create-code-evaluator")
@handle_errors
def code_create_evaluator(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Evaluator name (must be unique within the space)",
            prompt=True,
        ),
    ],
    space: Annotated[
        str,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID to create the evaluator in",
            prompt=True,
        ),
    ],
    commit_message: Annotated[
        str,
        typer.Option(
            "--commit-message",
            help="Commit message for the initial version",
        ),
    ],
    code_type: Annotated[
        str,
        typer.Option(
            "--code-type",
            help="Code evaluator kind: managed (built-in) or custom (user Python)",
            prompt=True,
        ),
    ],
    code_name: Annotated[
        str,
        typer.Option(
            "--code-name",
            help="Eval column name (alphanumeric, spaces, hyphens, underscores)",
            prompt=True,
        ),
    ],
    variables: Annotated[
        str,
        typer.Option(
            "--variables",
            help=(
                "JSON array of span attribute names to pass into the evaluator "
                "(e.g. '[\"output\"]'). Accepts inline JSON or a @file path."
            ),
            prompt=True,
        ),
    ],
    managed_evaluator: Annotated[
        ManagedCodeEvaluator | None,
        typer.Option(
            "--managed-evaluator",
            help=(
                "Built-in managed evaluator (--code-type managed): "
                "MATCHES_REGEX, JSON_PARSEABLE, CONTAINS_ANY_KEYWORD, "
                "CONTAINS_ALL_KEYWORDS, or EXACT_MATCH"
            ),
        ),
    ] = None,
    code: Annotated[
        str | None,
        typer.Option(
            "--code",
            help=(
                "Python source for --code-type custom. Pass source inline, "
                "or prefix with '@' to load from a file "
                "(e.g. --code @./evaluator.py)."
            ),
        ),
    ] = None,
    imports: Annotated[
        str | None,
        typer.Option(
            "--imports",
            help=(
                "Optional Python import block for --code-type custom. "
                "Inline or '@path/to/imports.py'."
            ),
        ),
    ] = None,
    static_params: Annotated[
        str | None,
        typer.Option(
            "--static-params",
            help=(
                "JSON array of static parameters. Each item: "
                "{name, type: STRING|STRING_ARRAY|REGEX, "
                "default_value: <string or array of strings>}. "
                "Accepts inline JSON or a @file path."
            ),
        ),
    ] = None,
    query_filter: Annotated[
        str | None,
        typer.Option(
            "--query-filter",
            help="Optional filter query applied before evaluation",
        ),
    ] = None,
    data_granularity: Annotated[
        DataGranularity | None,
        typer.Option(
            "--data-granularity",
            help="Data granularity: SPAN, TRACE, or SESSION",
            case_sensitive=False,
        ),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            help="Optional evaluator description",
        ),
    ] = None,
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
    """Create a new code evaluator with an initial version.

    Use ``--code-type managed`` for built-in evaluators (requires
    ``--managed-evaluator`` and ``--variables``) or ``--code-type custom``
    for user-supplied Python (requires ``--code`` and ``--variables``).
    """
    setup_logging(verbose)
    normalized_code_type = code_type.strip().upper()
    if normalized_code_type not in _CODE_TYPES:
        raise UsageError(
            f"--code-type must be one of {', '.join(_CODE_TYPES)}; "
            f"got '{code_type}'"
        )

    if normalized_code_type == _CODE_TYPE_MANAGED:
        if managed_evaluator is None:
            raise UsageError("--code-type managed requires --managed-evaluator")
        code_config = _build_managed_code_config(
            code_name=code_name,
            managed_evaluator=managed_evaluator,
            variables=variables,
            static_params=static_params,
            query_filter=query_filter,
            data_granularity=data_granularity,
        )
    else:  # custom
        if not code:
            raise UsageError("--code-type custom requires --code")
        code_config = _build_custom_code_config(
            code_name=code_name,
            code=code,
            imports=imports,
            variables=variables,
            static_params=static_params,
            query_filter=query_filter,
            data_granularity=data_granularity,
        )

    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Creating evaluator",
            success_msg="Evaluator created successfully",
        ):
            evaluator = client.evaluators.create_code_evaluator(
                name=name,
                space=space,
                commit_message=commit_message,
                code_config=code_config,
                description=description,
            )
    except Exception as e:
        raise APIError(f"Failed to create evaluator: {e}") from e
    else:
        output_data(
            evaluator,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("update")
@handle_errors
def update_evaluator(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Evaluator name or ID"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using evaluator name instead of ID)",
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="New evaluator name",
        ),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            help="New evaluator description",
        ),
    ] = None,
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
    """Update an evaluator's name or description."""
    if name is None and description is None:
        raise UsageError(
            "At least one of --name or --description must be provided"
        )

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Updating evaluator"):
            evaluator = client.evaluators.update(
                evaluator=name_or_id,
                space=space,
                name=name,
                description=description,
            )
    except Exception as e:
        raise APIError(f"Failed to update evaluator: {e}") from e
    else:
        output_data(
            evaluator,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("delete")
@handle_errors
def delete_evaluator(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Evaluator name or ID"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using evaluator name instead of ID)",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Skip confirmation prompt",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
) -> None:
    """Delete an evaluator and all its versions."""
    setup_logging(verbose)

    if not force:
        warning(
            "Warning: This will permanently delete the evaluator "
            "and all its versions"
        )
        if not confirm("Are you sure?", default=False):
            info("Evaluator not deleted")
            raise typer.Exit()

    client, _ = make_client()

    try:
        with spinner(
            "Deleting evaluator",
            success_msg=f"Evaluator '{name_or_id}' deleted successfully",
        ):
            client.evaluators.delete(
                evaluator=name_or_id,
                space=space,
            )
    except Exception as e:
        raise APIError(f"Failed to delete evaluator: {e}") from e


@app.command("list-versions")
@handle_errors
def list_versions(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Evaluator name or ID"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using evaluator name instead of ID)",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of versions to return",
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
    """List all versions of an evaluator."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching evaluator versions"):
            response = client.evaluators.list_versions(
                evaluator=name_or_id,
                space=space,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list evaluator versions: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("get-version")
@handle_errors
def get_version(
    version_id: Annotated[
        str,
        typer.Argument(help="Evaluator version ID"),
    ],
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
    """Get a specific evaluator version by ID."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching evaluator version"):
            version = client.evaluators.get_version(version_id=version_id)
    except Exception as e:
        raise APIError(f"Failed to get evaluator version: {e}") from e
    else:
        output_data(
            version,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("create-template-evaluator-version")
@handle_errors
def template_create_version(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Evaluator name or ID"),
    ],
    commit_message: Annotated[
        str,
        typer.Option(
            "--commit-message",
            help="Commit message describing the changes in this version",
        ),
    ],
    template_name: Annotated[
        str,
        typer.Option(
            "--template-name",
            help="Eval column name (alphanumeric, spaces, hyphens, underscores)",
            prompt=True,
        ),
    ],
    template: Annotated[
        str,
        typer.Option(
            "--template",
            help="Prompt template string with {{variable}} placeholders",
            prompt=True,
        ),
    ],
    ai_integration_id: Annotated[
        str,
        typer.Option(
            "--ai-integration-id",
            help="AI integration identifier (base64)",
            prompt=True,
        ),
    ],
    model_name: Annotated[
        str,
        typer.Option(
            "--model-name",
            help="Model name (e.g. gpt-4o)",
            prompt=True,
        ),
    ],
    include_explanations: Annotated[
        bool,
        typer.Option(
            "--include-explanations",
            help="Include reasoning explanation alongside the score",
        ),
    ] = False,
    use_function_calling: Annotated[
        bool,
        typer.Option(
            "--use-function-calling",
            help="Prefer structured function-call output when supported",
        ),
    ] = False,
    invocation_params: Annotated[
        str,
        typer.Option(
            "--invocation-params",
            help="JSON object of model invocation parameters",
        ),
    ] = "{}",
    provider_params: Annotated[
        str,
        typer.Option(
            "--provider-params",
            help="JSON object of provider-specific parameters",
        ),
    ] = "{}",
    classification_choices: Annotated[
        str | None,
        typer.Option(
            "--classification-choices",
            help=(
                "JSON object mapping choice labels to numeric scores "
                '(e.g. \'{"relevant":1,"irrelevant":0}\'). '
                "Omit for freeform (non-classification) output."
            ),
        ),
    ] = None,
    direction: Annotated[
        OptimizationDirection | None,
        typer.Option(
            "--direction",
            help="Optimization direction: MAXIMIZE, MINIMIZE, or NONE",
        ),
    ] = None,
    data_granularity: Annotated[
        DataGranularity | None,
        typer.Option(
            "--data-granularity",
            help="Data granularity: SPAN, TRACE, or SESSION",
            case_sensitive=False,
        ),
    ] = None,
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using evaluator name instead of ID)",
        ),
    ] = None,
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
    """Create a new template version of an existing evaluator."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    template_config = _build_template_config(
        template_name=template_name,
        template=template,
        ai_integration_id=ai_integration_id,
        model_name=model_name,
        include_explanations=include_explanations,
        use_function_calling=use_function_calling,
        invocation_params_str=invocation_params,
        provider_params_str=provider_params,
        classification_choices_str=classification_choices,
        direction=direction,
        data_granularity=data_granularity,
    )

    try:
        with spinner(
            "Creating evaluator version",
            success_msg="Evaluator version created successfully",
        ):
            version = client.evaluators.create_template_version(
                evaluator=name_or_id,
                space=space,
                commit_message=commit_message,
                template_config=template_config,
            )
    except Exception as e:
        raise APIError(f"Failed to create evaluator version: {e}") from e
    else:
        output_data(
            version,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("create-code-evaluator-version")
@handle_errors
def code_create_version(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Evaluator name or ID"),
    ],
    commit_message: Annotated[
        str,
        typer.Option(
            "--commit-message",
            help="Commit message describing the changes in this version",
        ),
    ],
    code_type: Annotated[
        str,
        typer.Option(
            "--code-type",
            help="Code evaluator kind: managed (built-in) or custom (user Python)",
            prompt=True,
        ),
    ],
    code_name: Annotated[
        str,
        typer.Option(
            "--code-name",
            help="Eval column name (alphanumeric, spaces, hyphens, underscores)",
            prompt=True,
        ),
    ],
    variables: Annotated[
        str,
        typer.Option(
            "--variables",
            help=(
                "JSON array of span attribute names to pass into the evaluator "
                "(e.g. '[\"output\"]'). Accepts inline JSON or a @file path."
            ),
            prompt=True,
        ),
    ],
    managed_evaluator: Annotated[
        ManagedCodeEvaluator | None,
        typer.Option(
            "--managed-evaluator",
            help=(
                "Built-in managed evaluator (--code-type managed): "
                "MATCHES_REGEX, JSON_PARSEABLE, CONTAINS_ANY_KEYWORD, "
                "CONTAINS_ALL_KEYWORDS, or EXACT_MATCH"
            ),
        ),
    ] = None,
    code: Annotated[
        str | None,
        typer.Option(
            "--code",
            help=(
                "Python source for --code-type custom. Pass source inline, "
                "or prefix with '@' to load from a file "
                "(e.g. --code @./evaluator.py)."
            ),
        ),
    ] = None,
    imports: Annotated[
        str | None,
        typer.Option(
            "--imports",
            help=(
                "Optional Python import block for --code-type custom. "
                "Inline or '@path/to/imports.py'."
            ),
        ),
    ] = None,
    static_params: Annotated[
        str | None,
        typer.Option(
            "--static-params",
            help=(
                "JSON array of static parameters. Each item: "
                "{name, type: STRING|STRING_ARRAY|REGEX, "
                "default_value: <string or array of strings>}. "
                "Accepts inline JSON or a @file path."
            ),
        ),
    ] = None,
    query_filter: Annotated[
        str | None,
        typer.Option(
            "--query-filter",
            help="Optional filter query applied before evaluation",
        ),
    ] = None,
    data_granularity: Annotated[
        DataGranularity | None,
        typer.Option(
            "--data-granularity",
            help="Data granularity: SPAN, TRACE, or SESSION",
            case_sensitive=False,
        ),
    ] = None,
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using evaluator name instead of ID)",
        ),
    ] = None,
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
    """Create a new code version of an existing evaluator.

    Use ``--code-type managed`` for built-in evaluators or
    ``--code-type custom`` for user-supplied Python.
    """
    setup_logging(verbose)
    normalized_code_type = code_type.strip().upper()
    if normalized_code_type not in _CODE_TYPES:
        raise UsageError(
            f"--code-type must be one of {', '.join(_CODE_TYPES)}; "
            f"got '{code_type}'"
        )

    if normalized_code_type == _CODE_TYPE_MANAGED:
        if managed_evaluator is None:
            raise UsageError("--code-type managed requires --managed-evaluator")
        code_config = _build_managed_code_config(
            code_name=code_name,
            managed_evaluator=managed_evaluator,
            variables=variables,
            static_params=static_params,
            query_filter=query_filter,
            data_granularity=data_granularity,
        )
    else:  # custom
        if not code:
            raise UsageError("--code-type custom requires --code")
        code_config = _build_custom_code_config(
            code_name=code_name,
            code=code,
            imports=imports,
            variables=variables,
            static_params=static_params,
            query_filter=query_filter,
            data_granularity=data_granularity,
        )

    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Creating evaluator version",
            success_msg="Evaluator version created successfully",
        ):
            version = client.evaluators.create_code_version(
                evaluator=name_or_id,
                space=space,
                commit_message=commit_message,
                code_config=code_config,
            )
    except Exception as e:
        raise APIError(f"Failed to create evaluator version: {e}") from e
    else:
        output_data(
            version,
            format_type=output_format,
            output_file=output_file,
        )
