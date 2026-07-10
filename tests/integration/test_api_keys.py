"""Integration tests for ``ax api-keys`` commands."""

from __future__ import annotations

import json
import uuid

import pytest

from tests.integration.conftest import ax, ax_json

pytestmark = pytest.mark.integration


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
