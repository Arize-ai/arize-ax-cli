"""Output formatters for different formats (table, json, csv, parquet)."""

import json
import re
import sys
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ax.core.exceptions import FileIOError
from ax.core.pydantic import (
    basemodel_to_dataframe,
    categorize_basemodel_fields,
    flatten_basemodel_for_export,
    is_list_response_model,
)
from ax.utils.console import new_line, success, text_dimmed

console = Console()


# Column-name tokens that mark id-like columns (ids, cursors, tokens, keys).
# Matched against `_`-delimited tokens, not as substrings, so "provider" and
# "provider_metadata" are NOT treated as id-like just because they contain "id".
_NO_WRAP_TOKENS: set[str] = {"id", "cursor", "token", "key"}
_EMPTY_VALUE = "[dim]—[/dim]"

# Render width large enough that a non-expanding table never has to shrink its
# columns to fit. rich emits the table at its natural width (it does not pad out
# to the console width), so the terminal wraps any overflow instead of rich
# collapsing columns and scattering ellipses.
_UNBOUNDED_WIDTH = 1_000_000
# Cap per-column width for prose columns; longer cells wrap (fold) within it so
# a single outlier value can't blow out the whole table width.
_MAX_COL_WIDTH = 30

_STATUS_COLORS: dict[str, str] = {
    "active": "green",
    "deleted": "red",
    "pending": "yellow",
    "expired": "dim",
    "inactive": "dim",
}


def _col_no_wrap(col_name: str) -> bool:
    """Return True for id-like columns that should stay on one line.

    Splits the column name into tokens (on any non-alphanumeric boundary) and
    matches whole tokens against ``_NO_WRAP_TOKENS`` — e.g. ``id``,
    ``created_by_user_id``, ``next_cursor``, ``has_api_key`` match, while
    ``provider`` and ``provider_metadata`` (which merely *contain* "id") do not.
    """
    tokens = re.split(r"[^a-z0-9]+", col_name.lower())
    return any(token in _NO_WRAP_TOKENS for token in tokens)


def _add_columns(table: Table, columns: Sequence[str]) -> None:
    """Add columns, capping prose columns and leaving id-like columns intact.

    id/cursor/token/key columns render on a single line (``no_wrap``) so values
    you may need to copy are never chopped into fixed-width chunks across rows.
    All other columns are capped at ``_MAX_COL_WIDTH`` and fold (wrap) so a long
    outlier value cannot blow out the entire table width.

    Args:
        table: Rich table to add columns to.
        columns: Column names (DataFrame columns).
    """
    for col in columns:
        if _col_no_wrap(col):
            table.add_column(str(col), no_wrap=True)
        else:
            table.add_column(
                str(col), max_width=_MAX_COL_WIDTH, overflow="fold"
            )


def _visible_width(rendered: str) -> int:
    """Return the widest visible line, ignoring ANSI control codes.

    Args:
        rendered: Captured table output, possibly containing ANSI styling.
    """
    return max(
        (Text.from_ansi(line).cell_len for line in rendered.splitlines()),
        default=0,
    )


def _print_overflow_hint() -> None:
    """Nudge an interactive user when a table is too wide for their terminal."""
    new_line()
    text_dimmed(
        "The table is wider than your terminal. To see it all, choose one of "
        "the following options:\n"
        "1. zoom out\n"
        "2. re-run with `-o json`\n"
        "3. pipe output to a pager (e.g. `| less -SR`)\n"
        "4. redirect to a file (e.g. `> out.txt`) and open it in an editor"
    )


def _print_table(table: Table) -> None:
    """Print a table at its full natural width, never shrinking columns.

    A non-expanding rich table renders at its natural width regardless of the
    console width, so rendering through a console widened past any real terminal
    means rich never collapses columns or inserts ellipses. The terminal wraps
    long lines; capped columns still fold within ``_MAX_COL_WIDTH``. The table is
    rendered once (into a capture buffer) so its visible width is known without a
    second pass; if that exceeds an interactive terminal, a muted hint is printed
    to stderr telling the user how to view the full table.

    Args:
        table: Rich table to render.
    """
    render_console = Console(
        file=console.file,
        width=_UNBOUNDED_WIDTH,
        force_terminal=console.is_terminal,
    )
    with render_console.capture() as capture:
        render_console.print(table)
    rendered = capture.get()
    render_console.file.write(rendered)
    # Manual write bypasses rich's flush; flush so the table lands before the
    # stderr hint below (otherwise the streams can interleave out of order).
    render_console.file.flush()

    # Only nudge an interactive user whose terminal is too narrow; piped or
    # redirected output already received the full table cleanly.
    if console.is_terminal and _visible_width(rendered) > console.width:
        _print_overflow_hint()


class BaseModelTableFormatter:
    """Formatter for rendering BaseModel objects as Rich tables with metadata panels."""

    def __init__(self, status_colors: dict[str, str] | None = None) -> None:
        """Initialise the formatter.

        Args:
            status_colors: Optional mapping of status string → Rich color name.
                Merged on top of the module-level ``_STATUS_COLORS`` defaults,
                so callers only need to supply overrides.
        """
        self._status_colors = status_colors or _STATUS_COLORS

    def format(self, model: BaseModel) -> None:
        """Format and display a BaseModel with metadata panel and list field tables.

        Args:
            model: Pydantic BaseModel instance to format
        """
        metadata, list_fields = categorize_basemodel_fields(model)

        # Render metadata panel if there are scalar fields
        if metadata:
            self._render_metadata_panel(model, metadata)

        # Render each list field as a separate table
        for field_name, items in list_fields.items():
            if metadata:  # Add spacing if we rendered a panel
                new_line()
            self._render_list_field_table(field_name, items)

    def _render_metadata_panel(
        self, model: BaseModel, metadata: dict[str, Any]
    ) -> None:
        """Render scalar fields as a Rich Panel.

        Args:
            model: BaseModel instance (for class name)
            metadata: Dictionary of scalar field values
        """
        lines = []
        for key, value in metadata.items():
            formatted_value = self._format_value(value)
            lines.append(f"[bold cyan]{key}:[/bold cyan] {formatted_value}")

        panel = Panel(
            "\n".join(lines),
            title=f"[bold]{model.__class__.__name__} Details[/bold]",
            border_style="cyan",
            padding=(1, 2),
        )
        console.print(panel)

    def _render_list_field_table(self, field_name: str, items: list) -> None:
        """Render a list field as a Rich Table.

        Args:
            field_name: Name of the field
            items: List of items (BaseModel or dict objects)
        """
        if not items:
            return

        # Convert to DataFrame
        df = basemodel_to_dataframe(items)

        if df.empty:
            return

        # Create Rich table with title showing count
        table = Table(
            show_header=True,
            header_style="bold cyan",
            title=f"[bold]{field_name.title()} ({len(items)})[/bold]",
            show_lines=True,
        )

        # Add columns
        _add_columns(table, list(df.columns))

        # Add rows with formatted values
        for _, row in df.iterrows():
            formatted_row = [self._format_value(val) for val in row]
            table.add_row(*formatted_row)

        _print_table(table)

    def _format_value(self, value: object) -> str:
        """Format a value for display in table or panel.

        Args:
            value: Value to format

        Returns:
            Formatted string
        """
        if value is None:
            return _EMPTY_VALUE
        if value is pd.NaT:
            return _EMPTY_VALUE
        # pandas converts Python None → float('nan') or pd.NA inside DataFrames
        if isinstance(value, float) and pd.isna(value):
            return _EMPTY_VALUE
        if value is pd.NA:
            return _EMPTY_VALUE
        if isinstance(value, bool):
            return "[green]True[/green]" if value else "[red]False[/red]"
        if isinstance(value, (datetime, pd.Timestamp)):
            try:
                if pd.isna(value):
                    return _EMPTY_VALUE
            except (TypeError, ValueError):
                pass
            if value.year <= 1:
                return _EMPTY_VALUE
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, list):
            if not value:
                return _EMPTY_VALUE
            formatted = [self._format_value(item) for item in value]
            if len(formatted) <= 3:
                return " | ".join(formatted)
            return "\n".join(formatted)
        # Unwrap SDK domain types that have __str__ (e.g. PredefinedOrgRole, PredefinedUserRole)
        if isinstance(value, BaseModel):
            return str(value)
        # Unwrap generated OneOf discriminated union wrapper dicts
        # (pattern: dict with `actual_instance` + `one_of_schemas` from openapi-generator)
        if (
            isinstance(value, dict)
            and "actual_instance" in value
            and "one_of_schemas" in value
        ):
            actual = value.get("actual_instance")
            if isinstance(actual, dict):
                # Predefined role: {'type': ..., 'name': ...} → show name
                if "name" in actual:
                    return self._format_value(actual["name"])
                # Custom role: {'type': ..., 'id': ...} → show id
                if "id" in actual:
                    return self._format_value(actual["id"])
            return self._format_value(actual)
        # Expand generic nested dicts as "key=value, ..." — skipping None and empty containers.
        if isinstance(value, dict):
            parts = []
            for k, v in value.items():
                if (
                    v is None
                    or (isinstance(v, dict) and not v)
                    or (isinstance(v, list) and not v)
                ):
                    continue
                parts.append(f"{k}={self._format_value(v)}")
            return ", ".join(parts) if parts else "[dim]{}[/dim]"
        # Unwrap enum instances (e.g. ApiKeyStatus.ACTIVE → "active") before display
        if isinstance(value, Enum):
            value = value.value
        if isinstance(value, str):
            color = self._status_colors.get(value.lower())
            if color:
                return f"[{color}]{value}[/{color}]"
        return str(value)


class OutputFormatter(ABC):
    """Base class for output formatters."""

    @abstractmethod
    def format(self, data: BaseModel, output_file: str = "") -> None:
        """Format and output data.

        Args:
            data: Data to format (DataFrame, dict, list, etc.)
            output_file: Optional file path to write to. If None, writes to stdout.
        """

    def _to_dataframe(self, data: BaseModel) -> pd.DataFrame:
        """Convert various data types to DataFrame."""
        # Handle list responses - extract items only (no pagination in files)
        if is_list_response_model(data):
            # These response objects should have an added `to_df()` method
            # that extracts the data as a dataframe (excluding pagination)
            return data.to_df(  # type:ignore
                exclude_none=True,
                expand_prefix="",
            )

        # Handle single BaseModel - flatten for export
        flattened = flatten_basemodel_for_export(data)
        return pd.DataFrame([flattened])


class TableFormatter(OutputFormatter):
    """Rich table formatter for beautiful terminal output."""

    def __init__(self, status_colors: dict[str, str] | None = None) -> None:
        """Initialise the formatter.

        Args:
            status_colors: Optional status-color overrides forwarded to
                :class:`BaseModelTableFormatter`.
        """
        self._status_colors = status_colors

    def format(self, data: BaseModel, output_file: str = "") -> None:
        """Format data as a Rich table."""
        if output_file:
            raise FileIOError(
                "Table format can only be output to terminal (stdout)"
            )

        # Special handling for list responses - show items + pagination
        if is_list_response_model(data):
            df = self._to_dataframe(data)
            # Prioritize 'name' column: move it immediately before 'id' if both present
            if "name" in df.columns and "id" in df.columns:
                cols = [c for c in df.columns if c != "name"]
                cols.insert(cols.index("id"), "name")
                df = df[cols]
            # Show items as table
            if len(df) > 0:
                # Render table
                table = Table(
                    show_header=True,
                    header_style="bold cyan",
                    show_lines=True,
                )
                _add_columns(table, list(df.columns))
                formatter = BaseModelTableFormatter(
                    status_colors=self._status_colors
                )
                for _, row in df.iterrows():
                    table.add_row(
                        *[formatter._format_value(val) for val in row]
                    )
                _print_table(table)
            else:
                text_dimmed("No items to display")

            # Show pagination info below (only for models that carry pagination)
            pagination = getattr(data, "pagination", None)
            if pagination is not None and pagination.has_more:
                new_line()
                if pagination.next_cursor:
                    text_dimmed(
                        "More items available. To fetch the next page, add:"
                    )
                    console.print(
                        f"  [bold cyan]--cursor[/bold cyan] "
                        f"[yellow]{pagination.next_cursor}[/yellow]"
                    )
                else:
                    text_dimmed(
                        "More items available. Pagination cursor not supported for "
                        "this command — it will be available in a future release."
                    )
            return

        # Special handling for BaseModel - use BaseModelTableFormatter
        if isinstance(data, BaseModel):
            formatter = BaseModelTableFormatter(
                status_colors=self._status_colors
            )
            formatter.format(data)
            return


class JSONFormatter(OutputFormatter):
    """JSON formatter for machine-readable output.

    Writes directly to sys.stdout instead of using Rich's console.print().
    Rich wraps long lines to fit the terminal width (default 80 columns),
    which inserts literal newlines into JSON string values and produces
    invalid JSON that json.loads() cannot parse.
    """

    def format(self, data: BaseModel, output_file: str = "") -> None:
        """Format data as JSON."""
        output = data.model_dump(mode="json", exclude_none=True)
        json_str = json.dumps(output, indent=2, default=str)

        if output_file:
            try:
                Path(output_file).write_text(json_str)
            except Exception as e:
                raise FileIOError(f"Failed to write JSON file: {e}") from e
            else:
                success(f"Saved to {output_file}")
        else:
            sys.stdout.write(json_str)
            sys.stdout.write("\n")


class CSVFormatter(OutputFormatter):
    """CSV formatter for export-friendly output.

    Writes directly to sys.stdout instead of Rich's console.print()
    for the same reason as JSONFormatter -- Rich line-wrapping corrupts
    machine-readable output.
    """

    def format(self, data: BaseModel, output_file: str = "") -> None:
        """Format data as CSV."""
        df = self._to_dataframe(data)

        if output_file:
            try:
                df.to_csv(output_file, index=False)
            except Exception as e:
                raise FileIOError(f"Failed to write CSV file: {e}") from e
            else:
                success(f"Saved to {output_file}")
        else:
            sys.stdout.write(df.to_csv(index=False))


class ParquetFormatter(OutputFormatter):
    """Parquet formatter for efficient binary storage."""

    def format(self, data: BaseModel, output_file: str = "") -> None:
        """Format data as Parquet."""
        if not output_file:
            raise FileIOError(
                "Parquet format requires an output file. "
                "Use --output to specify a file path."
            )

        try:
            df = self._to_dataframe(data)
            df.to_parquet(output_file, index=False)
        except Exception as e:
            raise FileIOError(f"Failed to write Parquet file: {e}") from e
        else:
            success(f"Saved to {output_file}")


def get_formatter(
    format_type: str,
    status_colors: dict[str, str] | None = None,
) -> OutputFormatter:
    """Factory function to get formatter by type.

    Args:
        format_type: Format type (table, json, csv, parquet)
        status_colors: Optional status-color overrides for the table formatter.
            Merged on top of the module-level defaults; only the table formatter
            uses this — other formatters ignore it.

    Returns:
        OutputFormatter instance

    Raises:
        ValueError: If format_type is not supported
    """
    format_type_lower = format_type.lower()
    if format_type_lower == "table":
        return TableFormatter(status_colors=status_colors)

    formatters: dict[str, type[OutputFormatter]] = {
        "json": JSONFormatter,
        "csv": CSVFormatter,
        "parquet": ParquetFormatter,
    }

    formatter_class = formatters.get(format_type_lower)
    if not formatter_class:
        raise ValueError(
            f"Unsupported format: {format_type}. "
            f"Supported formats: table, {', '.join(formatters.keys())}"
        )

    return formatter_class()


def output_data(
    data: BaseModel,
    format_type: str = "table",
    output_file: str = "",
    status_colors: dict[str, str] | None = None,
) -> None:
    """Convenience function to format and output data.

    Args:
        data: Data to output
        format_type: Output format (table, json, csv, parquet)
        output_file: Optional output file path
        status_colors: Optional status-color overrides for table output.
            Merged on top of the module-level defaults so callers only need
            to supply the values they want to change. For example,
            ``{"deleted": "green", "not_found": "yellow"}`` turns the
            ``"deleted"`` status green in a bulk-delete result table without
            affecting other commands.

    Example:
        >>> output_data(df, format_type="json", output_file="data.json")
        >>> output_data(df, format_type="table")
    """
    formatter = get_formatter(format_type, status_colors=status_colors)
    formatter.format(data, output_file)
