"""Tests for role-bindings CLI commands."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from arize.role_bindings.types import RoleBindingResourceType
from typer.testing import CliRunner, Result

from ax.cli import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers to build realistic SDK response objects
# ---------------------------------------------------------------------------

_BINDING_ID = "role_binding_test_1"
_USER_ID = "VXNlcjoxMjM="
_ROLE_ID = "Um9sZTo0NTY="
_RESOURCE_ID = "UHJvamVjdDoxMjM="
_CREATED_AT = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_role_binding_list_response(*bindings: MagicMock) -> MagicMock:
    """Build a RoleBindingsList200Response mock."""
    mock = MagicMock()
    mock.role_bindings = list(bindings)
    mock.pagination.has_more = False
    return mock


def _make_role_binding(
    binding_id: str = _BINDING_ID,
    user_id: str = _USER_ID,
    role_id: str = _ROLE_ID,
    resource_id: str = _RESOURCE_ID,
) -> MagicMock:
    """Build a minimal RoleBinding mock."""
    mock = MagicMock()
    mock.id = binding_id
    mock.user_id = user_id
    mock.role_id = role_id
    mock.resource_type = "PROJECT"
    mock.resource_id = resource_id
    mock.created_at = _CREATED_AT
    mock.updated_at = _CREATED_AT
    return mock


# ---------------------------------------------------------------------------
# Shared mock setup
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a mock ArizeClient with role_bindings subclient pre-wired."""
    return MagicMock()


@pytest.fixture
def mock_config() -> MagicMock:
    """Return a mock Config whose output.format is 'json'."""
    config = MagicMock()
    config.output.format = "json"
    return config


def _invoke(
    args: list[str],
    mock_config: MagicMock,
    mock_client: MagicMock,
    cli_input: str | None = None,
) -> Result:
    """Invoke the CLI app with standard mocks."""
    with (
        patch(
            "ax.commands.role_bindings.make_client",
            return_value=(mock_client, mock_config),
        ),
    ):
        return runner.invoke(app, args, input=cli_input)


# ---------------------------------------------------------------------------
# ax role-bindings list
# ---------------------------------------------------------------------------


class TestListRoleBindings:
    """Tests for `ax role-bindings list`."""

    def test_list_returns_bindings_in_output(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that listed bindings appear in the output."""
        mock_client.role_bindings.list.return_value = (
            _make_role_binding_list_response(
                _make_role_binding(),
                _make_role_binding(binding_id="role_binding_test_2"),
            )
        )

        result = _invoke(
            [
                "role-bindings",
                "list",
                "--resource-type",
                "PROJECT",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output

    def test_list_passes_filters_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --resource-type, --user-id, --limit, --cursor are forwarded."""
        mock_client.role_bindings.list.return_value = (
            _make_role_binding_list_response()
        )

        _invoke(
            [
                "role-bindings",
                "list",
                "--resource-type",
                "SPACE",
                "--user-id",
                _USER_ID,
                "--limit",
                "5",
                "--cursor",
                "tok",
            ],
            mock_config,
            mock_client,
        )

        mock_client.role_bindings.list.assert_called_once_with(
            resource_type=RoleBindingResourceType.SPACE,
            user_id=_USER_ID,
            limit=5,
            cursor="tok",
        )

    def test_list_resource_type_required(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that omitting --resource-type fails validation."""
        result = _invoke(
            ["role-bindings", "list"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.role_bindings.list.assert_not_called()

    def test_list_invalid_resource_type_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an invalid --resource-type fails Typer validation."""
        result = _invoke(
            ["role-bindings", "list", "--resource-type", "INVALID"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.role_bindings.list.assert_not_called()

    def test_list_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error results in a non-zero exit code."""
        mock_client.role_bindings.list.side_effect = RuntimeError("API error")
        result = _invoke(
            ["role-bindings", "list", "--resource-type", "PROJECT"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax role-bindings create
# ---------------------------------------------------------------------------


class TestCreateRoleBinding:
    """Tests for `ax role-bindings create`."""

    def test_create_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that create passes all params to the SDK."""
        mock_client.role_bindings.create.return_value = _make_role_binding()

        result = _invoke(
            [
                "role-bindings",
                "create",
                "--user-id",
                _USER_ID,
                "--role-id",
                _ROLE_ID,
                "--resource-type",
                "PROJECT",
                "--resource-id",
                _RESOURCE_ID,
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.role_bindings.create.call_args.kwargs
        assert call_kwargs["user_id"] == _USER_ID
        assert call_kwargs["role_id"] == _ROLE_ID
        assert call_kwargs["resource_id"] == _RESOURCE_ID

    def test_create_invalid_resource_type_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an invalid --resource-type fails Typer validation."""
        result = _invoke(
            [
                "role-bindings",
                "create",
                "--user-id",
                _USER_ID,
                "--role-id",
                _ROLE_ID,
                "--resource-type",
                "INVALID",
                "--resource-id",
                _RESOURCE_ID,
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.role_bindings.create.assert_not_called()

    def test_create_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error during create causes a non-zero exit."""
        mock_client.role_bindings.create.side_effect = RuntimeError("Forbidden")
        result = _invoke(
            [
                "role-bindings",
                "create",
                "--user-id",
                _USER_ID,
                "--role-id",
                _ROLE_ID,
                "--resource-type",
                "SPACE",
                "--resource-id",
                _RESOURCE_ID,
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax role-bindings get
# ---------------------------------------------------------------------------


class TestGetRoleBinding:
    """Tests for `ax role-bindings get <binding_id>`."""

    def test_get_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that get passes binding_id to the SDK."""
        mock_client.role_bindings.get.return_value = _make_role_binding()

        result = _invoke(
            ["role-bindings", "get", _BINDING_ID, "--output", "json"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.role_bindings.get.assert_called_once_with(
            binding_id=_BINDING_ID,
        )

    def test_get_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error during get causes a non-zero exit."""
        mock_client.role_bindings.get.side_effect = RuntimeError("Not found")
        result = _invoke(
            ["role-bindings", "get", _BINDING_ID],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax role-bindings update
# ---------------------------------------------------------------------------


class TestUpdateRoleBinding:
    """Tests for `ax role-bindings update <binding_id>`."""

    def test_update_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that update passes binding_id and role_id to the SDK."""
        new_role_id = "Um9sZTo3ODk="
        mock_client.role_bindings.update.return_value = _make_role_binding(
            role_id=new_role_id
        )

        result = _invoke(
            [
                "role-bindings",
                "update",
                _BINDING_ID,
                "--role-id",
                new_role_id,
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.role_bindings.update.assert_called_once_with(
            binding_id=_BINDING_ID,
            role_id=new_role_id,
        )

    def test_update_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error during update causes a non-zero exit."""
        mock_client.role_bindings.update.side_effect = RuntimeError("Not found")
        result = _invoke(
            ["role-bindings", "update", _BINDING_ID, "--role-id", _ROLE_ID],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax role-bindings delete
# ---------------------------------------------------------------------------


class TestDeleteRoleBinding:
    """Tests for `ax role-bindings delete <binding_id>`."""

    def test_delete_force_skips_confirmation(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --force bypasses the prompt and deletes the binding."""
        mock_client.role_bindings.delete.return_value = None

        result = _invoke(
            ["role-bindings", "delete", _BINDING_ID, "--force"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.role_bindings.delete.assert_called_once_with(
            binding_id=_BINDING_ID,
        )

    def test_delete_confirms_yes_calls_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that confirming the prompt proceeds with deletion."""
        mock_client.role_bindings.delete.return_value = None

        result = _invoke(
            ["role-bindings", "delete", _BINDING_ID],
            mock_config,
            mock_client,
            cli_input="y\n",
        )

        assert result.exit_code == 0, result.output
        assert "permanently delete" in result.output
        mock_client.role_bindings.delete.assert_called_once_with(
            binding_id=_BINDING_ID,
        )

    def test_delete_declines_does_not_call_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that declining the confirmation leaves the binding untouched."""
        result = _invoke(
            ["role-bindings", "delete", _BINDING_ID],
            mock_config,
            mock_client,
            cli_input="n\n",
        )

        assert result.exit_code == 0
        mock_client.role_bindings.delete.assert_not_called()

    def test_delete_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error during delete causes a non-zero exit."""
        mock_client.role_bindings.delete.side_effect = RuntimeError("Not found")
        result = _invoke(
            ["role-bindings", "delete", _BINDING_ID, "--force"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
