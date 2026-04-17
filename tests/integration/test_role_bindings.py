"""Integration tests for ``ax role-bindings`` commands.

Required environment variables:
  - ARIZE_API_KEY: valid Arize API key (always required)

Required for lifecycle tests (create / get / update / delete):
  - ARIZE_TEST_USER_ID: global ID (base64) of the user to bind a role to
  - ARIZE_TEST_ROLE_ID: global ID (base64) of the role to assign
  - ARIZE_TEST_SPACE: space name or ID used as the binding resource
    (falls back to the first space returned by ``ax spaces list``)

Run all role binding tests::

    ARIZE_API_KEY=<key> \\
    ARIZE_TEST_USER_ID=<user-global-id> \\
    ARIZE_TEST_ROLE_ID=<role-global-id> \\
    pytest tests/integration/test_role_bindings.py -m integration -v
"""

from __future__ import annotations

import json

import pytest

from tests.integration.conftest import ax, ax_json

pytestmark = pytest.mark.integration


class TestRoleBindingsErrors:
    """Verify that role-bindings commands reach the real API and surface errors correctly."""

    @pytest.mark.integration
    def test_get_nonexistent_binding_fails(self) -> None:
        """``ax role-bindings get`` with an unknown ID exits non-zero."""
        result = ax("role-bindings", "get", "cm9sZV9iaW5kaW5nOjk5OTk5OTk=")
        assert result.returncode != 0

    @pytest.mark.integration
    def test_update_nonexistent_binding_fails(self) -> None:
        """``ax role-bindings update`` with an unknown binding ID exits non-zero."""
        result = ax(
            "role-bindings",
            "update",
            "cm9sZV9iaW5kaW5nOjk5OTk5OTk=",
            "--role-id",
            "Um9sZTo5OTk5OTk=",
        )
        assert result.returncode != 0

    @pytest.mark.integration
    def test_delete_nonexistent_binding_fails(self) -> None:
        """``ax role-bindings delete --force`` with an unknown ID exits non-zero."""
        result = ax(
            "role-bindings",
            "delete",
            "cm9sZV9iaW5kaW5nOjk5OTk5OTk=",
            "--force",
        )
        assert result.returncode != 0


class TestRoleBindingsLifecycle:
    """Full create → get → update → duplicate → delete lifecycle.

    Skipped unless ARIZE_TEST_USER_ID and ARIZE_TEST_ROLE_ID are set.
    """

    @pytest.mark.integration
    def test_lifecycle(
        self,
        test_user_id: str,
        test_role_id: str,
        test_space_id: str,
    ) -> None:
        """Create a binding, get it, update it, verify conflict handling, then delete it."""
        binding_id: str | None = None

        try:
            # --- create ---
            create_result = ax(
                "role-bindings",
                "create",
                "--user-id",
                test_user_id,
                "--role-id",
                test_role_id,
                "--resource-type",
                "SPACE",
                "--resource-id",
                test_space_id,
                "--output",
                "json",
            )
            assert create_result.returncode == 0, (
                f"create failed:\nstdout: {create_result.stdout}\n"
                f"stderr: {create_result.stderr}"
            )
            created = json.loads(create_result.stdout)
            binding_id = created.get("id")
            assert binding_id, f"no id in create response: {created}"
            assert created.get("user_id") == test_user_id
            assert created.get("resource_id") == test_space_id

            # --- get ---
            data = ax_json("role-bindings", "get", binding_id)
            assert data.get("id") == binding_id
            assert data.get("user_id") == test_user_id

            # --- update (assign same role — still exercises the endpoint) ---
            update_result = ax(
                "role-bindings",
                "update",
                binding_id,
                "--role-id",
                test_role_id,
                "--output",
                "json",
            )
            assert update_result.returncode == 0, (
                f"update failed:\nstdout: {update_result.stdout}\n"
                f"stderr: {update_result.stderr}"
            )
            updated = json.loads(update_result.stdout)
            assert updated.get("id") == binding_id
            assert updated.get("role_id") == test_role_id

            # --- duplicate create is handled gracefully (exit 0, info message) ---
            dup_result = ax(
                "role-bindings",
                "create",
                "--user-id",
                test_user_id,
                "--role-id",
                test_role_id,
                "--resource-type",
                "SPACE",
                "--resource-id",
                test_space_id,
            )
            assert dup_result.returncode == 0, (
                f"duplicate create should exit 0:\nstdout: {dup_result.stdout}\n"
                f"stderr: {dup_result.stderr}"
            )
            assert "already exists" in dup_result.stderr

        finally:
            if binding_id:
                delete_result = ax(
                    "role-bindings", "delete", binding_id, "--force"
                )
                assert delete_result.returncode == 0, (
                    f"delete failed:\nstdout: {delete_result.stdout}\n"
                    f"stderr: {delete_result.stderr}"
                )
