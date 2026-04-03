"""Integration tests for ``ax datasets`` commands."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest

from tests.integration.conftest import ax, ax_json

pytestmark = pytest.mark.integration


class TestDatasetsList:
    """ax datasets list — smoke tests."""

    @pytest.mark.integration
    def test_list_returns_structure(self, test_space_id: str) -> None:
        """``ax datasets list --space <id>`` returns expected keys."""
        data = ax_json("datasets", "list", "--space", test_space_id)
        assert "datasets" in data

    @pytest.mark.integration
    def test_list_with_limit(self, test_space_id: str) -> None:
        """``--limit 1`` is respected."""
        data = ax_json(
            "datasets", "list", "--space", test_space_id, "--limit", "1"
        )
        assert "datasets" in data
        assert len(data["datasets"]) <= 1


class TestDatasetsGet:
    """ax datasets get — create a dataset, get by ID and name, then delete."""

    @pytest.mark.integration
    def test_get_by_id_and_name(self, test_space_id: str) -> None:
        """``ax datasets get <id>`` and ``get <name>`` both resolve correctly."""
        unique_name = f"ax-cli-get-{uuid.uuid4().hex[:8]}"
        examples = json.dumps([{"input": "q", "output": "a"}])

        create_result = ax(
            "datasets",
            "create",
            "--name",
            unique_name,
            "--space",
            test_space_id,
            "--json",
            examples,
            "--output",
            "json",
        )
        assert create_result.returncode == 0, (
            f"Create failed:\n{create_result.stderr}"
        )
        created: dict[str, Any] = json.loads(create_result.stdout)
        dataset_id = created.get("id") or created.get("dataset_id")
        assert dataset_id

        try:
            by_id = ax_json(
                "datasets", "get", dataset_id, "--space", test_space_id
            )
            assert by_id.get("id") == dataset_id

            by_name = ax_json(
                "datasets", "get", unique_name, "--space", test_space_id
            )
            assert by_name.get("id") == dataset_id
            assert by_name.get("name") == unique_name

        finally:
            ax(
                "datasets",
                "delete",
                dataset_id,
                "--space",
                test_space_id,
                "--force",
            )


class TestDatasetsCRUD:
    """Full dataset lifecycle: create → get → append → delete."""

    @pytest.mark.integration
    def test_create_get_append_delete(self, test_space_id: str) -> None:
        """Create a dataset, verify it, append examples, then delete it."""
        unique_name = f"ax-cli-integration-{uuid.uuid4().hex[:8]}"
        examples = json.dumps([{"question": "What is 2+2?", "answer": "4"}])

        create_result = ax(
            "datasets",
            "create",
            "--name",
            unique_name,
            "--space",
            test_space_id,
            "--json",
            examples,
            "--output",
            "json",
        )
        assert create_result.returncode == 0, (
            f"Create failed:\nstdout: {create_result.stdout}\n"
            f"stderr: {create_result.stderr}"
        )
        created: dict[str, Any] = json.loads(create_result.stdout)
        dataset_id = created.get("id") or created.get("dataset_id")
        assert dataset_id, f"No id in create response: {created}"

        try:
            # Get by name
            by_name = ax_json(
                "datasets", "get", unique_name, "--space", test_space_id
            )
            assert by_name.get("name") == unique_name

            # Get by ID
            by_id = ax_json(
                "datasets", "get", dataset_id, "--space", test_space_id
            )
            assert by_id.get("id") == dataset_id

            # Append examples
            more_examples = json.dumps(
                [{"question": "What is 3+3?", "answer": "6"}]
            )
            append_result = ax(
                "datasets",
                "append",
                dataset_id,
                "--space",
                test_space_id,
                "--json",
                more_examples,
            )
            assert append_result.returncode == 0, (
                f"Append failed:\nstdout: {append_result.stdout}\n"
                f"stderr: {append_result.stderr}"
            )

        finally:
            delete_result = ax(
                "datasets",
                "delete",
                dataset_id,
                "--space",
                test_space_id,
                "--force",
            )
            assert delete_result.returncode == 0, (
                f"Delete failed:\nstdout: {delete_result.stdout}\n"
                f"stderr: {delete_result.stderr}"
            )
