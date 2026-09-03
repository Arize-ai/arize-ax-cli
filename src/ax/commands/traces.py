"""Traces management commands."""

import json
import shutil
import sys
from contextlib import AbstractContextManager, nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any

import typer
from arize import ArizeClient
from arize._generated.api_client.models.span import Span
from arize.traces.types import ListTracesResponse, Trace
from openinference.semconv.trace import SpanAttributes
from rich.markup import escape

from ax.core.client_factory import make_client
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError, AxError
from ax.core.output import console as output_console
from ax.core.output import output_data
from ax.utils.console import (
    info,
    setup_logging,
    spinner,
    success,
    text,
    warning,
)
from ax.utils.datetime_parse import parse_optional_iso8601
from ax.utils.export import make_export_dir, print_json_array, write_json_array
from ax.utils.file_io import (
    parse_output_option,
)

_KIND_STYLE: dict[str, str] = {
    "AGENT": "blue",
    "CHAIN": "blue",
    "LLM": "magenta",
    "RETRIEVER": "cyan",
    "TOOL": "yellow",
    "EMBEDDING": "green",
    "RERANKER": "cyan",
    "GUARDRAIL": "red",
    "EVALUATOR": "yellow",
    "PROMPT": "blue",
}
_DEFAULT_KIND_STYLE = "white"
_TRACE_SEPARATOR = "=" * 80


def _style_for_kind(kind: str) -> str:
    """Return the Rich style for an OpenInference span kind."""
    return _KIND_STYLE.get(kind, _DEFAULT_KIND_STYLE)


def _format_duration_milliseconds(span: Span) -> str:
    """Format a span duration as integer milliseconds."""
    milliseconds = (span.end_time - span.start_time).total_seconds() * 1000
    return f"{milliseconds:.0f}ms"


def _span_label(span: Span, *, full_span_id: bool) -> str:
    """Build the Rich-markup label for one span."""
    span_id = span.context.span_id if full_span_id else span.context.span_id[:7]
    span_id = escape(span_id)
    kind = span.kind.value
    kind_style = _style_for_kind(kind)
    status = span.status_code.value if span.status_code else "OK"
    status_symbol = "[red]✗[/red]" if status == "ERROR" else "[green]✓[/green]"
    return (
        f"[dim]{span_id}[/dim] ([{kind_style}]{escape(kind)}[/{kind_style}]) "
        f"{status_symbol} {escape(span.name)} - "
        f"{_format_duration_milliseconds(span)}"
    )


def _format_cost(value: float) -> str:
    """Format a summed ``llm.cost.total`` value as a USD amount."""
    return f"${value:.6f}"


def _trace_cost(trace: Trace) -> float | None:
    """Sum the ``llm.cost.total`` attribute across a trace's spans.

    Returns ``None`` when no span carries a cost attribute, so the caller can
    omit the field rather than showing a misleading ``$0.000000``.
    """
    total = 0.0
    found = False
    for span in trace.spans:
        cost = (span.attributes or {}).get(SpanAttributes.LLM_COST_TOTAL)
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            total += float(cost)
            found = True
    return total if found else None


def _format_trace_attribute(value: object) -> str:
    """Format a trace input or output as a single Rich-safe line."""
    formatted = (
        json.dumps(value) if isinstance(value, (dict, list)) else str(value)
    )
    return escape(" ".join(formatted.splitlines()))


def _append_span_tree_lines(
    lines: list[str],
    root: Span,
    children: dict[str, list[Span]],
    *,
    full_span_ids: bool,
    is_last_root: bool = True,
) -> None:
    """Append a span tree in depth-first order."""
    stack = [(root, "│  ", is_last_root)]
    visited_span_ids = {root.context.span_id}
    while stack:
        span, prefix, is_last = stack.pop()
        connector = "└─" if is_last else "├─"
        lines.append(
            f"{prefix}{connector} "
            f"{_span_label(span, full_span_id=full_span_ids)}"
        )

        child_prefix = prefix + ("   " if is_last else "│  ")
        span_children = sorted(
            children.get(span.context.span_id, []),
            key=lambda child: child.start_time,
        )
        unvisited_children = []
        for child in span_children:
            child_span_id = child.context.span_id
            if child_span_id in visited_span_ids:
                continue
            visited_span_ids.add(child_span_id)
            unvisited_children.append(child)

        stack.extend(
            (
                unvisited_children[index],
                child_prefix,
                index == len(unvisited_children) - 1,
            )
            for index in range(len(unvisited_children) - 1, -1, -1)
        )


def _trace_lines(trace: Trace, *, full_span_ids: bool = False) -> list[str]:
    """Build the branch-graph lines for one trace.

    A trace's root span is not guaranteed to be present in ``trace.spans``:
    the server caps the number of spans returned per trace, and since the
    root is the oldest span it is the first one dropped once that cap is
    hit. Any span whose parent was dropped the same way is treated as an
    additional top-level branch rather than causing a crash.
    """
    lines = [f"┌─ Trace: [bold]{escape(trace.trace_id)}[/bold]", "│"]

    spans_by_id = {s.context.span_id: s for s in trace.spans}
    children: dict[str, list[Span]] = {}
    for span in trace.spans:
        if span.parent_id is not None:
            children.setdefault(span.parent_id, []).append(span)

    roots = sorted(
        (
            s
            for s in trace.spans
            if s.parent_id is None or s.parent_id not in spans_by_id
        ),
        key=lambda s: s.start_time,
    )

    if not roots:
        lines.extend(
            ("│", "│  [yellow]No spans returned for this trace[/yellow]", "└─")
        )
        return lines

    display_root = spans_by_id.get(trace.root_span_id) or roots[0]
    attributes = display_root.attributes or {}
    input_value = attributes.get(SpanAttributes.INPUT_VALUE)
    output_value = attributes.get(SpanAttributes.OUTPUT_VALUE)

    meta_parts = []
    if isinstance(trace.start_time, datetime):
        meta_parts.append(
            f"[bold]Start:[/bold] "
            f"{trace.start_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    trace_cost = _trace_cost(trace)
    if trace_cost is not None:
        meta_parts.append(f"[bold]Cost:[/bold] {_format_cost(trace_cost)}")
    if meta_parts:
        lines.append(f"│  {'   '.join(meta_parts)}")

    if input_value is not None:
        lines.append(
            f"│  [bold]Input:[/bold] {_format_trace_attribute(input_value)}"
        )
    if output_value is not None:
        lines.append(
            f"│  [bold]Output:[/bold] {_format_trace_attribute(output_value)}"
        )
    if meta_parts or input_value is not None or output_value is not None:
        lines.append("│")
    lines.append("│  [bold]Spans:[/bold]")

    for index, span_root in enumerate(roots):
        _append_span_tree_lines(
            lines,
            span_root,
            children,
            full_span_ids=full_span_ids,
            is_last_root=index == len(roots) - 1,
        )
    if trace.root_span_id not in spans_by_id:
        lines.extend(
            ("│", "│  [yellow]Root span not included in this page[/yellow]")
        )
    if trace.spans_truncated:
        lines.extend(("│", "│  [yellow]Spans truncated[/yellow]"))
    lines.append("└─")
    return lines


_PROSE_LINE_MARKERS = ("[bold]Input:[/bold]", "[bold]Output:[/bold]")


def _render_traces_graph(
    response: ListTracesResponse, *, full_span_ids: bool = False
) -> None:
    """Default `ax traces list` view: each trace as a branch graph.

    Rendered at the real terminal width (queried fresh on every call, with a
    generous fallback for non-interactive output) rather than relying on
    Rich's own detection, which falls back to a fixed 80 columns whenever it
    can't confirm a tty and otherwise truncates well short of the visible
    pane. In verbose mode the Input/Output lines wrap instead of ellipsizing
    so the full value is visible; everything else (span rows included) stays
    single-line so the tree structure never reflows.
    """
    term_width = shutil.get_terminal_size(fallback=(200, 24)).columns
    for index, trace in enumerate(response.traces):
        if index:
            output_console.print()
            output_console.print(_TRACE_SEPARATOR)
            output_console.print()
        for line in _trace_lines(trace, full_span_ids=full_span_ids):
            if full_span_ids and any(m in line for m in _PROSE_LINE_MARKERS):
                output_console.print(line, width=term_width)
            else:
                output_console.print(
                    line, overflow="ellipsis", no_wrap=True, width=term_width
                )

    pagination = response.pagination
    if getattr(pagination, "has_more", False):
        output_console.print(
            f"[dim]cursor:[/dim] {pagination.next_cursor}  "
            "[dim]· pass --cursor to fetch the next page[/dim]"
        )


# Create traces subcommand app
app = typer.Typer(
    name="traces",
    help="Manage traces",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


@app.command("list")
@handle_errors
def list_traces(
    project_id: Annotated[
        str,
        typer.Argument(help="Project name or ID"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required when using a project name)",
        ),
    ] = None,
    start_time: Annotated[
        str | None,
        typer.Option(
            "--start-time",
            help="Start of time window, inclusive (ISO 8601, e.g. "
            "2024-01-01T00:00:00Z; UTC assumed if no offset).",
        ),
    ] = None,
    end_time: Annotated[
        str | None,
        typer.Option(
            "--end-time",
            help="End of time window, exclusive (ISO 8601, e.g. "
            "2024-01-02T00:00:00Z; UTC assumed if no offset). Defaults to now.",
        ),
    ] = None,
    filter: Annotated[
        str | None,
        typer.Option(
            "--filter",
            help='Filter expression (e.g. "status_code = \'ERROR\'", "latency_ms > 1000"). '
            "A trace is returned when any of its spans matches.",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of traces to return (default: 15, max: 50)",
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
            help="Output format (table, json, csv, parquet) or file path. "
            "Defaults to a branch-graph view of each trace's spans.",
        ),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose log.",
        ),
    ] = False,
) -> None:
    """List traces in a project.

    Without --output, always renders the branch-graph view — this command
    does not fall back to the active profile's default output format the
    way other list commands do.
    """
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    start_dt = parse_optional_iso8601(start_time)
    end_dt = parse_optional_iso8601(end_time)

    try:
        fetch_context: AbstractContextManager[Any]
        if output:
            fetch_context = spinner("Fetching traces")
        else:
            text(f"Resolving project: {project_id}")
            text(f"Fetching last {limit} trace(s)...")
            fetch_context = nullcontext()
        with fetch_context:
            response = client.traces.list(
                project=project_id,
                space=space,
                start_time=start_dt,
                end_time=end_dt,
                filter=filter,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list traces: {e}") from e
    else:
        if output:
            output_data(
                response,
                format_type=output_format,
                output_file=output_file,
            )
        else:
            text(f"Found {len(response.traces)} trace(s)")
            _render_traces_graph(response, full_span_ids=verbose)


def _build_trace_id_in_filter(trace_ids: list[str]) -> str:
    """Build a ``context.trace_id IN (...)`` filter clause."""
    quoted = ", ".join(f"'{tid}'" for tid in trace_ids)
    return f"context.trace_id IN ({quoted})"


@app.command("export")
@handle_errors
def export_traces(
    project_id: Annotated[
        str,
        typer.Argument(
            help="Project name or ID (name requires --space; use project name with --all)"
        ),
    ],
    filter_expr: Annotated[
        str | None,
        typer.Option(
            "--filter",
            help="Filter expression applied to initial span lookup (e.g. \"status_code = 'ERROR'\").",
        ),
    ] = None,
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required when using a project name or --all)",
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
            help="Override start of time window (ISO 8601; UTC assumed if no offset)",
        ),
    ] = None,
    end_time: Annotated[
        str | None,
        typer.Option(
            "--end-time",
            help="Override end of time window (ISO 8601; UTC assumed if no offset)",
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
    """Export full traces (all spans for matching traces).

    Phase 1: find spans matching --filter (or all spans) to collect trace IDs.
    Phase 2: fetch every span belonging to those traces.

    Pass --all to use Arrow Flight for both phases (requires --space).
    """
    setup_logging(verbose)

    if days <= 0:
        raise typer.BadParameter("--days must be a positive integer.")

    if not use_all and limit <= 0:
        raise typer.BadParameter("--limit must be a positive integer.")

    if use_all and not space:
        raise typer.BadParameter("--space is required when using --all.")

    if use_all and limit != 50:
        warning("--limit is ignored when --all is set.")

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
            _export_traces_flight(
                client=client,
                project=project_id,
                space=space or "",
                start_dt=start_dt,
                end_dt=end_dt,
                filter_expr=filter_expr,
                output_dir=output_dir,
                stdout=stdout,
            )
        else:
            _export_traces_rest(
                client=client,
                project_id=project_id,
                space=space,
                start_dt=start_dt,
                end_dt=end_dt,
                filter_expr=filter_expr,
                limit=limit,
                output_dir=output_dir,
                stdout=stdout,
            )
    except AxError:
        raise
    except Exception as e:
        raise APIError(f"Failed to export traces: {e}") from e


def _export_traces_rest(
    *,
    client: ArizeClient,
    project_id: str,
    space: str | None,
    start_dt: datetime,
    end_dt: datetime,
    filter_expr: str | None,
    limit: int,
    output_dir: str,
    stdout: bool,
) -> None:
    """Two-phase trace export using the REST API."""
    with spinner("Phase 1: finding matching spans"):
        response = client.spans.list(
            project=project_id,
            space=space,
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
            project=project_id,
            space=space,
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
    space: str,
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
                space_id=space,
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
                space_id=space,
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
