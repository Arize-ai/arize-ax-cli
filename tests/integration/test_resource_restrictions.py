"""Integration tests for ``ax resource-restrictions`` commands."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.conftest import ax, ax_json

pytestmark = pytest.mark.integration


class TestResourceRestrictionsLifecycle:
    """Full restrict → restrict (idempotent) → unrestrict lifecycle on a real project."""

    @pytest.mark.integration
    def test_restrict_project(self, first_project: dict[str, Any]) -> None:
        """``ax resource-restrictions restrict`` marks the project as restricted."""
        project_id = first_project["id"]
        data = ax_json(
            "resource-restrictions", "restrict", "--resource-id", project_id
        )
        assert data.get("resource_id") == project_id
        assert data.get("resource_type") == "PROJECT"

    @pytest.mark.integration
    def test_restrict_is_idempotent(
        self, first_project: dict[str, Any]
    ) -> None:
        """Restricting an already-restricted project succeeds without error."""
        project_id = first_project["id"]
        data = ax_json(
            "resource-restrictions", "restrict", "--resource-id", project_id
        )
        assert data.get("resource_id") == project_id

    @pytest.mark.integration
    def test_unrestrict_project(self, first_project: dict[str, Any]) -> None:
        """``ax resource-restrictions unrestrict --force`` removes the restriction."""
        project_id = first_project["id"]
        result = ax(
            "resource-restrictions",
            "unrestrict",
            "--resource-id",
            project_id,
            "--force",
        )
        assert result.returncode == 0, (
            f"unrestrict failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
