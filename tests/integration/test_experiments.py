"""Integration tests for ``ax experiments`` commands."""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any, ClassVar

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


class TestExperimentsAnnotateRuns:
    """ax experiments annotate-runs — annotate runs in an experiment."""

    _ANNOTATIONS: ClassVar[list[dict]] = [
        {"record_id": "run-1", "values": [{"name": "quality", "score": 0.9}]}
    ]

    def _setup_dataset_and_experiment(
        self, space_id: str, tmp_dir: str
    ) -> tuple[str, str]:
        """Create a dataset and experiment, returning (dataset_id, experiment_id)."""
        ds_name = f"ax-cli-ann-exp-ds-{uuid.uuid4().hex[:8]}"
        exp_name = f"ax-cli-ann-exp-{uuid.uuid4().hex[:8]}"
        examples = json.dumps([{"question": "Q1", "answer": "A1"}])

        create_ds = ax(
            "datasets",
            "create",
            "--name",
            ds_name,
            "--space",
            space_id,
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

        runs = [{"example_id": "ex-1", "output": "answer"}]
        runs_file = Path(tmp_dir) / "runs.json"
        runs_file.write_text(json.dumps(runs))

        create_exp = ax(
            "experiments",
            "create",
            "--name",
            exp_name,
            "--dataset",
            dataset_id,
            "--file",
            str(runs_file),
            "--output",
            "json",
        )
        assert create_exp.returncode == 0, (
            f"Experiment create failed:\n{create_exp.stderr}"
        )
        experiment_id = json.loads(create_exp.stdout).get("id")
        assert experiment_id
        return dataset_id, experiment_id

    @pytest.mark.integration
    def test_annotate_runs_with_file(self, test_space_id: str) -> None:
        """``annotate-runs --file`` reads annotations from disk."""
        with tempfile.TemporaryDirectory() as tmp:
            dataset_id, experiment_id = self._setup_dataset_and_experiment(
                test_space_id, tmp
            )
        annotations_file: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(self._ANNOTATIONS, f)
                annotations_file = f.name

            result = ax(
                "experiments",
                "annotate-runs",
                experiment_id,
                "--file",
                annotations_file,
            )
            assert result.returncode == 0, (
                f"annotate-runs --file failed:\n{result.stderr}"
            )
        finally:
            ax("experiments", "delete", experiment_id, "--force")
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
    def test_annotate_runs_missing_input_fails(self) -> None:
        """``annotate-runs`` with no --file exits non-zero."""
        result = ax(
            "experiments",
            "annotate-runs",
            "nonexistent-experiment-id",
        )
        assert result.returncode != 0


class TestExperimentsListRuns:
    """ax experiments list-runs — smoke tests."""

    def _make_runs_file(self, tmp_dir: str) -> str:
        """Write a minimal experiment runs JSON file and return its path."""
        runs = [{"example_id": "ex-1", "output": "answer A"}]
        path = Path(tmp_dir) / "runs.json"
        path.write_text(json.dumps(runs))
        return str(path)

    @pytest.mark.integration
    def test_list_runs_nonexistent_exits_nonzero(self) -> None:
        """``ax experiments list-runs`` with a bogus ID should exit non-zero."""
        result = ax("experiments", "list-runs", "nonexistent-exp-id-xyz-12345")
        assert result.returncode != 0

    @pytest.mark.integration
    def test_list_runs_on_created_experiment(self, test_space_id: str) -> None:
        """Create a dataset + experiment, list-runs, verify structure, then clean up."""
        ds_name = f"ax-cli-lr-ds-{uuid.uuid4().hex[:8]}"
        exp_name = f"ax-cli-lr-exp-{uuid.uuid4().hex[:8]}"
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
        dataset_id = json.loads(create_ds.stdout).get("id") or json.loads(
            create_ds.stdout
        ).get("dataset_id")
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
            experiment_id = json.loads(create_exp.stdout).get("id")
            assert experiment_id

            data = ax_json(
                "experiments",
                "list-runs",
                experiment_id,
                "--output",
                "json",
            )
            assert "experiment_runs" in data

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
