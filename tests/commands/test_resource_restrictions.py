"""Tests for resource-restrictions CLI commands."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from arize.resource_restrictions.types import ResourceRestrictionType
from typer.testing import CliRunner, Result

from ax.cli import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers to build realistic SDK response objects
# ---------------------------------------------------------------------------

_RESOURCE_ID = "UHJvamVjdDoxMjM="
_CREATED_AT = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_resource_restriction(
    resource_id: str = _RESOURCE_ID,
) -> MagicMock:
    """Build a minimal ResourceRestriction mock."""
    mock = MagicMock()
    mock.resource_type = "PROJECT"
    mock.resource_id = resource_id
    mock.created_at = _CREATED_AT
    return mock


# ---------------------------------------------------------------------------
# Shared mock setup
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a mock ArizeClient with resource_restrictions subclient pre-wired."""
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
            "ax.commands.resource_restrictions.make_client",
            return_value=(mock_client, mock_config),
        ),
    ):
        return runner.invoke(app, args, input=cli_input)


# ---------------------------------------------------------------------------
# ax resource-restrictions list
# ---------------------------------------------------------------------------


class TestListResourceRestrictions:
    """Tests for `ax resource-restrictions list`."""

    def test_list_no_filters_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that list with no filters calls the SDK with defaults."""
        mock_response = MagicMock()
        mock_response.resource_restrictions = [_make_resource_restriction()]
        mock_client.resource_restrictions.list.return_value = mock_response

        result = _invoke(
            [
                "resource-restrictions",
                "list",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.resource_restrictions.list.assert_called_once_with(
            resource_type=None,
            limit=15,
            cursor=None,
        )

    def test_list_with_filters_forwards_arguments(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that list forwards resource_type, limit, and cursor verbatim."""
        mock_response = MagicMock()
        mock_response.resource_restrictions = [_make_resource_restriction()]
        mock_client.resource_restrictions.list.return_value = mock_response

        result = _invoke(
            [
                "resource-restrictions",
                "list",
                "--resource-type",
                "PROJECT",
                "--limit",
                "5",
                "--cursor",
                "abc",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.resource_restrictions.list.assert_called_once_with(
            resource_type=ResourceRestrictionType.PROJECT,
            limit=5,
            cursor="abc",
        )

    def test_list_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error during list causes a non-zero exit."""
        mock_client.resource_restrictions.list.side_effect = RuntimeError(
            "Internal error"
        )
        result = _invoke(
            [
                "resource-restrictions",
                "list",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax resource-restrictions restrict
# ---------------------------------------------------------------------------


class TestRestrictResource:
    """Tests for `ax resource-restrictions restrict`."""

    def test_restrict_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that restrict passes resource_id to the SDK."""
        mock_client.resource_restrictions.restrict.return_value = (
            _make_resource_restriction()
        )

        result = _invoke(
            [
                "resource-restrictions",
                "restrict",
                "--resource-id",
                _RESOURCE_ID,
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.resource_restrictions.restrict.assert_called_once_with(
            resource_id=_RESOURCE_ID,
        )

    def test_restrict_outputs_result(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that the restriction response is passed to output_data."""
        mock_client.resource_restrictions.restrict.return_value = (
            _make_resource_restriction()
        )

        result = _invoke(
            [
                "resource-restrictions",
                "restrict",
                "--resource-id",
                _RESOURCE_ID,
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output

    def test_restrict_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error results in a non-zero exit code."""
        mock_client.resource_restrictions.restrict.side_effect = RuntimeError(
            "Forbidden"
        )
        result = _invoke(
            [
                "resource-restrictions",
                "restrict",
                "--resource-id",
                _RESOURCE_ID,
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax resource-restrictions unrestrict
# ---------------------------------------------------------------------------


class TestUnrestrictResource:
    """Tests for `ax resource-restrictions unrestrict`."""

    def test_unrestrict_force_skips_confirmation(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --force bypasses the prompt and unrestricts the resource."""
        mock_client.resource_restrictions.unrestrict.return_value = None

        result = _invoke(
            [
                "resource-restrictions",
                "unrestrict",
                "--resource-id",
                _RESOURCE_ID,
                "--force",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.resource_restrictions.unrestrict.assert_called_once_with(
            resource_id=_RESOURCE_ID,
        )

    def test_unrestrict_confirms_yes_calls_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that confirming the prompt proceeds with unrestriction."""
        mock_client.resource_restrictions.unrestrict.return_value = None

        result = _invoke(
            [
                "resource-restrictions",
                "unrestrict",
                "--resource-id",
                _RESOURCE_ID,
            ],
            mock_config,
            mock_client,
            cli_input="y\n",
        )

        assert result.exit_code == 0, result.output
        assert "remove the restriction" in result.output
        mock_client.resource_restrictions.unrestrict.assert_called_once_with(
            resource_id=_RESOURCE_ID,
        )

    def test_unrestrict_declines_does_not_call_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that declining the confirmation leaves the resource untouched."""
        result = _invoke(
            [
                "resource-restrictions",
                "unrestrict",
                "--resource-id",
                _RESOURCE_ID,
            ],
            mock_config,
            mock_client,
            cli_input="n\n",
        )

        assert result.exit_code == 0
        mock_client.resource_restrictions.unrestrict.assert_not_called()

    def test_unrestrict_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error during unrestrict causes a non-zero exit."""
        mock_client.resource_restrictions.unrestrict.side_effect = RuntimeError(
            "Not found"
        )
        result = _invoke(
            [
                "resource-restrictions",
                "unrestrict",
                "--resource-id",
                _RESOURCE_ID,
                "--force",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
