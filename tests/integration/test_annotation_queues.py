r"""Integration tests for annotation-queues CLI commands against the real Arize API.

These tests are skipped unless ARIZE_API_KEY and ARIZE_TEST_SPACE are set.
They create real annotation configs and annotation queues, exercise each
command, and clean up after themselves.

Run with:
    ARIZE_API_KEY=<key> \
    ARIZE_TEST_SPACE=<space-id-or-name> \
    pytest tests/integration/test_annotation_queues.py -m integration -v
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Generator

import pytest

from tests.integration.conftest import ax, ax_json

# ---------------------------------------------------------------------------
# Skip unless credentials and required resources are available
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("ARIZE_API_KEY", "")
TEST_SPACE = os.environ.get("ARIZE_TEST_SPACE", "")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not API_KEY,
        reason="ARIZE_API_KEY must be set to run integration tests",
    ),
    pytest.mark.skipif(
        not TEST_SPACE,
        reason="ARIZE_TEST_SPACE must be set to run annotation queue integration tests",
    ),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UNIQUE = uuid.uuid4().hex[:8]
_QUEUE_NAME = f"ax-cli-test-queue-{_UNIQUE}"
_CONFIG_NAME = f"ax-cli-test-config-{_UNIQUE}"


# ---------------------------------------------------------------------------
# Fixtures: create an annotation config, then a queue; delete both after module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def created_annotation_config_id() -> Generator[str, None, None]:
    """Create a freeform annotation config before the module and delete it after."""
    result = ax(
        "annotation-configs",
        "create",
        "freeform",
        "--name",
        _CONFIG_NAME,
        "--space",
        TEST_SPACE,
        "--output",
        "json",
    )
    assert result.returncode == 0, (
        f"annotation-config create failed:\n{result.stderr}"
    )

    data = json.loads(result.stdout)
    config_id = data.get("id")
    assert config_id, (
        f"could not parse annotation config ID from output:\n{result.stdout}"
    )

    yield config_id

    # Cleanup — ignore errors (config may already be deleted)
    ax("annotation-configs", "delete", config_id, "--force")


@pytest.fixture(scope="module")
def created_queue_id(
    created_annotation_config_id: str,
) -> Generator[str, None, None]:
    """Create a test annotation queue before the module and delete it after."""
    result = ax(
        "annotation-queues",
        "create",
        "--name",
        _QUEUE_NAME,
        "--space",
        TEST_SPACE,
        "--annotation-config-id",
        created_annotation_config_id,
        "--annotator-email",
        "testuser@arize.com",
        "--output",
        "json",
    )
    assert result.returncode == 0, f"queue create failed:\n{result.stderr}"

    data = json.loads(result.stdout)
    queue_id = data.get("id")
    assert queue_id, f"could not parse queue ID from output:\n{result.stdout}"

    yield queue_id

    # Cleanup — ignore errors (queue may already be deleted by a test)
    ax("annotation-queues", "delete", queue_id, "--force")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAnnotationQueuesIntegration:
    """End-to-end integration tests for all `ax annotation-queues` commands."""

    def test_list_returns_queues(self) -> None:
        """annotation-queues list should return a list response."""
        data = ax_json("annotation-queues", "list", "--space", TEST_SPACE)
        assert "annotation_queues" in data

    def test_list_with_name_filter(self) -> None:
        """annotation-queues list --name should apply a name substring filter."""
        data = ax_json(
            "annotation-queues",
            "list",
            "--space",
            TEST_SPACE,
            "--name",
            "ax-cli-test",
        )
        assert "annotation_queues" in data

    def test_create_and_get_by_id(self, created_queue_id: str) -> None:
        """annotation-queues get with a real ID should return queue details."""
        data = ax_json("annotation-queues", "get", created_queue_id)
        assert data.get("id") == created_queue_id

    def test_get_by_name(self, created_queue_id: str) -> None:
        """annotation-queues get with a queue name should resolve and return the queue."""
        data = ax_json(
            "annotation-queues", "get", _QUEUE_NAME, "--space", TEST_SPACE
        )
        assert data.get("id") == created_queue_id

    def test_update_instructions(self, created_queue_id: str) -> None:
        """annotation-queues update --instructions should modify the queue."""
        data = ax_json(
            "annotation-queues",
            "update",
            created_queue_id,
            "--instructions",
            "Updated instructions from integration test",
        )
        assert data.get("id") == created_queue_id

    def test_update_name(self, created_queue_id: str) -> None:
        """annotation-queues update --name should rename the queue."""
        new_name = f"{_QUEUE_NAME}-renamed"
        ax_json(
            "annotation-queues",
            "update",
            created_queue_id,
            "--name",
            new_name,
        )

        # Rename back so other tests still find the queue by original name
        ax(
            "annotation-queues",
            "update",
            created_queue_id,
            "--name",
            _QUEUE_NAME,
        )

    def test_list_records_empty(self, created_queue_id: str) -> None:
        """annotation-queues list-records on an empty queue should succeed."""
        data = ax_json("annotation-queues", "list-records", created_queue_id)
        assert "records" in data

    def test_delete_by_name(self, created_annotation_config_id: str) -> None:
        """annotation-queues delete should work when passed a queue name."""
        tmp_name = f"ax-cli-tmp-{uuid.uuid4().hex[:6]}"
        create_result = ax(
            "annotation-queues",
            "create",
            "--name",
            tmp_name,
            "--space",
            TEST_SPACE,
            "--annotation-config-id",
            created_annotation_config_id,
            "--annotator-email",
            "testuser@arize.com",
            "--output",
            "json",
        )
        assert create_result.returncode == 0, (
            f"create failed:\n{create_result.stderr}"
        )

        delete_result = ax(
            "annotation-queues",
            "delete",
            tmp_name,
            "--space",
            TEST_SPACE,
            "--force",
        )
        assert delete_result.returncode == 0, delete_result.stderr

    def test_add_records_invalid_json_exits_nonzero(
        self, created_queue_id: str
    ) -> None:
        """add-records with invalid JSON should exit non-zero."""
        result = ax(
            "annotation-queues",
            "add-records",
            created_queue_id,
            "--space",
            TEST_SPACE,
            "--record-sources",
            "not-valid-json",
        )
        assert result.returncode != 0

    def test_add_records_non_array_json_exits_nonzero(
        self, created_queue_id: str
    ) -> None:
        """add-records with a JSON object (not array) should exit non-zero."""
        result = ax(
            "annotation-queues",
            "add-records",
            created_queue_id,
            "--space",
            TEST_SPACE,
            "--record-sources",
            '{"record_type": "SPAN"}',
        )
        assert result.returncode != 0
