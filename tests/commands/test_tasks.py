"""Tests for task CLI commands."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ax.commands.tasks import (
    _build_evaluators,
    _build_run_configuration,
    _parse_comma_separated_ids,
    app,
)

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
    mock.model_dump.return_value = {
        "tasks": [t.model_dump() for t in tasks],
        "pagination": {},
    }
    return mock


def _make_run(run_id: str = "run-1", status: str = "PENDING") -> MagicMock:
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


_RUN_CONFIG_JSON = (
    '{"experiment_type": "LLM_GENERATION", '
    '"ai_integration_id": "int-1", '
    '"model_name": "gpt-4o", '
    '"input_variable_format": "MUSTACHE", '
    '"messages": [{"role": "USER", "content": "{{input}}"}]}'
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
            "create-evaluation",
            "create-run-experiment",
            "update",
            "delete",
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
        """Valid list input is parsed into TaskEvaluatorInput objects."""
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


class TestBuildRunConfiguration:
    """Tests for the _build_run_configuration helper."""

    @pytest.mark.unit
    def test_array_raises(self) -> None:
        """Array input raises BadParameter."""
        import typer

        with pytest.raises(typer.BadParameter, match="JSON object"):
            _build_run_configuration([])  # type: ignore[arg-type]

    @pytest.mark.unit
    def test_valid_dict_parses_to_run_configuration(self) -> None:
        """Valid dict input is parsed and the RunConfiguration result is returned."""
        mock_rc = MagicMock()
        with patch(
            "ax.commands.tasks.RunConfiguration.from_dict", return_value=mock_rc
        ):
            result = _build_run_configuration(
                {"experiment_type": "LLM_GENERATION"}
            )
        assert result is mock_rc

    @pytest.mark.unit
    def test_from_dict_exception_wraps_as_bad_parameter(self) -> None:
        """Exception raised by RunConfiguration.from_dict is wrapped as BadParameter."""
        import typer

        with (
            patch(
                "ax.commands.tasks.RunConfiguration.from_dict",
                side_effect=ValueError("unknown discriminator"),
            ),
            pytest.raises(
                typer.BadParameter, match="Failed to parse run configuration"
            ),
        ):
            _build_run_configuration({"experiment_type": "bad"})

    @pytest.mark.unit
    def test_from_dict_returns_none_wraps_as_bad_parameter(self) -> None:
        """None returned by RunConfiguration.from_dict is wrapped as BadParameter."""
        import typer

        with (
            patch(
                "ax.commands.tasks.RunConfiguration.from_dict",
                return_value=None,
            ),
            pytest.raises(typer.BadParameter, match="result was None"),
        ):
            _build_run_configuration({"experiment_type": "bad"})


class TestParseExperimentIds:
    """Tests for the _parse_comma_separated_ids helper."""

    @pytest.mark.unit
    def test_none_returns_none(self) -> None:
        """None input returns None."""
        assert _parse_comma_separated_ids(None) is None

    @pytest.mark.unit
    def test_empty_string_returns_none(self) -> None:
        """Empty string returns None."""
        assert _parse_comma_separated_ids("") is None

    @pytest.mark.unit
    def test_single_id(self) -> None:
        """Single ID string returns a one-element list."""
        assert _parse_comma_separated_ids("exp-1") == ["exp-1"]

    @pytest.mark.unit
    def test_multiple_ids(self) -> None:
        """Comma-separated IDs are split into a list."""
        assert _parse_comma_separated_ids("exp-1,exp-2,exp-3") == [
            "exp-1",
            "exp-2",
            "exp-3",
        ]

    @pytest.mark.unit
    def test_strips_whitespace(self) -> None:
        """Leading/trailing whitespace around each ID is stripped."""
        assert _parse_comma_separated_ids(" exp-1 , exp-2 ") == [
            "exp-1",
            "exp-2",
        ]


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
            name=None,
            space=None,
            project=None,
            dataset=None,
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
                "--space",
                "space-1",
                "--project",
                "UHJvamVjdDox",
                "--task-type",
                "TEMPLATE_EVALUATION",
                "--limit",
                "5",
                "--cursor",
                "cursor-abc",
            ],
        )
        assert result.exit_code == 0
        mock_client.tasks.list.assert_called_once_with(
            name=None,
            space="space-1",
            project="UHJvamVjdDox",
            dataset=None,
            task_type="TEMPLATE_EVALUATION",
            limit=5,
            cursor="cursor-abc",
        )

    @pytest.mark.unit
    def test_project_passed_to_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--project is forwarded to tasks.list as 'project' (SDK handles name-or-ID)."""
        mock_client.tasks.list.return_value = _make_task_list_response()

        result = cli_runner.invoke(
            app,
            ["list", "--space", "space-1", "--project", "UHJvamVjdDox"],
        )
        assert result.exit_code == 0
        mock_client.tasks.list.assert_called_once_with(
            name=None,
            space="space-1",
            project="UHJvamVjdDox",
            dataset=None,
            task_type=None,
            limit=15,
            cursor=None,
        )

    @pytest.mark.unit
    def test_name_filter_forwarded(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--name filter is forwarded to the SDK."""
        mock_client.tasks.list.return_value = _make_task_list_response()

        result = cli_runner.invoke(app, ["list", "--name", "nightly"])
        assert result.exit_code == 0
        mock_client.tasks.list.assert_called_once_with(
            name="nightly",
            space=None,
            project=None,
            dataset=None,
            task_type=None,
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
        mock_client.tasks.get.assert_called_once_with(task="task-1")

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
    """Tests for the 'ax tasks create' command (dispatched)."""

    _EVALUATORS_JSON = '[{"evaluator_id": "ev-1"}]'

    @pytest.mark.unit
    def test_creates_project_task(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Create a project-based evaluation task and verify the SDK call."""
        mock_client.tasks.create_evaluation_task.return_value = _make_task()

        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "My Task",
                "--task-type",
                "TEMPLATE_EVALUATION",
                "--evaluators",
                self._EVALUATORS_JSON,
                "--project",
                "proj-1",
            ],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.tasks.create_evaluation_task.call_args.kwargs
        assert call_kwargs["name"] == "My Task"
        assert call_kwargs["task_type"] == "TEMPLATE_EVALUATION"
        assert call_kwargs["project"] == "proj-1"
        assert call_kwargs["dataset"] is None
        assert len(call_kwargs["evaluators"]) == 1
        assert call_kwargs["evaluators"][0].evaluator_id == "ev-1"

    @pytest.mark.unit
    def test_creates_dataset_task(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Create a dataset-based evaluation task with experiment IDs."""
        mock_client.tasks.create_evaluation_task.return_value = _make_task()

        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "My Task",
                "--task-type",
                "TEMPLATE_EVALUATION",
                "--evaluators",
                self._EVALUATORS_JSON,
                "--dataset",
                "ds-1",
                "--experiment-ids",
                "exp-1,exp-2",
            ],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.tasks.create_evaluation_task.call_args.kwargs
        assert call_kwargs["dataset"] == "ds-1"
        assert call_kwargs["project"] is None
        assert call_kwargs["experiment_ids"] == ["exp-1", "exp-2"]

    @pytest.mark.unit
    def test_project_name_resolved_to_id(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Project name is passed directly to the SDK (SDK handles name-or-ID resolution)."""
        mock_client.tasks.create_evaluation_task.return_value = _make_task()

        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "My Task",
                "--task-type",
                "TEMPLATE_EVALUATION",
                "--evaluators",
                self._EVALUATORS_JSON,
                "--project",
                "my-project",
                "--space",
                "space-1",
            ],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.tasks.create_evaluation_task.call_args.kwargs
        assert call_kwargs["project"] == "my-project"

    @pytest.mark.unit
    def test_requires_project_or_dataset(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """'create' without --project or --dataset exits non-zero for eval tasks."""
        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "My Task",
                "--task-type",
                "TEMPLATE_EVALUATION",
                "--evaluators",
                self._EVALUATORS_JSON,
            ],
        )
        assert result.exit_code != 0
        mock_client.tasks.create_evaluation_task.assert_not_called()

    @pytest.mark.unit
    def test_project_and_dataset_mutually_exclusive(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Providing both --project and --dataset exits non-zero."""
        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "My Task",
                "--task-type",
                "TEMPLATE_EVALUATION",
                "--evaluators",
                self._EVALUATORS_JSON,
                "--project",
                "proj-1",
                "--dataset",
                "ds-1",
            ],
        )
        assert result.exit_code != 0
        mock_client.tasks.create_evaluation_task.assert_not_called()

    @pytest.mark.unit
    def test_optional_flags_forwarded(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Optional flags (sampling-rate, is-continuous, query-filter) are passed through."""
        mock_client.tasks.create_evaluation_task.return_value = _make_task()

        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "My Task",
                "--task-type",
                "TEMPLATE_EVALUATION",
                "--evaluators",
                self._EVALUATORS_JSON,
                "--project",
                "proj-1",
                "--sampling-rate",
                "0.5",
                "--is-continuous",
                "--query-filter",
                "score > 0.8",
            ],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.tasks.create_evaluation_task.call_args.kwargs
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
        mock_client.tasks.create_evaluation_task.side_effect = Exception(
            "conflict"
        )
        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "My Task",
                "--task-type",
                "TEMPLATE_EVALUATION",
                "--evaluators",
                self._EVALUATORS_JSON,
                "--project",
                "proj-1",
            ],
        )
        assert result.exit_code != 0

    @pytest.mark.unit
    def test_creates_run_experiment_task(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--task-type run_experiment dispatches to create_run_experiment_task."""
        mock_client.tasks.create_run_experiment_task.return_value = _make_task()

        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "Exp Task",
                "--task-type",
                "RUN_EXPERIMENT",
                "--dataset",
                "ds-1",
                "--run-configuration",
                _RUN_CONFIG_JSON,
            ],
        )
        assert result.exit_code == 0, result.output
        call_kwargs = (
            mock_client.tasks.create_run_experiment_task.call_args.kwargs
        )
        assert call_kwargs["name"] == "Exp Task"
        assert call_kwargs["dataset"] == "ds-1"
        mock_client.tasks.create_evaluation_task.assert_not_called()

    @pytest.mark.unit
    def test_run_experiment_requires_dataset(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """run_experiment task without --dataset exits non-zero."""
        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "Exp Task",
                "--task-type",
                "RUN_EXPERIMENT",
                "--run-configuration",
                _RUN_CONFIG_JSON,
            ],
        )
        assert result.exit_code != 0
        mock_client.tasks.create_run_experiment_task.assert_not_called()

    @pytest.mark.unit
    def test_run_experiment_requires_run_configuration(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """run_experiment task without --run-configuration exits non-zero."""
        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "Exp Task",
                "--task-type",
                "RUN_EXPERIMENT",
                "--dataset",
                "ds-1",
            ],
        )
        assert result.exit_code != 0
        mock_client.tasks.create_run_experiment_task.assert_not_called()

    @pytest.mark.unit
    def test_run_experiment_rejects_eval_flags(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Providing --evaluators with run_experiment exits non-zero."""
        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "Exp Task",
                "--task-type",
                "RUN_EXPERIMENT",
                "--dataset",
                "ds-1",
                "--run-configuration",
                _RUN_CONFIG_JSON,
                "--evaluators",
                '[{"evaluator_id": "ev-1"}]',
            ],
        )
        assert result.exit_code != 0
        mock_client.tasks.create_run_experiment_task.assert_not_called()


# ---------------------------------------------------------------------------
# ax tasks create-evaluation
# ---------------------------------------------------------------------------


class TestCreateEvaluationSubcmd:
    """Tests for the 'ax tasks create-evaluation' subcommand."""

    _EVALUATORS_JSON = '[{"evaluator_id": "ev-1"}]'

    @pytest.mark.unit
    def test_creates_evaluation_task(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """create-evaluation calls create_evaluation_task with correct kwargs."""
        mock_client.tasks.create_evaluation_task.return_value = _make_task()

        result = cli_runner.invoke(
            app,
            [
                "create-evaluation",
                "--name",
                "Eval Task",
                "--task-type",
                "TEMPLATE_EVALUATION",
                "--evaluators",
                self._EVALUATORS_JSON,
                "--project",
                "proj-1",
            ],
        )
        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.tasks.create_evaluation_task.call_args.kwargs
        assert call_kwargs["name"] == "Eval Task"
        assert call_kwargs["task_type"] == "TEMPLATE_EVALUATION"
        assert call_kwargs["project"] == "proj-1"
        assert len(call_kwargs["evaluators"]) == 1
        assert call_kwargs["evaluators"][0].evaluator_id == "ev-1"

    @pytest.mark.unit
    def test_requires_project_or_dataset(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """create-evaluation without --project or --dataset exits non-zero."""
        result = cli_runner.invoke(
            app,
            [
                "create-evaluation",
                "--name",
                "Eval Task",
                "--task-type",
                "TEMPLATE_EVALUATION",
                "--evaluators",
                self._EVALUATORS_JSON,
            ],
        )
        assert result.exit_code != 0
        mock_client.tasks.create_evaluation_task.assert_not_called()

    @pytest.mark.unit
    def test_rejects_run_experiment_task_type(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--task-type run_experiment exits non-zero with a helpful message."""
        result = cli_runner.invoke(
            app,
            [
                "create-evaluation",
                "--name",
                "Eval Task",
                "--task-type",
                "RUN_EXPERIMENT",
                "--evaluators",
                self._EVALUATORS_JSON,
                "--project",
                "proj-1",
            ],
        )
        assert result.exit_code != 0
        assert "create-run-experiment" in result.output
        mock_client.tasks.create_evaluation_task.assert_not_called()

    @pytest.mark.unit
    def test_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """API failure results in a non-zero exit code."""
        mock_client.tasks.create_evaluation_task.side_effect = Exception(
            "conflict"
        )
        result = cli_runner.invoke(
            app,
            [
                "create-evaluation",
                "--name",
                "Eval Task",
                "--task-type",
                "TEMPLATE_EVALUATION",
                "--evaluators",
                self._EVALUATORS_JSON,
                "--project",
                "proj-1",
            ],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax tasks create-run-experiment
# ---------------------------------------------------------------------------


class TestCreateRunExperimentSubcmd:
    """Tests for the 'ax tasks create-run-experiment' subcommand."""

    @pytest.mark.unit
    def test_creates_run_experiment_task(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """create-run-experiment calls create_run_experiment_task with correct kwargs."""
        mock_client.tasks.create_run_experiment_task.return_value = _make_task()

        result = cli_runner.invoke(
            app,
            [
                "create-run-experiment",
                "--name",
                "Run Exp Task",
                "--dataset",
                "ds-1",
                "--run-configuration",
                _RUN_CONFIG_JSON,
            ],
        )
        assert result.exit_code == 0, result.output
        call_kwargs = (
            mock_client.tasks.create_run_experiment_task.call_args.kwargs
        )
        assert call_kwargs["name"] == "Run Exp Task"
        assert call_kwargs["dataset"] == "ds-1"

    @pytest.mark.unit
    def test_space_forwarded(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--space is forwarded to create_run_experiment_task."""
        mock_client.tasks.create_run_experiment_task.return_value = _make_task()

        result = cli_runner.invoke(
            app,
            [
                "create-run-experiment",
                "--name",
                "Run Exp Task",
                "--dataset",
                "ds-1",
                "--run-configuration",
                _RUN_CONFIG_JSON,
                "--space",
                "space-1",
            ],
        )
        assert result.exit_code == 0, result.output
        call_kwargs = (
            mock_client.tasks.create_run_experiment_task.call_args.kwargs
        )
        assert call_kwargs["space"] == "space-1"

    @pytest.mark.unit
    def test_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """API failure results in a non-zero exit code."""
        mock_client.tasks.create_run_experiment_task.side_effect = Exception(
            "conflict"
        )
        result = cli_runner.invoke(
            app,
            [
                "create-run-experiment",
                "--name",
                "Run Exp Task",
                "--dataset",
                "ds-1",
                "--run-configuration",
                _RUN_CONFIG_JSON,
            ],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax tasks update
# ---------------------------------------------------------------------------


class TestUpdateTask:
    """Tests for the 'ax tasks update' command."""

    @pytest.mark.unit
    def test_update_name(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--name is forwarded to client.tasks.update."""
        mock_client.tasks.update.return_value = _make_task(name="new-name")

        result = cli_runner.invoke(
            app,
            ["update", "task-1", "--name", "new-name"],
        )
        assert result.exit_code == 0
        mock_client.tasks.update.assert_called_once_with(
            task="task-1",
            name="new-name",
        )

    @pytest.mark.unit
    def test_update_sampling_rate(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        mock_client.tasks.update.return_value = _make_task()

        result = cli_runner.invoke(
            app,
            ["update", "tid", "--sampling-rate", "0.5"],
        )
        assert result.exit_code == 0
        mock_client.tasks.update.assert_called_once_with(
            task="tid",
            sampling_rate=pytest.approx(0.5),
        )

    @pytest.mark.unit
    def test_update_evaluators(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        mock_client.tasks.update.return_value = _make_task()
        json_arg = '[{"evaluator_id": "ev-1"}]'

        result = cli_runner.invoke(
            app,
            ["update", "tid", "--evaluators", json_arg],
        )
        assert result.exit_code == 0
        call_kw = mock_client.tasks.update.call_args.kwargs
        assert call_kw["task"] == "tid"
        assert len(call_kw["evaluators"]) == 1
        assert call_kw["evaluators"][0].evaluator_id == "ev-1"

    @pytest.mark.unit
    def test_clear_query_filter_with_empty_string(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Passing `--query-filter ""` clears the task-level query filter."""
        mock_client.tasks.update.return_value = _make_task()

        result = cli_runner.invoke(
            app,
            ["update", "tid", "--query-filter", ""],
        )
        assert result.exit_code == 0
        mock_client.tasks.update.assert_called_once_with(
            task="tid",
            query_filter=None,
        )

    @pytest.mark.unit
    def test_query_filter_non_empty_passes_through(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """A non-empty `--query-filter` is forwarded to the SDK verbatim."""
        mock_client.tasks.update.return_value = _make_task()

        result = cli_runner.invoke(
            app,
            ["update", "tid", "--query-filter", "score > 0.8"],
        )
        assert result.exit_code == 0
        mock_client.tasks.update.assert_called_once_with(
            task="tid",
            query_filter="score > 0.8",
        )

    @pytest.mark.unit
    def test_update_run_configuration(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--run-configuration is parsed and forwarded to client.tasks.update."""
        mock_client.tasks.update.return_value = _make_task()

        result = cli_runner.invoke(
            app,
            ["update", "tid", "--run-configuration", _RUN_CONFIG_JSON],
        )
        assert result.exit_code == 0, result.output
        call_kw = mock_client.tasks.update.call_args.kwargs
        assert call_kw["task"] == "tid"
        assert "run_configuration" in call_kw

    @pytest.mark.unit
    def test_usage_error_when_no_fields(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        result = cli_runner.invoke(app, ["update", "tid"])
        assert result.exit_code != 0
        mock_client.tasks.update.assert_not_called()

    @pytest.mark.unit
    def test_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        mock_client.tasks.update.side_effect = Exception("boom")
        result = cli_runner.invoke(
            app,
            ["update", "tid", "--name", "x"],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax tasks delete
# ---------------------------------------------------------------------------


class TestDeleteTask:
    """Tests for the 'ax tasks delete' command."""

    @pytest.mark.unit
    def test_delete_with_force(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        result = cli_runner.invoke(
            app,
            ["delete", "task-1", "--force"],
        )
        assert result.exit_code == 0
        mock_client.tasks.delete.assert_called_once_with(
            task="task-1",
            space=None,
        )

    @pytest.mark.unit
    def test_delete_confirmation_yes(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        result = cli_runner.invoke(
            app,
            ["delete", "task-1"],
            input="y\n",
        )
        assert result.exit_code == 0
        mock_client.tasks.delete.assert_called_once_with(
            task="task-1",
            space=None,
        )

    @pytest.mark.unit
    def test_delete_confirmation_no(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        result = cli_runner.invoke(
            app,
            ["delete", "task-1"],
            input="n\n",
        )
        assert result.exit_code == 0
        mock_client.tasks.delete.assert_not_called()

    @pytest.mark.unit
    def test_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        mock_client.tasks.delete.side_effect = Exception("gone")
        result = cli_runner.invoke(app, ["delete", "tid", "--force"])
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
            task="task-1",
            data_start_time=None,
            data_end_time=None,
            max_spans=None,
            override_evaluations=None,
            experiment_ids=None,
            example_ids=None,
            experiment_name=None,
            dataset_version_id=None,
            max_examples=None,
            tracing_metadata=None,
            evaluation_task_ids=None,
        )

    @pytest.mark.unit
    def test_wait_polls_until_terminal(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--wait causes wait_for_run to be called after the run is triggered."""
        run = _make_run(status="PENDING")
        mock_client.tasks.trigger_run.return_value = run
        completed_run = _make_run(status="COMPLETED")
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
    def test_run_experiment_kwargs_forwarded(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """run_experiment-specific kwargs are forwarded to trigger_run."""
        mock_client.tasks.trigger_run.return_value = _make_run()

        result = cli_runner.invoke(
            app,
            [
                "trigger-run",
                "task-1",
                "--experiment-name",
                "my-exp",
                "--dataset-version-id",
                "ver-123",
                "--max-examples",
                "50",
                "--tracing-metadata",
                '{"env": "prod"}',
            ],
        )
        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.tasks.trigger_run.call_args.kwargs
        assert call_kwargs["experiment_name"] == "my-exp"
        assert call_kwargs["dataset_version_id"] == "ver-123"
        assert call_kwargs["max_examples"] == 50
        assert call_kwargs["tracing_metadata"] == {"env": "prod"}

    @pytest.mark.unit
    def test_example_ids_parsed_and_forwarded(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Comma-separated --example-ids are parsed into a list and forwarded."""
        mock_client.tasks.trigger_run.return_value = _make_run()

        result = cli_runner.invoke(
            app,
            [
                "trigger-run",
                "task-1",
                "--experiment-name",
                "my-exp",
                "--example-ids",
                "ex-1,ex-2",
            ],
        )
        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.tasks.trigger_run.call_args.kwargs
        assert call_kwargs["example_ids"] == ["ex-1", "ex-2"]

    @pytest.mark.unit
    def test_evaluation_task_ids_parsed_and_forwarded(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Comma-separated --evaluation-task-ids are parsed into a list and forwarded."""
        mock_client.tasks.trigger_run.return_value = _make_run()

        result = cli_runner.invoke(
            app,
            [
                "trigger-run",
                "task-1",
                "--experiment-name",
                "my-exp",
                "--evaluation-task-ids",
                "eval-task-1,eval-task-2",
            ],
        )
        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.tasks.trigger_run.call_args.kwargs
        assert call_kwargs["evaluation_task_ids"] == [
            "eval-task-1",
            "eval-task-2",
        ]

    @pytest.mark.unit
    def test_example_ids_and_max_examples_mutually_exclusive(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--example-ids and --max-examples together should exit non-zero."""
        result = cli_runner.invoke(
            app,
            [
                "trigger-run",
                "task-1",
                "--experiment-name",
                "my-exp",
                "--example-ids",
                "ex-1",
                "--max-examples",
                "10",
            ],
        )
        assert result.exit_code != 0
        assert "mutually exclusive" in result.output.lower()

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
    def test_calls_client_task_runs_list(
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
            task="task-1",
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
            app, ["list-runs", "task-1", "--status", "COMPLETED"]
        )
        assert result.exit_code == 0
        mock_client.tasks.list_runs.assert_called_once_with(
            task="task-1",
            status="COMPLETED",
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
            status="CANCELLED"
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
            status="CANCELLED"
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
            status="COMPLETED"
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
            status="COMPLETED"
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
