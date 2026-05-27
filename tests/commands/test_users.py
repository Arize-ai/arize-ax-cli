"""Tests for users CLI commands."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner, Result

from ax.cli import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_ID = "user_test_1"
_CREATED_AT = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_user_list_response(*users: MagicMock) -> MagicMock:
    mock = MagicMock()
    mock.users = list(users)
    mock.pagination.has_more = False
    return mock


def _make_user(
    user_id: str = _USER_ID,
    name: str = "Test User",
    email: str = "test@example.com",
    is_developer: bool = True,
) -> MagicMock:
    mock = MagicMock()
    mock.id = user_id
    mock.name = name
    mock.email = email
    mock.is_developer = is_developer
    mock.created_at = _CREATED_AT
    return mock


# ---------------------------------------------------------------------------
# Shared mock setup
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a mock ArizeClient."""
    return MagicMock()


@pytest.fixture
def mock_config() -> MagicMock:
    """Return a mock config with JSON output format."""
    config = MagicMock()
    config.output.format = "json"
    return config


def _invoke(
    args: list[str],
    mock_config: MagicMock,
    mock_client: MagicMock,
    cli_input: str | None = None,
) -> Result:
    with (
        patch(
            "ax.commands.users.make_client",
            return_value=(mock_client, mock_config),
        ),
    ):
        return runner.invoke(app, args, input=cli_input)


# ---------------------------------------------------------------------------
# ax users list
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestListUsers:
    """Tests for `ax users list`."""

    def test_list_returns_users(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """List command should exit 0 and return users from the SDK."""
        mock_client.users.list.return_value = _make_user_list_response(
            _make_user(name="Alice"),
            _make_user(name="Bob"),
        )
        result = _invoke(
            ["users", "list", "--output", "json"],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output

    def test_list_passes_email_filter_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--email filter should be forwarded to the SDK."""
        mock_client.users.list.return_value = _make_user_list_response()
        _invoke(
            ["users", "list", "--email", "alice@example.com"],
            mock_config,
            mock_client,
        )
        mock_client.users.list.assert_called_once_with(
            email="alice@example.com",
            status=None,
            limit=50,
            cursor=None,
        )

    def test_list_passes_limit_and_cursor_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--limit and --cursor flags should be forwarded to the SDK."""
        mock_client.users.list.return_value = _make_user_list_response()
        _invoke(
            ["users", "list", "--limit", "10", "--cursor", "tok"],
            mock_config,
            mock_client,
        )
        mock_client.users.list.assert_called_once_with(
            email=None,
            status=None,
            limit=10,
            cursor="tok",
        )

    def test_list_passes_status_filter_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--status filter should be forwarded to the SDK."""
        mock_client.users.list.return_value = _make_user_list_response()
        _invoke(
            ["users", "list", "--status", "active"],
            mock_config,
            mock_client,
        )
        call_kwargs = mock_client.users.list.call_args.kwargs
        assert call_kwargs["status"] == ["active"]

    def test_list_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error should cause the command to exit non-zero."""
        mock_client.users.list.side_effect = RuntimeError("API error")
        result = _invoke(["users", "list"], mock_config, mock_client)
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax users get
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetUser:
    """Tests for `ax users get <user_id>`."""

    def test_get_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Get command should call the SDK with the user ID arg and exit 0."""
        mock_client.users.get.return_value = _make_user()
        result = _invoke(
            ["users", "get", _USER_ID, "--output", "json"],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output
        mock_client.users.get.assert_called_once_with(user=_USER_ID)

    def test_get_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error should cause the command to exit non-zero."""
        mock_client.users.get.side_effect = RuntimeError("Not found")
        result = _invoke(["users", "get", _USER_ID], mock_config, mock_client)
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax users create
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateUser:
    """Tests for `ax users create`."""

    def test_create_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Create command should call the SDK with correct args and exit 0."""
        mock_client.users.create.return_value = _make_user()
        result = _invoke(
            [
                "users",
                "create",
                "--full-name",
                "Alice",
                "--email",
                "alice@example.com",
                "--role",
                "member",
                "--invite-mode",
                "none",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )
        from arize.users.types import InviteMode, PredefinedUserRole, UserRole

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.users.create.call_args.kwargs
        assert call_kwargs["name"] == "Alice"
        assert call_kwargs["email"] == "alice@example.com"
        assert call_kwargs["role"] == PredefinedUserRole(
            name=UserRole("member")
        )
        assert call_kwargs["invite_mode"] == InviteMode("none")
        assert call_kwargs["is_developer"] is True

    def test_create_with_is_developer(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--is-developer flag should be forwarded to the SDK."""
        mock_client.users.create.return_value = _make_user(is_developer=False)
        _invoke(
            [
                "users",
                "create",
                "--full-name",
                "Alice",
                "--email",
                "alice@example.com",
                "--role",
                "member",
                "--invite-mode",
                "none",
                "--is-not-developer",
            ],
            mock_config,
            mock_client,
        )
        call_kwargs = mock_client.users.create.call_args.kwargs
        assert call_kwargs["is_developer"] is False

    def test_create_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error on create should cause the command to exit non-zero."""
        mock_client.users.create.side_effect = RuntimeError("Email taken")
        result = _invoke(
            [
                "users",
                "create",
                "--full-name",
                "Alice",
                "--email",
                "alice@example.com",
                "--role",
                "member",
                "--invite-mode",
                "none",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax users update
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestUpdateUser:
    """Tests for `ax users update <user_id>`."""

    def test_update_name_only(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Update with --full-name only should forward name to the SDK."""
        mock_client.users.update.return_value = _make_user(name="New Name")
        result = _invoke(
            [
                "users",
                "update",
                _USER_ID,
                "--full-name",
                "New Name",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output
        mock_client.users.update.assert_called_once_with(
            user_id=_USER_ID,
            name="New Name",
            is_developer=None,
        )

    def test_update_is_developer_flag(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--is-developer flag should be forwarded to the SDK."""
        mock_client.users.update.return_value = _make_user(is_developer=True)
        result = _invoke(
            ["users", "update", _USER_ID, "--is-developer", "--output", "json"],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output
        mock_client.users.update.assert_called_once_with(
            user_id=_USER_ID,
            name=None,
            is_developer=True,
        )

    def test_update_requires_at_least_one_field(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Update without any fields should exit non-zero and not call the SDK."""
        result = _invoke(
            ["users", "update", _USER_ID],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.users.update.assert_not_called()

    def test_update_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error on update should cause the command to exit non-zero."""
        mock_client.users.update.side_effect = RuntimeError("Not found")
        result = _invoke(
            ["users", "update", _USER_ID, "--full-name", "X"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax users delete
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDeleteUser:
    """Tests for `ax users delete <user_id>`."""

    def test_delete_force_skips_confirmation(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--force should bypass the confirmation prompt."""
        mock_client.users.delete.return_value = None
        result = _invoke(
            ["users", "delete", _USER_ID, "--force"],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output
        mock_client.users.delete.assert_called_once_with(user_id=_USER_ID)

    def test_delete_with_confirmation_yes(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Confirming the prompt should proceed with deletion."""
        mock_client.users.delete.return_value = None
        result = _invoke(
            ["users", "delete", _USER_ID],
            mock_config,
            mock_client,
            cli_input="y\n",
        )
        assert result.exit_code == 0, result.output
        mock_client.users.delete.assert_called_once_with(user_id=_USER_ID)

    def test_delete_with_confirmation_no(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Declining the confirmation prompt should abort the deletion."""
        result = _invoke(
            ["users", "delete", _USER_ID],
            mock_config,
            mock_client,
            cli_input="n\n",
        )
        assert result.exit_code == 0
        mock_client.users.delete.assert_not_called()

    def test_delete_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error on delete should cause the command to exit non-zero."""
        mock_client.users.delete.side_effect = RuntimeError("Not found")
        result = _invoke(
            ["users", "delete", _USER_ID, "--force"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax users resend-invitation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestResendInvitation:
    """Tests for `ax users resend-invitation <user_id>`."""

    def test_resend_invitation_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Resend invitation should call the SDK and exit 0."""
        mock_client.users.resend_invitation.return_value = None
        result = _invoke(
            ["users", "resend-invitation", _USER_ID],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output
        mock_client.users.resend_invitation.assert_called_once_with(
            user_id=_USER_ID
        )

    def test_resend_invitation_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error should cause the command to exit non-zero."""
        mock_client.users.resend_invitation.side_effect = RuntimeError(
            "User not in invited state"
        )
        result = _invoke(
            ["users", "resend-invitation", _USER_ID],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax users reset-password
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestResetPassword:
    """Tests for `ax users reset-password <user_id>`."""

    def test_reset_password_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Reset password should call the SDK and exit 0."""
        mock_client.users.reset_password.return_value = None
        result = _invoke(
            ["users", "reset-password", _USER_ID],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output
        mock_client.users.reset_password.assert_called_once_with(
            user_id=_USER_ID
        )

    def test_reset_password_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error should cause the command to exit non-zero."""
        mock_client.users.reset_password.side_effect = RuntimeError("SSO user")
        result = _invoke(
            ["users", "reset-password", _USER_ID],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
