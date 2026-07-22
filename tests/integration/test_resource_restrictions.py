"""Integration tests for ``ax resource-restrictions`` commands.

Required environment variables:
  - ARIZE_API_KEY: valid Arize API key (always required)

Optional:
  - ARIZE_TEST_SPACE: space name or ID used to resolve a test project
    (falls back to the first space returned by ``ax spaces list``).

The lifecycle and list-membership tests require at least one project in the
test space; they skip automatically if none is found.

Run all resource-restriction tests::

    ARIZE_API_KEY=<key> pytest tests/integration/test_resource_restrictions.py \\
        -m integration -v
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.conftest import ax, ax_json

pytestmark = pytest.mark.integration

# A well-formed but (practically) nonexistent Project global ID: base64 of
# "Project:99999999". Used to exercise the real API's error paths.
_NONEXISTENT_PROJECT_ID = "UHJvamVjdDo5OTk5OTk5OQ=="


class TestResourceRestrictionsErrors:
    """Verify commands reach the real API and surface failures as non-zero exits."""

    @pytest.mark.integration
    def test_restrict_nonexistent_resource_fails(self) -> None:
        """``restrict`` against an unknown resource ID exits non-zero."""
        result = ax(
            "resource-restrictions",
            "restrict",
            "--resource-id",
            _NONEXISTENT_PROJECT_ID,
        )
        assert result.returncode != 0

    @pytest.mark.integration
    def test_restrict_malformed_resource_fails(self) -> None:
        """``restrict`` with a malformed resource ID exits non-zero."""
        result = ax(
            "resource-restrictions",
            "restrict",
            "--resource-id",
            "not-a-valid-global-id",
        )
        assert result.returncode != 0

    @pytest.mark.integration
    def test_unrestrict_nonexistent_resource_fails(self) -> None:
        """``unrestrict --force`` against an unknown resource ID exits non-zero."""
        result = ax(
            "resource-restrictions",
            "unrestrict",
            "--resource-id",
            _NONEXISTENT_PROJECT_ID,
            "--force",
        )
        assert result.returncode != 0


class TestListResourceRestrictions:
    """Read-path coverage for ``ax resource-restrictions list``."""

    @pytest.mark.integration
    def test_list_returns_expected_shape(self) -> None:
        """``list`` returns a JSON object with a ``resource_restrictions`` array."""
        data = ax_json("resource-restrictions", "list")
        assert isinstance(data, dict)
        restrictions = data.get("resource_restrictions")
        assert isinstance(restrictions, list)

    @pytest.mark.integration
    def test_list_respects_limit(self) -> None:
        """``--limit 1`` returns at most one restriction."""
        data = ax_json("resource-restrictions", "list", "--limit", "1")
        restrictions = data.get("resource_restrictions") or []
        assert len(restrictions) <= 1

    @pytest.mark.integration
    def test_list_project_filter_only_returns_projects(self) -> None:
        """``--resource-type PROJECT`` never returns a non-PROJECT restriction."""
        data = ax_json(
            "resource-restrictions",
            "list",
            "--resource-type",
            "PROJECT",
            "--limit",
            "50",
        )
        restrictions = data.get("resource_restrictions") or []
        assert all(r.get("resource_type") == "PROJECT" for r in restrictions)


class TestResourceRestrictionsLifecycle:
    """Self-contained restrict -> idempotent restrict -> list -> unrestrict flow.

    Always unrestricts on teardown so the test leaves no lingering restriction
    on the shared test project.
    """

    @pytest.mark.integration
    def test_restrict_list_unrestrict(
        self, first_project: dict[str, Any]
    ) -> None:
        """Restrict a real project, confirm it via list, then unrestrict it."""
        project_id = first_project["id"]

        try:
            # --- restrict ---
            restricted = ax_json(
                "resource-restrictions",
                "restrict",
                "--resource-id",
                project_id,
            )
            assert restricted.get("resource_id") == project_id
            assert restricted.get("resource_type") == "PROJECT"

            # --- restrict again (idempotent, must not error) ---
            again = ax_json(
                "resource-restrictions",
                "restrict",
                "--resource-id",
                project_id,
            )
            assert again.get("resource_id") == project_id

            # --- the restricted project shows up in the list ---
            listing = ax_json(
                "resource-restrictions",
                "list",
                "--resource-type",
                "PROJECT",
                "--limit",
                "100",
            )
            restricted_ids = {
                r.get("resource_id")
                for r in (listing.get("resource_restrictions") or [])
            }
            assert project_id in restricted_ids, (
                f"restricted project {project_id} not present in list: "
                f"{sorted(restricted_ids)}"
            )
        finally:
            cleanup = ax(
                "resource-restrictions",
                "unrestrict",
                "--resource-id",
                project_id,
                "--force",
            )
            assert cleanup.returncode == 0, (
                f"unrestrict cleanup failed:\nstdout: {cleanup.stdout}\n"
                f"stderr: {cleanup.stderr}"
            )
