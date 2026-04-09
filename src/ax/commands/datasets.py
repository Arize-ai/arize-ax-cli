"""Dataset management commands."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from typing import TYPE_CHECKING, Annotated

import typer

if TYPE_CHECKING:
    import pandas as pd
from arize import ArizeClient

from ax.config.manager import ConfigManager
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError
from ax.core.output import output_data
from ax.utils.console import (
    confirm,
    info,
    new_line,
    progress_bar,
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

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 50
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 5


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


def _is_rate_limited(exc: Exception) -> bool:
    """Check if an exception indicates a rate limit (HTTP 429)."""
    err_str = str(exc)
    return "429" in err_str or "Too Many Requests" in err_str


def _append_batch_with_retry(
    client: ArizeClient,
    examples: list[dict[str, object]],
    *,
    dataset: str,
    space: str | None,
    dataset_version_id: str,
    batch_size: int,
    max_retries: int,
) -> tuple[int, int]:
    """Append examples in batches with retry and rate limit handling.

    Splits examples into batches, retries on transient failures with
    exponential backoff, and falls back to single-row inserts when a
    batch fails on a non-rate-limit error.

    Returns:
        Tuple of (success_count, failure_count).
    """
    total = len(examples)
    appended = 0
    failed = 0

    with progress_bar(total, "Appending examples") as progress:
        task = progress.add_task("Appending examples", total=total)

        for batch_start in range(0, total, batch_size):
            batch = examples[batch_start : batch_start + batch_size]
            batch_ok = False

            for attempt in range(max_retries):
                try:
                    client.datasets.append_examples(
                        dataset=dataset,
                        space=space,
                        dataset_version_id=dataset_version_id,
                        examples=batch,
                    )
                    appended += len(batch)
                    progress.update(task, advance=len(batch))
                    batch_ok = True
                    break
                except Exception as e:
                    if _is_rate_limited(e):
                        delay = INITIAL_RETRY_DELAY * (2**attempt)
                        logger.debug(
                            "Rate limited at row %d, waiting %ds (attempt %d/%d)",
                            batch_start,
                            delay,
                            attempt + 1,
                            max_retries,
                        )
                        warning(
                            f"Rate limited, retrying in {delay}s "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(delay)
                    elif attempt < max_retries - 1:
                        delay = INITIAL_RETRY_DELAY * (2**attempt)
                        logger.debug(
                            "Batch at row %d failed: %s. Retrying in %ds...",
                            batch_start,
                            e,
                            delay,
                        )
                        time.sleep(delay)
                    else:
                        # Final attempt failed — fall back to single-row inserts
                        logger.debug(
                            "Batch at row %d failed after %d attempts, "
                            "falling back to single-row inserts",
                            batch_start,
                            max_retries,
                        )
                        break

            if not batch_ok:
                # Single-row fallback for the failed batch
                for row in batch:
                    for row_attempt in range(max_retries):
                        try:
                            client.datasets.append_examples(
                                dataset=dataset,
                                space=space,
                                dataset_version_id=dataset_version_id,
                                examples=[row],
                            )
                            appended += 1
                            progress.update(task, advance=1)
                            break
                        except Exception as row_err:
                            if _is_rate_limited(row_err):
                                delay = INITIAL_RETRY_DELAY * (2**row_attempt)
                                time.sleep(delay)
                            elif row_attempt < max_retries - 1:
                                time.sleep(INITIAL_RETRY_DELAY)
                            else:
                                failed += 1
                                progress.update(task, advance=1)
                                logger.debug(
                                    "Row at offset %d failed: %s",
                                    batch_start,
                                    row_err,
                                )

    return appended, failed


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
    """Get a dataset by name or ID."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

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
    """Create a new dataset from a data file or inline JSON."""
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
        examples: list[dict[str, object]] | pd.DataFrame = parsed
    else:
        if file is None:
            raise typer.BadParameter("Provide examples via --json or --file.")
        examples = read_data_file(file)

    # Convert DataFrame to list of dicts for batching
    if not isinstance(examples, list):
        records: list[dict[str, object]] = examples.to_dict(orient="records")
    else:
        records = examples

    # Create dataset with first example, then batch-append the rest
    try:
        with spinner(
            "Creating dataset",
            success_msg="Dataset created successfully",
        ):
            dataset = client.datasets.create(
                name=name,
                space=space,
                examples=records[:1],
            )
    except Exception as e:
        raise APIError(f"Failed to create dataset: {e}") from e

    output_data(
        dataset,
        format_type=output_format,
        output_file=output_file,
    )

    # Append remaining examples in batches
    remaining = records[1:]
    if remaining:
        dataset_id = getattr(dataset, "id", None) or getattr(
            dataset, "dataset_id", None
        )
        if not dataset_id:
            warning("Could not determine dataset ID for batch append")
        else:
            appended, failed = _append_batch_with_retry(
                client,
                remaining,
                dataset=dataset_id,
                space=space,
                dataset_version_id="",
                batch_size=DEFAULT_BATCH_SIZE,
                max_retries=MAX_RETRIES,
            )
            # +1 for the initial create example
            success(f"Appended {appended + 1} / {len(records)} examples")
            if failed:
                warning(f"{failed} examples failed to append")

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
    batch_size: Annotated[
        int,
        typer.Option(
            "--batch-size",
            "-b",
            help="Number of examples per API call (default: 50)",
        ),
    ] = DEFAULT_BATCH_SIZE,
    max_retries: Annotated[
        int,
        typer.Option(
            "--max-retries",
            help="Max retry attempts per batch on transient errors (default: 3)",
        ),
    ] = MAX_RETRIES,
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

    For large uploads, examples are sent in batches (default: 50) with automatic
    retry on rate limits (429) and transient server errors. If a batch fails after
    all retries, individual rows are retried one at a time.
    """
    setup_logging(verbose)

    if json_data and file:
        raise typer.BadParameter("Provide either --json or --file, not both.")
    if not json_data and not file:
        raise typer.BadParameter("Provide examples via --json or --file.")

    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

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

    # Small payloads: send in one shot (preserves original behavior)
    if len(examples) <= batch_size:
        try:
            with spinner(
                "Appending examples",
                success_msg=f"Appended {len(examples)} example(s)",
            ):
                client.datasets.append_examples(
                    dataset=name_or_id,
                    space=space,
                    dataset_version_id=version_id or "",
                    examples=examples,
                )
        except Exception as e:
            raise APIError(f"Failed to append examples: {e}") from e
        return

    # Large payloads: batch with retry and progress
    info(f"Appending {len(examples)} examples in batches of {batch_size}")
    appended, failed = _append_batch_with_retry(
        client,
        examples,
        dataset=name_or_id,
        space=space,
        dataset_version_id=version_id or "",
        batch_size=batch_size,
        max_retries=max_retries,
    )
    success(f"Appended {appended} / {len(examples)} examples")
    if failed:
        warning(f"{failed} examples failed to append")


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
    """Delete a dataset by name or ID."""
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
            success_msg=f"Dataset '{name_or_id}' deleted successfully",
        ):
            client.datasets.delete(
                dataset=name_or_id,
                space=space,
            )
    except Exception as e:
        raise APIError(f"Failed to delete dataset: {e}") from e
