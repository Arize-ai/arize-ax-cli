"""File I/O utilities for reading and writing various formats."""

import os
from pathlib import Path

import pandas as pd

from ax.core.exceptions import FileIOError
from ax.utils.console import spinner


def read_data_file(path: str) -> pd.DataFrame:
    """Auto-detect file format and read into DataFrame.

    Supported formats:
    - CSV (.csv)
    - JSON (.json)
    - JSON Lines (.jsonl)
    - Parquet (.parquet, .pq)

    Args:
        path: Path to data file

    Returns:
        DataFrame containing the data

    Raises:
        FileIOError: If file doesn't exist, format unsupported, or read fails
    """
    file_path = Path(path)

    if not file_path.exists():
        raise FileIOError(f"File not found: {path}")

    suffix = file_path.suffix.lower()

    # Check file size to determine if we should show spinner
    # Only show spinner for files larger than 1MB to avoid flicker
    file_size = os.path.getsize(path)
    show_spinner = file_size > 1_000_000  # 1MB threshold

    filename = file_path.name

    def _read_file() -> pd.DataFrame:
        """Helper to read file with appropriate handler."""
        if suffix == ".csv":
            try:
                return pd.read_csv(path)
            except Exception as e:
                raise FileIOError(f"Failed to read file {path}: {e}") from e
        if suffix == ".json":
            try:
                return pd.read_json(path)
            except Exception as e:
                raise FileIOError(f"Failed to read file {path}: {e}") from e
        if suffix == ".jsonl":
            try:
                return pd.read_json(path, lines=True)
            except Exception as e:
                raise FileIOError(f"Failed to read file {path}: {e}") from e
        if suffix in (".parquet", ".pq"):
            try:
                return pd.read_parquet(path)
            except Exception as e:
                raise FileIOError(f"Failed to read file {path}: {e}") from e
        raise FileIOError(
            f"Unsupported file format: {suffix}\n"
            f"Supported formats: .csv, .json, .jsonl, .parquet, .pq"
        )

    # Show spinner for large files
    if show_spinner:
        with spinner(
            f"Reading {filename}",
            success_msg="File read successfully",
        ):
            return _read_file()
    return _read_file()


def write_data_file(
    df: pd.DataFrame, path: str, format_type: str | None = None
) -> None:
    """Write DataFrame to file with specified or auto-detected format.

    Args:
        df: DataFrame to write
        path: Output file path
        format_type: Optional format override (csv, json, jsonl, parquet)
                    If None, detects from file extension

    Raises:
        FileIOError: If write fails
    """
    file_path = Path(path)

    # Auto-detect format from extension if not specified
    if format_type is None:
        suffix = file_path.suffix.lower()
        format_map = {
            ".csv": "csv",
            ".json": "json",
            ".jsonl": "jsonl",
            ".parquet": "parquet",
            ".pq": "parquet",
        }
        format_type = format_map.get(suffix)
        if not format_type:
            raise FileIOError(
                f"Cannot auto-detect format from extension: {suffix}\n"
                f"Please specify format explicitly or use a supported extension"
            )

    # Validate format
    if format_type not in ("csv", "json", "jsonl", "parquet"):
        raise FileIOError(f"Unsupported format: {format_type}")

    # Write file
    try:
        if format_type == "csv":
            df.to_csv(path, index=False)
        elif format_type == "json":
            df.to_json(path, orient="records", indent=2)
        elif format_type == "jsonl":
            df.to_json(path, orient="records", lines=True)
        elif format_type == "parquet":
            df.to_parquet(path, index=False)
    except Exception as e:
        raise FileIOError(f"Failed to write file {path}: {e}") from e


def parse_output_option(output: str) -> tuple[str, str]:
    """Parse the unified --output option to determine format and file path.

    Args:
        output: Output value (format name or file path)

    Returns:
        Tuple of (format, file_path)
        - If output is a format name: (format, None)
        - If output is a file path: (detected_format, file_path)
        - If output is None: ("table", None)

    Examples:
        parse_output_option("json") -> ("json", None)
        parse_output_option("data.csv") -> ("csv", "data.csv")
        parse_output_option(None) -> ("table", None)
    """
    # Check if it's a format name
    valid_formats = {"table", "json", "csv", "parquet"}
    if output in valid_formats:
        return (output, "")

    # Otherwise, treat it as a file path
    try:
        format_type = _detect_format(output)
    except FileIOError:
        # If we can't detect format, raise a helpful error
        raise FileIOError(
            f"Invalid output option: {output}\n"
            f"Must be either:\n"
            f"  - A format: {', '.join(valid_formats)}\n"
            f"  - A file path with extension: .json, .csv, .jsonl, .parquet, .pq"
        ) from None
    else:
        return (format_type, output)


def _detect_format(path: str) -> str:
    """Detect file format from extension.

    Args:
        path: File path

    Returns:
        Format string (csv, json, jsonl, parquet)

    Raises:
        FileIOError: If format cannot be detected
    """
    suffix = Path(path).suffix.lower()
    format_map = {
        ".csv": "csv",
        ".json": "json",
        ".jsonl": "jsonl",
        ".parquet": "parquet",
        ".pq": "parquet",
    }

    format_type = format_map.get(suffix)
    if not format_type:
        raise FileIOError(
            f"Cannot detect format from extension: {suffix}\n"
            f"Supported extensions: {', '.join(format_map.keys())}"
        )

    return format_type
