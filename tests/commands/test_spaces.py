"""Tests for space CLI commands."""

from unittest.mock import MagicMock

from typer.testing import CliRunner

from ax.commands.spaces import app


class TestSpaceCommands:
    """Verify space subcommands are registered with the correct names."""

    def test_expected_commands_registered(self) -> None:
        """Check that list, get, create, update, delete subcommands exist."""
        names = [cmd.name for cmd in app.registered_commands]
        for expected in ("list", "get", "create", "update", "delete"):
            assert expected in names


class TestDeleteSpace:
    """Tests for the 'ax spaces delete' command.

    The delete confirmation uses a type-to-confirm string match (``typer.prompt``)
    rather than the boolean yes/no used by other delete commands — this is
    intentional because space deletion is irreversible and high-blast-radius.
    """

    def test_delete_force_skips_confirmation(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--force bypasses the prompt and deletes the space."""
        result = cli_runner.invoke(app, ["delete", "space-123", "--force"])
        assert result.exit_code == 0
        mock_client.spaces.delete.assert_called_once_with(space="space-123")

    def test_delete_correct_name_typed_calls_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Typing the correct space name proceeds with deletion."""
        result = cli_runner.invoke(
            app, ["delete", "my-space"], input="my-space\n"
        )
        assert result.exit_code == 0
        mock_client.spaces.delete.assert_called_once_with(space="my-space")

    def test_delete_wrong_name_typed_aborts(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Typing the wrong name aborts without calling the SDK."""
        result = cli_runner.invoke(
            app, ["delete", "my-space"], input="wrong-name\n"
        )
        assert result.exit_code == 0
        mock_client.spaces.delete.assert_not_called()

    def test_delete_sdk_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """API failure results in a non-zero exit code."""
        mock_client.spaces.delete.side_effect = Exception("not found")
        result = cli_runner.invoke(app, ["delete", "space-123", "--force"])
        assert result.exit_code != 0
