"""Integration tests for ``ax spans`` commands."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from tests.integration.conftest import ax

pytestmark = pytest.mark.integration


class TestSpansDelete:
    """ax spans delete — smoke tests."""

    @pytest.mark.integration
    def test_delete_missing_span_id_exits_nonzero(
        self, first_project: dict[str, Any], test_space_id: str
    ) -> None:
        """``ax spans delete`` without --span-id should exit non-zero."""
        project_id = first_project["id"]
        result = ax(
            "spans",
            "delete",
            project_id,
            "--space",
            test_space_id,
            "--force",
        )
        assert result.returncode != 0

    @pytest.mark.integration
    def test_delete_nonexistent_span_id_succeeds(
        self, first_project: dict[str, Any], test_space_id: str
    ) -> None:
        """Nonexistent span IDs are silently ignored; exit code should be 0."""
        project_id = first_project["id"]
        fake_span_id = uuid.uuid4().hex
        result = ax(
            "spans",
            "delete",
            project_id,
            "--space",
            test_space_id,
            "--span-id",
            fake_span_id,
            "--force",
        )
        assert result.returncode == 0, f"spans delete failed:\n{result.stderr}"
