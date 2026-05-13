"""Tests for space CLI commands."""

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from ax.commands.spaces import app


@pytest.mark.unit
class TestSpaceCommands:
    """Verify space subcommands are registered with the correct names."""

    def test_expected_commands_registered(self) -> None:
        """Check that list, get, create, update, delete, add-user, remove-user subcommands exist."""
        names = [cmd.name for cmd in app.registered_commands]
        for expected in (
            "list",
            "get",
            "create",
            "update",
            "delete",
            "add-user",
            "remove-user",
        ):
            assert expected in names


@pytest.mark.unit
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


@pytest.mark.unit
class TestAddUserToSpace:
    """Tests for the 'ax spaces add-user' command."""

    def test_add_user_calls_sdk_correctly(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """add-user should call the SDK with correct args and exit 0."""
        mock_membership = MagicMock()
        mock_membership.user_id = "user_1"
        mock_client.spaces.add_user.return_value = mock_membership

        result = cli_runner.invoke(
            app,
            [
                "add-user",
                "space-123",
                "--user-id",
                "user_1",
                "--role",
                "member",
            ],
        )
        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.spaces.add_user.call_args.kwargs
        assert call_kwargs["space"] == "space-123"
        assert call_kwargs["user_id"] == "user_1"
        assert call_kwargs["role"] is not None

    def test_add_user_sdk_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """SDK error should cause the command to exit non-zero."""
        mock_client.spaces.add_user.side_effect = Exception("not found")
        result = cli_runner.invoke(
            app,
            [
                "add-user",
                "space-123",
                "--user-id",
                "user_1",
                "--role",
                "member",
            ],
        )
        assert result.exit_code != 0


@pytest.mark.unit
class TestRemoveUserFromSpace:
    """Tests for the 'ax spaces remove-user' command."""

    def test_remove_user_force_skips_confirmation(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--force should bypass the confirmation prompt."""
        mock_client.spaces.remove_user.return_value = None
        result = cli_runner.invoke(
            app,
            ["remove-user", "space-123", "--user-id", "user_1", "--force"],
        )
        assert result.exit_code == 0, result.output
        mock_client.spaces.remove_user.assert_called_once_with(
            space="space-123",
            user_id="user_1",
        )

    def test_remove_user_with_confirmation_no(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Declining the prompt should abort removal."""
        result = cli_runner.invoke(
            app,
            ["remove-user", "space-123", "--user-id", "user_1"],
            input="n\n",
        )
        assert result.exit_code == 0
        mock_client.spaces.remove_user.assert_not_called()

    def test_remove_user_sdk_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """SDK error should cause the command to exit non-zero."""
        mock_client.spaces.remove_user.side_effect = Exception("not found")
        result = cli_runner.invoke(
            app,
            ["remove-user", "space-123", "--user-id", "user_1", "--force"],
        )
        assert result.exit_code != 0
