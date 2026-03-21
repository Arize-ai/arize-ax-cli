"""Traces management commands."""

import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Annotated

import typer
from arize import ArizeClient

from ax.config.manager import ConfigManager
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError
from ax.core.output import output_data
from ax.utils.console import (
    info,
    setup_logging,
    spinner,
    success,
    warning,
)
from ax.utils.datetime_parse import parse_optional_iso8601
from ax.utils.export import make_export_dir, print_json_array, write_json_array
from ax.utils.file_io import (
    parse_output_option,
)
from ax.utils.projects import resolve_project_id

# Create traces subcommand app
app = typer.Typer(
    name="traces",
    help="Manage traces",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


@app.command("list")
@handle_errors
def list_spans(
    project_id: Annotated[
        str,
        typer.Argument(help="Project name or ID"),
    ],
    space_id: Annotated[
        str | None,
        typer.Option(
            "--space-id",
            help="Space ID (required when using a project name instead of ID)",
        ),
    ] = None,
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
            "-l",
            help="Maximum number of traces to return",
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
    """List traces in a project."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    resolved_id = resolve_project_id(client, project_id, space_id)

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    start_dt = parse_optional_iso8601(start_time)
    end_dt = parse_optional_iso8601(end_time)

    # Traces are root spans (no parent). Always inject the parent_id filter.
    trace_filter = "parent_id = null"
    effective_filter = (
        f"{trace_filter} AND {filter}" if filter else trace_filter
    )

    try:
        with spinner("Fetching traces"):
            response = client.spans.list(
                project_id=resolved_id,
                start_time=start_dt,
                end_time=end_dt,
                filter=effective_filter,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list traces: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


def _build_trace_id_in_filter(trace_ids: list[str]) -> str:
    """Build a ``context.trace_id IN (...)`` filter clause."""
    quoted = ", ".join(f"'{tid}'" for tid in trace_ids)
    return f"context.trace_id IN ({quoted})"


@app.command("export")
@handle_errors
def export_traces(
    project: Annotated[
        str,
        typer.Argument(help="Project name or ID"),
    ],
    filter_expr: Annotated[
        str | None,
        typer.Option(
            "--filter",
            help="Filter expression applied to initial span lookup (e.g. \"status_code = 'ERROR'\").",
        ),
    ] = None,
    space_id: Annotated[
        str | None,
        typer.Option(
            "--space-id",
            help="Space ID (required when using a project name or --all)",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Max number of traces to export (default: 50)",
        ),
    ] = 50,
    days: Annotated[
        int,
        typer.Option(
            "--days",
            help="Lookback window in days (default: 30)",
        ),
    ] = 30,
    start_time: Annotated[
        str | None,
        typer.Option(
            "--start-time",
            help="Override start of time window (ISO 8601)",
        ),
    ] = None,
    end_time: Annotated[
        str | None,
        typer.Option(
            "--end-time",
            help="Override end of time window (ISO 8601)",
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
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help="Configuration profile to use",
        ),
    ] = "",
    use_all: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Use Arrow Flight for bulk export (streams all matching spans, ignores --limit).",
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
    """Export full traces (all spans for matching traces).

    Phase 1: find spans matching --filter (or all spans) to collect trace IDs.
    Phase 2: fetch every span belonging to those traces.

    Pass --all to use Arrow Flight for both phases (requires --space-id).
    """
    setup_logging(verbose)

    if days <= 0:
        raise typer.BadParameter("--days must be a positive integer.")

    if not use_all and limit <= 0:
        raise typer.BadParameter("--limit must be a positive integer.")

    if use_all and not space_id:
        raise typer.BadParameter("--space-id is required when using --all.")

    if use_all and limit != 50:
        warning("--limit is ignored when --all is set.")

    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    end_dt = parse_optional_iso8601(end_time) or datetime.now(tz=timezone.utc)
    start_dt = (
        parse_optional_iso8601(start_time)
        if start_time
        else end_dt - timedelta(days=days)
    )

    if start_dt >= end_dt:
        raise typer.BadParameter(
            f"--start-time ({start_dt.isoformat()}) must be before "
            f"--end-time ({end_dt.isoformat()})."
        )

    try:
        if use_all:
            _export_traces_flight(
                client=client,
                project=project,
                space_id=space_id or "",
                start_dt=start_dt,
                end_dt=end_dt,
                filter_expr=filter_expr,
                output_dir=output_dir,
                stdout=stdout,
            )
        else:
            _export_traces_rest(
                client=client,
                project=project,
                space_id=space_id,
                start_dt=start_dt,
                end_dt=end_dt,
                filter_expr=filter_expr,
                limit=limit,
                output_dir=output_dir,
                stdout=stdout,
            )
    except Exception as e:
        raise APIError(f"Failed to export traces: {e}") from e


def _export_traces_rest(
    *,
    client: ArizeClient,
    project: str,
    space_id: str | None,
    start_dt: datetime,
    end_dt: datetime,
    filter_expr: str | None,
    limit: int,
    output_dir: str,
    stdout: bool,
) -> None:
    """Two-phase trace export using the REST API."""
    resolved_id = resolve_project_id(client, project, space_id)

    with spinner("Phase 1: finding matching spans"):
        response = client.spans.list(
            project_id=resolved_id,
            start_time=start_dt,
            end_time=end_dt,
            filter=filter_expr,
            limit=500,
        )

    phase1_spans = getattr(response, "spans", None) or []
    if not phase1_spans:
        warning("No spans found matching filter")
        if stdout:
            print_json_array([])
        else:
            export_path = make_export_dir(output_dir, "traces", "empty")
            file_path = write_json_array(export_path, "spans.json", [])
            success(f"Exported 0 spans to {file_path}")
        return

    all_trace_ids = list(
        dict.fromkeys(s.context.trace_id for s in phase1_spans)
    )
    trace_ids = all_trace_ids[:limit]
    info(
        f"Found {len(all_trace_ids)} unique trace(s), "
        f"exporting {len(trace_ids)}"
    )

    trace_filter = _build_trace_id_in_filter(trace_ids)
    with spinner("Phase 2: fetching all spans for traces"):
        response2 = client.spans.list(
            project_id=resolved_id,
            start_time=start_dt,
            end_time=end_dt,
            filter=trace_filter,
            limit=500,
        )

    all_spans = getattr(response2, "spans", None) or []
    if stdout:
        print_json_array(all_spans)
    else:
        export_path = make_export_dir(output_dir, "traces", "filtered")
        file_path = write_json_array(export_path, "spans.json", all_spans)
        success(
            f"Exported {len(all_spans)} spans across "
            f"{len(trace_ids)} traces to {file_path}"
        )


def _export_traces_flight(
    *,
    client: ArizeClient,
    project: str,
    space_id: str,
    start_dt: datetime,
    end_dt: datetime,
    filter_expr: str | None,
    output_dir: str,
    stdout: bool,
) -> None:
    """Two-phase trace export using Arrow Flight."""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)

        with spinner("Phase 1: finding matching spans via Flight"):
            df1 = client.spans.export_to_df(
                space_id=space_id,
                project_name=project,
                start_time=start_dt,
                end_time=end_dt,
                where=filter_expr or "",
            )

        if df1.empty:
            warning("No spans found matching filter")
            if stdout:
                sys.stdout.write("[]\n")
            else:
                export_path = make_export_dir(output_dir, "traces", "empty")
                file_path = export_path / "spans.json"
                file_path.write_text("[]")
                success(f"Exported 0 spans to {file_path}")
            return

        trace_ids = df1["context.trace_id"].dropna().unique().tolist()
        info(f"Found {len(trace_ids)} unique trace(s) from {len(df1)} spans")

        trace_filter = _build_trace_id_in_filter(trace_ids)
        with spinner("Phase 2: fetching all spans for traces via Flight"):
            df2 = client.spans.export_to_df(
                space_id=space_id,
                project_name=project,
                start_time=start_dt,
                end_time=end_dt,
                where=trace_filter,
            )

    records = df2.to_dict(orient="records")
    data_json = json.dumps(records, indent=2, default=str)
    if stdout:
        sys.stdout.write(data_json)
        sys.stdout.write("\n")
    else:
        export_path = make_export_dir(output_dir, "traces", "filtered")
        file_path = export_path / "spans.json"
        file_path.write_text(data_json)
        success(
            f"Exported {len(records)} spans across "
            f"{len(trace_ids)} traces to {file_path}"
        )
