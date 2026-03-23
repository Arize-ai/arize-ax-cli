"""Dataset management commands."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from arize import ArizeClient

from ax.config.manager import ConfigManager
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError
from ax.core.output import output_data
from ax.utils.console import (
    confirm,
    info,
    new_line,
    setup_logging,
    spinner,
    success,
    text_dimmed,
    warning,
)
from ax.utils.export import make_export_dir, print_json_array, write_json_array
from ax.utils.file_io import (
    _is_stdin_path,
    parse_output_option,
    read_data_file,
)


def _validate_examples_structure(examples: list[dict[str, object]]) -> None:
    """Validate JSON structure before sending to the API.

    Only checks structural issues (empty array, non-object items). Field-level
    validation (forbidden columns, reserved prefixes) is enforced server-side.
    """
    if not examples:
        raise typer.BadParameter(
            "Examples array is empty; at least one example is required."
        )

    for i, example in enumerate(examples):
        if not isinstance(example, dict):
            raise typer.BadParameter(
                f"Example at index {i} is not a JSON object (got {type(example).__name__})."
            )
        if not example:
            raise typer.BadParameter(
                f"Example at index {i} is empty; each example must have at least one field."
            )


# Create datasets subcommand app
app = typer.Typer(
    name="datasets",
    help="Manage datasets",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


@app.command("list")
@handle_errors
def list_datasets(
    space_id: Annotated[
        str | None,
        typer.Option(
            "--space-id",
            help="Space ID to list datasets from",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of datasets to return",
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
    """List datasets in a space."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    # Resolve with helper functions
    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching datasets"):
            response = client.datasets.list(
                space_id=space_id,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list datasets: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("get")
@handle_errors
def get_dataset(
    id: Annotated[
        str,
        typer.Argument(help="Dataset ID"),
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
    """Get a dataset by ID."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching dataset"):
            dataset = client.datasets.get(dataset_id=id)
    except Exception as e:
        raise APIError(f"Failed to get dataset: {e}") from e
    else:
        output_data(
            dataset,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("export")
@handle_errors
def export_dataset(
    id: Annotated[
        str,
        typer.Argument(help="Dataset ID"),
    ],
    version_id: Annotated[
        str | None,
        typer.Option(
            "--version-id",
            help="Dataset version ID",
        ),
    ] = None,
    output_dir: Annotated[
        str,
        typer.Option(
            "--output-dir",
            help="Output directory (default: current directory)",
        ),
    ] = ".",
    stdout: Annotated[
        bool,
        typer.Option(
            "--stdout",
            help="Print JSON to stdout instead of saving to file",
        ),
    ] = False,
    use_all: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Use Arrow Flight for bulk export (streams all examples).",
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
    """Export examples from a dataset to a file.

    Pass --all to use Arrow Flight for bulk export.
    """
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    try:
        with spinner("Exporting dataset examples"):
            response = client.datasets.list_examples(
                dataset_id=id,
                dataset_version_id=version_id,
                all=use_all,
            )
    except Exception as e:
        raise APIError(f"Failed to export dataset: {e}") from e

    examples = getattr(response, "examples", None) or []
    if not examples:
        warning("No examples found in dataset")

    if stdout:
        print_json_array(examples)
    else:
        export_path = make_export_dir(output_dir, "dataset", id)
        file_path = write_json_array(export_path, "examples.json", examples)
        success(f"Exported {len(examples)} examples to {file_path}")


@app.command("create")
@handle_errors
def create_dataset(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Dataset name",
            prompt=True,
        ),
    ],
    space_id: Annotated[
        str,
        typer.Option(
            "--space-id",
            help="Space ID",
            prompt=True,
        ),
    ],
    file: Annotated[
        str,
        typer.Option(
            "--file",
            "-f",
            help="Data file (CSV, JSON, JSONL, or Parquet), or '-' for stdin",
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
    """Create a new dataset from a data file."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    # Read data file
    if not _is_stdin_path(file) and not Path(file).exists():
        raise typer.BadParameter(
            f"File not found: {file}", param_hint="'--file'"
        )
    df = read_data_file(file)

    try:
        # Create dataset
        with spinner(
            "Creating dataset",
            success_msg="Dataset created successfully",
        ):
            dataset = client.datasets.create(
                name=name,
                space_id=space_id,
                examples=df,
            )
    except Exception as e:
        raise APIError(f"Failed to create dataset: {e}") from e
    else:
        output_data(
            dataset,
            format_type=output_format,
            output_file=output_file,
        )
        new_line()
        text_dimmed(
            "You can export the examples using the 'ax datasets export' command."
        )


@app.command("append")
@handle_errors
def append_examples(
    id: Annotated[
        str,
        typer.Argument(help="Dataset ID to append examples to"),
    ],
    json_data: Annotated[
        str | None,
        typer.Option(
            "--json",
            help='JSON array of examples, e.g. \'[{"question": "...", "answer": "..."}]\'',
        ),
    ] = None,
    file: Annotated[
        str | None,
        typer.Option(
            "--file",
            "-f",
            help="Data file (CSV, JSON, JSONL, or Parquet), or '-' for stdin",
        ),
    ] = None,
    version_id: Annotated[
        str | None,
        typer.Option(
            "--version-id",
            help="Dataset version ID (default: latest version)",
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
    """Append examples to an existing dataset.

    Provide examples via --json (inline JSON array) or --file (CSV/JSON/JSONL/Parquet).
    Exactly one input source is required.
    """
    setup_logging(verbose)

    if json_data and file:
        raise typer.BadParameter("Provide either --json or --file, not both.")
    if not json_data and not file:
        raise typer.BadParameter("Provide examples via --json or --file.")

    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    if json_data:
        try:
            parsed = json.loads(json_data)
        except json.JSONDecodeError as e:
            raise typer.BadParameter(f"Invalid JSON: {e}") from e

        if not isinstance(parsed, list):
            raise typer.BadParameter(
                f"Expected a JSON array, got {type(parsed).__name__}. "
                "Wrap examples in brackets: [{...}, ...]"
            )

        _validate_examples_structure(parsed)
        examples: list[dict[str, object]] = parsed
    else:
        if not _is_stdin_path(file) and not Path(file).exists():  # type: ignore[arg-type]
            raise typer.BadParameter(
                f"File not found: {file}", param_hint="'--file'"
            )
        df = read_data_file(file)  # type: ignore[arg-type]
        records: list[dict[str, object]] = df.to_dict(orient="records")  # type: ignore[assignment]
        _validate_examples_structure(records)
        examples = records

    try:
        with spinner(
            "Appending examples",
            success_msg=f"Appended {len(examples)} example(s)",
        ):
            dataset = client.datasets.append_examples(
                dataset_id=id,
                dataset_version_id=version_id or "",
                examples=examples,
            )
    except Exception as e:
        raise APIError(f"Failed to append examples: {e}") from e
    else:
        output_data(
            dataset,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("delete")
@handle_errors
def delete_dataset(
    id: Annotated[
        str,
        typer.Argument(help="Dataset ID"),
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
    """Delete a dataset by ID."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    # Confirm deletion
    if not force:
        warning("This will permanently delete the dataset")

        if not confirm("Are you sure?", default=False):
            info("Dataset not deleted")
            raise typer.Exit()

    # Delete dataset
    try:
        with spinner(
            "Deleting dataset",
            success_msg=f"Dataset with ID '{id}' deleted successfully",
        ):
            client.datasets.delete(dataset_id=id)
    except Exception as e:
        raise APIError(f"Failed to delete dataset: {e}") from e
