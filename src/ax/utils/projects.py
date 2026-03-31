"""Project resolution utilities."""

import base64
import logging

from arize import ArizeClient

from ax.core.exceptions import UsageError

logger = logging.getLogger(__name__)


def _is_base64_id(value: str) -> bool:
    """Detect whether *value* is a base64-encoded project ID (e.g. ``TW9kZWw6MTIz``)."""
    try:
        decoded = base64.b64decode(value, validate=True).decode("utf-8")
    except Exception:
        return False
    else:
        return ":" in decoded


def resolve_project_id(
    client: ArizeClient,
    project: str,
    space_id: str | None,
) -> str:
    """Resolve a project name or base64 ID to the API project ID.

    Auto-detects the format of *project*:

    * **Base64 project ID** (e.g. ``"TW9kZWw6MTIz"``) -- returned as-is,
      regardless of whether *space_id* is provided.
    * **Human-readable name** (e.g. ``"copilot-prod"``) -- resolved by
      listing projects in the given space.  Requires *space_id*.

    Args:
        client: Authenticated Arize client.
        project: Project name or base64 project ID.
        space_id: Required when *project* is a name.  Ignored when
            *project* is already a base64 ID.

    Returns:
        The base64 project ID suitable for the REST API.

    Raises:
        UsageError: If the project name cannot be found, or if a name is
            given without *space_id*.
    """
    if _is_base64_id(project):
        logger.debug("Detected base64 project ID: %s", project)
        return project

    if not space_id:
        raise UsageError(
            f"Project '{project}' looks like a name, not a base64 ID. "
            f"Provide --space-id so the name can be resolved."
        )

    available: list[str] = []
    cursor: str | None = None

    while True:
        response = client.projects.list(
            space=space_id, limit=1000, cursor=cursor
        )
        for p in response.projects:
            if p.name == project:
                logger.debug("Resolved project '%s' → %s", project, p.id)
                return p.id
            available.append(p.name)

        cursor = getattr(response, "next_cursor", None)
        if not cursor:
            break

    raise UsageError(
        f"Project '{project}' not found in space {space_id}. "
        f"Available projects: {', '.join(available)}"
    )
