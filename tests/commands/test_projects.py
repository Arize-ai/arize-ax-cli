"""Tests for project CLI commands."""

from unittest.mock import MagicMock

from typer.testing import CliRunner

from ax.commands.projects import app


class TestProjectCommands:
    """Verify project subcommands are registered with the correct names."""

    def test_expected_commands_registered(self) -> None:
        """Check that list, get, create, delete subcommands exist."""
        names = [cmd.name for cmd in app.registered_commands]
        for expected in ("list", "get", "create", "delete"):
            assert expected in names


class TestListProjects:
    """Tests for the 'ax projects list' command."""

    def test_calls_client_projects_list_defaults(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'list' with defaults and verify the SDK call."""
        mock_client.projects.list.return_value = MagicMock(
            model_dump=MagicMock(return_value={"projects": []})
        )

        result = cli_runner.invoke(app, ["list"])
        assert result.exit_code == 0
        mock_client.projects.list.assert_called_once_with(
            name=None,
            space=None,
            limit=15,
            cursor=None,
        )

    def test_list_with_space(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify --space is forwarded to the SDK."""
        mock_client.projects.list.return_value = MagicMock(
            model_dump=MagicMock(return_value={"projects": []})
        )

        result = cli_runner.invoke(app, ["list", "--space", "space-abc"])
        assert result.exit_code == 0
        mock_client.projects.list.assert_called_once_with(
            name=None,
            space="space-abc",
            limit=15,
            cursor=None,
        )

    def test_list_name_filter_forwarded(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify --name filter is forwarded to the SDK."""
        mock_client.projects.list.return_value = MagicMock(
            model_dump=MagicMock(return_value={"projects": []})
        )

        result = cli_runner.invoke(app, ["list", "--name", "my-project"])
        assert result.exit_code == 0
        mock_client.projects.list.assert_called_once_with(
            name="my-project",
            space=None,
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
        mock_client.projects.list.side_effect = Exception("connection refused")
        result = cli_runner.invoke(app, ["list"])
        assert result.exit_code != 0


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
        mock_client.projects.get.assert_called_once_with(
            project="p-1", space=None
        )

    def test_get_with_space(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--space is forwarded when looking up by name."""
        mock_client.projects.get.return_value = MagicMock(
            model_dump=MagicMock(
                return_value={"id": "p-1", "name": "my-project"}
            )
        )

        result = cli_runner.invoke(
            app, ["get", "my-project", "--space", "space-abc"]
        )
        assert result.exit_code == 0
        mock_client.projects.get.assert_called_once_with(
            project="my-project", space="space-abc"
        )

    def test_get_sdk_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """SDK error results in a non-zero exit code."""
        mock_client.projects.get.side_effect = Exception("not found")
        result = cli_runner.invoke(app, ["get", "p-1"])
        assert result.exit_code != 0


class TestCreateProject:
    """Tests for the 'ax projects create' command."""

    def test_create_calls_sdk_correctly(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify create passes name and space to the SDK."""
        mock_client.projects.create.return_value = MagicMock(
            model_dump=MagicMock(
                return_value={"id": "p-new", "name": "my-proj"}
            )
        )

        result = cli_runner.invoke(
            app,
            ["create", "--name", "my-proj", "--space", "space-abc"],
        )
        assert result.exit_code == 0
        mock_client.projects.create.assert_called_once_with(
            name="my-proj",
            space="space-abc",
        )

    def test_create_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """API failure results in a non-zero exit code."""
        mock_client.projects.create.side_effect = Exception("conflict")
        result = cli_runner.invoke(
            app,
            ["create", "--name", "my-proj", "--space", "space-abc"],
        )
        assert result.exit_code != 0


class TestDeleteProject:
    """Tests for the 'ax projects delete' command."""

    def test_delete_force_skips_confirmation(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--force bypasses the prompt and deletes the project."""
        result = cli_runner.invoke(app, ["delete", "p-1", "--force"])
        assert result.exit_code == 0
        mock_client.projects.delete.assert_called_once_with(
            project="p-1", space=None
        )

    def test_delete_confirms_yes_calls_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Confirming the prompt proceeds with deletion."""
        result = cli_runner.invoke(app, ["delete", "p-1"], input="y\n")
        assert result.exit_code == 0
        mock_client.projects.delete.assert_called_once_with(
            project="p-1", space=None
        )

    def test_delete_declines_does_not_call_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Declining the confirmation leaves the project untouched."""
        result = cli_runner.invoke(app, ["delete", "p-1"], input="n\n")
        assert result.exit_code == 0
        mock_client.projects.delete.assert_not_called()

    def test_delete_with_space(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--space is forwarded when deleting by name."""
        result = cli_runner.invoke(
            app,
            ["delete", "my-project", "--force", "--space", "space-abc"],
        )
        assert result.exit_code == 0
        mock_client.projects.delete.assert_called_once_with(
            project="my-project", space="space-abc"
        )

    def test_delete_sdk_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """API failure results in a non-zero exit code."""
        mock_client.projects.delete.side_effect = Exception("not found")
        result = cli_runner.invoke(app, ["delete", "p-1", "--force"])
        assert result.exit_code != 0
