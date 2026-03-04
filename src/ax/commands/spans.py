"""Spans management commands."""

from dataclasses import asdict
from datetime import datetime
from typing import Annotated

import typer
from arize import ArizeClient

from ax.config.manager import ConfigManager
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError
from ax.core.output import output_data
from ax.utils.console import (
    setup_logging,
    spinner,
    success,
)
from ax.utils.file_io import (
    parse_output_option,
)

# Create spans subcommand app
app = typer.Typer(
    name="spans",
    help="Manage spans",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


@app.command("list")
@handle_errors
def list_spans(
    project_id: Annotated[
        str,
        typer.Argument(help="Project ID"),
    ],
    start_time: Annotated[
        str | None,
        typer.Option(
            "--start-time",
            help="Start of time window, inclusive (ISO 8601, e.g. 2024-01-01T00:00:00Z).",
        ),
    ] = None,
    end_time: Annotated[
        str | None,
        typer.Option(
            "--end-time",
            help="End of time window, exclusive (ISO 8601, e.g. 2024-01-02T00:00:00Z). Defaults to now.",
        ),
    ] = None,
    filter: Annotated[
        str | None,
        typer.Option(
            "--filter",
            help='Filter expression (e.g. "status_code = \'ERROR\'", "latency_ms > 1000").',
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum number of spans to return",
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
    """List spans in a project."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    # Resolve with helper functions
    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    start_dt = datetime.fromisoformat(start_time) if start_time else None
    end_dt = datetime.fromisoformat(end_time) if end_time else None

    try:
        with spinner("Fetching spans"):
            response = client.spans.list(
                project_id=project_id,
                start_time=start_dt,
                end_time=end_dt,
                filter=filter,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list spans: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )
        if output_file:
            success(f"Saved spans to {output_file}")
