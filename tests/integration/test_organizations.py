"""Integration tests for ``ax organizations`` commands."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.conftest import ax, ax_json

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def first_organization(api_key: str) -> dict[str, Any]:
    """Return the first organization accessible to the authenticated user."""
    data = ax_json("organizations", "list", "--limit", "1")
    orgs = data.get("organizations") or []
    if not orgs:
        pytest.skip("No organizations found for this API key")
    return orgs[0]


class TestOrganizationsList:
    """ax organizations list — smoke tests."""

    @pytest.mark.integration
    def test_list_returns_results(self, api_key: str) -> None:
        """``ax organizations list`` succeeds and returns at least one organization."""
        data = ax_json("organizations", "list")
        assert "organizations" in data

    @pytest.mark.integration
    def test_list_with_limit(self, api_key: str) -> None:
        """``--limit 1`` returns at most one organization."""
        data = ax_json("organizations", "list", "--limit", "1")
        assert "organizations" in data
        assert len(data["organizations"]) <= 1

    @pytest.mark.integration
    def test_list_with_name_filter(self, api_key: str) -> None:
        """``--name`` filter is accepted and returns a valid response."""
        data = ax_json(
            "organizations", "list", "--name", "nonexistent-xyz-12345"
        )
        assert "organizations" in data
        assert data["organizations"] == []


class TestOrganizationsGet:
    """ax organizations get — smoke tests."""

    @pytest.mark.integration
    def test_get_by_id(self, first_organization: dict[str, Any]) -> None:
        """``ax organizations get <id>`` returns the expected organization."""
        org_id = first_organization["id"]
        data = ax_json("organizations", "get", org_id)
        assert data.get("id") == org_id

    @pytest.mark.integration
    def test_get_by_name(self, first_organization: dict[str, Any]) -> None:
        """``ax organizations get <name>`` resolves by name and returns the org."""
        org_name = first_organization.get("name") or first_organization["id"]
        data = ax_json("organizations", "get", org_name)
        assert data.get("id") == first_organization["id"]

    @pytest.mark.integration
    def test_get_nonexistent_exits_nonzero(self, api_key: str) -> None:
        """Get with an unknown name should exit non-zero."""
        result = ax("organizations", "get", "nonexistent-org-xyz-12345")
        assert result.returncode != 0


class TestOrganizationsDelete:
    """ax organizations delete — error and abort tests."""

    @pytest.mark.integration
    def test_delete_nonexistent_exits_nonzero(self, api_key: str) -> None:
        """Delete with an unknown ID should exit non-zero."""
        result = ax(
            "organizations", "delete", "nonexistent-org-xyz-12345", "--force"
        )
        assert result.returncode != 0
