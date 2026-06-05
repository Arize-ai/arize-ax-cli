"""Tests for organizations CLI commands."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner, Result

from ax.cli import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ORG_ID = "org_test_1"
_CREATED_AT = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_org_list_response(*orgs: MagicMock) -> MagicMock:
    mock = MagicMock()
    mock.organizations = list(orgs)
    mock.pagination.has_more = False
    return mock


def _make_org(
    org_id: str = _ORG_ID,
    name: str = "Test Org",
    description: str = "A test organization",
) -> MagicMock:
    mock = MagicMock()
    mock.id = org_id
    mock.name = name
    mock.description = description
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
    """Return a mock ConfigManager config with JSON output format."""
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
            "ax.commands.organizations.make_client",
            return_value=(mock_client, mock_config),
        ),
    ):
        return runner.invoke(app, args, input=cli_input)


# ---------------------------------------------------------------------------
# ax organizations list
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestListOrganizations:
    """Tests for the `ax organizations list` command."""

    def test_list_returns_organizations(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """List command should exit 0 and return organizations from the SDK."""
        mock_client.organizations.list.return_value = _make_org_list_response(
            _make_org(name="Acme"),
            _make_org(name="Globex"),
        )
        result = _invoke(
            ["organizations", "list", "--output", "json"],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output

    def test_list_passes_name_filter_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--name filter should be forwarded to the SDK."""
        mock_client.organizations.list.return_value = _make_org_list_response()
        _invoke(
            ["organizations", "list", "--name", "Acme"],
            mock_config,
            mock_client,
        )
        mock_client.organizations.list.assert_called_once_with(
            name="Acme",
            limit=50,
            cursor=None,
        )

    def test_list_passes_limit_and_cursor_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--limit and --cursor flags should be forwarded to the SDK."""
        mock_client.organizations.list.return_value = _make_org_list_response()
        _invoke(
            [
                "organizations",
                "list",
                "--limit",
                "10",
                "--cursor",
                "tok",
            ],
            mock_config,
            mock_client,
        )
        mock_client.organizations.list.assert_called_once_with(
            name=None,
            limit=10,
            cursor="tok",
        )

    def test_list_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error should cause the command to exit non-zero."""
        mock_client.organizations.list.side_effect = RuntimeError("API error")
        result = _invoke(["organizations", "list"], mock_config, mock_client)
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax organizations get
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetOrganization:
    """Tests for the `ax organizations get` command."""

    def test_get_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Get command should call the SDK with the organization arg and exit 0."""
        mock_client.organizations.get.return_value = _make_org()
        result = _invoke(
            ["organizations", "get", _ORG_ID, "--output", "json"],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output
        mock_client.organizations.get.assert_called_once_with(
            organization=_ORG_ID
        )

    def test_get_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error should cause the command to exit non-zero."""
        mock_client.organizations.get.side_effect = RuntimeError("Not found")
        result = _invoke(
            ["organizations", "get", _ORG_ID], mock_config, mock_client
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax organizations create
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateOrganization:
    """Tests for the `ax organizations create` command."""

    def test_create_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Create command should call the SDK with name and exit 0."""
        mock_client.organizations.create.return_value = _make_org(name="My Org")
        result = _invoke(
            [
                "organizations",
                "create",
                "--name",
                "My Org",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output
        mock_client.organizations.create.assert_called_once_with(
            name="My Org",
            description=None,
        )

    def test_create_with_description(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--description flag should be forwarded to the SDK."""
        mock_client.organizations.create.return_value = _make_org()
        _invoke(
            [
                "organizations",
                "create",
                "--name",
                "My Org",
                "--description",
                "A test org",
            ],
            mock_config,
            mock_client,
        )
        call_kwargs = mock_client.organizations.create.call_args.kwargs
        assert call_kwargs["description"] == "A test org"

    def test_create_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error on create should cause the command to exit non-zero."""
        mock_client.organizations.create.side_effect = RuntimeError(
            "Name already exists"
        )
        result = _invoke(
            ["organizations", "create", "--name", "Dup"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax organizations update
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestUpdateOrganization:
    """Tests for the `ax organizations update` command."""

    def test_update_name_only(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Update with --name only should set name and leave description as None."""
        mock_client.organizations.update.return_value = _make_org(
            name="New Name"
        )
        result = _invoke(
            [
                "organizations",
                "update",
                _ORG_ID,
                "--name",
                "New Name",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output
        mock_client.organizations.update.assert_called_once_with(
            organization=_ORG_ID,
            name="New Name",
            description=None,
        )

    def test_update_description_only(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Update with --description only should set description and leave name as None."""
        mock_client.organizations.update.return_value = _make_org()
        result = _invoke(
            [
                "organizations",
                "update",
                _ORG_ID,
                "--description",
                "New desc",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output
        mock_client.organizations.update.assert_called_once_with(
            organization=_ORG_ID,
            name=None,
            description="New desc",
        )

    def test_update_requires_at_least_one_field(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Update without any fields should exit non-zero and not call the SDK."""
        result = _invoke(
            ["organizations", "update", _ORG_ID],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.organizations.update.assert_not_called()

    def test_update_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error on update should cause the command to exit non-zero."""
        mock_client.organizations.update.side_effect = RuntimeError("Not found")
        result = _invoke(
            ["organizations", "update", _ORG_ID, "--name", "X"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax organizations add-user
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAddUserToOrganization:
    """Tests for `ax organizations add-user <org>`."""

    def test_add_user_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """add-user should call the SDK with correct args and exit 0."""
        mock_membership = MagicMock()
        mock_membership.user_id = "user_1"
        mock_client.organizations.add_user.return_value = mock_membership

        result = _invoke(
            [
                "organizations",
                "add-user",
                _ORG_ID,
                "--user-id",
                "user_1",
                "--role",
                "member",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.organizations.add_user.call_args.kwargs
        assert call_kwargs["organization"] == _ORG_ID
        assert call_kwargs["user_id"] == "user_1"
        assert call_kwargs["role"] is not None

    def test_add_user_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error should cause the command to exit non-zero."""
        mock_client.organizations.add_user.side_effect = RuntimeError(
            "Not found"
        )
        result = _invoke(
            [
                "organizations",
                "add-user",
                _ORG_ID,
                "--user-id",
                "user_1",
                "--role",
                "member",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax organizations remove-user
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRemoveUserFromOrganization:
    """Tests for `ax organizations remove-user <org>`."""

    def test_remove_user_force_skips_confirmation(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--force should bypass the confirmation prompt."""
        mock_client.organizations.remove_user.return_value = None
        result = _invoke(
            [
                "organizations",
                "remove-user",
                _ORG_ID,
                "--user-id",
                "user_1",
                "--force",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output
        mock_client.organizations.remove_user.assert_called_once_with(
            organization=_ORG_ID,
            user_id="user_1",
        )

    def test_remove_user_with_confirmation_no(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Declining the prompt should abort removal."""
        result = _invoke(
            [
                "organizations",
                "remove-user",
                _ORG_ID,
                "--user-id",
                "user_1",
            ],
            mock_config,
            mock_client,
            cli_input="n\n",
        )
        assert result.exit_code == 0
        mock_client.organizations.remove_user.assert_not_called()

    def test_remove_user_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error should cause the command to exit non-zero."""
        mock_client.organizations.remove_user.side_effect = RuntimeError(
            "Not found"
        )
        result = _invoke(
            [
                "organizations",
                "remove-user",
                _ORG_ID,
                "--user-id",
                "user_1",
                "--force",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax organizations delete
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDeleteOrganization:
    """Tests for `ax organizations delete <org>`."""

    def test_delete_force_skips_confirmation(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--force should bypass the confirmation prompt and call the SDK."""
        mock_client.organizations.delete.return_value = None
        result = _invoke(
            ["organizations", "delete", _ORG_ID, "--force"],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output
        mock_client.organizations.delete.assert_called_once_with(
            organization=_ORG_ID
        )

    def test_delete_confirms_yes_calls_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Confirming the prompt should proceed with deletion."""
        mock_client.organizations.delete.return_value = None
        result = _invoke(
            ["organizations", "delete", _ORG_ID],
            mock_config,
            mock_client,
            cli_input="y\n",
        )
        assert result.exit_code == 0, result.output
        mock_client.organizations.delete.assert_called_once_with(
            organization=_ORG_ID
        )

    def test_delete_declines_does_not_call_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Declining the confirmation prompt should abort the deletion."""
        result = _invoke(
            ["organizations", "delete", _ORG_ID],
            mock_config,
            mock_client,
            cli_input="n\n",
        )
        assert result.exit_code == 0
        mock_client.organizations.delete.assert_not_called()

    def test_delete_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error should cause the command to exit non-zero."""
        mock_client.organizations.delete.side_effect = RuntimeError("Not found")
        result = _invoke(
            ["organizations", "delete", _ORG_ID, "--force"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
