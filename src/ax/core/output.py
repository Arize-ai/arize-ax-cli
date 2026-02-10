"""Output formatters for different formats (table, json, csv, parquet)."""

import json
from abc import ABC, abstractmethod
from datetime import datetime
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
from ax.utils.console import new_line, text, text_dimmed

console = Console()


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
            table.add_column(str(col))

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
                expand_field="additional_properties",
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
                    table.add_column(str(col))
                for _, row in df.iterrows():
                    table.add_row(*[str(val) for val in row])
                console.print(table)
            else:
                text_dimmed("No items to display")

            # Show pagination info below
            if data.pagination.has_more:  # type: ignore
                msg = "Page complete. More items available."
                if data.pagination.next_cursor:  # type: ignore
                    msg += f" Use --cursor {data.pagination.next_cursor}"  # type: ignore
                else:
                    msg += (
                        " Pagination cursor not supported for this command, "
                        "it will be available in a future release."
                    )
                new_line()
                text_dimmed(msg)
            return

        # Special handling for BaseModel - use BaseModelTableFormatter
        if isinstance(data, BaseModel):
            formatter = BaseModelTableFormatter()
            formatter.format(data)
            return


class JSONFormatter(OutputFormatter):
    """JSON formatter for machine-readable output."""

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
            text(json_str)


class CSVFormatter(OutputFormatter):
    """CSV formatter for export-friendly output."""

    def format(self, data: BaseModel, output_file: str = "") -> None:
        """Format data as CSV."""
        df = self._to_dataframe(data)

        if output_file:
            try:
                df.to_csv(output_file, index=False)
            except Exception as e:
                raise FileIOError(f"Failed to write CSV file: {e}") from e
        else:
            # Output to stdout
            csv_str = df.to_csv(index=False)
            text(csv_str)


class ParquetFormatter(OutputFormatter):
    """Parquet formatter for efficient binary storage."""

    def format(self, data: BaseModel, output_file: str = "") -> None:
        """Format data as Parquet."""
        if not output_file:
            raise FileIOError(
                "Parquet format requires an output file. "
                "Use --output to specify a file path."
            )

        df = self._to_dataframe(data)

        try:
            df.to_parquet(output_file, index=False)
        except Exception as e:
            raise FileIOError(f"Failed to write Parquet file: {e}") from e


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
