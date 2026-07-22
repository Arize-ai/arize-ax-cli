"""Integration tests for ``ax api-keys`` commands."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

import pytest

from tests.integration.conftest import ax, ax_json

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Org-scoped fixtures (required for service key tests)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def first_org(api_key: str) -> dict[str, Any]:
    """Return the first org accessible to the authenticated user."""
    result = ax("organizations", "list", "--limit", "1", "--output", "json")
    if result.returncode != 0:
        pytest.fail(f"Cannot list organizations:\n{result.stderr.strip()}")
    orgs = json.loads(result.stdout).get("organizations") or []
    if not orgs:
        pytest.skip("No organizations found — skipping service key tests")
    return orgs[0]


@pytest.fixture(scope="session")
def test_org_id(first_org: dict[str, Any]) -> str:
    """Return the test org ID, preferring ARIZE_TEST_ORG_ID env var."""
    return os.environ.get("ARIZE_TEST_ORG_ID") or first_org["id"]


class TestApiKeysList:
    """ax api-keys list — smoke tests (read-only)."""

    @pytest.mark.integration
    def test_list_returns_structure(self) -> None:
        """``ax api-keys list`` succeeds and returns expected structure."""
        data = ax_json("api-keys", "list")
        assert "api_keys" in data

    @pytest.mark.integration
    def test_list_filter_by_type(self) -> None:
        """``--key-type user`` filter returns only user keys."""
        data = ax_json("api-keys", "list", "--key-type", "user")
        assert "api_keys" in data
        for key in data["api_keys"]:
            assert key.get("key_type") == "user"

    @pytest.mark.integration
    def test_list_filter_active(self) -> None:
        """``--status active`` filter is accepted and returns active keys."""
        data = ax_json("api-keys", "list", "--status", "active")
        assert "api_keys" in data


class TestApiKeysCreateAndRevoke:
    """Create a user API key, verify it appears in list, then revoke it."""

    @pytest.mark.integration
    def test_create_then_list_then_revoke(self) -> None:
        """Full lifecycle: create a user key, find it in list, revoke it."""
        unique_name = f"ax-cli-test-key-{uuid.uuid4().hex[:8]}"

        create_result = ax(
            "api-keys",
            "create",
            "--name",
            unique_name,
            "--key-type",
            "user",
            "--output",
            "json",
        )
        assert create_result.returncode == 0, (
            f"Create failed:\nstdout: {create_result.stdout}\n"
            f"stderr: {create_result.stderr}"
        )
        created = json.loads(create_result.stdout)
        key_id = created.get("id")
        assert key_id, f"No id in create response: {created}"

        try:
            list_data = ax_json("api-keys", "list", "--key-type", "user")
            ids = [k.get("id") for k in list_data.get("api_keys", [])]
            assert key_id in ids, (
                f"Newly created key {key_id!r} not found in list"
            )
        finally:
            revoke_result = ax("api-keys", "revoke", key_id, "--force")
            assert revoke_result.returncode == 0, (
                f"Revoke failed:\nstdout: {revoke_result.stdout}\n"
                f"stderr: {revoke_result.stderr}"
            )

    @pytest.mark.integration
    def test_create_with_description(self) -> None:
        """API key created with --description stores the description."""
        unique_name = f"ax-cli-desc-key-{uuid.uuid4().hex[:8]}"
        description = "Created by ax-cli integration tests"

        create_result = ax(
            "api-keys",
            "create",
            "--name",
            unique_name,
            "--key-type",
            "user",
            "--description",
            description,
            "--output",
            "json",
        )
        assert create_result.returncode == 0, (
            f"Create failed:\nstdout: {create_result.stdout}\n"
            f"stderr: {create_result.stderr}"
        )
        created = json.loads(create_result.stdout)
        key_id = created.get("id")
        assert key_id

        try:
            assert created.get("description") == description
        finally:
            revoke_result = ax("api-keys", "revoke", key_id, "--force")
            assert revoke_result.returncode == 0, (
                f"Revoke failed:\nstdout: {revoke_result.stdout}\n"
                f"stderr: {revoke_result.stderr}"
            )

    @pytest.mark.integration
    def test_revoked_key_no_longer_active(self) -> None:
        """After revocation, the key does not appear in --status active list."""
        unique_name = f"ax-cli-revoke-key-{uuid.uuid4().hex[:8]}"

        create_result = ax(
            "api-keys",
            "create",
            "--name",
            unique_name,
            "--key-type",
            "user",
            "--output",
            "json",
        )
        assert create_result.returncode == 0, (
            f"Create failed:\nstdout: {create_result.stdout}\n"
            f"stderr: {create_result.stderr}"
        )
        key_id = json.loads(create_result.stdout).get("id")
        assert key_id

        try:
            revoke_result = ax("api-keys", "revoke", key_id, "--force")
            assert revoke_result.returncode == 0, (
                f"Revoke failed:\nstdout: {revoke_result.stdout}\n"
                f"stderr: {revoke_result.stderr}"
            )
            key_id = None  # Revoked — skip cleanup in finally

            active_data = ax_json("api-keys", "list", "--status", "active")
            active_ids = [k.get("id") for k in active_data.get("api_keys", [])]
            assert key_id not in active_ids, (
                "Revoked key still appears in active list"
            )
        finally:
            if key_id:
                ax("api-keys", "revoke", key_id, "--force")


# ---------------------------------------------------------------------------
# ax api-keys create-service-key (lifecycle)
# ---------------------------------------------------------------------------


class TestCreateServiceKey:
    """create-service-key → list → revoke lifecycle against the real API.

    Unit tests mock the SDK client, so only an integration test proves the
    ``--assignments`` JSON is serialised correctly and the server accepts it.
    Requires ARIZE_API_KEY with permission to create service keys and an
    accessible org. Set ARIZE_TEST_ORG_ID to pin the org; otherwise the first
    org returned by ``ax organizations list`` is used.
    """

    @staticmethod
    def _create_service_key(
        name: str,
        org_id: str,
        space_id: str,
        extra_args: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run create-service-key with inline --assignments and return payload."""
        assignments = json.dumps(
            [{"org_id": org_id, "spaces": [{"space": space_id}]}]
        )
        result = ax(
            "api-keys",
            "create-service-key",
            "--name",
            name,
            "--assignments",
            assignments,
            "--output",
            "json",
            *(extra_args or []),
        )
        assert result.returncode == 0, (
            f"create-service-key failed:\nstdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        return json.loads(result.stdout)

    def test_create_returns_key_id_and_value(
        self, test_org_id: str, test_space_id: str
    ) -> None:
        """Happy path: response contains ``id`` and a raw key ``key`` field."""
        name = f"ax-cli-svc-{uuid.uuid4().hex[:8]}"
        payload = self._create_service_key(name, test_org_id, test_space_id)
        key_id = payload.get("id", "")
        try:
            assert key_id, f"Expected 'id' in response, got: {payload}"
            assert payload.get("key"), "Expected raw key value in response"
        finally:
            if key_id:
                ax("api-keys", "revoke", key_id, "--force")

    def test_created_service_key_appears_in_list(
        self, test_org_id: str, test_space_id: str
    ) -> None:
        """A newly created service key is visible in ``ax api-keys list``."""
        name = f"ax-cli-svc-list-{uuid.uuid4().hex[:8]}"
        payload = self._create_service_key(name, test_org_id, test_space_id)
        key_id = payload.get("id", "")
        assert key_id
        try:
            list_data = ax_json(
                "api-keys", "list", "--key-type", "SERVICE", "--limit", "50"
            )
            ids = [k.get("id") for k in list_data.get("api_keys", [])]
            assert key_id in ids, (
                f"Newly created service key {key_id!r} not found in list"
            )
        finally:
            ax("api-keys", "revoke", key_id, "--force")

    def test_create_from_assignments_file(
        self, test_org_id: str, test_space_id: str, tmp_path: Any
    ) -> None:
        """``--assignments path/to/file.json`` reads bindings from disk."""
        name = f"ax-cli-svc-file-{uuid.uuid4().hex[:8]}"
        assignments_file = tmp_path / "assignments.json"
        assignments_file.write_text(
            json.dumps(
                [{"org_id": test_org_id, "spaces": [{"space": test_space_id}]}]
            )
        )
        result = ax(
            "api-keys",
            "create-service-key",
            "--name",
            name,
            "--assignments",
            str(assignments_file),
            "--output",
            "json",
        )
        assert result.returncode == 0, (
            f"create-service-key from file failed:\n{result.stderr}"
        )
        key_id = json.loads(result.stdout).get("id", "")
        assert key_id
        ax("api-keys", "revoke", key_id, "--force")

    def test_create_with_org_role(
        self, test_org_id: str, test_space_id: str
    ) -> None:
        """Org-level role in ``--assignments`` is accepted by the server."""
        name = f"ax-cli-svc-orgrole-{uuid.uuid4().hex[:8]}"
        assignments = json.dumps(
            [
                {
                    "org_id": test_org_id,
                    "role": "READ_ONLY",
                    "spaces": [{"space": test_space_id, "role": "MEMBER"}],
                }
            ]
        )
        result = ax(
            "api-keys",
            "create-service-key",
            "--name",
            name,
            "--assignments",
            assignments,
            "--output",
            "json",
        )
        assert result.returncode == 0, (
            f"create-service-key with org role failed:\n{result.stderr}"
        )
        key_id = json.loads(result.stdout).get("id", "")
        assert key_id
        ax("api-keys", "revoke", key_id, "--force")

    def test_create_displays_save_warning(
        self, test_org_id: str, test_space_id: str
    ) -> None:
        """The 'Save this API key now' warning must appear in stderr."""
        name = f"ax-cli-svc-warn-{uuid.uuid4().hex[:8]}"
        assignments = json.dumps(
            [{"org_id": test_org_id, "spaces": [{"space": test_space_id}]}]
        )
        result = ax(
            "api-keys",
            "create-service-key",
            "--name",
            name,
            "--assignments",
            assignments,
            "--output",
            "json",
        )
        assert result.returncode == 0, result.stderr
        combined = result.stdout + result.stderr
        assert "Save this API key now" in combined
        key_id = json.loads(result.stdout).get("id", "")
        if key_id:
            ax("api-keys", "revoke", key_id, "--force")

    def test_create_missing_assignments_exits_nonzero(self) -> None:
        """``create-service-key`` without ``--assignments`` exits non-zero."""
        result = ax("api-keys", "create-service-key", "--name", "no-bindings")
        assert result.returncode != 0

    def test_create_invalid_json_exits_nonzero(self) -> None:
        """Malformed JSON in ``--assignments`` exits non-zero."""
        result = ax(
            "api-keys",
            "create-service-key",
            "--name",
            "bad-json",
            "--assignments",
            "{not valid json",
        )
        assert result.returncode != 0

    def test_create_empty_assignments_array_exits_nonzero(self) -> None:
        """An empty ``--assignments`` array exits non-zero."""
        result = ax(
            "api-keys",
            "create-service-key",
            "--name",
            "empty",
            "--assignments",
            "[]",
        )
        assert result.returncode != 0
