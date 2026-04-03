"""Integration tests for ``ax spaces`` commands."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.conftest import ax_json

pytestmark = pytest.mark.integration


class TestSpacesList:
    """ax spaces list — smoke tests."""

    @pytest.mark.integration
    def test_list_returns_results(self, api_key: str) -> None:
        """``ax spaces list`` succeeds and returns at least one space."""
        data = ax_json("spaces", "list")
        assert "spaces" in data
        assert len(data["spaces"]) >= 1

    @pytest.mark.integration
    def test_list_with_limit(self, api_key: str) -> None:
        """``--limit 1`` returns at most one space."""
        data = ax_json("spaces", "list", "--limit", "1")
        assert "spaces" in data
        assert len(data["spaces"]) <= 1

    @pytest.mark.integration
    def test_list_cursor_shorthand(self, api_key: str) -> None:
        """``-l`` shorthand for --limit is accepted."""
        data = ax_json("spaces", "list", "-l", "1")
        assert "spaces" in data


class TestSpacesGet:
    """ax spaces get — smoke tests."""

    @pytest.mark.integration
    def test_get_by_id(self, first_space: dict[str, Any]) -> None:
        """``ax spaces get <id>`` returns the expected space."""
        space_id = first_space["id"]
        data = ax_json("spaces", "get", space_id)
        assert data.get("id") == space_id

    @pytest.mark.integration
    def test_get_by_name(self, first_space: dict[str, Any]) -> None:
        """``ax spaces get <name>`` resolves by name and returns the space."""
        space_name = first_space.get("name") or first_space["id"]
        data = ax_json("spaces", "get", space_name)
        assert data.get("id") == first_space["id"]
