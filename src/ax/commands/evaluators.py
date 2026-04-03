"""Evaluator management commands."""

from dataclasses import asdict
from typing import Annotated

import typer
from arize import ArizeClient
from arize._generated.api_client.models.evaluator_llm_config import (
    EvaluatorLlmConfig,
)
from arize._generated.api_client.models.template_config import TemplateConfig

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


def _parse_optional_direction(source: str | None) -> str | None:
    """Return API direction value or None."""
    if source is None or not source.strip():
        return None
    normalized = source.strip().lower()
    if normalized not in ("maximize", "minimize"):
        raise UsageError("--direction must be 'maximize' or 'minimize'")
    return normalized


def _parse_optional_data_granularity(source: str | None) -> str | None:
    """Return API data_granularity value or None."""
    if source is None or not source.strip():
        return None
    normalized = source.strip().lower()
    if normalized not in ("span", "trace", "session"):
        raise UsageError("--data-granularity must be span, trace, or session")
    return normalized


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
    direction: str | None = None,
    data_granularity: str | None = None,
) -> TemplateConfig:
    r"""Build a TemplateConfig from individual CLI option values."""
    invocation_params = load_json(invocation_params_str)
    if not isinstance(invocation_params, dict):
        raise UsageError("--invocation-params must be a JSON object")

    provider_params = load_json(provider_params_str)
    if not isinstance(provider_params, dict):
        raise UsageError("--provider-params must be a JSON object")

    llm_config = EvaluatorLlmConfig(
        ai_integration_id=ai_integration_id,
        model_name=model_name,
        invocation_parameters=invocation_params,
        provider_parameters=provider_params,
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
        direction=_parse_optional_direction(direction),
        data_granularity=_parse_optional_data_granularity(data_granularity),
    )


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
    """List evaluators, optionally filtered by space."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

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
    """Get an evaluator by name or ID, with its resolved version."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

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


@app.command("create")
@handle_errors
def create_evaluator(
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
            prompt=True,
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
            help="AI integration global ID (base64)",
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
        str | None,
        typer.Option(
            "--direction",
            help="Optimization direction: maximize or minimize",
        ),
    ] = None,
    data_granularity: Annotated[
        str | None,
        typer.Option(
            "--data-granularity",
            help="Data granularity: span, trace, or session",
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
    """Create a new evaluator with an initial version."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

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
            evaluator = client.evaluators.create(
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
    """Update an evaluator's name or description."""
    if name is None and description is None:
        raise UsageError(
            "At least one of --name or --description must be provided"
        )

    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

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

    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

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
    """List all versions of an evaluator."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

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
    """Get a specific evaluator version by ID."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

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


@app.command("create-version")
@handle_errors
def create_version(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Evaluator name or ID"),
    ],
    commit_message: Annotated[
        str,
        typer.Option(
            "--commit-message",
            help="Commit message describing the changes in this version",
            prompt=True,
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
            help="AI integration global ID (base64)",
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
        str | None,
        typer.Option(
            "--direction",
            help="Optimization direction: maximize or minimize",
        ),
    ] = None,
    data_granularity: Annotated[
        str | None,
        typer.Option(
            "--data-granularity",
            help="Data granularity: span, trace, or session",
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
    """Create a new version of an existing evaluator."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

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
            version = client.evaluators.create_version(
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
