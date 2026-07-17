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
    def test_create_then_get_then_delete(
        self, test_space_id: str, created_dataset_id: str
    ) -> None:
        """Create an experiment, get by ID and name, then delete it."""
        exp_name = f"ax-cli-exp-{uuid.uuid4().hex[:8]}"
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
                    created_dataset_id,
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
                "experiments", "get", exp_name, "--dataset", created_dataset_id
            )
            assert by_name.get("id") == experiment_id

            # Appears in list filtered by dataset
            list_data = ax_json(
                "experiments",
                "list",
                "--space",
                test_space_id,
                "--dataset",
                created_dataset_id,
            )
            exp_ids = [e.get("id") for e in list_data.get("experiments", [])]
            assert experiment_id in exp_ids

        finally:
            if experiment_id:
                ax("experiments", "delete", experiment_id, "--force")


class TestExperimentsRun:
    """ax experiments run — run a task against a dataset and upload results."""

    _TASK_SOURCE: ClassVar[str] = (
        "def task(dataset_row):\n"
        "    return str(dataset_row.get('question', 'no question'))\n"
    )

    @pytest.mark.integration
    def test_dry_run_succeeds_without_uploading(
        self, test_space_id: str, created_dataset_id: str
    ) -> None:
        """``--dry-run`` processes examples locally and exits 0."""
        with tempfile.TemporaryDirectory() as tmp:
            task_path = Path(tmp) / "task.py"
            task_path.write_text(self._TASK_SOURCE)

            result = ax(
                "experiments",
                "run",
                "--dataset",
                created_dataset_id,
                "--space",
                test_space_id,
                "--name",
                f"ax-cli-run-dry-{uuid.uuid4().hex[:8]}",
                "--task",
                str(task_path),
                "--dry-run",
            )
        assert result.returncode == 0, (
            f"experiments run --dry-run failed:\n{result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert "dry run" in combined.lower(), (
            f"Expected 'dry run' in output, got:\n{combined}"
        )

    @pytest.mark.integration
    def test_run_creates_experiment(
        self, test_space_id: str, created_dataset_id: str
    ) -> None:
        """``ax experiments run`` runs a task and uploads a real experiment."""
        exp_name = f"ax-cli-run-exp-{uuid.uuid4().hex[:8]}"
        experiment_id: str | None = None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                task_path = Path(tmp) / "task.py"
                task_path.write_text(self._TASK_SOURCE)

                result = ax(
                    "experiments",
                    "run",
                    "--dataset",
                    created_dataset_id,
                    "--space",
                    test_space_id,
                    "--name",
                    exp_name,
                    "--task",
                    str(task_path),
                )
            assert result.returncode == 0, (
                f"experiments run failed:\n{result.stderr}"
            )

            # Find the created experiment by listing filtered by dataset
            list_data = ax_json(
                "experiments",
                "list",
                "--space",
                test_space_id,
                "--dataset",
                created_dataset_id,
            )
            experiments = list_data.get("experiments", [])
            matches = [e for e in experiments if e.get("name") == exp_name]
            assert matches, (
                f"Created experiment '{exp_name}' not found in list: {experiments}"
            )
            experiment_id = matches[0]["id"]
        finally:
            if experiment_id:
                ax("experiments", "delete", experiment_id, "--force")

    @pytest.mark.integration
    def test_run_missing_task_file_fails(self) -> None:
        """``--task`` pointing to a non-existent file exits non-zero."""
        result = ax(
            "experiments",
            "run",
            "--dataset",
            "any-dataset-id",
            "--name",
            "test-exp",
            "--task",
            "/nonexistent/path/task.py",
        )
        assert result.returncode != 0


class TestExperimentsAnnotateRuns:
    """ax experiments annotate-runs — annotate runs in an experiment."""

    _ANNOTATIONS: ClassVar[list[dict]] = [
        {"record_id": "run-1", "values": [{"name": "quality", "score": 0.9}]}
    ]

    @pytest.mark.integration
    def test_annotate_runs_with_file(
        self, test_space_id: str, created_dataset_id: str
    ) -> None:
        """``annotate-runs --file`` reads annotations from disk."""
        ann_config_name = f"ax-cli-ann-cfg-{uuid.uuid4().hex[:8]}"
        exp_name = f"ax-cli-ann-exp-{uuid.uuid4().hex[:8]}"
        experiment_id: str | None = None
        annotations_file: str | None = None
        ann_config_created = False
        try:
            # Create the annotation config required by annotate-runs
            create_cfg = ax(
                "annotation-configs",
                "create",
                "--name",
                ann_config_name,
                "--space",
                test_space_id,
                "--type",
                "CONTINUOUS",
                "--min-score",
                "0",
                "--max-score",
                "1",
                "--output",
                "json",
            )
            assert create_cfg.returncode == 0, (
                f"Annotation config create failed:\n{create_cfg.stderr}"
            )
            ann_config_created = True

            with tempfile.TemporaryDirectory() as tmp:
                runs_file = Path(tmp) / "runs.json"
                runs_file.write_text(
                    json.dumps([{"example_id": "ex-1", "output": "answer"}])
                )
                create_exp = ax(
                    "experiments",
                    "create",
                    "--name",
                    exp_name,
                    "--dataset",
                    created_dataset_id,
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

            # Get a real run ID to annotate
            runs_data = ax_json(
                "experiments", "list-runs", experiment_id, "--output", "json"
            )
            runs = runs_data.get("experiment_runs", [])
            assert runs, f"No runs found in experiment {experiment_id}"
            run_id = runs[0]["id"]

            annotations = [
                {
                    "record_id": run_id,
                    "values": [{"name": ann_config_name, "score": 0.9}],
                }
            ]
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(annotations, f)
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
            if experiment_id:
                ax("experiments", "delete", experiment_id, "--force")
            if annotations_file:
                Path(annotations_file).unlink(missing_ok=True)
            if ann_config_created:
                ax(
                    "annotation-configs",
                    "delete",
                    ann_config_name,
                    "--space",
                    test_space_id,
                    "--force",
                )

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
    def test_list_runs_on_created_experiment(
        self, created_dataset_id: str
    ) -> None:
        """Create an experiment, list-runs, verify structure, then clean up."""
        exp_name = f"ax-cli-lr-exp-{uuid.uuid4().hex[:8]}"
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
                    created_dataset_id,
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
