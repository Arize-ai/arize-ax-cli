"""Regression tests for optional SDK response fields."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from arize._generated.api_client.models.span import Span
from arize._generated.api_client.models.span_context import SpanContext
from arize.api_keys.types import CreatedUserApiKey
from arize.traces.types import ListTracesResponse, Trace
from arize.webhooks.types import TestWebhookResponse as WebhookTestResponse
from typer.testing import CliRunner

from ax.cli import app
from ax.commands.api_keys import _write_key_to_dotenv_or_revoke
from ax.commands.traces import _trace_lines
from ax.core.exceptions import APIError


def test_trace_without_spans() -> None:
    trace = Trace.model_construct(trace_id="trace", spans=None)

    assert "No spans returned" in "\n".join(_trace_lines(trace))


def test_span_without_display_fields() -> None:
    span = Span.model_construct(
        context=SpanContext.model_construct(span_id="span"),
        start_time=None,
        end_time=None,
        name=None,
        kind=None,
        parent_id=None,
        attributes={},
        status_code=None,
    )
    trace = Trace.model_construct(
        trace_id="trace",
        spans=[span],
        root_span_id=None,
        spans_truncated=False,
        start_time=None,
    )

    rendered = "\n".join(_trace_lines(trace))

    assert "UNKNOWN" in rendered
    assert "Unnamed span" in rendered
    assert "unknown duration" in rendered


@pytest.mark.parametrize(
    "context", [None, SpanContext.model_construct(span_id=None)]
)
def test_span_without_id_reports_api_error(context: SpanContext | None) -> None:
    span = Span.model_construct(context=context)
    trace = Trace.model_construct(trace_id="trace", spans=[span])

    with pytest.raises(APIError, match="span without an ID"):
        _trace_lines(trace)


@pytest.mark.usefixtures("patch_config_and_client")
def test_list_traces_without_results_or_pagination(
    cli_runner: CliRunner, mock_client: MagicMock
) -> None:
    mock_client.traces.list.return_value = ListTracesResponse.model_construct(
        traces=None, pagination=None
    )

    result = cli_runner.invoke(app, ["traces", "list", "project"])

    assert result.exit_code == 0, result.output
    assert "Found 0 trace(s)" in result.output


def test_key_without_secret_is_revoked(
    mock_client: MagicMock, tmp_path: Path
) -> None:
    key = CreatedUserApiKey.model_construct(id="key-id", key=None)
    env_file = tmp_path / ".env"

    with pytest.raises(APIError, match="did not include a secret") as exc_info:
        _write_key_to_dotenv_or_revoke(mock_client, str(env_file), key)

    assert "newly created key was revoked" in str(exc_info.value)
    mock_client.api_keys.revoke.assert_called_once_with(api_key_id="key-id")
    assert not env_file.exists()


def test_key_without_id_is_not_written(
    mock_client: MagicMock, tmp_path: Path
) -> None:
    key = CreatedUserApiKey.model_construct(id=None, key="secret-value")
    env_file = tmp_path / ".env"

    with pytest.raises(APIError, match="incomplete response") as exc_info:
        _write_key_to_dotenv_or_revoke(mock_client, str(env_file), key)

    assert "secret-value" not in str(exc_info.value)
    mock_client.api_keys.revoke.assert_not_called()
    assert not env_file.exists()


@pytest.mark.usefixtures("patch_config_and_client")
def test_trigger_run_without_id_does_not_poll(
    cli_runner: CliRunner, mock_client: MagicMock
) -> None:
    mock_client.tasks.trigger_run.return_value.id = None

    result = cli_runner.invoke(app, ["tasks", "trigger-run", "task", "--wait"])

    assert result.exit_code == 4, result.output
    assert "did not include a run ID" in result.output
    mock_client.tasks.wait_for_run.assert_not_called()


@pytest.mark.usefixtures("patch_config_and_client")
def test_webhook_without_status_exits_unsuccessfully(
    cli_runner: CliRunner, mock_client: MagicMock
) -> None:
    mock_client.webhooks.test.return_value = (
        WebhookTestResponse.model_construct(
            status_code=None, error_message=None
        )
    )

    result = cli_runner.invoke(app, ["webhooks", "test", "hook"])

    assert result.exit_code == 1, result.output
    assert "no HTTP status code" in result.output
