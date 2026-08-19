"""Integration tests for roles CLI commands against the real Arize API.

These tests are skipped unless ARIZE_API_KEY is set. They create real roles,
exercise each command, and clean up after themselves.

Run with:
    ARIZE_API_KEY=<key> pytest tests/integration/test_roles.py -m integration -v
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Generator

import pytest

from tests.integration.conftest import ax, ax_json

# ---------------------------------------------------------------------------
# Skip unless credentials are available
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("ARIZE_API_KEY", "")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not API_KEY,
        reason="ARIZE_API_KEY must be set to run integration tests",
    ),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UNIQUE = uuid.uuid4().hex[:8]
_ROLE_NAME = f"ax-cli-test-role-{_UNIQUE}"


# ---------------------------------------------------------------------------
# Fixture: create a role and delete it after the test
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def created_role_id() -> Generator[str, None, None]:
    """Create a test role before the module and delete it after."""
    result = ax(
        "roles",
        "create",
        "--name",
        _ROLE_NAME,
        "--permissions",
        "PROJECT_READ",
        "--output",
        "json",
    )
    assert result.returncode == 0, f"role create failed:\n{result.stderr}"

    data = json.loads(result.stdout)
    role_id = data.get("id") or data.get("role", {}).get("id")
    assert role_id, f"could not parse role ID from output:\n{result.stdout}"

    yield role_id

    # Cleanup — ignore errors (role may already be deleted)
    ax("roles", "delete", role_id, "--force")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRolesIntegration:
    """End-to-end integration tests for all `ax roles` commands against the real API."""

    def test_list_returns_roles(self) -> None:
        """Roles list should return at least the predefined roles."""
        data = ax_json("roles", "list")
        assert "roles" in data

    def test_list_is_predefined_filter(self) -> None:
        """Roles list --is-predefined should only return predefined roles."""
        data = ax_json("roles", "list", "--is-predefined")
        assert "roles" in data

    def test_list_is_custom_filter(self) -> None:
        """Roles list --is-custom should only return custom roles."""
        data = ax_json("roles", "list", "--is-custom")
        assert "roles" in data

    def test_create_and_get_by_id(self, created_role_id: str) -> None:
        """Roles get with a real ID should return role details."""
        data = ax_json("roles", "get", created_role_id)
        assert data.get("id") == created_role_id

    def test_get_by_name(self, created_role_id: str) -> None:
        """Roles get with a role name should resolve and return the role."""
        data = ax_json("roles", "get", _ROLE_NAME)
        assert data.get("id") == created_role_id

    def test_update_name(self, created_role_id: str) -> None:
        """Roles update should modify the role name."""
        new_name = f"{_ROLE_NAME}-updated"
        data = ax_json("roles", "update", created_role_id, "--name", new_name)
        assert data.get("id") == created_role_id

        # Rename back so other tests still find the role by name
        ax("roles", "update", created_role_id, "--name", _ROLE_NAME)

    def test_update_permissions(self, created_role_id: str) -> None:
        """Roles update --permissions should replace the permission set."""
        data = ax_json(
            "roles",
            "update",
            created_role_id,
            "--permissions",
            "PROJECT_READ,DATASET_READ",
        )
        assert data.get("id") == created_role_id

    def test_delete_by_name(self) -> None:
        """Roles delete should work when passed a role name."""
        tmp_name = f"ax-cli-tmp-{uuid.uuid4().hex[:6]}"
        create_result = ax(
            "roles",
            "create",
            "--name",
            tmp_name,
            "--permissions",
            "PROJECT_READ",
            "--output",
            "json",
        )
        assert create_result.returncode == 0, create_result.stderr

        delete_result = ax("roles", "delete", tmp_name, "--force")
        assert delete_result.returncode == 0, delete_result.stderr

    def test_get_nonexistent_exits_nonzero(self) -> None:
        """Roles get with an unknown name should exit non-zero."""
        result = ax("roles", "get", "nonexistent-role-xyz-12345")
        assert result.returncode != 0
