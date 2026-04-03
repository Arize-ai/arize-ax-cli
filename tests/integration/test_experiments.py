"""Integration tests for ``ax experiments`` commands."""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any

import pytest

from tests.integration.conftest import ax, ax_json

pytestmark = pytest.mark.integration


class TestExperimentsList:
    """ax experiments list — smoke tests."""

    @pytest.mark.integration
    def test_list_returns_structure(self, test_space_id: str) -> None:
        """``ax experiments list --space <id>`` succeeds."""
        data = ax_json("experiments", "list", "--space", test_space_id)
        assert "experiments" in data

    @pytest.mark.integration
    def test_list_with_limit(self, test_space_id: str) -> None:
        """``--limit 1`` is respected."""
        data = ax_json(
            "experiments", "list", "--space", test_space_id, "--limit", "1"
        )
        assert "experiments" in data
        assert len(data["experiments"]) <= 1

    @pytest.mark.integration
    def test_list_filtered_by_dataset(self, test_space_id: str) -> None:
        """``--dataset`` filter scopes results to that dataset's experiments."""
        unique_name = f"ax-cli-exp-list-ds-{uuid.uuid4().hex[:8]}"
        examples = json.dumps([{"input": "q", "output": "a"}])

        create_ds = ax(
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
        assert create_ds.returncode == 0, (
            f"Dataset create failed:\n{create_ds.stderr}"
        )
        dataset_id = json.loads(create_ds.stdout).get("id") or json.loads(
            create_ds.stdout
        ).get("dataset_id")
        assert dataset_id

        try:
            data = ax_json(
                "experiments",
                "list",
                "--space",
                test_space_id,
                "--dataset",
                dataset_id,
            )
            assert "experiments" in data
        finally:
            ax(
                "datasets",
                "delete",
                dataset_id,
                "--space",
                test_space_id,
                "--force",
            )


class TestExperimentsCreateAndDelete:
    """Create an experiment on a dataset, verify it, then clean up both."""

    def _make_runs_file(self, tmp_dir: str) -> str:
        """Write a minimal experiment runs JSON file and return its path."""
        runs = [
            {"example_id": "ex-1", "output": "answer A"},
            {"example_id": "ex-2", "output": "answer B"},
        ]
        path = Path(tmp_dir) / "runs.json"
        path.write_text(json.dumps(runs))
        return str(path)

    @pytest.mark.integration
    def test_create_then_get_then_delete(self, test_space_id: str) -> None:
        """Create dataset + experiment, get by ID and name, delete both."""
        ds_name = f"ax-cli-exp-ds-{uuid.uuid4().hex[:8]}"
        exp_name = f"ax-cli-exp-{uuid.uuid4().hex[:8]}"

        # Create dataset
        examples = json.dumps([{"question": "Q1", "answer": "A1"}])
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
        created_ds: dict[str, Any] = json.loads(create_ds.stdout)
        dataset_id = created_ds.get("id") or created_ds.get("dataset_id")
        assert dataset_id

        experiment_id: str | None = None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                runs_file = self._make_runs_file(tmp)
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
            created_exp: dict[str, Any] = json.loads(create_exp.stdout)
            experiment_id = created_exp.get("id")
            assert experiment_id

            # Get by ID
            by_id = ax_json("experiments", "get", experiment_id)
            assert by_id.get("id") == experiment_id

            # Get by name (requires --dataset)
            by_name = ax_json(
                "experiments", "get", exp_name, "--dataset", dataset_id
            )
            assert by_name.get("id") == experiment_id

            # Appears in list filtered by dataset
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
                ax(
                    "experiments",
                    "delete",
                    experiment_id,
                    "--force",
                )
            ax(
                "datasets",
                "delete",
                dataset_id,
                "--space",
                test_space_id,
                "--force",
            )
