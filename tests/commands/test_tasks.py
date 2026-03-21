"""Tests for task CLI commands."""

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from ax.commands.tasks import _build_evaluators, _parse_experiment_ids, app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(task_id: str = "task-1", name: str = "My Task") -> MagicMock:
    mock = MagicMock()
    mock.id = task_id
    mock.name = name
    mock.model_dump.return_value = {"id": task_id, "name": name}
    return mock


def _make_task_list_response(*tasks: MagicMock) -> MagicMock:
    mock = MagicMock()
    mock.tasks = list(tasks)
    mock.pagination.has_more = False
    mock.model_dump.return_value = {"tasks": [], "pagination": {}}
    return mock


def _make_run(run_id: str = "run-1", status: str = "pending") -> MagicMock:
    mock = MagicMock()
    mock.id = run_id
    mock.status = status
    mock.model_dump.return_value = {"id": run_id, "status": status}
    return mock


def _make_run_list_response(*runs: MagicMock) -> MagicMock:
    mock = MagicMock()
    mock.task_runs = list(runs)
    mock.pagination.has_more = False
    mock.model_dump.return_value = {"task_runs": [], "pagination": {}}
    return mock


# ---------------------------------------------------------------------------
# Command registration
# ---------------------------------------------------------------------------


class TestTaskCommands:
    """Verify task subcommands are registered with the correct names."""

    def test_expected_commands_registered(self) -> None:
        """Check that all expected subcommands are present."""
        names = [cmd.name for cmd in app.registered_commands]
        for expected in (
            "list",
            "get",
            "create",
            "trigger-run",
            "list-runs",
            "get-run",
            "cancel-run",
            "wait-for-run",
        ):
            assert expected in names


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestBuildEvaluators:
    """Tests for the _build_evaluators helper."""

    @pytest.mark.unit
    def test_valid_evaluators(self) -> None:
        """Valid list input is parsed into TasksCreateRequestEvaluatorsInner objects."""
        result = _build_evaluators([{"evaluator_id": "ev-1"}])
        assert len(result) == 1
        assert result[0].evaluator_id == "ev-1"

    @pytest.mark.unit
    def test_not_a_list_raises(self) -> None:
        """Non-list input raises BadParameter."""
        import typer

        with pytest.raises(typer.BadParameter, match="non-empty JSON array"):
            _build_evaluators({"evaluator_id": "ev-1"})  # type: ignore[arg-type]

    @pytest.mark.unit
    def test_empty_list_raises(self) -> None:
        """Empty list raises BadParameter."""
        import typer

        with pytest.raises(typer.BadParameter, match="non-empty JSON array"):
            _build_evaluators([])


class TestParseExperimentIds:
    """Tests for the _parse_experiment_ids helper."""

    @pytest.mark.unit
    def test_none_returns_none(self) -> None:
        """None input returns None."""
        assert _parse_experiment_ids(None) is None

    @pytest.mark.unit
    def test_empty_string_returns_none(self) -> None:
        """Empty string returns None."""
        assert _parse_experiment_ids("") is None

    @pytest.mark.unit
    def test_single_id(self) -> None:
        """Single ID string returns a one-element list."""
        assert _parse_experiment_ids("exp-1") == ["exp-1"]

    @pytest.mark.unit
    def test_multiple_ids(self) -> None:
        """Comma-separated IDs are split into a list."""
        assert _parse_experiment_ids("exp-1,exp-2,exp-3") == [
            "exp-1",
            "exp-2",
            "exp-3",
        ]

    @pytest.mark.unit
    def test_strips_whitespace(self) -> None:
        """Leading/trailing whitespace around each ID is stripped."""
        assert _parse_experiment_ids(" exp-1 , exp-2 ") == ["exp-1", "exp-2"]


# ---------------------------------------------------------------------------
# ax tasks list
# ---------------------------------------------------------------------------


class TestListTasks:
    """Tests for the 'ax tasks list' command."""

    @pytest.mark.unit
    def test_calls_client_tasks_list(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'list' with defaults and verify the SDK call."""
        mock_client.tasks.list.return_value = _make_task_list_response()

        result = cli_runner.invoke(app, ["list"])
        assert result.exit_code == 0
        mock_client.tasks.list.assert_called_once_with(
            space_id=None,
            project_id=None,
            dataset_id=None,
            task_type=None,
            limit=15,
            cursor=None,
        )

    @pytest.mark.unit
    def test_filters_passed_to_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """All filter flags are forwarded to the SDK."""
        mock_client.tasks.list.return_value = _make_task_list_response()

        result = cli_runner.invoke(
            app,
            [
                "list",
                "--space-id",
                "space-1",
                "--project-id",
                "proj-1",
                "--task-type",
                "template_evaluation",
                "--limit",
                "5",
                "--cursor",
                "cursor-abc",
            ],
        )
        assert result.exit_code == 0
        mock_client.tasks.list.assert_called_once_with(
            space_id="space-1",
            project_id="proj-1",
            dataset_id=None,
            task_type="template_evaluation",
            limit=5,
            cursor="cursor-abc",
        )

    @pytest.mark.unit
    def test_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """API failure results in a non-zero exit code."""
        mock_client.tasks.list.side_effect = Exception("connection refused")
        result = cli_runner.invoke(app, ["list"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax tasks get
# ---------------------------------------------------------------------------


class TestGetTask:
    """Tests for the 'ax tasks get' command."""

    @pytest.mark.unit
    def test_calls_client_tasks_get(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'get' and verify the SDK call."""
        mock_client.tasks.get.return_value = _make_task()

        result = cli_runner.invoke(app, ["get", "task-1"])
        assert result.exit_code == 0
        mock_client.tasks.get.assert_called_once_with(task_id="task-1")

    @pytest.mark.unit
    def test_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """API failure results in a non-zero exit code."""
        mock_client.tasks.get.side_effect = Exception("not found")
        result = cli_runner.invoke(app, ["get", "task-1"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax tasks create
# ---------------------------------------------------------------------------


class TestCreateTask:
    """Tests for the 'ax tasks create' command."""

    _EVALUATORS_JSON = '[{"evaluator_id": "ev-1"}]'

    @pytest.mark.unit
    def test_creates_project_task(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Create a project-based task and verify the SDK call arguments."""
        mock_client.tasks.create.return_value = _make_task()

        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "My Task",
                "--task-type",
                "template_evaluation",
                "--evaluators",
                self._EVALUATORS_JSON,
                "--project-id",
                "proj-1",
            ],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.tasks.create.call_args.kwargs
        assert call_kwargs["name"] == "My Task"
        assert call_kwargs["task_type"] == "template_evaluation"
        assert call_kwargs["project_id"] == "proj-1"
        assert call_kwargs["dataset_id"] is None
        assert len(call_kwargs["evaluators"]) == 1
        assert call_kwargs["evaluators"][0].evaluator_id == "ev-1"

    @pytest.mark.unit
    def test_creates_dataset_task(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Create a dataset-based task with experiment IDs."""
        mock_client.tasks.create.return_value = _make_task()

        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "My Task",
                "--task-type",
                "template_evaluation",
                "--evaluators",
                self._EVALUATORS_JSON,
                "--dataset-id",
                "ds-1",
                "--experiment-ids",
                "exp-1,exp-2",
            ],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.tasks.create.call_args.kwargs
        assert call_kwargs["dataset_id"] == "ds-1"
        assert call_kwargs["project_id"] is None
        assert call_kwargs["experiment_ids"] == ["exp-1", "exp-2"]

    @pytest.mark.unit
    def test_requires_project_or_dataset(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """'create' without --project-id or --dataset-id exits non-zero."""
        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "My Task",
                "--task-type",
                "template_evaluation",
                "--evaluators",
                self._EVALUATORS_JSON,
            ],
        )
        assert result.exit_code != 0
        mock_client.tasks.create.assert_not_called()

    @pytest.mark.unit
    def test_project_and_dataset_mutually_exclusive(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Providing both --project-id and --dataset-id exits non-zero."""
        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "My Task",
                "--task-type",
                "template_evaluation",
                "--evaluators",
                self._EVALUATORS_JSON,
                "--project-id",
                "proj-1",
                "--dataset-id",
                "ds-1",
            ],
        )
        assert result.exit_code != 0
        mock_client.tasks.create.assert_not_called()

    @pytest.mark.unit
    def test_optional_flags_forwarded(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Optional flags (sampling-rate, is-continuous, query-filter) are passed through."""
        mock_client.tasks.create.return_value = _make_task()

        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "My Task",
                "--task-type",
                "template_evaluation",
                "--evaluators",
                self._EVALUATORS_JSON,
                "--project-id",
                "proj-1",
                "--sampling-rate",
                "0.5",
                "--is-continuous",
                "--query-filter",
                "score > 0.8",
            ],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.tasks.create.call_args.kwargs
        assert call_kwargs["sampling_rate"] == pytest.approx(0.5)
        assert call_kwargs["is_continuous"] is True
        assert call_kwargs["query_filter"] == "score > 0.8"

    @pytest.mark.unit
    def test_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """API failure results in a non-zero exit code."""
        mock_client.tasks.create.side_effect = Exception("conflict")
        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "My Task",
                "--task-type",
                "template_evaluation",
                "--evaluators",
                self._EVALUATORS_JSON,
                "--project-id",
                "proj-1",
            ],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax tasks trigger-run
# ---------------------------------------------------------------------------


class TestTriggerRun:
    """Tests for the 'ax tasks trigger-run' command."""

    @pytest.mark.unit
    def test_triggers_run(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'trigger-run' with defaults and verify the SDK call."""
        mock_client.tasks.trigger_run.return_value = _make_run()

        result = cli_runner.invoke(app, ["trigger-run", "task-1"])
        assert result.exit_code == 0
        mock_client.tasks.trigger_run.assert_called_once_with(
            task_id="task-1",
            data_start_time=None,
            data_end_time=None,
            max_spans=None,
            override_evaluations=None,
            experiment_ids=None,
        )

    @pytest.mark.unit
    def test_wait_polls_until_terminal(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--wait causes wait_for_run to be called after the run is triggered."""
        run = _make_run(status="pending")
        mock_client.tasks.trigger_run.return_value = run
        completed_run = _make_run(status="completed")
        mock_client.tasks.wait_for_run.return_value = completed_run

        result = cli_runner.invoke(app, ["trigger-run", "task-1", "--wait"])
        assert result.exit_code == 0
        mock_client.tasks.wait_for_run.assert_called_once_with(
            run_id=run.id,
            poll_interval=5.0,
            timeout=600.0,
        )

    @pytest.mark.unit
    def test_experiment_ids_parsed(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Comma-separated --experiment-ids are parsed into a list."""
        mock_client.tasks.trigger_run.return_value = _make_run()

        result = cli_runner.invoke(
            app,
            ["trigger-run", "task-1", "--experiment-ids", "exp-1,exp-2"],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.tasks.trigger_run.call_args.kwargs
        assert call_kwargs["experiment_ids"] == ["exp-1", "exp-2"]

    @pytest.mark.unit
    def test_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """API failure results in a non-zero exit code."""
        mock_client.tasks.trigger_run.side_effect = Exception("server error")
        result = cli_runner.invoke(app, ["trigger-run", "task-1"])
        assert result.exit_code != 0

    @pytest.mark.unit
    def test_wait_timeout_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """TimeoutError during --wait results in a non-zero exit code."""
        mock_client.tasks.trigger_run.return_value = _make_run()
        mock_client.tasks.wait_for_run.side_effect = TimeoutError("timed out")

        result = cli_runner.invoke(app, ["trigger-run", "task-1", "--wait"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax tasks list-runs
# ---------------------------------------------------------------------------


class TestListRuns:
    """Tests for the 'ax tasks list-runs' command."""

    @pytest.mark.unit
    def test_calls_client_tasks_list_runs(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'list-runs' with defaults and verify the SDK call."""
        mock_client.tasks.list_runs.return_value = _make_run_list_response()

        result = cli_runner.invoke(app, ["list-runs", "task-1"])
        assert result.exit_code == 0
        mock_client.tasks.list_runs.assert_called_once_with(
            task_id="task-1",
            status=None,
            limit=15,
            cursor=None,
        )

    @pytest.mark.unit
    def test_status_filter_forwarded(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--status filter is forwarded to the SDK."""
        mock_client.tasks.list_runs.return_value = _make_run_list_response()

        result = cli_runner.invoke(
            app, ["list-runs", "task-1", "--status", "completed"]
        )
        assert result.exit_code == 0
        mock_client.tasks.list_runs.assert_called_once_with(
            task_id="task-1",
            status="completed",
            limit=15,
            cursor=None,
        )

    @pytest.mark.unit
    def test_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """API failure results in a non-zero exit code."""
        mock_client.tasks.list_runs.side_effect = Exception("server error")
        result = cli_runner.invoke(app, ["list-runs", "task-1"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax tasks get-run
# ---------------------------------------------------------------------------


class TestGetRun:
    """Tests for the 'ax tasks get-run' command."""

    @pytest.mark.unit
    def test_calls_client_tasks_get_run(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'get-run' and verify the SDK call."""
        mock_client.tasks.get_run.return_value = _make_run()

        result = cli_runner.invoke(app, ["get-run", "run-1"])
        assert result.exit_code == 0
        mock_client.tasks.get_run.assert_called_once_with(run_id="run-1")

    @pytest.mark.unit
    def test_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """API failure results in a non-zero exit code."""
        mock_client.tasks.get_run.side_effect = Exception("not found")
        result = cli_runner.invoke(app, ["get-run", "run-1"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax tasks cancel-run
# ---------------------------------------------------------------------------


class TestCancelRun:
    """Tests for the 'ax tasks cancel-run' command."""

    @pytest.mark.unit
    def test_prompts_confirmation(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'cancel-run' without --force; confirm 'y' to proceed."""
        mock_client.tasks.cancel_run.return_value = _make_run(
            status="cancelled"
        )

        result = cli_runner.invoke(app, ["cancel-run", "run-1"], input="y\n")
        assert result.exit_code == 0
        mock_client.tasks.cancel_run.assert_called_once_with(run_id="run-1")

    @pytest.mark.unit
    def test_declined_confirmation_does_not_cancel(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Declining the confirmation prompt leaves the run untouched."""
        result = cli_runner.invoke(app, ["cancel-run", "run-1"], input="n\n")
        assert result.exit_code == 0
        mock_client.tasks.cancel_run.assert_not_called()

    @pytest.mark.unit
    def test_force_skips_confirmation(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--force cancels without prompting."""
        mock_client.tasks.cancel_run.return_value = _make_run(
            status="cancelled"
        )

        result = cli_runner.invoke(app, ["cancel-run", "run-1", "--force"])
        assert result.exit_code == 0
        mock_client.tasks.cancel_run.assert_called_once_with(run_id="run-1")

    @pytest.mark.unit
    def test_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """API failure results in a non-zero exit code."""
        mock_client.tasks.cancel_run.side_effect = Exception("already terminal")
        result = cli_runner.invoke(app, ["cancel-run", "run-1", "--force"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax tasks wait-for-run
# ---------------------------------------------------------------------------


class TestWaitForRun:
    """Tests for the 'ax tasks wait-for-run' command."""

    @pytest.mark.unit
    def test_waits_for_run(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'wait-for-run' with defaults and verify the SDK call."""
        mock_client.tasks.wait_for_run.return_value = _make_run(
            status="completed"
        )

        result = cli_runner.invoke(app, ["wait-for-run", "run-1"])
        assert result.exit_code == 0
        mock_client.tasks.wait_for_run.assert_called_once_with(
            run_id="run-1",
            poll_interval=5.0,
            timeout=600.0,
        )

    @pytest.mark.unit
    def test_custom_poll_interval_and_timeout(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Custom --poll-interval and --timeout are forwarded to the SDK."""
        mock_client.tasks.wait_for_run.return_value = _make_run(
            status="completed"
        )

        result = cli_runner.invoke(
            app,
            [
                "wait-for-run",
                "run-1",
                "--poll-interval",
                "10",
                "--timeout",
                "120",
            ],
        )
        assert result.exit_code == 0
        mock_client.tasks.wait_for_run.assert_called_once_with(
            run_id="run-1",
            poll_interval=10.0,
            timeout=120.0,
        )

    @pytest.mark.unit
    def test_timeout_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """TimeoutError results in a non-zero exit code."""
        mock_client.tasks.wait_for_run.side_effect = TimeoutError(
            "timed out after 600s"
        )
        result = cli_runner.invoke(app, ["wait-for-run", "run-1"])
        assert result.exit_code != 0

    @pytest.mark.unit
    def test_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """API failure results in a non-zero exit code."""
        mock_client.tasks.wait_for_run.side_effect = Exception("server error")
        result = cli_runner.invoke(app, ["wait-for-run", "run-1"])
        assert result.exit_code != 0
