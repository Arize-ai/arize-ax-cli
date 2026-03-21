"""Prompt management commands."""

from dataclasses import asdict
from typing import Annotated, Any

import typer
from arize import ArizeClient
from arize._generated.api_client.models.input_variable_format import (
    InputVariableFormat,
)
from arize._generated.api_client.models.llm_message import LLMMessage
from arize._generated.api_client.models.llm_provider import LlmProvider

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

# Create prompts subcommand app
app = typer.Typer(
    name="prompts",
    help="Manage prompts and prompt versions",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


def _build_llm_messages(
    parsed: dict[str, Any] | list[dict[str, Any]],
) -> list[LLMMessage]:
    """Parse a JSON document into a list of :class:`LLMMessage`.

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
        messages = [LLMMessage.from_dict(m) for m in parsed]
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
    space_id: Annotated[
        str | None,
        typer.Option(
            "--space-id",
            help="Space ID to filter prompts",
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
    """List prompts in a space."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching prompts"):
            response = client.prompts.list(
                space_id=space_id,
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
    id: Annotated[
        str,
        typer.Argument(help="Prompt ID"),
    ],
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
    """Get a prompt by ID.

    Optionally resolve a specific version via --version-id or --label.
    If neither is supplied, the latest version is returned.
    """
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        prompt = client.prompts.get(
            prompt_id=id,
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
    space_id: Annotated[
        str,
        typer.Option(
            "--space-id",
            help="Space ID to create the prompt in",
        ),
    ],
    provider: Annotated[
        LlmProvider,
        typer.Option(
            "--provider",
            help=(
                "LLM provider "
                "(openAI, azureOpenAI, awsBedrock, vertexAI, custom)"
            ),
        ),
    ],
    input_variable_format: Annotated[
        InputVariableFormat,
        typer.Option(
            "--input-variable-format",
            help="Variable interpolation format (f_string, mustache, none)",
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
    r"""Create a prompt with an initial version.

    Pass messages as a path to a JSON file or as inline JSON. Example array:

    \b
    [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Summarize: {text}"},
      {"role": "assistant", "tool_calls": [
        {"id": "tool-call-1", "type": "function",
         "function": {"name": "search",
                      "arguments": "{\"query\": \"summarize {text}\"}"}}
      ]},
      {"role": "tool", "tool_call_id": "tool-call-1",
       "content": "This is the result of the search function."},
    ]
    """
    parsed_messages = _build_llm_messages(load_json(messages))

    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Creating prompt", success_msg="Prompt created successfully"
        ):
            prompt = client.prompts.create(
                space_id=space_id,
                name=name,
                commit_message=commit_message,
                input_variable_format=input_variable_format,
                provider=provider,
                messages=parsed_messages,
                description=description,
                model=model,
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
    id: Annotated[
        str,
        typer.Argument(help="Prompt ID"),
    ],
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            help="Updated description for the prompt",
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
    """Update a prompt's metadata.

    At least one option must be specified.
    """
    if description is None:
        raise UsageError(
            "At least one option must be provided to update the prompt. "
            "Available: --description"
        )
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Updating prompt", success_msg="Prompt updated successfully"
        ):
            prompt = client.prompts.update(
                prompt_id=id,
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
    id: Annotated[
        str,
        typer.Argument(help="Prompt ID"),
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
    """Delete a prompt by ID.

    This operation is irreversible and removes all associated versions.
    """
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

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
            success_msg=f"Prompt with ID '{id}' deleted successfully",
        ):
            client.prompts.delete(prompt_id=id)
    except Exception as e:
        raise APIError(f"Failed to delete prompt: {e}") from e


@app.command("list-versions")
@handle_errors
def list_versions(
    id: Annotated[
        str,
        typer.Argument(help="Prompt ID"),
    ],
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
    """List versions for a prompt."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching prompt versions"):
            response = client.prompts.list_versions(
                prompt_id=id,
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
    id: Annotated[
        str,
        typer.Argument(help="Prompt ID to create a new version for"),
    ],
    provider: Annotated[
        LlmProvider,
        typer.Option(
            "--provider",
            help=(
                "LLM provider "
                "(openAI, azureOpenAI, awsBedrock, vertexAI, custom)"
            ),
        ),
    ],
    input_variable_format: Annotated[
        InputVariableFormat,
        typer.Option(
            "--input-variable-format",
            help="Variable interpolation format (f_string, mustache, none)",
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
    r"""Create a new version for an existing prompt.

    Pass messages as a path to a JSON file or as inline JSON. Example array:

    \b
    [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user",   "content": "Summarize: {text}"}
    ]
    """
    parsed_messages = _build_llm_messages(load_json(messages))

    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Creating prompt version",
            success_msg="Prompt version created successfully",
        ):
            version = client.prompts.create_version(
                prompt_id=id,
                commit_message=commit_message,
                input_variable_format=input_variable_format,
                provider=provider,
                messages=parsed_messages,
                model=model,
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
    id: Annotated[
        str,
        typer.Argument(help="Prompt ID"),
    ],
    label: Annotated[
        str,
        typer.Option(
            "--label",
            help="Label name to resolve (e.g. 'production', 'staging')",
        ),
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
    """Resolve a label to the prompt version it points to."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching prompt version by label"):
            version = client.prompts.get_label(
                prompt_id=id,
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
    r"""Set labels on a prompt version.

    Replaces all existing labels on the version with the provided list.

    \b
    Example:
        ax prompts set-version-labels <version-id> --label production --label staging
    """
    if not labels:
        raise UsageError("At least one --label must be provided.")

    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

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
    """Remove a label from a prompt version."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

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
