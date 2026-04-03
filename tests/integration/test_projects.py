"""Integration tests for ``ax projects`` commands."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.conftest import ax_json

pytestmark = pytest.mark.integration


class TestProjectsList:
    """ax projects list — smoke tests against a known space."""

    @pytest.mark.integration
    def test_list_by_space_id(self, test_space_id: str) -> None:
        """``ax projects list --space <id>`` succeeds."""
        data = ax_json("projects", "list", "--space", test_space_id)
        assert "projects" in data

    @pytest.mark.integration
    def test_list_by_space_name(self, first_space: dict[str, Any]) -> None:
        """``ax projects list --space <name>`` accepts a name as well as an ID."""
        space_name = first_space.get("name") or first_space["id"]
        data = ax_json("projects", "list", "--space", space_name)
        assert "projects" in data

    @pytest.mark.integration
    def test_list_with_limit(self, test_space_id: str) -> None:
        """``--limit 1`` is respected."""
        data = ax_json(
            "projects", "list", "--space", test_space_id, "--limit", "1"
        )
        assert "projects" in data
        assert len(data["projects"]) <= 1
