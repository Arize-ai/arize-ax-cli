"""Shared utilities for export commands."""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)

_GITIGNORE_ENTRY = ".arize-tmp-traces/"


def _ensure_gitignored(output_dir: Path) -> None:
    """Add the output directory to .gitignore if it looks like our tmp traces dir.

    Walks up from *output_dir* looking for a .gitignore next to a .git directory.
    If the resolved top-level output directory name matches the well-known
    ``.arize-tmp-traces`` convention, ensures the entry is present in .gitignore.
    """
    try:
        resolved = output_dir.resolve()
    except OSError:
        return

    if _GITIGNORE_ENTRY.rstrip("/") not in resolved.parts:
        return

    search = resolved
    while search != search.parent:
        if (search / ".git").exists():
            gitignore = search / ".gitignore"
            try:
                existing = gitignore.read_text() if gitignore.exists() else ""
                if _GITIGNORE_ENTRY not in existing.splitlines():
                    with gitignore.open("a") as f:
                        if existing and not existing.endswith("\n"):
                            f.write("\n")
                        f.write(f"{_GITIGNORE_ENTRY}\n")
            except OSError:
                logger.debug("Could not update .gitignore at %s", gitignore)
            return
        search = search.parent


def make_export_dir(output_dir: str, prefix: str, id: str) -> Path:
    """Create a timestamped export directory.

    Returns a path like ``{output_dir}/trace_abc123_20260305_141500/``.
    If the output directory is under ``.arize-tmp-traces``, automatically
    ensures that directory is listed in the nearest .gitignore.
    """
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_id = id.replace("/", "_")[:50]
    dir_name = f"{prefix}_{safe_id}_{timestamp}"
    path = Path(output_dir) / dir_name
    path.mkdir(parents=True, exist_ok=True)
    _ensure_gitignored(path)
    return path


def write_json_array(
    path: Path,
    filename: str,
    items: list[BaseModel],
) -> Path:
    """Serialize a list of Pydantic models as a JSON array and write to *path/filename*."""
    file_path = path / filename
    data = [item.model_dump(mode="json", exclude_none=True) for item in items]
    file_path.write_text(json.dumps(data, indent=2))
    return file_path


def print_json_array(items: list[BaseModel]) -> None:
    """Print a list of Pydantic models as a JSON array to stdout."""
    data = [item.model_dump(mode="json", exclude_none=True) for item in items]
    json.dump(data, sys.stdout, indent=2)
    sys.stdout.write("\n")
