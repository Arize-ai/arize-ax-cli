"""Tests for project CLI commands."""

from unittest.mock import MagicMock

from typer.testing import CliRunner

from ax.commands.projects import app


class TestProjectCommands:
    """Verify project subcommands are registered with the correct names."""

    def test_get_command_registered(self) -> None:
        """Test that 'get' subcommand exists."""
        names = [cmd.name for cmd in app.registered_commands]
        assert "get" in names


class TestGetProject:
    """Tests for the 'ax projects get' command."""

    def test_calls_client_projects_get(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test that get invokes client.projects.get with the project ID."""
        mock_client.projects.get.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "p-1", "name": "test"})
        )

        result = cli_runner.invoke(app, ["get", "p-1"])
        assert result.exit_code == 0
        mock_client.projects.get.assert_called_once_with(project_id="p-1")
