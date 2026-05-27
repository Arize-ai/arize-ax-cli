"""Experiment management commands."""

from typing import Annotated

import typer
from arize.experiments.types import ExperimentTaskFieldNames

from ax.auth.auth_guards import require_api_key_auth
from ax.core.client_factory import make_client
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError, AxError
from ax.core.output import output_data
from ax.utils.annotations import parse_annotations
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
    dataset: Annotated[
        str | None,
        typer.Option(
            "--dataset",
            help="Filter experiments by dataset name or ID",
        ),
    ] = None,
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using dataset name instead of ID)",
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
    """List experiments, optionally filtered by dataset."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching experiments"):
            response = client.experiments.list(
                dataset=dataset,
                space=space,
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
    name_or_id: Annotated[
        str,
        typer.Argument(help="Experiment name or ID"),
    ],
    dataset: Annotated[
        str | None,
        typer.Option(
            "--dataset",
            help="Dataset name or ID (required if using experiment name instead of ID)",
        ),
    ] = None,
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using dataset name instead of ID)",
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
    """Get an experiment by name or ID."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching experiment"):
            experiment = client.experiments.get(
                experiment=name_or_id,
                dataset=dataset,
                space=space,
            )
    except Exception as e:
        raise APIError(f"Failed to get experiment: {e}") from e
    else:
        output_data(
            experiment,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("export")
@require_api_key_auth("--all")
@handle_errors
def export_experiment(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Experiment name or ID"),
    ],
    dataset: Annotated[
        str | None,
        typer.Option(
            "--dataset",
            help="Dataset name or ID (required if using experiment name instead of ID)",
        ),
    ] = None,
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using dataset name instead of ID)",
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
            help="Use Arrow Flight for bulk export (streams all runs).",
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
    """Export runs from an experiment to a file.

    Pass --all to use Arrow Flight for bulk export (recommended for large experiments).

    Failed runs (where the task raised an exception) are included in the export
    with output=null and an 'error' field containing the exception message.
    """
    setup_logging(verbose)
    client, _ = make_client()

    try:
        with spinner("Exporting experiment runs"):
            response = client.experiments.list_runs(
                experiment=name_or_id,
                dataset=dataset,
                space=space,
                all=use_all,
            )
    except Exception as e:
        raise APIError(f"Failed to export experiment: {e}") from e

    runs = getattr(response, "experiment_runs", None) or []
    if not runs:
        warning("No runs found in experiment")

    failed = [r for r in runs if getattr(r, "output", None) is None]
    if failed:
        warning(
            f"{len(failed)} run(s) failed (output=null). "
            "Check the 'error' field in the export for details."
        )

    if stdout:
        print_json_array(runs)
    else:
        export_path = make_export_dir(output_dir, "experiment", name_or_id)
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
    dataset: Annotated[
        str,
        typer.Option(
            "--dataset",
            help="Dataset name or ID to attach the experiment to",
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
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using dataset name instead of ID)",
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
    """Create an experiment from a data file.

    The file must contain 'example_id' and 'output' columns.
    Extra columns are passed through as additional fields.
    """
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    # Read data file
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
                dataset=dataset,
                space=space,
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
    name_or_id: Annotated[
        str,
        typer.Argument(help="Experiment name or ID"),
    ],
    dataset: Annotated[
        str | None,
        typer.Option(
            "--dataset",
            help="Dataset name or ID (required if using experiment name instead of ID)",
        ),
    ] = None,
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using dataset name instead of ID)",
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
    """Delete an experiment by name or ID."""
    setup_logging(verbose)
    client, _ = make_client()

    if not force:
        warning("This will permanently delete the experiment")

        if not confirm("Are you sure?", default=False):
            info("Experiment not deleted")
            raise typer.Exit()

    try:
        with spinner(
            "Deleting experiment",
            success_msg=f"Experiment '{name_or_id}' deleted successfully",
        ):
            client.experiments.delete(
                experiment=name_or_id,
                dataset=dataset,
                space=space,
            )
    except Exception as e:
        raise APIError(f"Failed to delete experiment: {e}") from e


@app.command("annotate-runs")
@handle_errors
def annotate_runs(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Experiment name or ID"),
    ],
    file: Annotated[
        str | None,
        typer.Option(
            "--file",
            "-f",
            help="Path to a file containing annotation records (JSON, JSONL, CSV, Parquet), or '-' for stdin",
        ),
    ] = None,
    dataset: Annotated[
        str | None,
        typer.Option(
            "--dataset",
            help="Dataset name or ID (required to resolve experiment by name)",
        ),
    ] = None,
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required when dataset is a name)",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
) -> None:
    """Annotate a batch of runs in an experiment.

    Provide annotations via --file (JSON, JSONL, CSV, or Parquet; use '-' for stdin).
    Each array item must have a ``record_id`` (the experiment run ID) and
    ``values`` (a list of annotation dicts with at least ``name``, plus
    optionally ``score``, ``label``, or ``text``).

    Annotations are upserted — resubmitting the same annotation config name
    for the same run overwrites the previous value. Up to 1000 runs may be
    annotated per request. Unmatched record IDs are silently ignored.
    """
    setup_logging(verbose)

    annotations = parse_annotations(file)

    client, _ = make_client()

    try:
        with spinner(
            "Annotating experiment runs",
            success_msg=f"Annotated {len(annotations)} run(s) successfully",
        ):
            client.experiments.annotate_runs(
                experiment=name_or_id,
                dataset=dataset,
                space=space,
                annotations=annotations,
            )
    except AxError:
        raise
    except Exception as e:
        raise APIError(f"Failed to annotate experiment runs: {e}") from e
