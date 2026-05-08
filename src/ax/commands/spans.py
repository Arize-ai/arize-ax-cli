"""Spans management commands."""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

import typer

from ax.auth.auth_guards import require_api_key_auth
from ax.core.client_factory import make_client
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError, AxError
from ax.utils.console import (
    setup_logging,
    spinner,
    success,
    warning,
)
from ax.utils.datetime_parse import parse_optional_iso8601
from ax.utils.export import make_export_dir, print_json_array, write_json_array

# Create spans subcommand app
app = typer.Typer(
    name="spans",
    help="Manage spans",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


def _build_span_filter(
    trace_id: str | None,
    span_id: str | None,
    session_id: str | None,
    filter_expr: str | None = None,
) -> tuple[str | None, str, str]:
    """Build a combined filter from ID flags and an optional filter expression.

    Returns ``(filter_string_or_None, dir_prefix, dir_id)`` used by the export
    command for both the API call and the output directory name.
    """
    provided = [
        ("trace_id", trace_id),
        ("span_id", span_id),
        ("session_id", session_id),
    ]
    set_flags = [(name, val) for name, val in provided if val is not None]

    if len(set_flags) > 1:
        names = ", ".join(f"--{n.replace('_', '-')}" for n, _ in set_flags)
        raise typer.BadParameter(
            f"Only one of --trace-id, --span-id, or --session-id may be "
            f"provided (got {names})."
        )

    filter_parts: list[str] = []
    prefix = "spans"
    id_value = "all"

    if set_flags:
        flag_name, flag_value = set_flags[0]
        filter_map = {
            "trace_id": (f"context.trace_id = '{flag_value}'", "trace"),
            "span_id": (f"context.span_id = '{flag_value}'", "span"),
            "session_id": (
                f"attributes.session.id = '{flag_value}'",
                "session",
            ),
        }
        id_filter, prefix = filter_map[flag_name]
        id_value = flag_value
        filter_parts.append(id_filter)

    if filter_expr:
        filter_parts.append(filter_expr)
        if not set_flags:
            id_value = "filtered"

    combined = " AND ".join(filter_parts) if filter_parts else None
    return combined, prefix, id_value


@app.command("export")
@require_api_key_auth("--all")
@handle_errors
def export_spans(
    project_id: Annotated[
        str,
        typer.Argument(help="Project name or ID"),
    ],
    trace_id: Annotated[
        str | None,
        typer.Option(
            "--trace-id",
            help="Filter by trace ID",
        ),
    ] = None,
    span_id: Annotated[
        str | None,
        typer.Option(
            "--span-id",
            help="Filter by span ID",
        ),
    ] = None,
    session_id: Annotated[
        str | None,
        typer.Option(
            "--session-id",
            help="Filter by session ID",
        ),
    ] = None,
    filter_expr: Annotated[
        str | None,
        typer.Option(
            "--filter",
            help='Filter expression (e.g. "status_code = \'ERROR\'", "latency_ms > 1000").',
        ),
    ] = None,
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space ID (required when using --all for Arrow Flight export)",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of spans to export",
        ),
    ] = 100,
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
    """Export spans to a JSON file.

    Filter by trace ID, span ID, or session ID (mutually exclusive), and
    optionally combine with --filter for additional narrowing.  Without any
    ID flag, all spans are exported (optionally narrowed by --filter).

    By default writes to a file under --output-dir; use --stdout to print
    JSON to stdout instead.

    Pass --all to use Arrow Flight for bulk export (requires --space).
    """
    setup_logging(verbose)

    if days <= 0:
        raise typer.BadParameter("--days must be a positive integer.")

    if not use_all and limit <= 0:
        raise typer.BadParameter("--limit must be a positive integer.")

    if use_all and not space:
        raise typer.BadParameter("--space is required when using --all.")

    if use_all and limit != 100:
        warning("--limit is ignored when --all is set.")

    filter_combined, prefix, id_value = _build_span_filter(
        trace_id, span_id, session_id, filter_expr
    )

    client, _ = make_client()

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

    if not stdout and output_dir == ".":
        traces_dir = Path.cwd() / ".arize-tmp-traces"
        traces_dir.mkdir(exist_ok=True)
        output_dir = str(traces_dir)

    try:
        if use_all:
            with spinner("Exporting spans via Arrow Flight"):
                import warnings

                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    df = client.spans.export_to_df(
                        space_id=space or "",
                        project_name=project_id,
                        start_time=start_dt,
                        end_time=end_dt,
                        where=filter_combined or "",
                    )
            records = df.to_dict(orient="records")
            if not records:
                warning("No spans found")
            data_json = json.dumps(records, indent=2, default=str)
            if stdout:
                sys.stdout.write(data_json)
                sys.stdout.write("\n")
            else:
                export_path = make_export_dir(output_dir, prefix, id_value)
                file_path = export_path / "spans.json"
                file_path.write_text(data_json)
                success(f"Exported {len(records)} spans to {file_path}")
        else:
            with spinner("Exporting spans"):
                response = client.spans.list(
                    project=project_id,
                    space=space,
                    start_time=start_dt,
                    end_time=end_dt,
                    filter=filter_combined,
                    limit=limit,
                )
            spans = getattr(response, "spans", None) or []
            if not spans:
                warning("No spans found")
            if stdout:
                print_json_array(spans)
            else:
                export_path = make_export_dir(output_dir, prefix, id_value)
                file_path = write_json_array(export_path, "spans.json", spans)
                success(f"Exported {len(spans)} spans to {file_path}")
    except AxError:
        raise
    except Exception as e:
        raise APIError(f"Failed to export spans: {e}") from e
