"""Experiment management commands."""

from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from arize import ArizeClient
from arize.experiments.types import ExperimentTaskFieldNames

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

# Create experiments subcommand app
app = typer.Typer(
    name="experiments",
    help="Manage experiments",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


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
            "-l",
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
    setup_logging(verbose)
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
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching experiment"):
            experiment = client.experiments.get(experiment_id=id)
    except Exception as e:
        raise APIError(f"Failed to get experiment: {e}") from e
    else:
        output_data(
            experiment,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("export")
@handle_errors
def export_experiment(
    id: Annotated[
        str,
        typer.Argument(help="Experiment ID"),
    ],
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
            help="Use Arrow Flight for bulk export (streams all runs).",
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
    """Export runs from an experiment to a file.

    Pass --all to use Arrow Flight for bulk export.
    """
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    try:
        with spinner("Exporting experiment runs"):
            response = client.experiments.list_runs(
                experiment_id=id,
                all=use_all,
            )
    except Exception as e:
        raise APIError(f"Failed to export experiment: {e}") from e

    runs = getattr(response, "experiment_runs", None) or []
    if not runs:
        warning("No runs found in experiment")

    if stdout:
        print_json_array(runs)
    else:
        export_path = make_export_dir(output_dir, "experiment", id)
        file_path = write_json_array(export_path, "runs.json", runs)
        success(f"Exported {len(runs)} runs to {file_path}")


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
        str,
        typer.Option(
            "--file",
            "-f",
            help="Data file (CSV, JSON, JSONL, or Parquet) with experiment runs, or '-' for stdin",
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
            "You can export the runs using the 'ax experiments export' command."
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
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    if not force:
        warning("This will permanently delete the experiment")

        if not confirm("Are you sure?", default=False):
            info("Experiment not deleted")
            raise typer.Exit()

    try:
        with spinner(
            "Deleting experiment",
            success_msg=f"Experiment with ID '{id}' deleted successfully",
        ):
            client.experiments.delete(experiment_id=id)
    except Exception as e:
        raise APIError(f"Failed to delete experiment: {e}") from e
