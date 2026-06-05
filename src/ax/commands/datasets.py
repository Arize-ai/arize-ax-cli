"""Dataset management commands."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated

import typer

if TYPE_CHECKING:
    import pandas as pd

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
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Case-insensitive substring filter on dataset name",
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
            help="Maximum number of datasets to return",
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
    """List datasets in a space."""
    setup_logging(verbose)
    client, config = make_client()

    # Resolve with helper functions
    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching datasets"):
            response = client.datasets.list(
                name=name,
                space=space,
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
    name_or_id: Annotated[
        str,
        typer.Argument(help="Dataset name or ID"),
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
    """Get a dataset by name or ID."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching dataset"):
            dataset = client.datasets.get(
                dataset=name_or_id,
                space=space,
            )
    except Exception as e:
        raise APIError(f"Failed to get dataset: {e}") from e
    else:
        output_data(
            dataset,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("export")
@require_api_key_auth("--all")
@handle_errors
def export_dataset(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Dataset name or ID"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using dataset name instead of ID)",
        ),
    ] = None,
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
    client, _ = make_client()

    try:
        with spinner("Exporting dataset examples"):
            response = client.datasets.list_examples(
                dataset=name_or_id,
                space=space,
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
        export_path = make_export_dir(output_dir, "dataset", name_or_id)
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
    space: Annotated[
        str,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID",
            prompt=True,
        ),
    ],
    file: Annotated[
        str | None,
        typer.Option(
            "--file",
            "-f",
            help="Data file (CSV, JSON, JSONL, or Parquet), or '-' for stdin",
        ),
    ] = None,
    json_data: Annotated[
        str | None,
        typer.Option(
            "--json",
            help='JSON array of examples, e.g. \'[{"question": "...", "answer": "..."}]\'',
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
    """Create a new dataset from a data file or inline JSON."""
    setup_logging(verbose)

    if json_data and file:
        raise typer.BadParameter("Provide either --json or --file, not both.")
    if not json_data and not file:
        raise typer.BadParameter("Provide examples via --json or --file.")

    client, config = make_client()

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
        examples: list[dict[str, object]] | pd.DataFrame = parsed
    else:
        if file is None:
            raise typer.BadParameter("Provide examples via --json or --file.")
        examples = read_data_file(file)

    try:
        # Create dataset
        with spinner(
            "Creating dataset",
            success_msg="Dataset created successfully",
        ):
            dataset = client.datasets.create(
                name=name,
                space=space,
                examples=examples,
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
    name_or_id: Annotated[
        str,
        typer.Argument(help="Dataset name or ID to append examples to"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using dataset name instead of ID)",
        ),
    ] = None,
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

    client, config = make_client()

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
                dataset=name_or_id,
                space=space,
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


@app.command("update")
@handle_errors
def update_dataset(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Dataset name or ID"),
    ],
    new_name: Annotated[
        str,
        typer.Option(
            "--name",
            help="New name for the dataset",
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
    """Update a dataset."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Updating dataset",
            success_msg="Dataset updated successfully",
        ):
            dataset = client.datasets.update(
                dataset=name_or_id,
                space=space,
                name=new_name,
            )
    except Exception as e:
        raise APIError(f"Failed to update dataset: {e}") from e
    else:
        output_data(
            dataset,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("delete")
@handle_errors
def delete_dataset(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Dataset name or ID"),
    ],
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
    """Delete a dataset by name or ID."""
    setup_logging(verbose)
    client, _ = make_client()

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
            success_msg=f"Dataset '{name_or_id}' deleted successfully",
        ):
            client.datasets.delete(
                dataset=name_or_id,
                space=space,
            )
    except Exception as e:
        raise APIError(f"Failed to delete dataset: {e}") from e


@app.command("annotate-examples")
@handle_errors
def annotate_examples(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Dataset name or ID"),
    ],
    file: Annotated[
        str | None,
        typer.Option(
            "--file",
            "-f",
            help="Path to a file containing annotation records (JSON, JSONL, CSV, Parquet), or '-' for stdin",
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
    """Annotate a batch of examples in a dataset.

    Provide annotations via --file (JSON, JSONL, CSV, or Parquet; use '-' for stdin).
    Each array item must have a ``record_id`` (the dataset example ID) and
    ``values`` (a list of annotation dicts with at least ``name``, plus
    optionally ``score``, ``label``, or ``text``).

    Annotations are upserted — resubmitting the same annotation config name
    for the same example overwrites the previous value. Up to 1000 examples
    may be annotated per request. Unmatched record IDs are silently ignored.
    """
    setup_logging(verbose)

    annotations = parse_annotations(file)

    client, _ = make_client()

    try:
        with spinner(
            "Annotating dataset examples",
            success_msg=f"Annotated {len(annotations)} example(s) successfully",
        ):
            client.datasets.annotate_examples(
                dataset=name_or_id,
                space=space,
                annotations=annotations,
            )
    except AxError:
        raise
    except Exception as e:
        raise APIError(f"Failed to annotate dataset examples: {e}") from e
