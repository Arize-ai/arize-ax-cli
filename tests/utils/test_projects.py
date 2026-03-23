"""Tests for project resolution utilities."""

from unittest.mock import MagicMock

import pytest

from ax.core.exceptions import UsageError
from ax.utils.projects import _is_base64_id, resolve_project_id


class TestIsBase64Id:
    """Tests for _is_base64_id helper."""

    def test_valid_project_id(self) -> None:
        """Base64-encoded project ID with colon separator is detected."""
        assert _is_base64_id("TW9kZWw6MTIz") is True  # Model:123

    def test_human_readable_name(self) -> None:
        """Human-readable project name is not mistaken for a base64 ID."""
        assert _is_base64_id("copilot-prod") is False

    def test_empty_string(self) -> None:
        """Empty string is not a base64 ID."""
        assert _is_base64_id("") is False

    def test_plain_number(self) -> None:
        """Plain number string is not a base64 ID."""
        assert _is_base64_id("12345") is False


class TestResolveProjectId:
    """Tests for resolve_project_id."""

    def test_base64_id_returned_without_space_id(self) -> None:
        """A base64 project ID is returned as-is even without space_id."""
        client = MagicMock()
        assert (
            resolve_project_id(client, "TW9kZWw6MTIz", None) == "TW9kZWw6MTIz"
        )
        client.projects.list.assert_not_called()

    def test_base64_id_returned_with_space_id(self) -> None:
        """A base64 project ID is returned as-is even when space_id is given."""
        client = MagicMock()
        assert (
            resolve_project_id(client, "TW9kZWw6MTIz", "space-123")
            == "TW9kZWw6MTIz"
        )
        client.projects.list.assert_not_called()

    def test_name_without_space_id_raises(self) -> None:
        """A name without space_id raises a helpful error."""
        client = MagicMock()
        with pytest.raises(UsageError, match="looks like a name"):
            resolve_project_id(client, "copilot-prod", None)

    def test_resolves_name_to_id(self) -> None:
        """When space_id is provided, project name is resolved via projects.list."""
        proj = MagicMock()
        proj.name = "copilot-prod"
        proj.id = "TW9kZWw6MjMwMDI5NDQwNDpqdlp4"

        client = MagicMock()
        response = MagicMock()
        response.projects = [proj]
        response.next_cursor = None
        client.projects.list.return_value = response

        result = resolve_project_id(client, "copilot-prod", "space-123")
        assert result == "TW9kZWw6MjMwMDI5NDQwNDpqdlp4"
        client.projects.list.assert_called_once_with(
            space_id="space-123", limit=1000, cursor=None
        )

    def test_paginates_to_find_project(self) -> None:
        """Follows next_cursor across multiple pages to find a project."""
        proj_page1 = MagicMock()
        proj_page1.name = "other-project"

        proj_page2 = MagicMock()
        proj_page2.name = "copilot-prod"
        proj_page2.id = "TW9kZWw6MjMwMDI5NDQwNDpqdlp4"

        page1 = MagicMock()
        page1.projects = [proj_page1]
        page1.next_cursor = "cursor-abc"

        page2 = MagicMock()
        page2.projects = [proj_page2]
        page2.next_cursor = None

        client = MagicMock()
        client.projects.list.side_effect = [page1, page2]

        result = resolve_project_id(client, "copilot-prod", "space-123")
        assert result == "TW9kZWw6MjMwMDI5NDQwNDpqdlp4"
        assert client.projects.list.call_count == 2

    def test_raises_when_project_not_found(self) -> None:
        """Raises ValueError when the project name doesn't match any project."""
        proj = MagicMock()
        proj.name = "other-project"

        client = MagicMock()
        response = MagicMock()
        response.projects = [proj]
        response.next_cursor = None
        client.projects.list.return_value = response

        with pytest.raises(UsageError, match="not found in space"):
            resolve_project_id(client, "copilot-prod", "space-123")

    def test_matches_exact_name(self) -> None:
        """Only exact name matches are returned, not partial matches."""
        proj1 = MagicMock()
        proj1.name = "copilot-prod-v2"
        proj1.id = "id-v2"

        proj2 = MagicMock()
        proj2.name = "copilot-prod"
        proj2.id = "id-exact"

        client = MagicMock()
        response = MagicMock()
        response.projects = [proj1, proj2]
        response.next_cursor = None
        client.projects.list.return_value = response

        assert (
            resolve_project_id(client, "copilot-prod", "space-1") == "id-exact"
        )
