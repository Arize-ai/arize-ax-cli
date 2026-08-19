"""Integration tests for ``ax users`` commands and related user membership commands.

Requires:
  - ARIZE_API_KEY environment variable set to a valid API key
  - (Optional) ARIZE_TEST_ORG_ID set to an organization ID for org membership tests.
  - (Optional) ARIZE_TEST_SPACE_ID set to a space ID for space membership tests.
    Both ARIZE_TEST_ORG_ID and ARIZE_TEST_SPACE_ID are required for space membership tests.

Run::

    ARIZE_API_KEY=<key> pytest tests/integration/test_users.py -m integration -v

"""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest

from tests.integration.conftest import ax, ax_json

pytestmark = pytest.mark.integration

_UNIQUE_EMAIL_DOMAIN = "ax-cli-test.arize.com"


def _unique_email() -> str:
    return f"{uuid.uuid4().hex[:10]}@{_UNIQUE_EMAIL_DOMAIN}"


def _unique_name(prefix: str = "ax-cli-test-user") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def created_user(api_key: str) -> dict[str, Any]:
    """Create a test user for the module, clean up after all tests run."""
    name = _unique_name()
    email = _unique_email()
    data = ax_json(
        "users",
        "create",
        "--full-name",
        name,
        "--email",
        email,
        "--role",
        "MEMBER",
        "--invite-mode",
        "NONE",
    )
    assert "id" in data, f"User creation response missing 'id': {data}"
    yield data
    # Cleanup
    ax("users", "delete", "--id", data["id"], "--force")


@pytest.fixture(scope="module")
def test_org_id() -> str:
    """Return the test organization ID from ARIZE_TEST_ORG_ID, skipping if not set."""
    org_id = os.environ.get("ARIZE_TEST_ORG_ID", "")
    if not org_id:
        pytest.skip("ARIZE_TEST_ORG_ID not set")
    return org_id


@pytest.fixture(scope="module")
def test_space_id_for_users() -> str:
    """Return the test space ID from ARIZE_TEST_SPACE_ID, skipping if not set."""
    space_id = os.environ.get("ARIZE_TEST_SPACE_ID", "")
    if not space_id:
        pytest.skip("ARIZE_TEST_SPACE_ID not set")
    return space_id


# ---------------------------------------------------------------------------
# ax users list
# ---------------------------------------------------------------------------


class TestUsersList:
    """ax users list — smoke tests."""

    @pytest.mark.integration
    def test_list_returns_results(self, api_key: str) -> None:
        """``ax users list`` succeeds and returns a users key."""
        data = ax_json("users", "list")
        assert "users" in data

    @pytest.mark.integration
    def test_list_with_limit(self, api_key: str) -> None:
        """``--limit 1`` returns at most one user."""
        data = ax_json("users", "list", "--limit", "1")
        assert "users" in data
        assert len(data["users"]) <= 1

    @pytest.mark.integration
    def test_list_with_email_filter(self, api_key: str) -> None:
        """``--email`` filter returns a valid (possibly empty) response."""
        data = ax_json(
            "users", "list", "--email", "nonexistent-xyz-12345@example.com"
        )
        assert "users" in data
        assert data["users"] == []

    @pytest.mark.integration
    def test_list_newly_created_user_appears(
        self, created_user: dict[str, Any]
    ) -> None:
        """Newly created user should appear in list results."""
        data = ax_json(
            "users", "list", "--email", created_user["email"], "--limit", "10"
        )
        user_ids = [u["id"] for u in data.get("users", [])]
        assert created_user["id"] in user_ids


# ---------------------------------------------------------------------------
# ax users get
# ---------------------------------------------------------------------------


class TestUsersGet:
    """ax users get — smoke tests."""

    @pytest.mark.integration
    def test_get_by_id(self, created_user: dict[str, Any]) -> None:
        """``ax users get <id>`` returns the expected user."""
        data = ax_json("users", "get", created_user["id"])
        assert data.get("id") == created_user["id"]

    @pytest.mark.integration
    def test_get_nonexistent_exits_nonzero(self, api_key: str) -> None:
        """Get with an unknown ID should exit non-zero."""
        result = ax("users", "get", "nonexistent-user-id-xyz-12345")
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# ax users create + update + delete lifecycle
# ---------------------------------------------------------------------------


class TestUsersLifecycle:
    """Full create → update → delete lifecycle tests."""

    @pytest.mark.integration
    def test_create_update_delete(self, api_key: str) -> None:
        """Create a user, update the name, then delete it."""
        name = _unique_name()
        email = _unique_email()

        created = ax_json(
            "users",
            "create",
            "--full-name",
            name,
            "--email",
            email,
            "--role",
            "MEMBER",
            "--invite-mode",
            "NONE",
        )
        user_id = created["id"]

        try:
            assert created["name"] == name

            new_name = _unique_name("updated-user")
            updated = ax_json(
                "users",
                "update",
                user_id,
                "--full-name",
                new_name,
            )
            assert updated["id"] == user_id
            assert updated["name"] == new_name

        finally:
            result = ax("users", "delete", "--id", user_id, "--force")
            assert result.returncode == 0

    @pytest.mark.integration
    def test_create_with_email_link_invite(self, api_key: str) -> None:
        """Create a user with email_link invite mode."""
        name = _unique_name()
        email = _unique_email()

        create_result = ax(
            "users",
            "create",
            "--full-name",
            name,
            "--email",
            email,
            "--role",
            "MEMBER",
            "--invite-mode",
            "EMAIL_LINK",
            "--output",
            "json",
        )
        if create_result.returncode != 0:
            pytest.skip(
                "EMAIL_LINK invite not supported in this environment"
                f" (server error: {create_result.stderr.strip()})"
            )
        import json as _json

        user_id = _json.loads(create_result.stdout)["id"]

        try:
            assert user_id is not None
        finally:
            ax("users", "delete", "--id", user_id, "--force")


# ---------------------------------------------------------------------------
# ax users resend-invitation
# ---------------------------------------------------------------------------


class TestUsersResendInvitation:
    """ax users resend-invitation — smoke test."""

    @pytest.mark.integration
    def test_resend_invitation(self, api_key: str) -> None:
        """Create a user with email_link invite, resend invitation, then delete."""
        name = _unique_name()
        email = _unique_email()

        create_result = ax(
            "users",
            "create",
            "--full-name",
            name,
            "--email",
            email,
            "--role",
            "MEMBER",
            "--invite-mode",
            "EMAIL_LINK",
            "--output",
            "json",
        )
        if create_result.returncode != 0:
            pytest.skip(
                "EMAIL_LINK invite not supported in this environment"
                f" (server error: {create_result.stderr.strip()})"
            )
        import json as _json

        user_id = _json.loads(create_result.stdout)["id"]

        try:
            result = ax("users", "resend-invitation", user_id)
            assert result.returncode == 0
        finally:
            ax("users", "delete", "--id", user_id, "--force")


# ---------------------------------------------------------------------------
# ax organizations add-user / remove-user
# ---------------------------------------------------------------------------


class TestUsersBulkDelete:
    """ax users delete (bulk) — smoke tests."""

    @pytest.mark.integration
    def test_bulk_delete_single_user(self, api_key: str) -> None:
        """Create a user, delete by their ID, verify exit 0."""
        name = _unique_name()
        email = _unique_email()

        created = ax_json(
            "users",
            "create",
            "--full-name",
            name,
            "--email",
            email,
            "--role",
            "MEMBER",
            "--invite-mode",
            "NONE",
        )
        user_id = created["id"]

        result = ax("users", "delete", "--id", user_id, "--force")
        assert result.returncode == 0, f"users delete failed:\n{result.stderr}"

    @pytest.mark.integration
    def test_bulk_delete_missing_user_id_exits_nonzero(
        self, api_key: str
    ) -> None:
        """Delete with no --id or --email should exit non-zero."""
        result = ax("users", "delete", "--force")
        assert result.returncode != 0


class TestOrganizationUserMembership:
    """ax organizations add-user / remove-user — smoke tests."""

    @pytest.mark.integration
    def test_add_and_remove_user(self, api_key: str, test_org_id: str) -> None:
        """Add a user to an org then remove them."""
        name = _unique_name()
        email = _unique_email()

        created = ax_json(
            "users",
            "create",
            "--full-name",
            name,
            "--email",
            email,
            "--role",
            "MEMBER",
            "--invite-mode",
            "NONE",
        )
        user_id = created["id"]

        try:
            membership = ax_json(
                "organizations",
                "add-user",
                test_org_id,
                "--user-id",
                user_id,
                "--role",
                "MEMBER",
            )
            assert membership.get("user_id") == user_id

            result = ax(
                "organizations",
                "remove-user",
                test_org_id,
                "--user-id",
                user_id,
                "--force",
            )
            assert result.returncode == 0
        finally:
            ax("users", "delete", "--id", user_id, "--force")


# ---------------------------------------------------------------------------
# ax spaces add-user / remove-user
# ---------------------------------------------------------------------------


class TestSpaceUserMembership:
    """ax spaces add-user / remove-user — smoke tests."""

    @pytest.mark.integration
    def test_add_and_remove_user(
        self,
        api_key: str,
        test_org_id: str,
        test_space_id_for_users: str,
    ) -> None:
        """Add a user to org and space, then remove from both."""
        name = _unique_name()
        email = _unique_email()

        created = ax_json(
            "users",
            "create",
            "--full-name",
            name,
            "--email",
            email,
            "--role",
            "MEMBER",
            "--invite-mode",
            "NONE",
        )
        user_id = created["id"]

        try:
            # Must be in org before space
            ax_json(
                "organizations",
                "add-user",
                test_org_id,
                "--user-id",
                user_id,
                "--role",
                "MEMBER",
            )

            membership = ax_json(
                "spaces",
                "add-user",
                test_space_id_for_users,
                "--user-id",
                user_id,
                "--role",
                "MEMBER",
            )
            assert membership.get("user_id") == user_id

            result = ax(
                "spaces",
                "remove-user",
                test_space_id_for_users,
                "--user-id",
                user_id,
                "--force",
            )
            assert result.returncode == 0
        finally:
            # Best-effort cleanup
            ax(
                "organizations",
                "remove-user",
                test_org_id,
                "--user-id",
                user_id,
                "--force",
            )
            ax("users", "delete", user_id, "--force")
