"""Experiment management commands."""

from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from arize import ArizeClient
from arize.experiments.types import ExperimentTaskFieldNames
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

# Create experiments subcommand app
app = typer.Typer(
    name="experiments",
    help="Manage experiments",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)

console = Console()


@app.command("list")
@handle_errors
def list_experiments(
    dataset_id: Annotated[
        str | None,
        typer.Option(
            "--dataset-id",
            help="Filter experiments by dataset ID",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum number of experiments to return",
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
    """List experiments, optionally filtered by dataset."""
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching experiments"):
            response = client.experiments.list(
                dataset_id=dataset_id,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list experiments: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )
        if output_file:
            success(f"Saved experiments to {output_file}")


@app.command("get")
@handle_errors
def get_experiment(
    id: Annotated[
        str,
        typer.Argument(help="Experiment ID"),
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
    """Get an experiment by ID."""
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        experiment = client.experiments.get(experiment_id=id)
    except Exception as e:
        raise APIError(f"Failed to get experiment: {e}") from e
    else:
        output_data(
            experiment,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("create")
@handle_errors
def create_experiment(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Experiment name",
            prompt=True,
        ),
    ],
    dataset_id: Annotated[
        str,
        typer.Option(
            "--dataset-id",
            help="Dataset ID to attach the experiment to",
            prompt=True,
        ),
    ],
    file: Annotated[
        Path,
        typer.Option(
            "--file",
            "-f",
            help="Data file (CSV, JSON, JSONL, or Parquet) with experiment runs",
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
    """Create an experiment from a data file.

    The file must contain 'example_id' and 'output' columns.
    Extra columns are passed through as additional fields.
    """
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    # Read data file
    df = read_data_file(str(file))

    required_cols = {"example_id", "output"}
    missing = required_cols - set(df.columns)
    if missing:
        raise APIError(
            f"File is missing required columns: {', '.join(sorted(missing))}. "
            "The file must contain 'example_id' and 'output' columns."
        )

    try:
        with spinner(
            "Creating experiment",
            success_msg="Experiment created successfully",
        ):
            experiment = client.experiments.create(
                name=name,
                dataset_id=dataset_id,
                experiment_runs=df,
                task_fields=ExperimentTaskFieldNames(
                    example_id="example_id",
                    output="output",
                ),
                force_http=True,
            )
    except Exception as e:
        raise APIError(f"Failed to create experiment: {e}") from e
    else:
        output_data(
            experiment,
            format_type=output_format,
            output_file=output_file,
        )
        new_line()
        text_dimmed(
            "You can explore the runs using the 'ax experiments list_runs' command."
        )


@app.command("delete")
@handle_errors
def delete_experiment(
    id: Annotated[
        str,
        typer.Argument(help="Experiment ID"),
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
    """Delete an experiment by ID."""
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    if not force:
        warning("Warning: This will permanently delete the experiment")

        if not confirm("Are you sure?", default=False):
            info("Experiment not deleted")
            raise typer.Exit()

    try:
        client.experiments.delete(experiment_id=id)
    except Exception as e:
        raise APIError(f"Failed to delete experiment: {e}") from e
    else:
        success(f"Experiment with ID '{id}' deleted successfully")


@app.command("list_runs")
@handle_errors
def list_runs(
    id: Annotated[
        str,
        typer.Argument(help="Experiment ID"),
    ],
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum number of runs to return",
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
    """List runs for an experiment."""
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        response = client.experiments.list_runs(
            experiment_id=id,
            limit=limit,
        )
    except Exception as e:
        raise APIError(f"Failed to list experiment runs: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )

        if output_file:
            success(f"Saved experiment runs to {output_file}")
