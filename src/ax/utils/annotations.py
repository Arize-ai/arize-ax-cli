"""Shared utilities for batch annotation CLI commands."""

from __future__ import annotations

import typer
from arize.datasets.types import AnnotateRecordInput

from ax.utils.file_io import read_data_file


def parse_annotations(file: str | None) -> list[AnnotateRecordInput]:
    """Read annotation records from a file or stdin.

    Args:
        file: Path to a JSON, JSONL, CSV, or Parquet file, or ``'-'`` for stdin.

    Returns:
        A list of :class:`AnnotateRecordInput` objects ready for the SDK.

    Raises:
        typer.BadParameter: If no file is provided.
    """
    if not file:
        raise typer.BadParameter(
            "Provide annotations via --file (use '-' for stdin)."
        )
    records = read_data_file(file).to_dict(orient="records")
    return [
        r
        for item in records
        if (r := AnnotateRecordInput.from_dict(item)) is not None  # type: ignore[arg-type]
    ]
