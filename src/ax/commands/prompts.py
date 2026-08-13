"""Prompt management commands."""

from typing import Annotated, Any

import typer
from arize.prompts.types import (
    InputVariableFormat,
    InvocationParamsRequest,
    LLMMessageRequest,
    LlmProvider,
    ProviderParamsRequest,
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

# Create prompts subcommand app
app = typer.Typer(
    name="prompts",
    help="Manage prompts and prompt versions",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


def _build_llm_messages(
    parsed: dict[str, Any] | list[dict[str, Any]],
) -> list[LLMMessageRequest]:
    """Parse a JSON document into a list of :class:`LLMMessageRequest`.

    Args:
        parsed: Parsed JSON value (dict or list of dicts).

    Returns:
        A non-empty list of messages.

    Raises:
        typer.BadParameter: If messages cannot be parsed.
    """
    if not isinstance(parsed, list) or not parsed:
        raise typer.BadParameter(
            "Messages must be a non-empty JSON array of message objects."
        )

    try:
        messages = [LLMMessageRequest.from_dict(m) for m in parsed]
    except Exception as exc:
        raise typer.BadParameter(f"Failed to parse messages: {exc}") from exc

    bad = [i for i, m in enumerate(messages) if m is None]
    if bad:
        raise typer.BadParameter(
            f"Failed to parse message(s) at index(es): {bad}. "
            "Each message must have at least a 'role' field."
        )
    return [m for m in messages if m is not None]


@app.command("list")
@handle_errors
def list_prompts(
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Case-insensitive substring filter on prompt name",
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
            help="Maximum number of prompts to return",
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
    """List prompts in a space."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching prompts"):
            response = client.prompts.list(
                name=name,
                space=space,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list prompts: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("get")
@handle_errors
def get_prompt(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Prompt name or ID"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using prompt name instead of ID)",
        ),
    ] = None,
    version_id: Annotated[
        str | None,
        typer.Option(
            "--version-id",
            help="Specific version ID to retrieve",
        ),
    ] = None,
    label: Annotated[
        str | None,
        typer.Option(
            "--label",
            help="Label name to resolve to a version (e.g. 'production')",
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
    """Get a prompt by name or ID.

    Optionally resolve a specific version via --version-id or --label.
    If neither is supplied, the latest version is returned.
    """
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        prompt = client.prompts.get(
            prompt=name_or_id,
            space=space,
            version_id=version_id,
            label=label,
        )
    except Exception as e:
        raise APIError(f"Failed to get prompt: {e}") from e
    else:
        output_data(
            prompt,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("create")
@handle_errors
def create_prompt(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Prompt name (must be unique within the space)",
        ),
    ],
    space: Annotated[
        str,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID to create the prompt in",
        ),
    ],
    provider: Annotated[
        LlmProvider,
        typer.Option(
            "--provider",
            help=(
                "LLM provider "
                "(OPEN_AI, AZURE_OPEN_AI, AWS_BEDROCK, VERTEX_AI, ANTHROPIC, CUSTOM)"
            ),
        ),
    ],
    input_variable_format: Annotated[
        InputVariableFormat,
        typer.Option(
            "--input-variable-format",
            help="Variable interpolation format (F_STRING, MUSTACHE, NONE)",
        ),
    ],
    messages: Annotated[
        str,
        typer.Option(
            "--messages",
            help=(
                "Path to a JSON file, or inline JSON starting with '[' or '{'. "
                "Must be a non-empty array of message objects; each needs "
                "a 'role' and optionally 'content', 'tool_call_id', "
                "'tool_calls'."
            ),
        ),
    ],
    commit_message: Annotated[
        str,
        typer.Option(
            "--commit-message",
            help="Commit message for the initial version",
        ),
    ] = "Initial version",
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            help="Optional prompt description",
        ),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            help="Default model name for this version",
        ),
    ] = None,
    invocation_params: Annotated[
        str | None,
        typer.Option(
            "--invocation-params",
            help=(
                "JSON file path or inline JSON with invocation parameters "
                "(e.g. temperature, max_tokens, top_p, stop)"
            ),
        ),
    ] = None,
    provider_params: Annotated[
        str | None,
        typer.Option(
            "--provider-params",
            help=(
                "JSON file path or inline JSON with provider-specific parameters "
                "(e.g. azure deployment name, Bedrock region)"
            ),
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
    r"""Create a prompt with an initial version.

    Pass messages as a path to a JSON file or as inline JSON. Example array:

    \b
    [
      {"role": "SYSTEM", "content": "You are a helpful assistant."},
      {"role": "USER", "content": "Summarize: {text}"},
      {"role": "ASSISTANT", "tool_calls": [
        {"id": "tool-call-1", "type": "FUNCTION",
         "function": {"name": "search",
                      "arguments": "{\"query\": \"summarize {text}\"}"}}
      ]},
      {"role": "TOOL", "tool_call_id": "tool-call-1",
       "content": "This is the result of the search function."},
    ]
    """
    parsed_messages = _build_llm_messages(load_json(messages))

    parsed_invocation_params: InvocationParamsRequest | None = None
    if invocation_params is not None:
        _raw_inv = load_json(invocation_params)
        if not isinstance(_raw_inv, dict):
            raise typer.BadParameter(
                "--invocation-params must be a JSON object."
            )
        try:
            parsed_invocation_params = InvocationParamsRequest.from_dict(
                _raw_inv
            )
        except Exception as exc:
            raise typer.BadParameter(
                f"Failed to parse --invocation-params: {exc}"
            ) from exc

    parsed_provider_params: ProviderParamsRequest | None = None
    if provider_params is not None:
        _raw_prov = load_json(provider_params)
        if not isinstance(_raw_prov, dict):
            raise typer.BadParameter("--provider-params must be a JSON object.")
        try:
            parsed_provider_params = ProviderParamsRequest.from_dict(_raw_prov)
        except Exception as exc:
            raise typer.BadParameter(
                f"Failed to parse --provider-params: {exc}"
            ) from exc

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Creating prompt", success_msg="Prompt created successfully"
        ):
            prompt = client.prompts.create(
                space=space,
                name=name,
                commit_message=commit_message,
                input_variable_format=input_variable_format,
                provider=provider,
                messages=parsed_messages,
                description=description,
                model=model,
                invocation_params=parsed_invocation_params,
                provider_params=parsed_provider_params,
            )
    except Exception as e:
        raise APIError(f"Failed to create prompt: {e}") from e
    else:
        output_data(
            prompt,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("update")
@handle_errors
def update_prompt(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Prompt name or ID"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using prompt name instead of ID)",
        ),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            help="Updated description for the prompt",
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
    """Update a prompt's metadata.

    At least one option must be specified.
    """
    if description is None:
        raise UsageError(
            "At least one option must be provided to update the prompt. "
            "Available: --description"
        )
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Updating prompt", success_msg="Prompt updated successfully"
        ):
            prompt = client.prompts.update(
                prompt=name_or_id,
                space=space,
                description=description,
            )
    except Exception as e:
        raise APIError(f"Failed to update prompt: {e}") from e
    else:
        output_data(
            prompt,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("delete")
@handle_errors
def delete_prompt(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Prompt name or ID"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using prompt name instead of ID)",
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
    """Delete a prompt by name or ID.

    This operation is irreversible and removes all associated versions.
    """
    setup_logging(verbose)
    client, _ = make_client()

    if not force:
        warning(
            "Warning: This will permanently delete the prompt and all its versions"
        )

        if not confirm("Are you sure?", default=False):
            info("Prompt not deleted")
            raise typer.Exit()

    try:
        with spinner(
            "Deleting prompt",
            success_msg=f"Prompt '{name_or_id}' deleted successfully",
        ):
            client.prompts.delete(
                prompt=name_or_id,
                space=space,
            )
    except Exception as e:
        raise APIError(f"Failed to delete prompt: {e}") from e


@app.command("list-versions")
@handle_errors
def list_versions(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Prompt name or ID"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using prompt name instead of ID)",
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
    """List versions for a prompt."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching prompt versions"):
            response = client.prompts.list_versions(
                prompt=name_or_id,
                space=space,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list prompt versions: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("create-version")
@handle_errors
def create_version(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Prompt name or ID to create a new version for"),
    ],
    provider: Annotated[
        LlmProvider,
        typer.Option(
            "--provider",
            help=(
                "LLM provider "
                "(OPEN_AI, AZURE_OPEN_AI, AWS_BEDROCK, VERTEX_AI, ANTHROPIC, CUSTOM)"
            ),
        ),
    ],
    input_variable_format: Annotated[
        InputVariableFormat,
        typer.Option(
            "--input-variable-format",
            help="Variable interpolation format (F_STRING, MUSTACHE, NONE)",
        ),
    ],
    messages: Annotated[
        str,
        typer.Option(
            "--messages",
            help=(
                "Path to a JSON file, or inline JSON starting with '[' or '{'. "
                "Must be a non-empty array of message objects; each needs "
                "a 'role' and optionally 'content', 'tool_call_id', "
                "'tool_calls'."
            ),
        ),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using prompt name instead of ID)",
        ),
    ] = None,
    commit_message: Annotated[
        str,
        typer.Option(
            "--commit-message",
            help="Commit message describing this version",
        ),
    ] = "New version",
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            help="Default model name for this version",
        ),
    ] = None,
    invocation_params: Annotated[
        str | None,
        typer.Option(
            "--invocation-params",
            help=(
                "JSON file path or inline JSON with invocation parameters "
                "(e.g. temperature, max_tokens, top_p, stop)"
            ),
        ),
    ] = None,
    provider_params: Annotated[
        str | None,
        typer.Option(
            "--provider-params",
            help=(
                "JSON file path or inline JSON with provider-specific parameters "
                "(e.g. azure deployment name, Bedrock region)"
            ),
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
    r"""Create a new version for an existing prompt.

    Pass messages as a path to a JSON file or as inline JSON. Example array:

    \b
    [
      {"role": "SYSTEM", "content": "You are a helpful assistant."},
      {"role": "USER",   "content": "Summarize: {text}"}
    ]
    """
    parsed_messages = _build_llm_messages(load_json(messages))

    parsed_invocation_params: InvocationParamsRequest | None = None
    if invocation_params is not None:
        _raw_inv = load_json(invocation_params)
        if not isinstance(_raw_inv, dict):
            raise typer.BadParameter(
                "--invocation-params must be a JSON object."
            )
        try:
            parsed_invocation_params = InvocationParamsRequest.from_dict(
                _raw_inv
            )
        except Exception as exc:
            raise typer.BadParameter(
                f"Failed to parse --invocation-params: {exc}"
            ) from exc

    parsed_provider_params: ProviderParamsRequest | None = None
    if provider_params is not None:
        _raw_prov = load_json(provider_params)
        if not isinstance(_raw_prov, dict):
            raise typer.BadParameter("--provider-params must be a JSON object.")
        try:
            parsed_provider_params = ProviderParamsRequest.from_dict(_raw_prov)
        except Exception as exc:
            raise typer.BadParameter(
                f"Failed to parse --provider-params: {exc}"
            ) from exc

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Creating prompt version",
            success_msg="Prompt version created successfully",
        ):
            version = client.prompts.create_version(
                prompt=name_or_id,
                space=space,
                commit_message=commit_message,
                input_variable_format=input_variable_format,
                provider=provider,
                messages=parsed_messages,
                model=model,
                invocation_params=parsed_invocation_params,
                provider_params=parsed_provider_params,
            )
    except Exception as e:
        raise APIError(f"Failed to create prompt version: {e}") from e
    else:
        output_data(
            version,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("get-version-by-label")
@handle_errors
def get_version_by_label(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Prompt name or ID"),
    ],
    label: Annotated[
        str,
        typer.Option(
            "--label",
            help="Label name to resolve (e.g. 'production', 'staging')",
        ),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using prompt name instead of ID)",
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
    """Resolve a label to the prompt version it points to."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching prompt version by label"):
            version = client.prompts.get_version_by_label(
                prompt=name_or_id,
                space=space,
                label_name=label,
            )
    except Exception as e:
        raise APIError(f"Failed to get label: {e}") from e
    else:
        output_data(
            version,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("set-version-labels")
@handle_errors
def set_version_labels(
    version_id: Annotated[
        str,
        typer.Argument(help="Prompt version ID to set labels on"),
    ],
    labels: Annotated[
        list[str],
        typer.Option(
            "--label",
            help=(
                "Label name to assign (repeat for multiple, "
                "e.g. --label production --label staging). "
                "Replaces all existing labels on the version."
            ),
        ),
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
    r"""Set labels on a prompt version.

    Replaces all existing labels on the version with the provided list.

    \b
    Example:
        ax prompts set-version-labels <version-id> --label production --label staging
    """
    if not labels:
        raise UsageError("At least one --label must be provided.")

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Setting labels", success_msg="Labels set successfully"):
            response = client.prompts.set_labels(
                version_id=version_id,
                labels=labels,
            )
    except Exception as e:
        raise APIError(f"Failed to set labels: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("remove-version-label")
@handle_errors
def remove_version_label(
    version_id: Annotated[
        str,
        typer.Argument(help="Prompt version ID"),
    ],
    label: Annotated[
        str,
        typer.Option(
            "--label",
            help="Label name to remove (e.g. 'production', 'staging')",
        ),
    ],
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
) -> None:
    """Remove a label from a prompt version."""
    setup_logging(verbose)
    client, _ = make_client()

    try:
        with spinner(
            "Removing label",
            success_msg=f"Label '{label}' removed from version '{version_id}' successfully",
        ):
            client.prompts.delete_label(
                version_id=version_id,
                label_name=label,
            )
    except Exception as e:
        raise APIError(f"Failed to remove version label: {e}") from e
