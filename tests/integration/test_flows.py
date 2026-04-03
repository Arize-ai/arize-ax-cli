"""Integration tests for cross-resource CLI flows.

These tests exercise workflows that span multiple resources to verify
end-to-end behaviour.  They are skipped automatically when
``ARIZE_API_KEY`` is not set (see conftest.py).

Run::

    ARIZE_API_KEY=<key> pytest tests/integration/ -m integration -v
"""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any

import pytest

from tests.integration.conftest import ax, ax_json

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_runs_file(tmp_dir: str, rows: list[dict]) -> str:
    """Write experiment runs as JSON to a temp file, return its path."""
    path = Path(tmp_dir) / "runs.json"
    path.write_text(json.dumps(rows))
    return str(path)


# ---------------------------------------------------------------------------
# Dataset → verify visibility flow
# ---------------------------------------------------------------------------


class TestDatasetVisibility:
    """Dataset is immediately reachable by ID and name after creation."""

    @pytest.mark.integration
    def test_dataset_visible_after_create(self, test_space_id: str) -> None:
        """A newly created dataset is retrievable by name, ID, and list."""
        unique_name = f"ax-cli-flow-{uuid.uuid4().hex[:8]}"
        examples = json.dumps([{"input": "hello", "output": "world"}])

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
            by_name = ax_json(
                "datasets", "get", unique_name, "--space", test_space_id
            )
            assert by_name.get("name") == unique_name

            by_id = ax_json(
                "datasets", "get", dataset_id, "--space", test_space_id
            )
            assert by_id.get("id") == dataset_id

            list_data = ax_json("datasets", "list", "--space", test_space_id)
            ids = [d.get("id") for d in list_data.get("datasets", [])]
            assert dataset_id in ids

        finally:
            ax(
                "datasets",
                "delete",
                dataset_id,
                "--space",
                test_space_id,
                "--force",
            )


# ---------------------------------------------------------------------------
# Dataset → append flow
# ---------------------------------------------------------------------------


class TestDatasetAppend:
    """Create a dataset and append examples to it."""

    @pytest.mark.integration
    def test_append_examples(self, test_space_id: str) -> None:
        """Append succeeds and the dataset remains retrievable afterward."""
        unique_name = f"ax-cli-append-{uuid.uuid4().hex[:8]}"
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
        assert create_result.returncode == 0
        dataset_id = json.loads(create_result.stdout).get("id")
        assert dataset_id

        try:
            more = json.dumps([{"question": "What is 3+3?", "answer": "6"}])
            append_result = ax(
                "datasets",
                "append",
                dataset_id,
                "--space",
                test_space_id,
                "--json",
                more,
            )
            assert append_result.returncode == 0, (
                f"Append failed:\n{append_result.stderr}"
            )

            # Dataset is still reachable after append
            data = ax_json(
                "datasets", "get", dataset_id, "--space", test_space_id
            )
            assert data.get("id") == dataset_id

        finally:
            ax(
                "datasets",
                "delete",
                dataset_id,
                "--space",
                test_space_id,
                "--force",
            )


# ---------------------------------------------------------------------------
# Dataset → experiment flow
# ---------------------------------------------------------------------------


class TestDatasetExperimentFlow:
    """Create a dataset, attach an experiment, verify the linkage, clean up."""

    @pytest.mark.integration
    def test_create_dataset_then_experiment(self, test_space_id: str) -> None:
        """Dataset + experiment: create, get by name/ID, list by dataset, delete."""
        ds_name = f"ax-cli-ds-{uuid.uuid4().hex[:8]}"
        exp_name = f"ax-cli-exp-{uuid.uuid4().hex[:8]}"
        examples = json.dumps([{"question": "Q", "answer": "A"}])

        # Create dataset
        create_ds = ax(
            "datasets",
            "create",
            "--name",
            ds_name,
            "--space",
            test_space_id,
            "--json",
            examples,
            "--output",
            "json",
        )
        assert create_ds.returncode == 0, (
            f"Dataset create failed:\n{create_ds.stderr}"
        )
        dataset_id = json.loads(create_ds.stdout).get("id") or json.loads(
            create_ds.stdout
        ).get("dataset_id")
        assert dataset_id

        experiment_id: str | None = None
        try:
            # Create experiment on that dataset
            rows = [
                {"example_id": "ex-1", "output": "out-1"},
                {"example_id": "ex-2", "output": "out-2"},
            ]
            with tempfile.TemporaryDirectory() as tmp:
                runs_file = _write_runs_file(tmp, rows)
                create_exp = ax(
                    "experiments",
                    "create",
                    "--name",
                    exp_name,
                    "--dataset",
                    dataset_id,
                    "--file",
                    runs_file,
                    "--output",
                    "json",
                )
            assert create_exp.returncode == 0, (
                f"Experiment create failed:\n{create_exp.stderr}"
            )
            experiment_id = json.loads(create_exp.stdout).get("id")
            assert experiment_id

            # Get experiment by ID
            by_id = ax_json("experiments", "get", experiment_id)
            assert by_id.get("id") == experiment_id

            # Get experiment by name (requires --dataset)
            by_name = ax_json(
                "experiments", "get", exp_name, "--dataset", dataset_id
            )
            assert by_name.get("id") == experiment_id

            # Experiment appears in list scoped to its dataset
            list_data = ax_json(
                "experiments",
                "list",
                "--space",
                test_space_id,
                "--dataset",
                dataset_id,
            )
            exp_ids = [e.get("id") for e in list_data.get("experiments", [])]
            assert experiment_id in exp_ids

        finally:
            if experiment_id:
                ax("experiments", "delete", experiment_id, "--force")
            ax(
                "datasets",
                "delete",
                dataset_id,
                "--space",
                test_space_id,
                "--force",
            )


# ---------------------------------------------------------------------------
# API key create → list → delete flow
# ---------------------------------------------------------------------------


class TestApiKeyFlow:
    """Create a user API key, verify it's visible, delete it."""

    @pytest.mark.integration
    def test_create_list_delete(self) -> None:
        """User API key appears in list after creation and disappears after deletion."""
        unique_name = f"ax-cli-key-{uuid.uuid4().hex[:8]}"

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
            f"Create failed:\n{create_result.stderr}"
        )
        key_id = json.loads(create_result.stdout).get("id")
        assert key_id

        try:
            list_data = ax_json("api-keys", "list", "--key-type", "user")
            ids = [k.get("id") for k in list_data.get("api_keys", [])]
            assert key_id in ids

        finally:
            delete_result = ax("api-keys", "delete", key_id, "--force")
            assert delete_result.returncode == 0

        # Confirm it no longer appears as active
        active_data = ax_json("api-keys", "list", "--status", "active")
        active_ids = [k.get("id") for k in active_data.get("api_keys", [])]
        assert key_id not in active_ids
