"""Annotation queue management commands."""

from typing import Annotated, Any

import typer
from arize.annotation_queues.types import AnnotationInput, AssignmentMethod

from ax.core.client_factory import make_client
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError
from ax.core.output import output_data
from ax.utils.console import (
    confirm,
    error,
    info,
    setup_logging,
    spinner,
    warning,
)
from ax.utils.file_io import parse_output_option
from ax.utils.json_source import load_json

# Create annotation-queues subcommand app
app = typer.Typer(
    name="annotation-queues",
    help="Manage annotation queues",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


@app.command("list")
@handle_errors
def list_annotation_queues(
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID",
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Filter by queue name (substring match)",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of annotation queues to return",
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
    """List annotation queues in a space."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching annotation queues"):
            response = client.annotation_queues.list(
                space=space,
                name=name,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list annotation queues: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("get")
@handle_errors
def get_annotation_queue(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Annotation queue name or ID"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using queue name instead of ID)",
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
    """Get an annotation queue by name or ID."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching annotation queue"):
            queue = client.annotation_queues.get(
                annotation_queue=name_or_id,
                space=space,
            )
    except Exception as e:
        raise APIError(f"Failed to get annotation queue: {e}") from e
    else:
        output_data(
            queue,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("create")
@handle_errors
def create_annotation_queue(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Annotation queue name",
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
    annotation_config_ids: Annotated[
        list[str],
        typer.Option(
            "--annotation-config-id",
            help="Annotation config ID to associate (repeat for multiple)",
        ),
    ] = [],  # noqa: B006
    annotator_emails: Annotated[
        list[str],
        typer.Option(
            "--annotator-email",
            help="Annotator email to assign (repeat for multiple)",
        ),
    ] = [],  # noqa: B006
    instructions: Annotated[
        str | None,
        typer.Option(
            "--instructions",
            help="Instructions for annotators (max 5000 characters)",
        ),
    ] = None,
    assignment_method: Annotated[
        AssignmentMethod | None,
        typer.Option(
            "--assignment-method",
            help="How records are assigned to annotators (ALL, RANDOM)",
        ),
    ] = None,
    record_sources: Annotated[
        str | None,
        typer.Option(
            "--record-sources",
            help=(
                "JSON file path or inline JSON array of initial record sources. "
                "Each source must have a 'record_type' field set to 'SPAN' or "
                "'EXAMPLE', plus type-specific fields. "
                "Span source: project_id, start_time (ISO 8601), end_time "
                "(ISO 8601), and optional span_ids. "
                "Example source: dataset_id and example_ids."
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
    """Create a new annotation queue.

    At least one --annotation-config-id is required.
    """
    setup_logging(verbose)

    if not annotation_config_ids:
        error(
            "--annotation-config-id is required; specify at least one annotation config ID"
        )
        raise typer.Exit(code=1)

    if not annotator_emails:
        error(
            "--annotator-email is required; specify at least one annotator email"
        )
        raise typer.Exit(code=1)

    parsed_record_sources: list[Any] | None = None
    if record_sources is not None:
        parsed = load_json(record_sources)
        if not isinstance(parsed, list):
            raise typer.BadParameter(
                "--record-sources must be a JSON array of record source objects."
            )
        parsed_record_sources = parsed

    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Creating annotation queue",
            success_msg="Annotation queue created successfully",
        ):
            queue = client.annotation_queues.create(
                name=name,
                space=space,
                annotation_config_ids=annotation_config_ids,
                annotator_emails=annotator_emails,
                instructions=instructions,
                assignment_method=assignment_method,
                record_sources=parsed_record_sources,
            )
    except Exception as e:
        raise APIError(f"Failed to create annotation queue: {e}") from e
    else:
        output_data(
            queue,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("update")
@handle_errors
def update_annotation_queue(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Annotation queue name or ID"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using queue name instead of ID)",
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="New name for the annotation queue",
        ),
    ] = None,
    instructions: Annotated[
        str | None,
        typer.Option(
            "--instructions",
            help='New instructions for annotators. Pass "" (empty string) to clear.',
        ),
    ] = None,
    annotation_config_ids: Annotated[
        list[str] | None,
        typer.Option(
            "--annotation-config-id",
            help="Full replacement list of annotation config IDs (repeat for multiple)",
        ),
    ] = None,
    annotator_emails: Annotated[
        list[str] | None,
        typer.Option(
            "--annotator-email",
            help="Full replacement list of annotator emails (repeat for multiple)",
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
    """Update an annotation queue.

    Only the fields you provide are updated. Omitted fields are left unchanged.
    List fields (--annotation-config-id, --annotator-email) fully replace
    existing values when provided.
    """
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Updating annotation queue",
            success_msg="Annotation queue updated successfully",
        ):
            # None (flag omitted) → SDK excludes → unchanged.
            # Empty list (flag with no values) → SDK sends [] → clears the field.
            queue = client.annotation_queues.update(
                annotation_queue=name_or_id,
                space=space,
                name=name,
                instructions=instructions,
                annotation_config_ids=annotation_config_ids,
                annotator_emails=annotator_emails,
            )
    except Exception as e:
        raise APIError(f"Failed to update annotation queue: {e}") from e
    else:
        output_data(
            queue,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("delete")
@handle_errors
def delete_annotation_queue(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Annotation queue name or ID"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using queue name instead of ID)",
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
    """Delete an annotation queue by name or ID."""
    setup_logging(verbose)
    client, _ = make_client()

    if not force:
        warning("This will permanently delete the annotation queue")

        if not confirm("Are you sure?", default=False):
            info("Annotation queue not deleted")
            raise typer.Exit()

    try:
        with spinner(
            "Deleting annotation queue",
            success_msg=f"Annotation queue '{name_or_id}' deleted successfully",
        ):
            client.annotation_queues.delete(
                annotation_queue=name_or_id,
                space=space,
            )
    except Exception as e:
        raise APIError(f"Failed to delete annotation queue: {e}") from e


@app.command("list-records")
@handle_errors
def list_records(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Annotation queue name or ID"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using queue name instead of ID)",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of records to return",
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
    """List records in an annotation queue."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching annotation queue records"):
            response = client.annotation_queues.list_records(
                annotation_queue=name_or_id,
                space=space,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list annotation queue records: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("delete-records")
@handle_errors
def delete_records(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Annotation queue name or ID"),
    ],
    record_ids: Annotated[
        list[str],
        typer.Option(
            "--record-id",
            help="Record ID to delete (repeat for multiple, max 100)",
        ),
    ] = [],  # noqa: B006
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using queue name instead of ID)",
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
    """Delete records from an annotation queue by record ID."""
    setup_logging(verbose)

    if not record_ids:
        error("--record-id is required; specify at least one record ID")
        raise typer.Exit(code=1)

    client, _ = make_client()

    if not force:
        warning(f"This will permanently delete {len(record_ids)} record(s)")

        if not confirm("Are you sure?", default=False):
            info("Records not deleted")
            raise typer.Exit()

    try:
        with spinner(
            "Deleting records",
            success_msg=f"Deleted {len(record_ids)} record(s) successfully",
        ):
            client.annotation_queues.delete_records(
                annotation_queue=name_or_id,
                space=space,
                record_ids=record_ids,
            )
    except Exception as e:
        raise APIError(f"Failed to delete annotation queue records: {e}") from e


@app.command("annotate-record")
@handle_errors
def annotate_record(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Annotation queue name or ID"),
    ],
    record_id: Annotated[
        str,
        typer.Argument(help="Record ID to annotate"),
    ],
    annotation_name: Annotated[
        str,
        typer.Option(
            "--annotation-name",
            help="Name of the annotation config",
            prompt=True,
        ),
    ],
    score: Annotated[
        float | None,
        typer.Option(
            "--score",
            help="Numeric score value",
        ),
    ] = None,
    label: Annotated[
        str | None,
        typer.Option(
            "--label",
            help="Label value (for categorical annotation configs)",
        ),
    ] = None,
    text: Annotated[
        str | None,
        typer.Option(
            "--text",
            help="Free-text annotation",
        ),
    ] = None,
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using queue name instead of ID)",
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
    """Submit an annotation for a record in an annotation queue.

    Annotations are upserted by annotation config name; call this command
    multiple times to annotate with different configs.
    """
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    annotation = AnnotationInput(
        name=annotation_name,
        score=score,
        label=label,
        text=text,
    )

    try:
        with spinner(
            "Submitting annotation",
            success_msg="Annotation submitted successfully",
        ):
            result = client.annotation_queues.annotate_record(
                annotation_queue=name_or_id,
                space=space,
                record_id=record_id,
                annotations=[annotation],
            )
    except Exception as e:
        raise APIError(f"Failed to annotate record: {e}") from e
    else:
        output_data(
            result,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("assign-record")
@handle_errors
def assign_record(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Annotation queue name or ID"),
    ],
    record_id: Annotated[
        str,
        typer.Argument(help="Record ID to assign"),
    ],
    emails: Annotated[
        list[str],
        typer.Option(
            "--email",
            help="User email to assign (repeat for multiple; pass no --email flags to clear all assignments)",
        ),
    ] = [],  # noqa: B006
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using queue name instead of ID)",
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
    """Assign users to a record in an annotation queue.

    Fully replaces all existing record-level assignments.
    Pass no --email flags to remove all assignments.
    """
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Assigning users to record",
            success_msg="Record assignment updated successfully",
        ):
            result = client.annotation_queues.assign_record(
                annotation_queue=name_or_id,
                space=space,
                record_id=record_id,
                assigned_user_emails=emails,
            )
    except Exception as e:
        raise APIError(f"Failed to assign record: {e}") from e
    else:
        output_data(
            result,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("add-records")
@handle_errors
def add_records(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Annotation queue name or ID"),
    ],
    record_sources: Annotated[
        str,
        typer.Option(
            "--record-sources",
            help=(
                "JSON file path or inline JSON array of record sources. "
                "Each source must have a 'record_type' field set to 'SPAN' or "
                "'EXAMPLE', plus type-specific fields. "
                "Span source: project_id, start_time (ISO 8601), end_time "
                "(ISO 8601), and optional span_ids. "
                "Example source: dataset_id and example_ids."
            ),
        ),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using queue name instead of ID)",
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
    r"""Add records to an annotation queue.

    Records may come from spans (project time range) or dataset examples.

    \b
    Examples:
        # Add spans from a project time range (sources in a file)
        ax annotation-queues add-records my-queue \\
          --record-sources sources.json

        # Add specific dataset examples (inline JSON)
        ax annotation-queues add-records my-queue \\
          --record-sources '[{"record_type": "EXAMPLE", "dataset_id": "ds-1",
          "example_ids": ["ex-1", "ex-2"]}]'
    """
    parsed_sources: list[Any] = load_json(record_sources)  # type: ignore[assignment]
    if not isinstance(parsed_sources, list):
        raise typer.BadParameter(
            "--record-sources must be a JSON array of record source objects."
        )

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Adding records to annotation queue",
            success_msg="Records added successfully",
        ):
            result = client.annotation_queues.add_records(
                annotation_queue=name_or_id,
                space=space,
                record_sources=parsed_sources,
            )
    except Exception as e:
        raise APIError(f"Failed to add records to annotation queue: {e}") from e
    else:
        output_data(
            result,
            format_type=output_format,
            output_file=output_file,
        )
