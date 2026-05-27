"""Integration tests for roles CLI commands against the real Arize API.

These tests are skipped unless ARIZE_API_KEY is set. They create real roles,
exercise each command, and clean up after themselves.

Run with:
    ARIZE_API_KEY=<key> pytest tests/commands/test_roles_integration.py -m integration -v
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from collections.abc import Generator

import pytest
from typer.testing import CliRunner

from ax.cli import app
from ax.config.schema import AuthConfig, Config

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

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UNIQUE = uuid.uuid4().hex[:8]
_ROLE_NAME = f"ax-cli-test-role-{_UNIQUE}"


def _real_config() -> Config:
    """Return a Config backed by the real API key."""
    return Config(auth=AuthConfig(api_key=API_KEY))


def _invoke(*args: str, cli_input: str | None = None) -> object:
    """Invoke a CLI command with a real config and no mocks (except ConfigManager)."""
    config = _real_config()
    with patch("ax.commands.roles.ConfigManager.load", return_value=config):
        return runner.invoke(app, list(args), input=cli_input)


# ---------------------------------------------------------------------------
# Fixture: create a role and delete it after the test
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def created_role_id() -> Generator[str, None, None]:
    """Create a test role before the module and delete it after."""
    result = _invoke(
        "roles",
        "create",
        "--name",
        _ROLE_NAME,
        "--permissions",
        "PROJECT_READ",
        "--output",
        "json",
    )
    assert result.exit_code == 0, f"role create failed:\n{result.output}"

    # Parse the role ID from JSON output
    import json

    data = json.loads(result.output)
    role_id = data.get("id") or data.get("role", {}).get("id")
    assert role_id, f"could not parse role ID from output:\n{result.output}"

    yield role_id

    # Cleanup — ignore errors (role may already be deleted)
    _invoke("roles", "delete", role_id, "--force")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRolesIntegration:
    """End-to-end integration tests for all `ax roles` commands against the real API."""

    def test_list_returns_roles(self) -> None:
        """Roles list should return at least the predefined roles."""
        result = _invoke("roles", "list", "--output", "json")
        assert result.exit_code == 0, result.output

    def test_list_is_predefined_filter(self) -> None:
        """Roles list --is-predefined should only return predefined roles."""
        result = _invoke("roles", "list", "--is-predefined", "--output", "json")
        assert result.exit_code == 0, result.output

    def test_list_is_custom_filter(self) -> None:
        """Roles list --is-custom should only return custom roles."""
        result = _invoke("roles", "list", "--is-custom", "--output", "json")
        assert result.exit_code == 0, result.output

    def test_create_and_get_by_id(self, created_role_id: str) -> None:
        """Roles get with a real ID should return role details."""
        result = _invoke("roles", "get", created_role_id, "--output", "json")
        assert result.exit_code == 0, result.output

    def test_get_by_name(self, created_role_id: str) -> None:
        """Roles get with a role name should resolve and return the role."""
        result = _invoke("roles", "get", _ROLE_NAME, "--output", "json")
        assert result.exit_code == 0, result.output

    def test_update_name(self, created_role_id: str) -> None:
        """Roles update should modify the role name."""
        new_name = f"{_ROLE_NAME}-updated"
        result = _invoke(
            "roles",
            "update",
            created_role_id,
            "--name",
            new_name,
            "--output",
            "json",
        )
        assert result.exit_code == 0, result.output

        # Rename back so other tests still find the role by name
        _invoke(
            "roles",
            "update",
            created_role_id,
            "--name",
            _ROLE_NAME,
        )

    def test_update_permissions(self, created_role_id: str) -> None:
        """Roles update --permissions should replace the permission set."""
        result = _invoke(
            "roles",
            "update",
            created_role_id,
            "--permissions",
            "PROJECT_READ,DATASET_READ",
            "--output",
            "json",
        )
        assert result.exit_code == 0, result.output

    def test_delete_by_name(self) -> None:
        """Roles delete should work when passed a role name."""
        # Create a throwaway role specifically for this delete-by-name test
        tmp_name = f"ax-cli-tmp-{uuid.uuid4().hex[:6]}"
        create_result = _invoke(
            "roles",
            "create",
            "--name",
            tmp_name,
            "--permissions",
            "PROJECT_READ",
            "--output",
            "json",
        )
        assert create_result.exit_code == 0, create_result.output

        delete_result = _invoke("roles", "delete", tmp_name, "--force")
        assert delete_result.exit_code == 0, delete_result.output

    def test_get_nonexistent_exits_nonzero(self) -> None:
        """Roles get with an unknown name should exit non-zero."""
        result = _invoke("roles", "get", "nonexistent-role-xyz-12345")
        assert result.exit_code != 0
