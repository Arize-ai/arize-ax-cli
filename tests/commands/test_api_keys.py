"""Tests for api-keys CLI commands."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from arize.api_keys.types import (
    ApiKeyStatus,
    ApiKeyType,
    OrgBinding,
    SpaceBinding,
)
from typer.testing import CliRunner, Result

from ax.cli import app
from ax.core.exceptions import APIError, FileIOError

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

    def test_create_displays_save_warning_when_printed(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """A key printed to the terminal warns that it won't be shown again."""
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

    def test_create_writes_key_to_env_file(
        self, mock_config: MagicMock, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """--env-file replaces an existing user-key assignment."""
        mock_client.api_keys.create.return_value = _make_api_key(
            key_value="new-user-key"
        )
        dotenv_path = tmp_path / ".env"
        dotenv_path.write_text('export ARIZE_API_KEY="old-key" # current\n')

        result = _invoke(
            [
                "api-keys",
                "create",
                "--name",
                "My Key",
                "--env-file",
                str(dotenv_path),
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        assert dotenv_path.read_text() == (
            'export ARIZE_API_KEY="new-user-key" # current\n'
        )
        assert "API key written to" in result.output
        assert dotenv_path.name in "".join(result.output.splitlines())
        assert "new-user-key" not in result.output
        assert "Save this API key now" not in result.output

    def test_create_output_file_suppresses_save_warning(
        self, mock_config: MagicMock, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """A key persisted to an --output file needs no save warning."""
        mock_client.api_keys.create.return_value = _make_api_key()
        output_path = tmp_path / "created-key.json"

        with patch("ax.commands.api_keys.output_data"):
            result = _invoke(
                [
                    "api-keys",
                    "create",
                    "--name",
                    "My Key",
                    "--output",
                    str(output_path),
                ],
                mock_config,
                mock_client,
            )

        assert result.exit_code == 0, result.output
        assert "Save this API key now" not in result.output

    def test_create_writes_to_env_and_output_file(
        self, mock_config: MagicMock, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """--env-file and an --output file both receive the created key."""
        mock_client.api_keys.create.return_value = _make_api_key(
            key_value="new-user-key"
        )
        dotenv_path = tmp_path / ".env"
        output_path = tmp_path / "created-key.json"

        with patch("ax.commands.api_keys.output_data") as output_data:
            result = _invoke(
                [
                    "api-keys",
                    "create",
                    "--name",
                    "My Key",
                    "--env-file",
                    str(dotenv_path),
                    "--output",
                    str(output_path),
                ],
                mock_config,
                mock_client,
            )

        assert result.exit_code == 0, result.output
        assert dotenv_path.read_text() == "ARIZE_API_KEY=new-user-key\n"
        output_data.assert_called_once_with(
            mock_client.api_keys.create.return_value,
            format_type="json",
            output_file=str(output_path),
        )

    def test_create_invalid_env_file_does_not_create_key(
        self, mock_config: MagicMock, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Invalid --env-file targets fail before creating a nonrecoverable key."""
        result = _invoke(
            [
                "api-keys",
                "create",
                "--name",
                "My Key",
                "--env-file",
                str(tmp_path / "key.txt"),
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code != 0
        assert "dotenv filename" in result.output
        mock_client.api_keys.create.assert_not_called()

    def test_create_symlink_env_file_does_not_create_key(
        self, mock_config: MagicMock, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """A symlinked --env-file target is rejected before the key is created."""
        real_target = tmp_path / "secrets.env"
        real_target.write_text("ARIZE_API_KEY=old-key\n")
        symlink_path = tmp_path / ".env"
        symlink_path.symlink_to(real_target)

        result = _invoke(
            [
                "api-keys",
                "create",
                "--name",
                "My Key",
                "--env-file",
                str(symlink_path),
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code != 0
        assert "symlink" in result.output
        mock_client.api_keys.create.assert_not_called()
        assert symlink_path.is_symlink()

    def test_create_env_write_failure_revokes_key(
        self, mock_config: MagicMock, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """A dotenv write failure revokes the orphaned key without printing it."""
        mock_client.api_keys.create.return_value = _make_api_key(
            key_value="new-user-key"
        )

        with patch(
            "ax.commands.api_keys.write_api_key_to_dotenv",
            side_effect=FileIOError("permission denied"),
        ):
            result = _invoke(
                [
                    "api-keys",
                    "create",
                    "--name",
                    "My Key",
                    "--env-file",
                    str(tmp_path / ".env"),
                ],
                mock_config,
                mock_client,
            )

        assert result.exit_code != 0
        assert "permission denied" in result.output
        assert "created successfully" not in result.output
        assert "new-user-key" not in result.output
        mock_client.api_keys.revoke.assert_called_once_with(api_key_id=_KEY_ID)

    def test_create_env_write_interrupted_revokes_key(
        self, mock_config: MagicMock, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """An interrupted dotenv write revokes the key and exits as cancelled."""
        mock_client.api_keys.create.return_value = _make_api_key(
            key_value="new-user-key"
        )

        with patch(
            "ax.commands.api_keys.write_api_key_to_dotenv",
            side_effect=KeyboardInterrupt,
        ):
            result = _invoke(
                [
                    "api-keys",
                    "create",
                    "--name",
                    "My Key",
                    "--env-file",
                    str(tmp_path / ".env"),
                ],
                mock_config,
                mock_client,
            )

        assert result.exit_code == 130
        assert "Operation cancelled by user" in result.output
        assert "new-user-key" not in result.output
        mock_client.api_keys.revoke.assert_called_once_with(api_key_id=_KEY_ID)

    def test_create_env_write_and_revoke_failure_reports_key_id(
        self, mock_config: MagicMock, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """When rollback fails too, the key id and manual revoke are surfaced."""
        mock_client.api_keys.create.return_value = _make_api_key(
            key_value="new-user-key"
        )
        mock_client.api_keys.revoke.side_effect = APIError("network down")

        with patch(
            "ax.commands.api_keys.write_api_key_to_dotenv",
            side_effect=FileIOError("permission denied"),
        ):
            result = _invoke(
                [
                    "api-keys",
                    "create",
                    "--name",
                    "My Key",
                    "--env-file",
                    str(tmp_path / ".env"),
                ],
                mock_config,
                mock_client,
            )

        assert result.exit_code != 0
        collapsed = " ".join(result.output.split())
        assert f"ax api-keys revoke {_KEY_ID}" in collapsed
        assert "new-user-key" not in result.output

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


_ASSIGNMENTS_ONE = json.dumps(
    [{"org_id": "O1", "spaces": [{"space": "my-space", "role": "MEMBER"}]}]
)

_ASSIGNMENTS_MULTI = json.dumps(
    [
        {
            "org_id": "O1",
            "role": "READ_ONLY",
            "spaces": [
                {"space": "prod", "role": "MEMBER"},
                {"space": "staging"},
            ],
        },
        {
            "org_id": "O2",
            "spaces": [{"space": "sandbox", "role": "ADMIN"}],
        },
    ]
)


class TestCreateServiceApiKey:
    """Tests for `ax api-keys create-service-key`."""

    def test_create_service_key_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Happy path: name and assignments build the expected OrgBinding list."""
        mock_client.api_keys.create_service_key.return_value = _make_api_key(
            name="Svc Key"
        )

        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Svc Key",
                "--assignments",
                _ASSIGNMENTS_ONE,
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.api_keys.create_service_key.call_args.kwargs
        assert call_kwargs["name"] == "Svc Key"
        orgs: list[OrgBinding] = call_kwargs["orgs"]
        assert len(orgs) == 1
        assert orgs[0].org_id == "O1"
        assert len(orgs[0].spaces) == 1
        space: SpaceBinding = orgs[0].spaces[0]
        assert space.space == "my-space"
        assert space.role is not None
        assert space.role.actual_instance.name == "MEMBER"

    def test_create_service_key_writes_key_to_env_file(
        self, mock_config: MagicMock, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """--env-file appends a newly created service key."""
        mock_client.api_keys.create_service_key.return_value = _make_api_key(
            key_value="new-service-key"
        )
        dotenv_path = tmp_path / ".env.production.local"
        dotenv_path.write_text("OTHER=value")

        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Svc Key",
                "--assignments",
                _ASSIGNMENTS_ONE,
                "--env-file",
                str(dotenv_path),
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        assert (
            dotenv_path.read_text()
            == "OTHER=value\nARIZE_API_KEY=new-service-key\n"
        )
        assert "Service API key written to" in result.output
        assert dotenv_path.name in "".join(result.output.splitlines())
        assert "new-service-key" not in result.output
        assert "Save this API key now" not in result.output

    def test_create_service_key_writes_to_env_and_output_file(
        self, mock_config: MagicMock, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """Service-key creation writes to both requested file destinations."""
        mock_client.api_keys.create_service_key.return_value = _make_api_key(
            key_value="new-service-key"
        )
        dotenv_path = tmp_path / ".env.local"
        output_path = tmp_path / "service-key.json"

        with patch("ax.commands.api_keys.output_data") as output_data:
            result = _invoke(
                [
                    "api-keys",
                    "create-service-key",
                    "--name",
                    "Svc Key",
                    "--assignments",
                    _ASSIGNMENTS_ONE,
                    "--env-file",
                    str(dotenv_path),
                    "--output",
                    str(output_path),
                ],
                mock_config,
                mock_client,
            )

        assert result.exit_code == 0, result.output
        assert dotenv_path.read_text() == "ARIZE_API_KEY=new-service-key\n"
        output_data.assert_called_once_with(
            mock_client.api_keys.create_service_key.return_value,
            format_type="json",
            output_file=str(output_path),
        )

    def test_create_service_key_env_write_failure_revokes_key(
        self, mock_config: MagicMock, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """A service-key dotenv write failure revokes the orphaned key."""
        mock_client.api_keys.create_service_key.return_value = _make_api_key(
            key_value="new-service-key"
        )

        with patch(
            "ax.commands.api_keys.write_api_key_to_dotenv",
            side_effect=FileIOError("permission denied"),
        ):
            result = _invoke(
                [
                    "api-keys",
                    "create-service-key",
                    "--name",
                    "Svc Key",
                    "--assignments",
                    _ASSIGNMENTS_ONE,
                    "--env-file",
                    str(tmp_path / ".env"),
                ],
                mock_config,
                mock_client,
            )

        assert result.exit_code != 0
        assert "permission denied" in result.output
        assert "created successfully" not in result.output
        assert "new-service-key" not in result.output
        mock_client.api_keys.revoke.assert_called_once_with(api_key_id=_KEY_ID)

    def test_create_service_key_env_and_revoke_failure_reports_key_id(
        self, mock_config: MagicMock, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """When service-key rollback fails, the manual revoke is surfaced."""
        mock_client.api_keys.create_service_key.return_value = _make_api_key(
            key_value="new-service-key"
        )
        mock_client.api_keys.revoke.side_effect = APIError("network down")

        with patch(
            "ax.commands.api_keys.write_api_key_to_dotenv",
            side_effect=FileIOError("permission denied"),
        ):
            result = _invoke(
                [
                    "api-keys",
                    "create-service-key",
                    "--name",
                    "Svc Key",
                    "--assignments",
                    _ASSIGNMENTS_ONE,
                    "--env-file",
                    str(tmp_path / ".env"),
                ],
                mock_config,
                mock_client,
            )

        assert result.exit_code != 0
        collapsed = " ".join(result.output.split())
        assert f"ax api-keys revoke {_KEY_ID}" in collapsed
        assert "new-service-key" not in result.output

    def test_create_service_key_multi_org_multi_space(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Multi-org/multi-space assignments build the correct nested structure."""
        mock_client.api_keys.create_service_key.return_value = _make_api_key()

        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Multi Key",
                "--assignments",
                _ASSIGNMENTS_MULTI,
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        orgs: list[OrgBinding] = (
            mock_client.api_keys.create_service_key.call_args.kwargs["orgs"]
        )
        assert len(orgs) == 2
        # First org: READ_ONLY at org level, two spaces
        assert orgs[0].org_id == "O1"
        assert orgs[0].role is not None
        assert orgs[0].role.actual_instance.name == "READ_ONLY"
        assert len(orgs[0].spaces) == 2
        assert orgs[0].spaces[0].space == "prod"
        assert orgs[0].spaces[1].space == "staging"
        assert orgs[0].spaces[1].role is None  # no role → None
        # Second org: no org role, one space
        assert orgs[1].org_id == "O2"
        assert orgs[1].role is None

    def test_create_service_key_account_role_forwarded(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--account-role is wrapped into a UserRoleAssignment."""
        mock_client.api_keys.create_service_key.return_value = _make_api_key()

        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Key",
                "--assignments",
                _ASSIGNMENTS_ONE,
                "--account-role",
                "MEMBER",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        account_role = mock_client.api_keys.create_service_key.call_args.kwargs[
            "account_role"
        ]
        assert account_role is not None
        assert account_role.actual_instance.name == "MEMBER"

    def test_create_service_key_no_account_role_passes_none(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Omitting --account-role passes account_role=None to the SDK."""
        mock_client.api_keys.create_service_key.return_value = _make_api_key()

        _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Key",
                "--assignments",
                _ASSIGNMENTS_ONE,
            ],
            mock_config,
            mock_client,
        )

        assert (
            mock_client.api_keys.create_service_key.call_args.kwargs[
                "account_role"
            ]
            is None
        )

    def test_create_service_key_assignments_from_file(
        self, mock_config: MagicMock, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """--assignments path/to/file.json reads the JSON from disk."""
        mock_client.api_keys.create_service_key.return_value = _make_api_key()
        assignments_file = tmp_path / "assignments.json"
        assignments_file.write_text(_ASSIGNMENTS_ONE)

        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "File Key",
                "--assignments",
                str(assignments_file),
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        orgs = mock_client.api_keys.create_service_key.call_args.kwargs["orgs"]
        assert orgs[0].org_id == "O1"

    def test_create_service_key_missing_assignments_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--assignments is required; omitting it must fail."""
        result = _invoke(
            ["api-keys", "create-service-key", "--name", "Svc Key"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.api_keys.create_service_key.assert_not_called()

    def test_create_service_key_invalid_json_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Malformed JSON in --assignments must produce a non-zero exit."""
        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Key",
                "--assignments",
                "{not json}",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.api_keys.create_service_key.assert_not_called()

    def test_create_service_key_empty_list_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """An empty assignments array must produce a non-zero exit."""
        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Key",
                "--assignments",
                "[]",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.api_keys.create_service_key.assert_not_called()

    def test_create_service_key_missing_org_id_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Binding entry without org_id must produce a non-zero exit."""
        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Key",
                "--assignments",
                json.dumps([{"spaces": [{"space": "prod"}]}]),
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.api_keys.create_service_key.assert_not_called()

    def test_create_service_key_empty_spaces_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Binding entry with empty spaces array must produce a non-zero exit."""
        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Key",
                "--assignments",
                json.dumps([{"org_id": "O1", "spaces": []}]),
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.api_keys.create_service_key.assert_not_called()

    def test_create_service_key_invalid_account_role_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Invalid --account-role value fails Typer validation."""
        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Key",
                "--assignments",
                _ASSIGNMENTS_ONE,
                "--account-role",
                "superadmin",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.api_keys.create_service_key.assert_not_called()

    def test_create_service_key_displays_save_warning_when_printed(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """A key printed to the terminal warns that it won't be shown again."""
        mock_client.api_keys.create_service_key.return_value = _make_api_key()

        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "My Key",
                "--assignments",
                _ASSIGNMENTS_ONE,
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
                "--assignments",
                _ASSIGNMENTS_ONE,
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0

    def test_create_service_key_nonexistent_file_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """A nonexistent file path must produce a clean non-zero exit."""
        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Key",
                "--assignments",
                "/tmp/does-not-exist-ax-test.json",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.api_keys.create_service_key.assert_not_called()

    def test_create_service_key_spaces_not_a_list_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Binding entry where 'spaces' is not a list must produce a non-zero exit."""
        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Key",
                "--assignments",
                json.dumps([{"org_id": "O1", "spaces": "not-a-list"}]),
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.api_keys.create_service_key.assert_not_called()

    def test_create_service_key_forwards_description_and_expires_at(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """--description and --expires-at are forwarded to the SDK."""
        mock_client.api_keys.create_service_key.return_value = _make_api_key()

        _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Key",
                "--assignments",
                _ASSIGNMENTS_ONE,
                "--description",
                "My service key",
                "--expires-at",
                "2030-01-01T00:00:00",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        kwargs = mock_client.api_keys.create_service_key.call_args.kwargs
        assert kwargs["description"] == "My service key"
        assert kwargs["expires_at"] == datetime(
            2030, 1, 1, 0, 0, 0, tzinfo=timezone.utc
        )

    def test_create_service_key_invalid_space_role_in_assignments_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """An invalid space role name in --assignments must produce a clean error."""
        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Key",
                "--assignments",
                json.dumps(
                    [
                        {
                            "org_id": "O1",
                            "spaces": [{"space": "prod", "role": "SUPERADMIN"}],
                        }
                    ]
                ),
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.api_keys.create_service_key.assert_not_called()

    def test_create_service_key_invalid_org_role_in_assignments_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """An invalid org role name in --assignments must produce a clean error."""
        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Key",
                "--assignments",
                json.dumps(
                    [
                        {
                            "org_id": "O1",
                            "role": "SUPERADMIN",
                            "spaces": [{"space": "prod"}],
                        }
                    ]
                ),
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.api_keys.create_service_key.assert_not_called()

    def test_create_service_key_non_array_assignments_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """A non-array JSON value in --assignments must produce a non-zero exit."""
        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Key",
                "--assignments",
                '"not a list"',
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.api_keys.create_service_key.assert_not_called()

    def test_create_service_key_space_binding_missing_space_field_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Space binding without 'space' field must produce a non-zero exit."""
        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Key",
                "--assignments",
                json.dumps([{"org_id": "O1", "spaces": [{"role": "MEMBER"}]}]),
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.api_keys.create_service_key.assert_not_called()

    def test_create_service_key_custom_space_role(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Custom space/org roles specified as objects are forwarded correctly."""
        mock_client.api_keys.create_service_key.return_value = _make_api_key()

        assignments = json.dumps(
            [
                {
                    "org_id": "O1",
                    "role": {"type": "CUSTOM", "id": "custom-org-role-id"},
                    "spaces": [
                        {
                            "space": "prod",
                            "role": {
                                "type": "CUSTOM",
                                "id": "custom-space-role-id",
                            },
                        }
                    ],
                }
            ]
        )

        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Custom Role Key",
                "--assignments",
                assignments,
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        orgs: list[OrgBinding] = (
            mock_client.api_keys.create_service_key.call_args.kwargs["orgs"]
        )
        assert orgs[0].role is not None
        assert orgs[0].role.actual_instance.id == "custom-org-role-id"
        assert orgs[0].spaces[0].role is not None
        assert (
            orgs[0].spaces[0].role.actual_instance.id == "custom-space-role-id"
        )

    def test_create_service_key_invalid_custom_role_missing_id_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Custom role without 'id' must produce a non-zero exit."""
        result = _invoke(
            [
                "api-keys",
                "create-service-key",
                "--name",
                "Key",
                "--assignments",
                json.dumps(
                    [
                        {
                            "org_id": "O1",
                            "spaces": [
                                {"space": "prod", "role": {"type": "CUSTOM"}}
                            ],
                        }
                    ]
                ),
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.api_keys.create_service_key.assert_not_called()


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

    def test_refresh_displays_save_warning_when_printed(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Refresh mints a new one-time key, so it warns when printed."""
        mock_client.api_keys.refresh.return_value = _make_api_key()

        result = _invoke(
            ["api-keys", "refresh", _KEY_ID, "--output", "json"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        assert "Save this API key now" in result.output

    def test_refresh_output_file_suppresses_save_warning(
        self, mock_config: MagicMock, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        """A refreshed key persisted to an --output file needs no warning."""
        mock_client.api_keys.refresh.return_value = _make_api_key()
        output_path = tmp_path / "refreshed-key.json"

        with patch("ax.commands.api_keys.output_data"):
            result = _invoke(
                ["api-keys", "refresh", _KEY_ID, "--output", str(output_path)],
                mock_config,
                mock_client,
            )

        assert result.exit_code == 0, result.output
        assert "Save this API key now" not in result.output

    def test_refresh_passes_expires_at(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that a naive --expires-at is forwarded as tz-aware UTC."""
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
        assert call_kwargs["expires_at"] == datetime(
            2025, 12, 31, 0, 0, 0, tzinfo=timezone.utc
        )

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
