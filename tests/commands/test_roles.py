"""Tests for roles CLI commands."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner, Result

from ax.cli import app
from ax.commands.roles import _parse_permissions

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ROLE_ID = "role_test_1"
_CREATED_AT = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_role_list_response(*roles: MagicMock) -> MagicMock:
    mock = MagicMock()
    mock.roles = list(roles)
    mock.pagination.has_more = False
    return mock


def _make_role(
    role_id: str = _ROLE_ID,
    name: str = "Test Role",
    is_predefined: bool = False,
) -> MagicMock:
    mock = MagicMock()
    mock.id = role_id
    mock.name = name
    mock.is_predefined = is_predefined
    mock.created_at = _CREATED_AT
    mock.updated_at = _CREATED_AT
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
            "ax.commands.roles.make_client",
            return_value=(mock_client, mock_config),
        ),
    ):
        return runner.invoke(app, args, input=cli_input)


# ---------------------------------------------------------------------------
# _parse_permissions helper
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParsePermissions:
    """Tests for the _parse_permissions helper."""

    def test_valid_single_permission(self) -> None:
        """Single valid permission string should return a list of one Permission."""
        result = _parse_permissions(["PROJECT_READ"])
        assert len(result) == 1

    def test_valid_multiple_permissions(self) -> None:
        """Multiple valid permission strings should all be converted."""
        result = _parse_permissions(["PROJECT_READ", "DATASET_CREATE"])
        assert len(result) == 2

    def test_empty_list_returns_empty(self) -> None:
        """Empty input should return an empty list."""
        assert _parse_permissions([]) == []

    def test_invalid_permission_raises_bad_parameter(self) -> None:
        """Unknown permission string should raise BadParameter."""
        with pytest.raises(typer.BadParameter, match="NOT_REAL"):
            _parse_permissions(["NOT_REAL"])

    def test_invalid_permission_preserves_cause(self) -> None:
        """Exception chain should be preserved (from e)."""
        with pytest.raises(typer.BadParameter) as exc_info:
            _parse_permissions(["BAD_PERM"])
        assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# --permissions comma-separated parsing (via CLI)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPermissionsArgParsing:
    """Tests for --permissions comma-separated argument parsing via the CLI."""

    def test_comma_separated_splits_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Comma-separated permissions string should be split into individual values."""
        mock_client.roles.create.return_value = _make_role()
        _invoke(
            [
                "roles",
                "create",
                "--name",
                "R",
                "--permissions",
                "PROJECT_READ,DATASET_READ",
            ],
            mock_config,
            mock_client,
        )
        call_kwargs = mock_client.roles.create.call_args.kwargs
        assert len(call_kwargs["permissions"]) == 2

    def test_spaces_around_commas_are_stripped(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Whitespace around commas in permissions should be stripped."""
        mock_client.roles.create.return_value = _make_role()
        _invoke(
            [
                "roles",
                "create",
                "--name",
                "R",
                "--permissions",
                "PROJECT_READ , DATASET_READ",
            ],
            mock_config,
            mock_client,
        )
        call_kwargs = mock_client.roles.create.call_args.kwargs
        assert len(call_kwargs["permissions"]) == 2

    def test_trailing_comma_ignored(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Trailing comma in permissions string should produce no extra empty entry."""
        mock_client.roles.create.return_value = _make_role()
        _invoke(
            [
                "roles",
                "create",
                "--name",
                "R",
                "--permissions",
                "PROJECT_READ,",
            ],
            mock_config,
            mock_client,
        )
        call_kwargs = mock_client.roles.create.call_args.kwargs
        assert len(call_kwargs["permissions"]) == 1


# ---------------------------------------------------------------------------
# ax roles list
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestListRoles:
    """Tests for the `ax roles list` command."""

    def test_list_returns_roles(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """List command should exit 0 and return roles from the SDK."""
        mock_client.roles.list.return_value = _make_role_list_response(
            _make_role(name="Admin"),
            _make_role(name="Viewer"),
        )
        result = _invoke(
            ["roles", "list", "--output", "json"], mock_config, mock_client
        )
        assert result.exit_code == 0, result.output

    def test_list_passes_filters_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Filter flags (--is-predefined, --limit, --cursor) should be forwarded to the SDK."""
        mock_client.roles.list.return_value = _make_role_list_response()
        _invoke(
            [
                "roles",
                "list",
                "--is-predefined",
                "--limit",
                "5",
                "--cursor",
                "tok",
            ],
            mock_config,
            mock_client,
        )
        mock_client.roles.list.assert_called_once_with(
            limit=5,
            cursor="tok",
            is_predefined=True,
        )

    def test_list_is_custom_sets_is_predefined_false(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--is-custom flag should translate to is_predefined=False in the SDK call."""
        mock_client.roles.list.return_value = _make_role_list_response()
        _invoke(["roles", "list", "--is-custom"], mock_config, mock_client)
        mock_client.roles.list.assert_called_once_with(
            limit=15,
            cursor=None,
            is_predefined=False,
        )

    def test_list_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error should cause the command to exit non-zero."""
        mock_client.roles.list.side_effect = RuntimeError("API error")
        result = _invoke(["roles", "list"], mock_config, mock_client)
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax roles get
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetRole:
    """Tests for the `ax roles get` command."""

    def test_get_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Get command should call the SDK with the role ID and exit 0."""
        mock_client.roles.get.return_value = _make_role()
        result = _invoke(
            ["roles", "get", _ROLE_ID, "--output", "json"],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output
        mock_client.roles.get.assert_called_once_with(role=_ROLE_ID)

    def test_get_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error should cause the command to exit non-zero."""
        mock_client.roles.get.side_effect = RuntimeError("Not found")
        result = _invoke(["roles", "get", _ROLE_ID], mock_config, mock_client)
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax roles create
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateRole:
    """Tests for the `ax roles create` command."""

    def test_create_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Create command should call the SDK with name and permissions, then exit 0."""
        mock_client.roles.create.return_value = _make_role(name="My Role")
        result = _invoke(
            [
                "roles",
                "create",
                "--name",
                "My Role",
                "--permissions",
                "PROJECT_READ,DATASET_CREATE",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.roles.create.call_args.kwargs
        assert call_kwargs["name"] == "My Role"
        assert len(call_kwargs["permissions"]) == 2

    def test_create_with_description(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--description flag should be forwarded to the SDK."""
        mock_client.roles.create.return_value = _make_role()
        _invoke(
            [
                "roles",
                "create",
                "--name",
                "My Role",
                "--permissions",
                "PROJECT_READ",
                "--description",
                "A test role",
            ],
            mock_config,
            mock_client,
        )
        call_kwargs = mock_client.roles.create.call_args.kwargs
        assert call_kwargs["description"] == "A test role"

    def test_create_requires_at_least_one_permission(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Create without --permissions should exit non-zero and not call the SDK."""
        result = _invoke(
            ["roles", "create", "--name", "My Role"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.roles.create.assert_not_called()

    def test_create_invalid_permission_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Invalid permission string should cause the command to exit non-zero."""
        result = _invoke(
            [
                "roles",
                "create",
                "--name",
                "My Role",
                "--permissions",
                "NOT_A_REAL_PERMISSION",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.roles.create.assert_not_called()

    def test_create_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error on create should cause the command to exit non-zero."""
        mock_client.roles.create.side_effect = RuntimeError(
            "Name already exists"
        )
        result = _invoke(
            [
                "roles",
                "create",
                "--name",
                "Dup",
                "--permissions",
                "PROJECT_READ",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax roles update
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestUpdateRole:
    """Tests for the `ax roles update` command."""

    def test_update_name_only(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Update with --name only should set name and leave permissions as None."""
        mock_client.roles.update.return_value = _make_role(name="New Name")
        result = _invoke(
            [
                "roles",
                "update",
                _ROLE_ID,
                "--name",
                "New Name",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.roles.update.call_args.kwargs
        assert call_kwargs["role"] == _ROLE_ID
        assert call_kwargs["name"] == "New Name"
        assert call_kwargs["permissions"] is None

    def test_update_permissions_replaces_all(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--permissions flag should replace the full permission set on the role."""
        mock_client.roles.update.return_value = _make_role()
        _invoke(
            [
                "roles",
                "update",
                _ROLE_ID,
                "--permissions",
                "PROJECT_READ,DATASET_READ",
            ],
            mock_config,
            mock_client,
        )
        call_kwargs = mock_client.roles.update.call_args.kwargs
        assert call_kwargs["permissions"] is not None
        assert len(call_kwargs["permissions"]) == 2

    def test_update_requires_at_least_one_field(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Update without any fields should exit non-zero and not call the SDK."""
        result = _invoke(
            ["roles", "update", _ROLE_ID],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.roles.update.assert_not_called()

    def test_update_invalid_permission_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Invalid permission in --permissions should cause the command to exit non-zero."""
        result = _invoke(
            ["roles", "update", _ROLE_ID, "--permissions", "FAKE_PERM"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.roles.update.assert_not_called()

    def test_update_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error on update should cause the command to exit non-zero."""
        mock_client.roles.update.side_effect = RuntimeError("Not found")
        result = _invoke(
            ["roles", "update", _ROLE_ID, "--name", "X"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax roles delete
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDeleteRole:
    """Tests for the `ax roles delete` command."""

    def test_delete_force_skips_confirmation(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--force flag should skip the confirmation prompt and call the SDK."""
        mock_client.roles.delete.return_value = None
        result = _invoke(
            ["roles", "delete", _ROLE_ID, "--force"],
            mock_config,
            mock_client,
        )
        assert result.exit_code == 0, result.output
        mock_client.roles.delete.assert_called_once_with(role=_ROLE_ID)

    def test_delete_confirms_yes_calls_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Answering 'y' to the confirmation prompt should call the SDK."""
        mock_client.roles.delete.return_value = None
        result = _invoke(
            ["roles", "delete", _ROLE_ID],
            mock_config,
            mock_client,
            cli_input="y\n",
        )
        assert result.exit_code == 0, result.output
        assert "permanently delete" in result.output
        mock_client.roles.delete.assert_called_once_with(role=_ROLE_ID)

    def test_delete_declines_does_not_call_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Answering 'n' to the confirmation prompt should abort without calling the SDK."""
        result = _invoke(
            ["roles", "delete", _ROLE_ID],
            mock_config,
            mock_client,
            cli_input="n\n",
        )
        assert result.exit_code == 0
        mock_client.roles.delete.assert_not_called()

    def test_delete_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error on delete should cause the command to exit non-zero."""
        mock_client.roles.delete.side_effect = RuntimeError("Not found")
        result = _invoke(
            ["roles", "delete", _ROLE_ID, "--force"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
