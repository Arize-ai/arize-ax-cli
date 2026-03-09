"""Tests for experiment CLI commands."""

from unittest.mock import MagicMock, patch

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
            experiment_id="exp-1"
        )


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
            experiment_id="exp-1",
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
            experiment_id="exp-1",
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
