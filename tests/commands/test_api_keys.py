"""Tests for api-keys CLI commands."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from arize.api_keys.types import ApiKeySpaceRole, ApiKeyStatus, ApiKeyType
from typer.testing import CliRunner, Result

from ax.cli import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers to build realistic SDK response objects
# ---------------------------------------------------------------------------

_KEY_ID = "ak_test_1"
_CREATED_AT = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_api_key_list_response(*keys: MagicMock) -> MagicMock:
    """Build an ApiKeysList200Response mock."""
    mock = MagicMock()
    mock.api_keys = list(keys)
    mock.pagination.has_more = False
    return mock


def _make_api_key_redacted(
    key_id: str = _KEY_ID,
    name: str = "My Key",
    last_used_at: datetime | None = None,
) -> MagicMock:
    """Build a minimal ApiKeyRedacted mock (listing)."""
    mock = MagicMock()
    mock.id = key_id
    mock.name = name
    mock.last_used_at = last_used_at
    return mock


def _make_api_key(
    key_id: str = _KEY_ID,
    name: str = "My Key",
    key_value: str = "arize_sk_test_abc123",
) -> MagicMock:
    """Build an ApiKey mock (contains raw key value)."""
    mock = MagicMock()
    mock.id = key_id
    mock.name = name
    mock.key = key_value
    return mock


# ---------------------------------------------------------------------------
# Shared mock setup
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a mock ArizeClient with api_keys subclient pre-wired."""
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
            "ax.commands.api_keys.make_client",
            return_value=(mock_client, mock_config),
        ),
    ):
        return runner.invoke(app, args, input=cli_input)


# ---------------------------------------------------------------------------
# ax api-keys list
# ---------------------------------------------------------------------------


class TestListApiKeys:
    """Tests for `ax api-keys list`."""

    def test_list_returns_keys_in_output(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that listed keys appear in the output."""
        mock_client.api_keys.list.return_value = _make_api_key_list_response(
            _make_api_key_redacted(name="Alpha"),
            _make_api_key_redacted(name="Beta"),
        )

        result = _invoke(
            ["api-keys", "list", "--output", "json"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output

    def test_list_passes_filters_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --key-type, --status, --limit, --cursor are forwarded."""
        mock_client.api_keys.list.return_value = _make_api_key_list_response()

        _invoke(
            [
                "api-keys",
                "list",
                "--key-type",
                "SERVICE",
                "--status",
                "ACTIVE",
                "--limit",
                "5",
                "--cursor",
                "tok",
            ],
            mock_config,
            mock_client,
        )

        mock_client.api_keys.list.assert_called_once_with(
            key_type=ApiKeyType.SERVICE,
            status=ApiKeyStatus.ACTIVE,
            limit=5,
            cursor="tok",
        )

    def test_list_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error results in a non-zero exit code."""
        mock_client.api_keys.list.side_effect = RuntimeError("API error")
        result = _invoke(["api-keys", "list"], mock_config, mock_client)
        assert result.exit_code != 0

    def test_list_invalid_key_type_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an invalid --key-type fails Click/Typer validation."""
        result = _invoke(
            ["api-keys", "list", "--key-type", "admin"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.api_keys.list.assert_not_called()

    def test_list_invalid_status_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an invalid --status fails Click/Typer validation."""
        result = _invoke(
            ["api-keys", "list", "--status", "pending"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.api_keys.list.assert_not_called()


# ---------------------------------------------------------------------------
# ax api-keys create
# ---------------------------------------------------------------------------


class TestCreateApiKey:
    """Tests for `ax api-keys create`."""

    def test_create_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that create passes name to the SDK."""
        mock_client.api_keys.create.return_value = _make_api_key(
            name="Prod Key"
        )

        result = _invoke(
            [
                "api-keys",
                "create",
                "--name",
                "Prod Key",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.api_keys.create.call_args.kwargs
        assert call_kwargs["name"] == "Prod Key"

    def test_create_space_flag_not_accepted(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--space is not accepted by create (use create-service-key instead)."""
        result = _invoke(
            [
                "api-keys",
                "create",
                "--name",
                "Key",
                "--space",
                "my-space",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code != 0
        mock_client.api_keys.create.assert_not_called()

    def test_create_space_id_flag_no_longer_accepted(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--space-id should no longer be accepted (renamed to --space)."""
        result = _invoke(
            ["api-keys", "create", "--name", "Key", "--space-id", "sp-123"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.api_keys.create.assert_not_called()

    def test_create_displays_save_warning(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that a 'save this key' warning appears after creating a key."""
        mock_client.api_keys.create.return_value = _make_api_key()

        result = _invoke(
            [
                "api-keys",
                "create",
                "--name",
                "My Key",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        assert "Save this API key now" in result.output

    def test_create_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error during create causes a non-zero exit."""
        mock_client.api_keys.create.side_effect = RuntimeError("Forbidden")
        result = _invoke(
            ["api-keys", "create", "--name", "Key"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax api-keys create-service-key
# ---------------------------------------------------------------------------


class TestCreateServiceApiKey:
    """Tests for `ax api-keys create-service-key`."""

    def test_create_service_key_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Happy path: name, space, and optional role are forwarded to the SDK."""
        mock_client.api_keys.create_service_key.return_value = _make_api_key(
            name="Svc Key"
        )

        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Svc Key",
                "--space",
                "my-space",
                "--space-role",
                "MEMBER",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.api_keys.create_service_key.call_args.kwargs
        assert call_kwargs["name"] == "Svc Key"
        assert call_kwargs["space"] == "my-space"
        assert call_kwargs["space_role"] == ApiKeySpaceRole.MEMBER

    def test_create_service_key_missing_space_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--space is required; omitting it must fail."""
        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Svc Key",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.api_keys.create_service_key.assert_not_called()

    def test_create_service_key_invalid_space_role_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Invalid --space-role value fails Typer validation."""
        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Svc Key",
                "--space",
                "my-space",
                "--space-role",
                "superadmin",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.api_keys.create_service_key.assert_not_called()

    def test_create_service_key_displays_save_warning(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """A 'save this key' warning must appear after creating a service key."""
        mock_client.api_keys.create_service_key.return_value = _make_api_key()

        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "My Key",
                "--space",
                "my-space",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        assert "Save this API key now" in result.output

    def test_create_service_key_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """SDK error during create-service-key must produce a non-zero exit."""
        mock_client.api_keys.create_service_key.side_effect = RuntimeError(
            "Forbidden"
        )
        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Svc Key",
                "--space",
                "my-space",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax api-keys revoke
# ---------------------------------------------------------------------------


class TestRevokeApiKey:
    """Tests for `ax api-keys revoke <id>`."""

    def test_revoke_force_skips_confirmation(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --force bypasses the prompt and revokes the key."""
        mock_client.api_keys.revoke.return_value = None

        result = _invoke(
            ["api-keys", "revoke", _KEY_ID, "--force"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.api_keys.revoke.assert_called_once_with(api_key_id=_KEY_ID)

    def test_revoke_confirms_yes_calls_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that confirming the prompt proceeds with revocation."""
        mock_client.api_keys.revoke.return_value = None

        result = _invoke(
            ["api-keys", "revoke", _KEY_ID],
            mock_config,
            mock_client,
            cli_input="y\n",
        )

        assert result.exit_code == 0, result.output
        assert "permanently revoke" in result.output
        mock_client.api_keys.revoke.assert_called_once_with(api_key_id=_KEY_ID)

    def test_revoke_declines_does_not_call_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that declining the confirmation leaves the key untouched."""
        result = _invoke(
            ["api-keys", "revoke", _KEY_ID],
            mock_config,
            mock_client,
            cli_input="n\n",
        )

        assert result.exit_code == 0
        mock_client.api_keys.revoke.assert_not_called()

    def test_revoke_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error during revoke causes a non-zero exit."""
        mock_client.api_keys.revoke.side_effect = RuntimeError("Not found")
        result = _invoke(
            ["api-keys", "revoke", _KEY_ID, "--force"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax api-keys refresh
# ---------------------------------------------------------------------------


class TestRefreshApiKey:
    """Tests for `ax api-keys refresh <id>`."""

    def test_refresh_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that refresh passes api_key_id to the SDK."""
        mock_client.api_keys.refresh.return_value = _make_api_key()

        result = _invoke(
            ["api-keys", "refresh", _KEY_ID, "--output", "json"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.api_keys.refresh.assert_called_once_with(
            api_key_id=_KEY_ID,
            expires_at=None,
            grace_period_seconds=None,
        )

    def test_refresh_displays_save_warning(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that a 'save this key' warning appears after refreshing."""
        mock_client.api_keys.refresh.return_value = _make_api_key()

        result = _invoke(
            ["api-keys", "refresh", _KEY_ID, "--output", "json"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        assert "Save this API key now" in result.output

    def test_refresh_passes_expires_at(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --expires-at is parsed and forwarded."""
        mock_client.api_keys.refresh.return_value = _make_api_key()

        _invoke(
            [
                "api-keys",
                "refresh",
                _KEY_ID,
                "--expires-at",
                "2025-12-31T00:00:00",
            ],
            mock_config,
            mock_client,
        )

        call_kwargs = mock_client.api_keys.refresh.call_args.kwargs
        assert call_kwargs["expires_at"] == datetime(2025, 12, 31, 0, 0, 0)

    def test_refresh_invalid_expires_at_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an invalid --expires-at causes a non-zero exit."""
        result = _invoke(
            ["api-keys", "refresh", _KEY_ID, "--expires-at", "not-a-date"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0

    def test_refresh_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error during refresh causes a non-zero exit."""
        mock_client.api_keys.refresh.side_effect = RuntimeError("Not found")
        result = _invoke(
            ["api-keys", "refresh", _KEY_ID],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0

    def test_refresh_passes_grace_period_seconds(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --grace-period-seconds is forwarded to the SDK."""
        mock_client.api_keys.refresh.return_value = _make_api_key()

        _invoke(
            [
                "api-keys",
                "refresh",
                _KEY_ID,
                "--grace-period-seconds",
                "300",
            ],
            mock_config,
            mock_client,
        )

        call_kwargs = mock_client.api_keys.refresh.call_args.kwargs
        assert call_kwargs["grace_period_seconds"] == 300

    def test_refresh_grace_period_seconds_defaults_to_none(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that grace_period_seconds defaults to None when omitted."""
        mock_client.api_keys.refresh.return_value = _make_api_key()

        _invoke(
            ["api-keys", "refresh", _KEY_ID, "--output", "json"],
            mock_config,
            mock_client,
        )

        call_kwargs = mock_client.api_keys.refresh.call_args.kwargs
        assert call_kwargs["grace_period_seconds"] is None
