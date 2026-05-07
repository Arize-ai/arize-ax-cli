"""Integration tests for ``ax tasks`` commands."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest

from tests.integration.conftest import ax, ax_json

pytestmark = pytest.mark.integration


class TestTasksList:
    """ax tasks list — smoke tests."""

    @pytest.mark.integration
    def test_list_returns_structure(self) -> None:
        """``ax tasks list`` returns expected keys."""
        data = ax_json("tasks", "list")
        assert "tasks" in data

    @pytest.mark.integration
    def test_list_by_space(self, test_space_id: str) -> None:
        """``ax tasks list --space <id>`` succeeds."""
        data = ax_json("tasks", "list", "--space", test_space_id)
        assert "tasks" in data

    @pytest.mark.integration
    def test_list_with_limit(self, test_space_id: str) -> None:
        """``--limit 1`` is respected."""
        data = ax_json(
            "tasks", "list", "--space", test_space_id, "--limit", "1"
        )
        assert "tasks" in data
        assert len(data["tasks"]) <= 1


class TestTasksLifecycle:
    """Full task lifecycle: create → get → update → delete.

    Requires ``ARIZE_TEST_EVALUATOR_ID`` env var (an evaluator global ID in
    the target space) and at least one project in the test space.
    """

    @pytest.mark.integration
    def test_create_update_delete(
        self,
        test_space_id: str,
        first_project: dict[str, Any],
        test_evaluator_id: str,
    ) -> None:
        """Create a project-based task, update its fields, then delete it."""
        unique_name = f"ax-cli-task-{uuid.uuid4().hex[:8]}"
        evaluators = json.dumps([{"evaluator_id": test_evaluator_id}])

        create_result = ax(
            "tasks",
            "create",
            "--name",
            unique_name,
            "--task-type",
            "template_evaluation",
            "--evaluators",
            evaluators,
            "--project",
            first_project["id"],
            "--space",
            test_space_id,
            "--query-filter",
            "status_code = 'OK'",
            "--output",
            "json",
        )
        assert create_result.returncode == 0, (
            f"Create failed:\nstdout: {create_result.stdout}\n"
            f"stderr: {create_result.stderr}"
        )
        created: dict[str, Any] = json.loads(create_result.stdout)
        task_id = created.get("id")
        assert task_id, f"No id in create response: {created}"

        try:
            got = ax_json("tasks", "get", task_id)
            assert got.get("id") == task_id
            assert got.get("name") == unique_name

            new_name = f"{unique_name}-renamed"
            renamed = ax_json(
                "tasks",
                "update",
                task_id,
                "--name",
                new_name,
            )
            assert renamed.get("name") == new_name

            cleared = ax_json(
                "tasks",
                "update",
                task_id,
                "--query-filter",
                "",
            )
            assert not cleared.get("query_filter")

        finally:
            delete_result = ax(
                "tasks",
                "delete",
                task_id,
                "--space",
                test_space_id,
                "--force",
            )
            assert delete_result.returncode == 0, (
                f"Delete failed:\nstdout: {delete_result.stdout}\n"
                f"stderr: {delete_result.stderr}"
            )
