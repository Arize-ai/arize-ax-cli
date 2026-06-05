r"""Integration tests for annotation-queues CLI commands against the real Arize API.

These tests are skipped unless ARIZE_API_KEY and ARIZE_TEST_SPACE are set.
They create real annotation configs and annotation queues, exercise each
command, and clean up after themselves.

Run with:
    ARIZE_API_KEY=<key> \\
    ARIZE_TEST_SPACE=<space-id-or-name> \\
    pytest tests/commands/test_annotation_queues_integration.py -m integration -v
"""

from __future__ import annotations

import json
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

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UNIQUE = uuid.uuid4().hex[:8]
_QUEUE_NAME = f"ax-cli-test-queue-{_UNIQUE}"
_CONFIG_NAME = f"ax-cli-test-config-{_UNIQUE}"


def _real_config() -> Config:
    """Return a Config backed by the real API key."""
    return Config(auth=AuthConfig(api_key=API_KEY))


def _invoke(*args: str, cli_input: str | None = None) -> object:
    """Invoke a CLI command with a real config and no mocks (except ConfigManager)."""
    config = _real_config()
    with (
        patch(
            "ax.commands.annotation_queues.ConfigManager.load",
            return_value=config,
        ),
        patch(
            "ax.commands.annotation_configs.ConfigManager.load",
            return_value=config,
        ),
    ):
        return runner.invoke(app, list(args), input=cli_input)


# ---------------------------------------------------------------------------
# Fixtures: create an annotation config, then a queue; delete both after module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def created_annotation_config_id() -> Generator[str, None, None]:
    """Create a freeform annotation config before the module and delete it after."""
    result = _invoke(
        "annotation-configs",
        "create",
        "--name",
        _CONFIG_NAME,
        "--space",
        TEST_SPACE,
        "--type",
        "freeform",
        "--output",
        "json",
    )
    assert result.exit_code == 0, (
        f"annotation-config create failed:\n{result.output}"
    )

    data = json.loads(result.output)
    config_id = data.get("id")
    assert config_id, (
        f"could not parse annotation config ID from output:\n{result.output}"
    )

    yield config_id

    # Cleanup — ignore errors (config may already be deleted)
    _invoke("annotation-configs", "delete", config_id, "--force")


@pytest.fixture(scope="module")
def created_queue_id(
    created_annotation_config_id: str,
) -> Generator[str, None, None]:
    """Create a test annotation queue before the module and delete it after."""
    result = _invoke(
        "annotation-queues",
        "create",
        "--name",
        _QUEUE_NAME,
        "--space",
        TEST_SPACE,
        "--annotation-config-id",
        created_annotation_config_id,
        "--output",
        "json",
    )
    assert result.exit_code == 0, f"queue create failed:\n{result.output}"

    data = json.loads(result.output)
    queue_id = data.get("id")
    assert queue_id, f"could not parse queue ID from output:\n{result.output}"

    yield queue_id

    # Cleanup — ignore errors (queue may already be deleted by a test)
    _invoke("annotation-queues", "delete", queue_id, "--force")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAnnotationQueuesIntegration:
    """End-to-end integration tests for all `ax annotation-queues` commands."""

    def test_list_returns_queues(self) -> None:
        """annotation-queues list should return at a list response."""
        result = _invoke(
            "annotation-queues",
            "list",
            "--space",
            TEST_SPACE,
            "--output",
            "json",
        )
        assert result.exit_code == 0, result.output

    def test_list_with_name_filter(self) -> None:
        """annotation-queues list --name should apply a name substring filter."""
        result = _invoke(
            "annotation-queues",
            "list",
            "--space",
            TEST_SPACE,
            "--name",
            "ax-cli-test",
            "--output",
            "json",
        )
        assert result.exit_code == 0, result.output

    def test_create_and_get_by_id(self, created_queue_id: str) -> None:
        """annotation-queues get with a real ID should return queue details."""
        result = _invoke(
            "annotation-queues",
            "get",
            created_queue_id,
            "--output",
            "json",
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data.get("id") == created_queue_id

    def test_get_by_name(self, created_queue_id: str) -> None:
        """annotation-queues get with a queue name should resolve and return the queue."""
        result = _invoke(
            "annotation-queues",
            "get",
            _QUEUE_NAME,
            "--space",
            TEST_SPACE,
            "--output",
            "json",
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data.get("id") == created_queue_id

    def test_update_instructions(self, created_queue_id: str) -> None:
        """annotation-queues update --instructions should modify the queue."""
        result = _invoke(
            "annotation-queues",
            "update",
            created_queue_id,
            "--instructions",
            "Updated instructions from integration test",
            "--output",
            "json",
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data.get("id") == created_queue_id

    def test_update_name(self, created_queue_id: str) -> None:
        """annotation-queues update --name should rename the queue."""
        new_name = f"{_QUEUE_NAME}-renamed"
        result = _invoke(
            "annotation-queues",
            "update",
            created_queue_id,
            "--name",
            new_name,
            "--output",
            "json",
        )
        assert result.exit_code == 0, result.output

        # Rename back so other tests still find the queue by original name
        _invoke(
            "annotation-queues",
            "update",
            created_queue_id,
            "--name",
            _QUEUE_NAME,
        )

    def test_list_records_empty(self, created_queue_id: str) -> None:
        """annotation-queues list-records on an empty queue should succeed."""
        result = _invoke(
            "annotation-queues",
            "list-records",
            created_queue_id,
            "--output",
            "json",
        )
        assert result.exit_code == 0, result.output

    def test_delete_by_name(self, created_annotation_config_id: str) -> None:
        """annotation-queues delete should work when passed a queue name."""
        tmp_name = f"ax-cli-tmp-{uuid.uuid4().hex[:6]}"
        create_result = _invoke(
            "annotation-queues",
            "create",
            "--name",
            tmp_name,
            "--space",
            TEST_SPACE,
            "--annotation-config-id",
            created_annotation_config_id,
            "--output",
            "json",
        )
        assert create_result.exit_code == 0, (
            f"create failed:\n{create_result.output}"
        )

        delete_result = _invoke(
            "annotation-queues",
            "delete",
            tmp_name,
            "--space",
            TEST_SPACE,
            "--force",
        )
        assert delete_result.exit_code == 0, delete_result.output

    def test_add_records_invalid_json_exits_nonzero(
        self, created_queue_id: str
    ) -> None:
        """add-records with invalid JSON should exit non-zero."""
        result = _invoke(
            "annotation-queues",
            "add-records",
            created_queue_id,
            "--space",
            TEST_SPACE,
            "--record-sources",
            "not-valid-json",
        )
        assert result.exit_code != 0

    def test_add_records_non_array_json_exits_nonzero(
        self, created_queue_id: str
    ) -> None:
        """add-records with a JSON object (not array) should exit non-zero."""
        result = _invoke(
            "annotation-queues",
            "add-records",
            created_queue_id,
            "--space",
            TEST_SPACE,
            "--record-sources",
            '{"record_type": "span"}',
        )
        assert result.exit_code != 0
