"""Tests for annotation-configs CLI commands."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from arize._generated.api_client.models import (
    AnnotationConfig,
    AnnotationConfigsList200Response,
    CategoricalAnnotationConfig,
    CategoricalAnnotationValue,
    ContinuousAnnotationConfig,
    FreeformAnnotationConfig,
    OptimizationDirection,
    PaginationMetadata,
)
from arize.annotation_configs.types import AnnotationConfigType
from typer.testing import CliRunner, Result

from ax.cli import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers to build realistic SDK response objects
# ---------------------------------------------------------------------------

_CREATED_AT = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _freeform(
    id: str = "ac_free_1", name: str = "My Freeform"
) -> AnnotationConfig:
    return AnnotationConfig(
        actual_instance=FreeformAnnotationConfig(
            id=id,
            name=name,
            created_at=_CREATED_AT,
            space_id="sp_test",
            type="freeform",
        )
    )


def _continuous(
    id: str = "ac_cont_1", name: str = "My Score"
) -> AnnotationConfig:
    return AnnotationConfig(
        actual_instance=ContinuousAnnotationConfig(
            id=id,
            name=name,
            created_at=_CREATED_AT,
            space_id="sp_test",
            type="continuous",
            minimum_score=0.0,
            maximum_score=1.0,
        )
    )


def _categorical(
    id: str = "ac_cat_1", name: str = "My Verdict"
) -> AnnotationConfig:
    return AnnotationConfig(
        actual_instance=CategoricalAnnotationConfig(
            id=id,
            name=name,
            created_at=_CREATED_AT,
            space_id="sp_test",
            type="categorical",
            values=[
                CategoricalAnnotationValue(label="good"),
                CategoricalAnnotationValue(label="bad"),
            ],
        )
    )


def _list_response(
    *configs: AnnotationConfig, has_more: bool = False
) -> AnnotationConfigsList200Response:
    return AnnotationConfigsList200Response(
        annotation_configs=list(configs),
        pagination=PaginationMetadata(has_more=has_more),
    )


# ---------------------------------------------------------------------------
# Shared mock setup
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a mock ArizeClient with annotation_configs subclient pre-wired."""
    return MagicMock()


@pytest.fixture
def mock_config() -> MagicMock:
    """Return a mock Config whose output.format is 'json' (easiest to assert on)."""
    config = MagicMock()
    config.output.format = "json"
    return config


def _invoke(
    args: list[str],
    mock_config: MagicMock,
    mock_client: MagicMock,
    cli_input: str | None = None,
) -> Result:
    """Invoke the CLI app with standard mocks for ConfigManager, asdict, and ArizeClient."""
    with (
        patch(
            "ax.commands.annotation_configs.ConfigManager.load",
            return_value=mock_config,
        ),
        patch("ax.commands.annotation_configs.asdict", return_value={}),
        patch(
            "ax.commands.annotation_configs.ArizeClient",
            return_value=mock_client,
        ),
    ):
        return runner.invoke(app, args, input=cli_input)


# ---------------------------------------------------------------------------
# ax annotation-configs list
# ---------------------------------------------------------------------------


class TestListAnnotationConfigs:
    """Tests for `ax annotation-configs list`."""

    def test_list_returns_configs_in_output(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that listed configs appear in the JSON output."""
        mock_client.annotation_configs.list.return_value = _list_response(
            _freeform(name="Alpha"),
            _continuous(name="Beta"),
        )

        result = _invoke(
            ["annotation-configs", "list", "--output", "json"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        # The spinner prints an info line before the JSON in non-TTY mode,
        # so check for key substrings rather than parsing the whole output.
        assert "Alpha" in result.output
        assert "Beta" in result.output

    def test_list_passes_space_limit_cursor_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --space, --limit, --cursor are forwarded to the SDK call."""
        mock_client.annotation_configs.list.return_value = _list_response()

        _invoke(
            [
                "annotation-configs",
                "list",
                "--space",
                "sp_abc",
                "--limit",
                "5",
                "--cursor",
                "tok",
            ],
            mock_config,
            mock_client,
        )

        mock_client.annotation_configs.list.assert_called_once_with(
            name=None,
            space="sp_abc",
            limit=5,
            cursor="tok",
        )

    def test_list_name_filter_forwarded(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --name is forwarded to the SDK."""
        mock_client.annotation_configs.list.return_value = _list_response()

        _invoke(
            ["annotation-configs", "list", "--name", "quality"],
            mock_config,
            mock_client,
        )

        mock_client.annotation_configs.list.assert_called_once_with(
            name="quality",
            space=None,
            limit=15,
            cursor=None,
        )

    def test_list_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error results in a non-zero exit code."""
        mock_client.annotation_configs.list.side_effect = RuntimeError(
            "API error"
        )
        result = _invoke(
            ["annotation-configs", "list"], mock_config, mock_client
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax annotation-configs get
# ---------------------------------------------------------------------------


class TestGetAnnotationConfig:
    """Tests for `ax annotation-configs get <id>`."""

    def test_get_returns_config_in_output(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that the fetched config's data appears in the JSON output."""
        mock_client.annotation_configs.get.return_value = _freeform(
            id="ac_xyz", name="Special Config"
        )

        result = _invoke(
            ["annotation-configs", "get", "ac_xyz", "--output", "json"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        assert "ac_xyz" in result.output
        assert "Special Config" in result.output

    def test_get_calls_sdk_with_correct_id(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that the CLI passes the positional ID argument to the SDK."""
        mock_client.annotation_configs.get.return_value = _freeform(id="ac_123")
        _invoke(
            ["annotation-configs", "get", "ac_123"], mock_config, mock_client
        )
        mock_client.annotation_configs.get.assert_called_once_with(
            annotation_config="ac_123", space=None
        )

    def test_get_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error (e.g. 404) results in a non-zero exit."""
        mock_client.annotation_configs.get.side_effect = RuntimeError(
            "Not found"
        )
        result = _invoke(
            ["annotation-configs", "get", "ac_999"], mock_config, mock_client
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax annotation-configs create
# ---------------------------------------------------------------------------


class TestCreateAnnotationConfig:
    """Tests for `ax annotation-configs create`."""

    def test_create_freeform_returns_config_in_output(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that a newly created freeform config appears in JSON output."""
        mock_client.annotation_configs.create.return_value = _freeform(
            id="ac_new", name="Quality"
        )

        result = _invoke(
            [
                "annotation-configs",
                "create",
                "--name",
                "Quality",
                "--space",
                "sp_abc",
                "--type",
                "freeform",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        # The spinner prints an info line before the JSON in non-TTY mode,
        # so check for key substrings rather than parsing the whole output.
        assert "Quality" in result.output
        assert "ac_new" in result.output

    def test_create_freeform_calls_sdk_correctly(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that create passes the right type and no type-specific args for freeform."""
        mock_client.annotation_configs.create.return_value = _freeform()

        _invoke(
            [
                "annotation-configs",
                "create",
                "--name",
                "Q",
                "--space",
                "sp_abc",
                "--type",
                "freeform",
            ],
            mock_config,
            mock_client,
        )

        mock_client.annotation_configs.create.assert_called_once_with(
            name="Q",
            space="sp_abc",
            config_type=AnnotationConfigType.FREEFORM,
            minimum_score=None,
            maximum_score=None,
            values=None,
            optimization_direction=None,
        )

    def test_create_continuous_passes_score_range(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --min-score, --max-score, and --optimization-direction are forwarded."""
        mock_client.annotation_configs.create.return_value = _continuous(
            name="Score"
        )

        result = _invoke(
            [
                "annotation-configs",
                "create",
                "--name",
                "Score",
                "--space",
                "sp_abc",
                "--type",
                "continuous",
                "--min-score",
                "0",
                "--max-score",
                "1",
                "--optimization-direction",
                "maximize",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.annotation_configs.create.assert_called_once_with(
            name="Score",
            space="sp_abc",
            config_type=AnnotationConfigType.CONTINUOUS,
            minimum_score=0.0,
            maximum_score=1.0,
            values=None,
            optimization_direction=OptimizationDirection("maximize"),
        )

    def test_create_categorical_parses_comma_separated_values(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --value 'good' --value 'neutral' --value 'bad' is
        parsed into CategoricalAnnotationValue list.
        """  # noqa: D205
        mock_client.annotation_configs.create.return_value = _categorical(
            name="Verdict"
        )

        result = _invoke(
            [
                "annotation-configs",
                "create",
                "--name",
                "Verdict",
                "--space",
                "sp_abc",
                "--type",
                "categorical",
                "--value",
                "good",
                "--value",
                "neutral",
                "--value",
                "bad",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.annotation_configs.create.call_args.kwargs
        assert call_kwargs["config_type"] == AnnotationConfigType.CATEGORICAL
        assert call_kwargs["values"] == [
            CategoricalAnnotationValue(label="good"),
            CategoricalAnnotationValue(label="neutral"),
            CategoricalAnnotationValue(label="bad"),
        ]

    def test_create_invalid_optimization_direction_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an unrecognized --optimization-direction causes a non-zero exit."""
        result = _invoke(
            [
                "annotation-configs",
                "create",
                "--name",
                "Score",
                "--space",
                "sp_abc",
                "--type",
                "continuous",
                "--optimization-direction",
                "sideways",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0

    def test_create_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error during create causes a non-zero exit."""
        mock_client.annotation_configs.create.side_effect = RuntimeError(
            "Conflict"
        )

        result = _invoke(
            [
                "annotation-configs",
                "create",
                "--name",
                "Test",
                "--space",
                "sp_abc",
                "--type",
                "freeform",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax annotation-configs delete
# ---------------------------------------------------------------------------


class TestDeleteAnnotationConfig:
    """Tests for `ax annotation-configs delete <id>`."""

    def test_delete_force_skips_confirmation_and_calls_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that --force bypasses the prompt and deletes the config."""
        mock_client.annotation_configs.delete.return_value = None

        result = _invoke(
            ["annotation-configs", "delete", "ac_123", "--force"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        assert "ac_123" in result.output
        mock_client.annotation_configs.delete.assert_called_once_with(
            annotation_config="ac_123", space=None
        )

    def test_delete_confirms_yes_calls_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that confirming the prompt proceeds with deletion."""
        mock_client.annotation_configs.delete.return_value = None

        result = _invoke(
            ["annotation-configs", "delete", "ac_123"],
            mock_config,
            mock_client,
            cli_input="y\n",
        )

        assert result.exit_code == 0, result.output
        mock_client.annotation_configs.delete.assert_called_once_with(
            annotation_config="ac_123", space=None
        )

    def test_delete_declines_does_not_call_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that declining the confirmation leaves the config untouched."""
        result = _invoke(
            ["annotation-configs", "delete", "ac_123"],
            mock_config,
            mock_client,
            cli_input="n\n",
        )

        assert result.exit_code == 0
        mock_client.annotation_configs.delete.assert_not_called()

    def test_delete_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test that an SDK error during delete causes a non-zero exit."""
        mock_client.annotation_configs.delete.side_effect = RuntimeError(
            "Not found"
        )
        result = _invoke(
            ["annotation-configs", "delete", "ac_999", "--force"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
