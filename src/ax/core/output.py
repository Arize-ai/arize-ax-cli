"""Output formatters for different formats (table, json, csv, parquet)."""

import json
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ax.core.exceptions import FileIOError
from ax.core.pydantic import (
    basemodel_to_dataframe,
    categorize_basemodel_fields,
    flatten_basemodel_for_export,
    is_list_response_model,
)
from ax.utils.console import new_line, success, text_dimmed

console = Console()


_NO_WRAP_SUBSTRINGS: set[str] = {"id", "cursor", "token", "key"}

_STATUS_COLORS: dict[str, str] = {
    "active": "green",
    "deleted": "red",
    "pending": "yellow",
    "expired": "dim",
    "inactive": "dim",
}


def _col_no_wrap(col_name: str) -> bool:
    """Return True for columns that should not wrap (IDs, tokens, cursors)."""
    lower = col_name.lower()
    return any(sub in lower for sub in _NO_WRAP_SUBSTRINGS)


def _all_none(obj: object) -> bool:
    """Return True if obj is None or a BaseModel whose every field is None."""
    if obj is None:
        return True
    if isinstance(obj, BaseModel):
        return all(getattr(obj, f) is None for f in type(obj).model_fields)
    return False


def _is_prompt_with_version(model: BaseModel) -> bool:
    """Duck-type check: True if model looks like a PromptWithVersion."""
    version = getattr(model, "version", None)
    return (
        isinstance(version, BaseModel)
        and hasattr(version, "messages")
        and hasattr(version, "provider")
    )


def _is_prompt_version(model: BaseModel) -> bool:
    """Duck-type check: True if model looks like a standalone PromptVersion.

    Excludes PromptWithVersion by requiring the `version` field (if present)
    to NOT be a BaseModel with messages+provider (i.e. a nested PromptVersion).
    """
    if not (
        hasattr(model, "messages")
        and isinstance(getattr(model, "messages", None), list)
        and hasattr(model, "provider")
        and hasattr(model, "commit_message")
    ):
        return False
    # Exclude PromptWithVersion: its `version` child is a BaseModel with messages
    version_field = getattr(model, "version", None)
    return not (
        isinstance(version_field, BaseModel)
        and hasattr(version_field, "messages")
        and hasattr(version_field, "provider")
    )


class PromptFormatter:
    """Dedicated formatter for PromptWithVersion and PromptVersion SDK objects.

    Replaces the generic BaseModelTableFormatter for prompt types to avoid
    leaking internal Python repr strings (LLMMessage, enum values, etc.).
    """

    def format_with_version(self, model: BaseModel) -> None:
        """Format a PromptWithVersion cleanly."""
        version = getattr(model, "version")
        lines: list[str] = []

        for field in ("id", "name", "description", "space_id"):
            val = getattr(model, field, None)
            if val is not None:
                lines.append(f"[bold cyan]{field}:[/bold cyan] {val}")

        for field in ("created_at", "updated_at"):
            val = getattr(model, field, None)
            if isinstance(val, datetime):
                lines.append(
                    f"[bold cyan]{field}:[/bold cyan] "
                    f"{val.strftime('%Y-%m-%d %H:%M:%S')}"
                )

        lines += self._version_lines(version)

        console.print(
            Panel(
                "\n".join(lines),
                title="[bold]Prompt Details[/bold]",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    def format_version(self, model: BaseModel) -> None:
        """Format a standalone PromptVersion cleanly."""
        lines = self._version_lines(model)
        console.print(
            Panel(
                "\n".join(lines),
                title="[bold]Prompt Version Details[/bold]",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _version_lines(self, version: BaseModel) -> list[str]:
        lines: list[str] = []

        for field in ("id", "prompt_id", "commit_hash", "commit_message"):
            val = getattr(version, field, None)
            if val is not None:
                lines.append(f"[bold cyan]{field}:[/bold cyan] {val}")

        labels = getattr(version, "labels", None)
        if labels:
            lines.append(
                f"[bold cyan]labels:[/bold cyan] {', '.join(labels)}"
            )

        messages = getattr(version, "messages", None) or []
        if messages:
            lines.append("")
            lines.append("[bold]Messages[/bold]")
            lines.append("─" * 55)
            for msg in messages:
                lines.extend(self._format_message_lines(msg))

        model_name = getattr(version, "model", None)
        provider = getattr(version, "provider", None)
        ivf = getattr(version, "input_variable_format", None)

        if model_name or provider or ivf:
            lines.append("")
        if model_name:
            if provider is not None:
                pstr = (
                    provider.value if isinstance(provider, Enum) else str(provider)
                )
                lines.append(
                    f"[bold cyan]model:[/bold cyan] {model_name} ({pstr})"
                )
            else:
                lines.append(f"[bold cyan]model:[/bold cyan] {model_name}")
        elif provider is not None:
            pstr = provider.value if isinstance(provider, Enum) else str(provider)
            lines.append(f"[bold cyan]provider:[/bold cyan] {pstr}")

        if ivf is not None:
            fstr = ivf.value if isinstance(ivf, Enum) else str(ivf)
            lines.append(
                f"[bold cyan]input_variable_format:[/bold cyan] {fstr}"
            )

        invocation_params = getattr(version, "invocation_params", None)
        if invocation_params is not None and not _all_none(invocation_params):
            lines.append("")
            lines.append("[bold]Invocation Parameters[/bold]")
            for field_name in type(invocation_params).model_fields:
                val = getattr(invocation_params, field_name, None)
                if val is not None:
                    lines.append(
                        f"  [bold cyan]{field_name}:[/bold cyan] {val}"
                    )

        return lines

    def _format_message_lines(self, msg: object) -> list[str]:
        role = getattr(msg, "role", None)
        role_str = (
            role.value if isinstance(role, Enum) else str(role) if role else "?"
        )
        content = getattr(msg, "content", None)
        tool_calls = getattr(msg, "tool_calls", None)
        tool_call_id = getattr(msg, "tool_call_id", None)

        if content is not None:
            return [f"  [[cyan]{role_str}[/cyan]] {content}"]
        if tool_calls:
            lines = []
            for tc in tool_calls:
                fn = getattr(tc, "function", None)
                fn_name = getattr(fn, "name", "?") if fn else "?"
                lines.append(f"  [[cyan]{role_str}[/cyan]] \u2192 {fn_name}()")
            return lines
        if tool_call_id:
            return [
                f"  [[cyan]{role_str}[/cyan]] (tool response for {tool_call_id})"
            ]
        return [f"  [[cyan]{role_str}[/cyan]]"]


class BaseModelTableFormatter:
    """Formatter for rendering BaseModel objects as Rich tables with metadata panels."""

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
        )

        # Add columns
        for col in df.columns:
            table.add_column(str(col), no_wrap=_col_no_wrap(col))

        # Add rows with formatted values
        for _, row in df.iterrows():
            formatted_row = [self._format_value(val) for val in row]
            table.add_row(*formatted_row)

        console.print(table)

    def _format_value(self, value: object) -> str:
        """Format a value for display in table or panel.

        Args:
            value: Value to format

        Returns:
            Formatted string
        """
        if value is None:
            return "[dim]None[/dim]"
        if isinstance(value, bool):
            return "[green]True[/green]" if value else "[red]False[/red]"
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, list):
            # Empty list or list of scalars
            return f"[dim]{len(value)} items[/dim]" if value else "[dim][]"
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
        # Unwrap enum instances (e.g. ApiKeyStatus.ACTIVE → "active") before display
        if isinstance(value, Enum):
            value = value.value
        if isinstance(value, str):
            color = _STATUS_COLORS.get(value.lower())
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

    def format(self, data: BaseModel, output_file: str = "") -> None:
        """Format data as a Rich table."""
        if output_file:
            raise FileIOError(
                "Table format can only be output to terminal (stdout)"
            )

        # Special handling for list responses - show items + pagination
        if is_list_response_model(data):
            df = self._to_dataframe(data)
            # Show items as table
            if len(df) > 0:
                # Render table
                table = Table(show_header=True, header_style="bold cyan")
                for col in df.columns:
                    table.add_column(str(col), no_wrap=_col_no_wrap(col))
                formatter = BaseModelTableFormatter()
                for _, row in df.iterrows():
                    table.add_row(
                        *[formatter._format_value(val) for val in row]
                    )
                console.print(table)
            else:
                text_dimmed("No items to display")

            # Show pagination info below
            if data.pagination.has_more:  # type: ignore
                new_line()
                if data.pagination.next_cursor:  # type: ignore
                    text_dimmed(
                        "More items available. To fetch the next page, add:"
                    )
                    console.print(
                        f"  [bold cyan]--cursor[/bold cyan] "
                        f"[yellow]{data.pagination.next_cursor}[/yellow]"  # type: ignore
                    )
                else:
                    text_dimmed(
                        "More items available. Pagination cursor not supported for "
                        "this command — it will be available in a future release."
                    )
            return

        # Special handling for prompt types — use dedicated formatter to avoid
        # leaking internal SDK repr strings.
        if isinstance(data, BaseModel):
            if _is_prompt_with_version(data):
                PromptFormatter().format_with_version(data)
                return
            if _is_prompt_version(data):
                PromptFormatter().format_version(data)
                return

        # Special handling for BaseModel - use BaseModelTableFormatter
        if isinstance(data, BaseModel):
            formatter = BaseModelTableFormatter()
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


def get_formatter(format_type: str) -> OutputFormatter:
    """Factory function to get formatter by type.

    Args:
        format_type: Format type (table, json, csv, parquet)

    Returns:
        OutputFormatter instance

    Raises:
        ValueError: If format_type is not supported
    """
    formatters: dict[str, type[OutputFormatter]] = {
        "table": TableFormatter,
        "json": JSONFormatter,
        "csv": CSVFormatter,
        "parquet": ParquetFormatter,
    }

    formatter_class = formatters.get(format_type.lower())
    if not formatter_class:
        raise ValueError(
            f"Unsupported format: {format_type}. "
            f"Supported formats: {', '.join(formatters.keys())}"
        )

    return formatter_class()


def output_data(
    data: BaseModel,
    format_type: str = "table",
    output_file: str = "",
) -> None:
    """Convenience function to format and output data.

    Args:
        data: Data to output
        format_type: Output format (table, json, csv, parquet)
        output_file: Optional output file path

    Example:
        >>> output_data(df, format_type="json", output_file="data.json")
        >>> output_data(df, format_type="table")
    """
    formatter = get_formatter(format_type)
    formatter.format(data, output_file)
