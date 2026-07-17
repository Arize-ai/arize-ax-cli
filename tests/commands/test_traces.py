"""Tests for traces CLI commands."""

import json
import sys
from pathlib import Path
from typing import Annotated
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from pydantic import BaseModel, Field
from typer.testing import CliRunner

from ax.commands.traces import _build_trace_id_in_filter, app


class _LimitModel(BaseModel):
    """Mirrors the generated SDK's list_spans ``limit`` constraint (le=500)."""

    limit: Annotated[int, Field(le=500, ge=1)]


def _list_spans_validation_error() -> Exception:
    """Build the same ValidationError the generated SDK raises for an
    out-of-range ``--limit`` (client-side, before any network call).
    """
    try:
        _LimitModel(limit=99999)
    except Exception as e:
        return e
    raise AssertionError("expected a ValidationError")


class TestTraceCommands:
    """Verify trace subcommands are registered."""

    def test_export_command_registered(self) -> None:
        """Export subcommand is registered on the traces app."""
        names = [cmd.name for cmd in app.registered_commands]
        assert "export" in names

    def test_list_command_registered(self) -> None:
        """List subcommand is registered on the traces app."""
        names = [cmd.name for cmd in app.registered_commands]
        assert "list" in names


class TestBuildTraceIdInFilter:
    """Tests for the _build_trace_id_in_filter helper."""

    def test_single_id(self) -> None:
        """Single trace ID produces a valid IN clause."""
        result = _build_trace_id_in_filter(["abc"])
        assert result == "context.trace_id IN ('abc')"

    def test_multiple_ids(self) -> None:
        """Multiple trace IDs produce a comma-separated IN clause."""
        result = _build_trace_id_in_filter(["a", "b", "c"])
        assert result == "context.trace_id IN ('a', 'b', 'c')"


class TestListSpans:
    """Tests for 'ax traces list', including out-of-range --limit handling."""

    def test_out_of_range_limit_shows_friendly_error(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A --limit above the server's max surfaces a clean message instead
        of a raw pydantic ValidationError traceback (regression test for the
        'ax traces list limit must be <= 100 (no user-friendly error)' bug).

        ``sys.argv`` is pinned to a non-verbose invocation because
        ``is_verbose_mode()`` inspects the real process argv, which
        otherwise picks up pytest's own ``-v``/``--verbose`` flag when this
        suite is run verbosely.
        """
        monkeypatch.setattr(
            sys, "argv", ["ax", "traces", "list", "TW9kZWw6MTIz"]
        )
        mock_client.spans.list.side_effect = _list_spans_validation_error()

        result = cli_runner.invoke(
            app,
            ["list", "TW9kZWw6MTIz", "--limit", "99999"],
        )

        assert result.exit_code == 4
        assert "limit" in result.output
        assert "less than or equal to 500" in result.output
        assert "pydantic.dev" not in result.output
        assert "SpansApi" not in result.output
        assert "type=less_than_equal" not in result.output


class TestExportTracesRest:
    """Tests for the REST path of 'ax traces export'."""

    def _make_span(self, trace_id: str, span_id: str) -> MagicMock:
        span = MagicMock()
        span.context = MagicMock()
        span.context.trace_id = trace_id
        span.context.span_id = span_id
        span.model_dump.return_value = {
            "context": {"trace_id": trace_id, "span_id": span_id},
            "name": "test",
        }
        return span

    def test_two_phase_rest_calls(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Phase 1 finds spans, phase 2 fetches all spans for those trace IDs."""
        phase1_response = MagicMock()
        phase1_response.spans = [
            self._make_span("t1", "s1"),
            self._make_span("t1", "s2"),
            self._make_span("t2", "s3"),
        ]

        phase2_response = MagicMock()
        phase2_response.spans = [
            self._make_span("t1", "s1"),
            self._make_span("t1", "s2"),
            self._make_span("t1", "s4"),
            self._make_span("t2", "s3"),
            self._make_span("t2", "s5"),
        ]

        mock_client.spans.list.side_effect = [phase1_response, phase2_response]

        result = cli_runner.invoke(
            app,
            ["export", "TW9kZWw6MTIz", "--stdout"],
        )
        assert result.exit_code == 0
        assert mock_client.spans.list.call_count == 2

        phase2_kwargs = mock_client.spans.list.call_args_list[1].kwargs
        assert "context.trace_id IN" in phase2_kwargs["filter"]
        assert "'t1'" in phase2_kwargs["filter"]
        assert "'t2'" in phase2_kwargs["filter"]

    def test_phase1_with_filter(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--filter is passed to phase 1."""
        phase1_response = MagicMock()
        phase1_response.spans = [self._make_span("t1", "s1")]

        phase2_response = MagicMock()
        phase2_response.spans = [self._make_span("t1", "s1")]

        mock_client.spans.list.side_effect = [phase1_response, phase2_response]

        result = cli_runner.invoke(
            app,
            [
                "export",
                "TW9kZWw6MTIz",
                "--filter",
                "status_code = 'ERROR'",
                "--stdout",
            ],
        )
        assert result.exit_code == 0
        phase1_kwargs = mock_client.spans.list.call_args_list[0].kwargs
        assert phase1_kwargs["filter"] == "status_code = 'ERROR'"

    def test_no_spans_found(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """No spans in phase 1 produces a warning and empty output."""
        response = MagicMock()
        response.spans = []
        mock_client.spans.list.return_value = response

        result = cli_runner.invoke(
            app,
            ["export", "TW9kZWw6MTIz", "--stdout"],
        )
        assert result.exit_code == 0
        assert mock_client.spans.list.call_count == 1

    def test_writes_file_by_default(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """Without --stdout, export writes a JSON file."""
        phase1_response = MagicMock()
        phase1_response.spans = [self._make_span("t1", "s1")]
        phase2_response = MagicMock()
        phase2_response.spans = [self._make_span("t1", "s1")]
        mock_client.spans.list.side_effect = [phase1_response, phase2_response]

        with patch("ax.commands.traces.make_export_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            with patch("ax.commands.traces.write_json_array") as mock_write:
                mock_write.return_value = tmp_path / "spans.json"
                result = cli_runner.invoke(
                    app,
                    ["export", "TW9kZWw6MTIz", "--output-dir", str(tmp_path)],
                )
                assert result.exit_code == 0
                mock_write.assert_called_once()

    def test_phase1_always_fetches_500_spans(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Phase 1 always requests 500 spans regardless of --limit."""
        response = MagicMock()
        response.spans = []
        mock_client.spans.list.return_value = response

        result = cli_runner.invoke(app, ["export", "TW9kZWw6MTIz", "--stdout"])
        assert result.exit_code == 0
        phase1_kwargs = mock_client.spans.list.call_args.kwargs
        assert phase1_kwargs["limit"] == 500

    def test_limit_caps_trace_ids(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--limit caps the number of unique trace IDs sent to phase 2."""
        phase1_response = MagicMock()
        phase1_response.spans = [
            self._make_span("t1", "s1"),
            self._make_span("t2", "s2"),
            self._make_span("t3", "s3"),
            self._make_span("t4", "s4"),
            self._make_span("t5", "s5"),
        ]

        phase2_response = MagicMock()
        phase2_response.spans = [
            self._make_span("t1", "s1"),
            self._make_span("t2", "s2"),
        ]

        mock_client.spans.list.side_effect = [phase1_response, phase2_response]

        result = cli_runner.invoke(
            app,
            ["export", "TW9kZWw6MTIz", "--limit", "2", "--stdout"],
        )
        assert result.exit_code == 0
        phase2_kwargs = mock_client.spans.list.call_args_list[1].kwargs
        filter_str = phase2_kwargs["filter"]
        assert "'t1'" in filter_str
        assert "'t2'" in filter_str
        assert "'t3'" not in filter_str


class TestExportTracesFlight:
    """Tests for the --all (Flight) path of 'ax traces export'."""

    def _make_mock_df(self, records: list[dict] | None = None) -> pd.DataFrame:
        return pd.DataFrame(records or [])

    def test_all_calls_export_to_df_twice(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--all uses export_to_df for both phases."""
        df1 = self._make_mock_df(
            [
                {"context.trace_id": "t1", "context.span_id": "s1"},
                {"context.trace_id": "t2", "context.span_id": "s2"},
            ]
        )
        df2 = self._make_mock_df(
            [
                {"context.trace_id": "t1", "context.span_id": "s1"},
                {"context.trace_id": "t1", "context.span_id": "s3"},
                {"context.trace_id": "t2", "context.span_id": "s2"},
            ]
        )
        mock_client.spans.export_to_df.side_effect = [df1, df2]

        result = cli_runner.invoke(
            app,
            [
                "export",
                "my-project",
                "--all",
                "--space",
                "space-abc",
                "--stdout",
            ],
        )
        assert result.exit_code == 0
        assert mock_client.spans.export_to_df.call_count == 2
        mock_client.spans.list.assert_not_called()

        phase2_kwargs = mock_client.spans.export_to_df.call_args_list[1].kwargs
        assert "context.trace_id IN" in phase2_kwargs["where"]

    def test_all_requires_space_id(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--all without --space should fail."""
        result = cli_runner.invoke(
            app,
            ["export", "my-project", "--all", "--stdout"],
        )
        assert result.exit_code != 0

    def test_all_outputs_json(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--all with --stdout outputs DataFrame records as JSON."""
        df1 = self._make_mock_df(
            [
                {"context.trace_id": "t1", "context.span_id": "s1"},
            ]
        )
        df2 = self._make_mock_df(
            [
                {"context.trace_id": "t1", "context.span_id": "s1"},
                {"context.trace_id": "t1", "context.span_id": "s2"},
            ]
        )
        mock_client.spans.export_to_df.side_effect = [df1, df2]

        result = cli_runner.invoke(
            app,
            [
                "export",
                "my-project",
                "--all",
                "--space",
                "space-abc",
                "--stdout",
            ],
        )
        assert result.exit_code == 0
        json_start = result.output.index("[")
        data = json.loads(result.output[json_start:])
        assert len(data) == 2

    def test_all_writes_file(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """--all without --stdout writes a JSON file."""
        df1 = self._make_mock_df(
            [
                {"context.trace_id": "t1", "context.span_id": "s1"},
            ]
        )
        df2 = self._make_mock_df(
            [
                {"context.trace_id": "t1", "context.span_id": "s1"},
            ]
        )
        mock_client.spans.export_to_df.side_effect = [df1, df2]

        with patch("ax.commands.traces.make_export_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            result = cli_runner.invoke(
                app,
                [
                    "export",
                    "my-project",
                    "--all",
                    "--space",
                    "space-abc",
                    "--output-dir",
                    str(tmp_path),
                ],
            )
            assert result.exit_code == 0
            written = json.loads((tmp_path / "spans.json").read_text())
            assert len(written) == 1

    def test_all_empty_no_phase2(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--all with no spans in phase 1 skips phase 2."""
        mock_client.spans.export_to_df.return_value = self._make_mock_df()

        result = cli_runner.invoke(
            app,
            [
                "export",
                "my-project",
                "--all",
                "--space",
                "space-abc",
                "--stdout",
            ],
        )
        assert result.exit_code == 0
        assert mock_client.spans.export_to_df.call_count == 1

    def test_default_uses_rest(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Without --all, export uses REST via spans.list."""
        response = MagicMock()
        response.spans = []
        mock_client.spans.list.return_value = response

        result = cli_runner.invoke(
            app,
            ["export", "TW9kZWw6MTIz", "--stdout"],
        )
        assert result.exit_code == 0
        mock_client.spans.list.assert_called_once()
        mock_client.spans.export_to_df.assert_not_called()
