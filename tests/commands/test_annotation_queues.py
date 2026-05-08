"""Tests for annotation-queues CLI commands."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from arize.annotation_queues.types import (
    AnnotationInput,
    AnnotationQueue,
    AnnotationQueueRecord,
    AnnotationQueueRecordAnnotateResult,
    AnnotationQueueRecordAssignResult,
    AnnotationQueueRecordsList200Response,
    AnnotationQueuesList200Response,
    AssignmentMethod,
    PaginationMetadata,
)
from typer.testing import CliRunner, Result

from ax.cli import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers to build realistic SDK response objects
# ---------------------------------------------------------------------------

_CREATED_AT = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_queue(
    id: str = "aq_1",
    name: str = "My Queue",
    space_id: str = "sp_test",
) -> AnnotationQueue:
    return AnnotationQueue(
        id=id,
        name=name,
        space_id=space_id,
        created_at=_CREATED_AT,
        updated_at=_CREATED_AT,
        annotation_configs=[],
        annotators=[],
    )


def _make_queue_list_response(
    *queues: AnnotationQueue, has_more: bool = False
) -> AnnotationQueuesList200Response:
    return AnnotationQueuesList200Response(
        annotation_queues=list(queues),
        pagination=PaginationMetadata(has_more=has_more),
    )


def _make_record(
    id: str = "rec_1",
    annotation_queue_id: str = "aq_1",
) -> AnnotationQueueRecord:
    return AnnotationQueueRecord(
        id=id,
        annotation_queue_id=annotation_queue_id,
        source_type="spans",
        data={},
        annotations=[],
        evaluations=[],
        assigned_users=[],
    )


def _make_record_list_response(
    *records: AnnotationQueueRecord, has_more: bool = False
) -> AnnotationQueueRecordsList200Response:
    return AnnotationQueueRecordsList200Response(
        records=list(records),
        pagination=PaginationMetadata(has_more=has_more),
    )


# ---------------------------------------------------------------------------
# Shared mock setup
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a mock ArizeClient with annotation_queues subclient pre-wired."""
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
    """Invoke the CLI app with standard mocks for ConfigManager, asdict, and ArizeClient."""
    with (
        patch(
            "ax.commands.annotation_queues.make_client",
            return_value=(mock_client, mock_config),
        ),
    ):
        return runner.invoke(app, args, input=cli_input)


# ---------------------------------------------------------------------------
# ax annotation-queues list
# ---------------------------------------------------------------------------


class TestListAnnotationQueues:
    """Tests for `ax annotation-queues list`."""

    def test_list_returns_queues_in_output(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.list.return_value = (
            _make_queue_list_response(
                _make_queue(name="Alpha"),
                _make_queue(name="Beta"),
            )
        )

        result = _invoke(
            ["annotation-queues", "list", "--output", "json"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        assert "Alpha" in result.output
        assert "Beta" in result.output

    def test_list_passes_filters_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.list.return_value = (
            _make_queue_list_response()
        )

        _invoke(
            [
                "annotation-queues",
                "list",
                "--space",
                "sp_abc",
                "--name",
                "test",
                "--limit",
                "5",
                "--cursor",
                "tok",
            ],
            mock_config,
            mock_client,
        )

        mock_client.annotation_queues.list.assert_called_once_with(
            space="sp_abc",
            name="test",
            limit=5,
            cursor="tok",
        )

    def test_list_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.list.side_effect = RuntimeError(
            "API error"
        )
        result = _invoke(
            ["annotation-queues", "list"], mock_config, mock_client
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax annotation-queues get
# ---------------------------------------------------------------------------


class TestGetAnnotationQueue:
    """Tests for `ax annotation-queues get <id>`."""

    def test_get_returns_queue_in_output(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.get.return_value = _make_queue(
            id="aq_xyz", name="Special Queue"
        )

        result = _invoke(
            ["annotation-queues", "get", "aq_xyz", "--output", "json"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        assert "aq_xyz" in result.output
        assert "Special Queue" in result.output

    def test_get_calls_sdk_with_correct_args(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.get.return_value = _make_queue(
            id="aq_123"
        )

        _invoke(
            ["annotation-queues", "get", "aq_123", "--space", "sp_abc"],
            mock_config,
            mock_client,
        )

        mock_client.annotation_queues.get.assert_called_once_with(
            annotation_queue="aq_123",
            space="sp_abc",
        )

    def test_get_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.get.side_effect = RuntimeError(
            "Not found"
        )
        result = _invoke(
            ["annotation-queues", "get", "aq_999"], mock_config, mock_client
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax annotation-queues create
# ---------------------------------------------------------------------------


class TestCreateAnnotationQueue:
    """Tests for `ax annotation-queues create`."""

    def test_create_basic_returns_queue_in_output(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.create.return_value = _make_queue(
            id="aq_new", name="New Queue"
        )

        result = _invoke(
            [
                "annotation-queues",
                "create",
                "--name",
                "New Queue",
                "--space",
                "sp_abc",
                "--annotation-config-id",
                "ac_1",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        assert "aq_new" in result.output

    def test_create_forwards_all_fields_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.create.return_value = _make_queue()

        _invoke(
            [
                "annotation-queues",
                "create",
                "--name",
                "Q",
                "--space",
                "sp_abc",
                "--annotation-config-id",
                "ac_1",
                "--annotation-config-id",
                "ac_2",
                "--annotator-email",
                "a@example.com",
                "--instructions",
                "Be thorough",
                "--assignment-method",
                "random",
            ],
            mock_config,
            mock_client,
        )

        mock_client.annotation_queues.create.assert_called_once_with(
            name="Q",
            space="sp_abc",
            annotation_config_ids=["ac_1", "ac_2"],
            annotator_emails=["a@example.com"],
            instructions="Be thorough",
            assignment_method=AssignmentMethod("random"),
        )

    def test_create_without_annotation_config_id_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        result = _invoke(
            [
                "annotation-queues",
                "create",
                "--name",
                "Q",
                "--space",
                "sp_abc",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.annotation_queues.create.assert_not_called()

    def test_create_invalid_assignment_method_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        result = _invoke(
            [
                "annotation-queues",
                "create",
                "--name",
                "Q",
                "--space",
                "sp_abc",
                "--annotation-config-id",
                "ac_1",
                "--assignment-method",
                "invalid",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0

    def test_create_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.create.side_effect = RuntimeError(
            "Conflict"
        )
        result = _invoke(
            [
                "annotation-queues",
                "create",
                "--name",
                "Q",
                "--space",
                "sp_abc",
                "--annotation-config-id",
                "ac_1",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax annotation-queues update
# ---------------------------------------------------------------------------


class TestUpdateAnnotationQueue:
    """Tests for `ax annotation-queues update <id>`."""

    def test_update_name_forwarded_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.update.return_value = _make_queue(
            name="Renamed"
        )

        _invoke(
            [
                "annotation-queues",
                "update",
                "aq_1",
                "--name",
                "Renamed",
            ],
            mock_config,
            mock_client,
        )

        mock_client.annotation_queues.update.assert_called_once_with(
            annotation_queue="aq_1",
            space=None,
            name="Renamed",
            instructions=None,
            annotation_config_ids=None,
            annotator_emails=None,
        )

    def test_update_instructions_forwarded_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.update.return_value = _make_queue()

        _invoke(
            [
                "annotation-queues",
                "update",
                "aq_1",
                "--instructions",
                "New instructions",
                "--space",
                "sp_abc",
            ],
            mock_config,
            mock_client,
        )

        mock_client.annotation_queues.update.assert_called_once_with(
            annotation_queue="aq_1",
            space="sp_abc",
            name=None,
            instructions="New instructions",
            annotation_config_ids=None,
            annotator_emails=None,
        )

    def test_update_config_ids_forwarded_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.update.return_value = _make_queue()

        _invoke(
            [
                "annotation-queues",
                "update",
                "aq_1",
                "--annotation-config-id",
                "ac_1",
                "--annotation-config-id",
                "ac_2",
            ],
            mock_config,
            mock_client,
        )

        call_kwargs = mock_client.annotation_queues.update.call_args.kwargs
        assert call_kwargs["annotation_config_ids"] == ["ac_1", "ac_2"]

    def test_update_without_annotation_config_ids_passes_none_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        """No --annotation-config-id flags → None (not []) passed to SDK."""
        mock_client.annotation_queues.update.return_value = _make_queue()

        _invoke(
            ["annotation-queues", "update", "aq_1", "--name", "Renamed"],
            mock_config,
            mock_client,
        )

        call_kwargs = mock_client.annotation_queues.update.call_args.kwargs
        assert call_kwargs["annotation_config_ids"] is None
        assert call_kwargs["annotator_emails"] is None

    def test_update_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.update.side_effect = RuntimeError(
            "Not found"
        )
        result = _invoke(
            ["annotation-queues", "update", "aq_999", "--name", "X"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax annotation-queues delete
# ---------------------------------------------------------------------------


class TestDeleteAnnotationQueue:
    """Tests for `ax annotation-queues delete <id>`."""

    def test_delete_force_skips_confirmation_and_calls_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.delete.return_value = None

        result = _invoke(
            ["annotation-queues", "delete", "aq_1", "--force"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        assert "aq_1" in result.output
        mock_client.annotation_queues.delete.assert_called_once_with(
            annotation_queue="aq_1", space=None
        )

    def test_delete_confirms_yes_calls_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.delete.return_value = None

        result = _invoke(
            ["annotation-queues", "delete", "aq_1"],
            mock_config,
            mock_client,
            cli_input="y\n",
        )

        assert result.exit_code == 0, result.output
        mock_client.annotation_queues.delete.assert_called_once_with(
            annotation_queue="aq_1", space=None
        )

    def test_delete_declines_does_not_call_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        result = _invoke(
            ["annotation-queues", "delete", "aq_1"],
            mock_config,
            mock_client,
            cli_input="n\n",
        )

        assert result.exit_code == 0
        mock_client.annotation_queues.delete.assert_not_called()

    def test_delete_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.delete.side_effect = RuntimeError(
            "Not found"
        )
        result = _invoke(
            ["annotation-queues", "delete", "aq_999", "--force"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax annotation-queues list-records
# ---------------------------------------------------------------------------


class TestListRecords:
    """Tests for `ax annotation-queues list-records <id>`."""

    def test_list_records_returns_data_in_output(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.list_records.return_value = (
            _make_record_list_response(
                _make_record(id="rec_1"),
                _make_record(id="rec_2"),
            )
        )

        result = _invoke(
            ["annotation-queues", "list-records", "aq_1", "--output", "json"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        assert "rec_1" in result.output
        assert "rec_2" in result.output

    def test_list_records_passes_filters_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.list_records.return_value = (
            _make_record_list_response()
        )

        _invoke(
            [
                "annotation-queues",
                "list-records",
                "aq_1",
                "--space",
                "sp_abc",
                "--limit",
                "10",
                "--cursor",
                "tok",
            ],
            mock_config,
            mock_client,
        )

        mock_client.annotation_queues.list_records.assert_called_once_with(
            annotation_queue="aq_1",
            space="sp_abc",
            limit=10,
            cursor="tok",
        )

    def test_list_records_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.list_records.side_effect = RuntimeError(
            "Not found"
        )
        result = _invoke(
            ["annotation-queues", "list-records", "aq_999"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax annotation-queues delete-records
# ---------------------------------------------------------------------------


class TestDeleteRecords:
    """Tests for `ax annotation-queues delete-records <id>`."""

    def test_delete_records_force_skips_confirmation(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.delete_records.return_value = None

        result = _invoke(
            [
                "annotation-queues",
                "delete-records",
                "aq_1",
                "--record-id",
                "rec_1",
                "--record-id",
                "rec_2",
                "--force",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.annotation_queues.delete_records.assert_called_once_with(
            annotation_queue="aq_1",
            space=None,
            record_ids=["rec_1", "rec_2"],
        )

    def test_delete_records_confirms_yes_calls_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.delete_records.return_value = None

        result = _invoke(
            [
                "annotation-queues",
                "delete-records",
                "aq_1",
                "--record-id",
                "rec_1",
            ],
            mock_config,
            mock_client,
            cli_input="y\n",
        )

        assert result.exit_code == 0, result.output
        mock_client.annotation_queues.delete_records.assert_called_once()

    def test_delete_records_declines_does_not_call_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        result = _invoke(
            [
                "annotation-queues",
                "delete-records",
                "aq_1",
                "--record-id",
                "rec_1",
            ],
            mock_config,
            mock_client,
            cli_input="n\n",
        )

        assert result.exit_code == 0
        mock_client.annotation_queues.delete_records.assert_not_called()

    def test_delete_records_without_record_id_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        result = _invoke(
            ["annotation-queues", "delete-records", "aq_1"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
        mock_client.annotation_queues.delete_records.assert_not_called()

    def test_delete_records_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.delete_records.side_effect = RuntimeError(
            "Not found"
        )
        result = _invoke(
            [
                "annotation-queues",
                "delete-records",
                "aq_1",
                "--record-id",
                "rec_1",
                "--force",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax annotation-queues annotate-record
# ---------------------------------------------------------------------------


class TestAnnotateRecord:
    """Tests for `ax annotation-queues annotate-record <queue> <record_id>`."""

    def test_annotate_record_forwards_annotation_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.annotate_record.return_value = (
            AnnotationQueueRecordAnnotateResult(
                id="rec_1",
                annotation_queue_id="aq_1",
                source_type="spans",
                annotations=[],
            )
        )

        result = _invoke(
            [
                "annotation-queues",
                "annotate-record",
                "aq_1",
                "rec_1",
                "--annotation-name",
                "quality",
                "--score",
                "0.9",
                "--label",
                "good",
                "--text",
                "Looks great",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = (
            mock_client.annotation_queues.annotate_record.call_args.kwargs
        )
        assert call_kwargs["annotation_queue"] == "aq_1"
        assert call_kwargs["record_id"] == "rec_1"
        assert call_kwargs["annotations"] == [
            AnnotationInput(
                name="quality", score=0.9, label="good", text="Looks great"
            )
        ]

    def test_annotate_record_score_only(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.annotate_record.return_value = (
            AnnotationQueueRecordAnnotateResult(
                id="rec_1",
                annotation_queue_id="aq_1",
                source_type="spans",
                annotations=[],
            )
        )

        _invoke(
            [
                "annotation-queues",
                "annotate-record",
                "aq_1",
                "rec_1",
                "--annotation-name",
                "score_config",
                "--score",
                "0.5",
            ],
            mock_config,
            mock_client,
        )

        call_kwargs = (
            mock_client.annotation_queues.annotate_record.call_args.kwargs
        )
        assert call_kwargs["annotations"] == [
            AnnotationInput(
                name="score_config", score=0.5, label=None, text=None
            )
        ]

    def test_annotate_record_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.annotate_record.side_effect = (
            RuntimeError("Not found")
        )
        result = _invoke(
            [
                "annotation-queues",
                "annotate-record",
                "aq_1",
                "rec_999",
                "--annotation-name",
                "quality",
            ],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# ax annotation-queues assign-record
# ---------------------------------------------------------------------------


class TestAssignRecord:
    """Tests for `ax annotation-queues assign-record <queue> <record_id>`."""

    def test_assign_record_emails_forwarded_to_sdk(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.assign_record.return_value = (
            AnnotationQueueRecordAssignResult(
                id="rec_1",
                annotation_queue_id="aq_1",
                source_type="spans",
                assigned_users=[],
            )
        )

        result = _invoke(
            [
                "annotation-queues",
                "assign-record",
                "aq_1",
                "rec_1",
                "--email",
                "alice@example.com",
                "--email",
                "bob@example.com",
                "--output",
                "json",
            ],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        mock_client.annotation_queues.assign_record.assert_called_once_with(
            annotation_queue="aq_1",
            space=None,
            record_id="rec_1",
            assigned_user_emails=["alice@example.com", "bob@example.com"],
        )

    def test_assign_record_empty_email_list_clears_assignments(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.assign_record.return_value = (
            AnnotationQueueRecordAssignResult(
                id="rec_1",
                annotation_queue_id="aq_1",
                source_type="spans",
                assigned_users=[],
            )
        )

        result = _invoke(
            ["annotation-queues", "assign-record", "aq_1", "rec_1"],
            mock_config,
            mock_client,
        )

        assert result.exit_code == 0, result.output
        call_kwargs = (
            mock_client.annotation_queues.assign_record.call_args.kwargs
        )
        assert call_kwargs["assigned_user_emails"] == []

    def test_assign_record_sdk_error_exits_nonzero(
        self, mock_config: MagicMock, mock_client: MagicMock
    ) -> None:
        mock_client.annotation_queues.assign_record.side_effect = RuntimeError(
            "Not found"
        )
        result = _invoke(
            ["annotation-queues", "assign-record", "aq_1", "rec_999"],
            mock_config,
            mock_client,
        )
        assert result.exit_code != 0
