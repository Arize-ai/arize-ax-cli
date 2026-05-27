"""Integration tests for ``ax datasets`` commands."""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any, ClassVar

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


class TestDatasetsUpdate:
    """ax datasets update — create a dataset, rename it, then delete."""

    @pytest.mark.integration
    def test_update_name(self, test_space_id: str) -> None:
        """``ax datasets update <id> --name <name>`` renames the dataset."""
        original_name = f"ax-cli-update-{uuid.uuid4().hex[:8]}"
        new_name = f"ax-cli-renamed-{uuid.uuid4().hex[:8]}"
        examples = json.dumps([{"input": "q", "output": "a"}])

        create_result = ax(
            "datasets",
            "create",
            "--name",
            original_name,
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
            update_result = ax(
                "datasets",
                "update",
                dataset_id,
                "--name",
                new_name,
                "--space",
                test_space_id,
                "--output",
                "json",
            )
            assert update_result.returncode == 0, (
                f"Update failed:\n{update_result.stderr}"
            )
            updated: dict[str, Any] = json.loads(update_result.stdout)
            assert updated.get("name") == new_name
            assert updated.get("id") == dataset_id

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


class TestDatasetsAnnotateExamples:
    """ax datasets annotate-examples — annotate examples in a dataset."""

    _ANNOTATIONS: ClassVar[list[dict]] = [
        {"record_id": "ex-1", "values": [{"name": "quality", "score": 0.9}]}
    ]

    def _create_dataset(self, space_id: str, name: str) -> str:
        """Create a minimal dataset and return its ID."""
        examples = json.dumps([{"input": "q", "output": "a"}])
        result = ax(
            "datasets",
            "create",
            "--name",
            name,
            "--space",
            space_id,
            "--json",
            examples,
            "--output",
            "json",
        )
        assert result.returncode == 0, (
            f"Dataset create failed:\n{result.stderr}"
        )
        created: dict[str, Any] = json.loads(result.stdout)
        dataset_id = created.get("id") or created.get("dataset_id")
        assert dataset_id
        return dataset_id

    @pytest.mark.integration
    def test_annotate_examples_with_file(self, test_space_id: str) -> None:
        """``annotate-examples --file`` with a temp file succeeds and exits 0."""
        name = f"ax-cli-ann-file-{uuid.uuid4().hex[:8]}"
        dataset_id = self._create_dataset(test_space_id, name)
        annotations_file: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(self._ANNOTATIONS, f)
                annotations_file = f.name

            result = ax(
                "datasets",
                "annotate-examples",
                dataset_id,
                "--space",
                test_space_id,
                "--file",
                annotations_file,
            )
            assert result.returncode == 0, (
                f"annotate-examples failed:\n{result.stderr}"
            )
        finally:
            ax(
                "datasets",
                "delete",
                dataset_id,
                "--space",
                test_space_id,
                "--force",
            )
            if annotations_file:
                Path(annotations_file).unlink(missing_ok=True)

    @pytest.mark.integration
    def test_annotate_examples_missing_input_fails(
        self, test_space_id: str
    ) -> None:
        """``annotate-examples`` with no --file exits non-zero."""
        result = ax(
            "datasets",
            "annotate-examples",
            "nonexistent-dataset-id",
            "--space",
            test_space_id,
        )
        assert result.returncode != 0
