"""Dataset management commands."""

from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from arize import ArizeClient
from click import confirm
from rich.console import Console

from ax.config.manager import ConfigManager
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError
from ax.core.output import output_data
from ax.utils.console import (
    info,
    new_line,
    spinner,
    success,
    text_dimmed,
    warning,
)
from ax.utils.file_io import (
    parse_output_option,
    read_data_file,
)

# Create datasets subcommand app
app = typer.Typer(
    name="datasets",
    help="Manage datasets",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)

console = Console()


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
            "-n",
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
        if output_file:
            success(f"Saved datasets to {output_file}")


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
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    # Resolve with helper functions
    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        dataset = client.datasets.get(dataset_id=id)
    except Exception as e:
        raise APIError(f"Failed to get dataset: {e}") from e
    else:
        output_data(
            dataset,
            format_type=output_format,
            output_file=output_file,
        )


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
        Path,
        typer.Option(
            "--file",
            "-f",
            help="Data file (CSV, JSON, JSONL, or Parquet)",
            exists=True,
            prompt=True,
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
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    # Read data file
    df = read_data_file(str(file))

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
            "You can explore the examples in the dataset using the 'ax datasets list_examples' command."
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
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    # Confirm deletion
    if not force:
        warning("Warning: This will permanently delete the dataset")

        if not confirm("Are you sure?", default=False):
            info("Dataset not deleted")
            raise typer.Exit()

    # Delete dataset
    try:
        client.datasets.delete(dataset_id=id)
    except Exception as e:
        raise APIError(f"Failed to delete dataset: {e}") from e
    else:
        success(f"Dataset with ID '{id}' deleted successfully")


@app.command("list_examples")
@handle_errors
def list_examples(
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
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum number of examples to return",
        ),
    ] = 30,
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
    """List examples from a dataset."""
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    # Resolve with helper functions
    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        # Get examples
        response = client.datasets.list_examples(
            dataset_id=id,
            dataset_version_id=version_id,
            limit=limit,
        )
    except Exception as e:
        raise APIError(f"Failed to list examples: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )

        if output_file:
            success(f"Saved dataset examples to {output_file}")
