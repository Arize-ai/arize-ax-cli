"""Tests for experiment CLI commands."""

from unittest.mock import MagicMock, patch

import pandas as pd
from typer.testing import CliRunner

from ax.commands.experiments import app


class TestExperimentCommands:
    """Verify experiment subcommands are registered with the correct names."""

    def test_get_command_registered(self) -> None:
        """Test that 'get' subcommand exists."""
        names = [cmd.name for cmd in app.registered_commands]
        assert "get" in names

    def test_export_command_registered(self) -> None:
        """Test that 'export' subcommand exists."""
        names = [cmd.name for cmd in app.registered_commands]
        assert "export" in names

    def test_list_runs_command_not_registered(self) -> None:
        """Test that old 'list_runs' subcommand no longer exists."""
        names = [cmd.name for cmd in app.registered_commands]
        assert "list_runs" not in names
        assert "list-runs" not in names

    def test_list_command_registered(self) -> None:
        """Test that 'list' subcommand exists."""
        names = [cmd.name for cmd in app.registered_commands]
        assert "list" in names

    def test_delete_command_registered(self) -> None:
        """Test that 'delete' subcommand exists."""
        names = [cmd.name for cmd in app.registered_commands]
        assert "delete" in names


class TestListExperiments:
    """Tests for the 'ax experiments list' command."""

    def test_calls_client_experiments_list_defaults(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'list' with defaults and verify the SDK call."""
        mock_client.experiments.list.return_value = MagicMock(
            model_dump=MagicMock(return_value={"experiments": []})
        )

        result = cli_runner.invoke(app, ["list"])
        assert result.exit_code == 0
        mock_client.experiments.list.assert_called_once_with(
            dataset=None,
            space=None,
            limit=15,
            cursor=None,
        )

    def test_list_with_dataset_and_space(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify --dataset and --space are forwarded to the SDK."""
        mock_client.experiments.list.return_value = MagicMock(
            model_dump=MagicMock(return_value={"experiments": []})
        )

        result = cli_runner.invoke(
            app,
            ["list", "--dataset", "ds-1", "--space", "space-abc"],
        )
        assert result.exit_code == 0
        mock_client.experiments.list.assert_called_once_with(
            dataset="ds-1",
            space="space-abc",
            limit=15,
            cursor=None,
        )

    def test_list_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """API failure results in a non-zero exit code."""
        mock_client.experiments.list.side_effect = Exception(
            "connection refused"
        )
        result = cli_runner.invoke(app, ["list"])
        assert result.exit_code != 0


class TestGetExperiment:
    """Tests for the 'ax experiments get' command."""

    def test_calls_client_experiments_get(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test that get invokes client.experiments.get with the ID."""
        mock_client.experiments.get.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "exp-1", "name": "test"})
        )

        result = cli_runner.invoke(app, ["get", "exp-1"])
        assert result.exit_code == 0
        mock_client.experiments.get.assert_called_once_with(
            experiment="exp-1", dataset=None, space=None
        )

    def test_get_sdk_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """SDK error results in a non-zero exit code."""
        mock_client.experiments.get.side_effect = Exception("not found")
        result = cli_runner.invoke(app, ["get", "exp-1"])
        assert result.exit_code != 0


class TestExportExperiment:
    """Tests for the 'ax experiments export' command."""

    def test_export_defaults_to_rest(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test that export defaults to all=False (REST)."""
        response = MagicMock()
        response.experiment_runs = []
        mock_client.experiments.list_runs.return_value = response

        result = cli_runner.invoke(app, ["export", "exp-1", "--stdout"])
        assert result.exit_code == 0
        mock_client.experiments.list_runs.assert_called_once_with(
            experiment="exp-1",
            dataset=None,
            space=None,
            all=False,
        )

    def test_export_all_uses_flight(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test that --all passes all=True to SDK (Flight path)."""
        response = MagicMock()
        response.experiment_runs = []
        mock_client.experiments.list_runs.return_value = response

        result = cli_runner.invoke(
            app, ["export", "exp-1", "--all", "--stdout"]
        )
        assert result.exit_code == 0
        mock_client.experiments.list_runs.assert_called_once_with(
            experiment="exp-1",
            dataset=None,
            space=None,
            all=True,
        )

    def test_export_writes_file(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: object,
    ) -> None:
        """Test that export writes a JSON file when --stdout is not set."""
        response = MagicMock()
        response.experiment_runs = []
        mock_client.experiments.list_runs.return_value = response

        with patch("ax.commands.experiments.make_export_dir") as mock_dir:
            mock_dir.return_value = tmp_path  # type: ignore[assignment]
            with patch(
                "ax.commands.experiments.write_json_array"
            ) as mock_write:
                mock_write.return_value = tmp_path / "runs.json"  # type: ignore[operator]

                result = cli_runner.invoke(
                    app,
                    ["export", "exp-1", "--output-dir", str(tmp_path)],
                )
                assert result.exit_code == 0
                mock_write.assert_called_once()


class TestDeleteExperiment:
    """Tests for the 'ax experiments delete' command."""

    def test_delete_force_skips_confirmation(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--force bypasses the prompt and deletes the experiment."""
        result = cli_runner.invoke(app, ["delete", "exp-1", "--force"])
        assert result.exit_code == 0
        mock_client.experiments.delete.assert_called_once_with(
            experiment="exp-1",
            dataset=None,
            space=None,
        )

    def test_delete_confirms_yes_calls_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Confirming the prompt proceeds with deletion."""
        result = cli_runner.invoke(app, ["delete", "exp-1"], input="y\n")
        assert result.exit_code == 0
        mock_client.experiments.delete.assert_called_once_with(
            experiment="exp-1",
            dataset=None,
            space=None,
        )

    def test_delete_declines_does_not_call_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Declining the confirmation leaves the experiment untouched."""
        result = cli_runner.invoke(app, ["delete", "exp-1"], input="n\n")
        assert result.exit_code == 0
        mock_client.experiments.delete.assert_not_called()

    def test_delete_with_dataset_and_space(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--dataset and --space are forwarded to the SDK."""
        result = cli_runner.invoke(
            app,
            [
                "delete",
                "my-exp",
                "--force",
                "--dataset",
                "ds-1",
                "--space",
                "space-abc",
            ],
        )
        assert result.exit_code == 0
        mock_client.experiments.delete.assert_called_once_with(
            experiment="my-exp",
            dataset="ds-1",
            space="space-abc",
        )

    def test_delete_sdk_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """API failure results in a non-zero exit code."""
        mock_client.experiments.delete.side_effect = Exception("not found")
        result = cli_runner.invoke(app, ["delete", "exp-1", "--force"])
        assert result.exit_code != 0


class TestCreateExperiment:
    """Tests for the 'ax experiments create' command."""

    _RUNS_DF = pd.DataFrame([{"example_id": "ex-1", "output": "Paris"}])

    def test_create_command_registered(self) -> None:
        """Test that 'create' subcommand exists."""
        names = [cmd.name for cmd in app.registered_commands]
        assert "create" in names

    def test_create_with_space_passes_to_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--space is forwarded to client.experiments.create."""
        mock_client.experiments.create.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "exp-1", "name": "my-exp"})
        )

        with patch(
            "ax.commands.experiments.read_data_file",
            return_value=self._RUNS_DF,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "create",
                    "--name",
                    "my-exp",
                    "--dataset",
                    "ds-1",
                    "--file",
                    "runs.json",
                    "--space",
                    "space-abc",
                ],
            )

        assert result.exit_code == 0, result.output
        mock_client.experiments.create.assert_called_once()
        call_kwargs = mock_client.experiments.create.call_args.kwargs
        assert call_kwargs["space"] == "space-abc"
        assert call_kwargs["dataset"] == "ds-1"

    def test_create_without_space_passes_none(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """space=None is passed when --space is omitted."""
        mock_client.experiments.create.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "exp-1", "name": "my-exp"})
        )

        with patch(
            "ax.commands.experiments.read_data_file",
            return_value=self._RUNS_DF,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "create",
                    "--name",
                    "my-exp",
                    "--dataset",
                    "ds-id-123",
                    "--file",
                    "runs.json",
                ],
            )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.experiments.create.call_args.kwargs
        assert call_kwargs["space"] is None
