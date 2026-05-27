"""Tests for spans CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import typer
from typer.testing import CliRunner

from ax.commands.spans import _build_span_filter, app


class TestSpanCommands:
    """Verify span subcommands are registered with the correct names."""

    def test_export_command_registered(self) -> None:
        """Test that 'export' subcommand exists."""
        names = [cmd.name for cmd in app.registered_commands]
        assert "export" in names

    def test_annotate_command_registered(self) -> None:
        """Test that 'annotate' subcommand exists."""
        names = [cmd.name for cmd in app.registered_commands]
        assert "annotate" in names

    def test_list_command_not_registered(self) -> None:
        """List was merged into export and should no longer exist."""
        names = [cmd.name for cmd in app.registered_commands]
        assert "list" not in names


class TestBuildSpanFilter:
    """Tests for the _build_span_filter helper."""

    @pytest.mark.parametrize(
        "args,expected_expr,expected_prefix",
        [
            (("t1", None, None), "context.trace_id = 't1'", "trace"),
            ((None, "s1", None), "context.span_id = 's1'", "span"),
            (
                (None, None, "sess1"),
                "attributes.session.id = 'sess1'",
                "session",
            ),
        ],
    )
    def test_single_id_flag_builds_filter(
        self,
        args: tuple,
        expected_expr: str,
        expected_prefix: str,
    ) -> None:
        """Each ID flag produces the correct filter expression and prefix."""
        expr, prefix, _val = _build_span_filter(*args)
        assert expr == expected_expr
        assert prefix == expected_prefix

    def test_no_flags_returns_none(self) -> None:
        """Omitting all flags returns None filter with default prefix."""
        expr, prefix, id_value = _build_span_filter(None, None, None)
        assert expr is None
        assert prefix == "spans"
        assert id_value == "all"

    def test_filter_only(self) -> None:
        """A --filter without ID flags returns that filter as-is."""
        expr, prefix, id_value = _build_span_filter(
            None, None, None, filter_expr="status_code = 'ERROR'"
        )
        assert expr == "status_code = 'ERROR'"
        assert prefix == "spans"
        assert id_value == "filtered"

    def test_filter_combined_with_id(self) -> None:
        """A --filter with an ID flag ANDs them together."""
        expr, prefix, id_value = _build_span_filter(
            "t1", None, None, filter_expr="latency_ms > 1000"
        )
        assert expr == "context.trace_id = 't1' AND latency_ms > 1000"
        assert prefix == "trace"
        assert id_value == "t1"

    def test_multiple_id_flags_raises(self) -> None:
        """Providing more than one ID flag should raise."""
        with pytest.raises(typer.BadParameter, match="Only one"):
            _build_span_filter("t1", "s1", None)


class TestExportSpans:
    """Tests for the 'ax spans export' command."""

    def test_requires_project_arg(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Project is a required positional argument."""
        result = cli_runner.invoke(app, ["export", "--stdout"])
        assert result.exit_code != 0

    def test_export_all_spans_to_stdout(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """No filter or ID flag exports all spans."""
        response = MagicMock()
        response.spans = []
        mock_client.spans.list.return_value = response

        result = cli_runner.invoke(app, ["export", "TW9kZWw6MTIz", "--stdout"])
        assert result.exit_code == 0
        call_kwargs = mock_client.spans.list.call_args.kwargs
        assert call_kwargs["filter"] is None
        assert call_kwargs["limit"] == 100

    def test_export_with_trace_id(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--trace-id builds a filter and passes through."""
        response = MagicMock()
        response.spans = []
        mock_client.spans.list.return_value = response

        result = cli_runner.invoke(
            app,
            ["export", "TW9kZWw6MTIz", "--trace-id", "t1", "--stdout"],
        )
        assert result.exit_code == 0
        mock_client.spans.list.assert_called_once()
        call_kwargs = mock_client.spans.list.call_args.kwargs
        assert call_kwargs["filter"] == "context.trace_id = 't1'"

    def test_export_with_filter(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--filter passes through to the API."""
        response = MagicMock()
        response.spans = []
        mock_client.spans.list.return_value = response

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
        call_kwargs = mock_client.spans.list.call_args.kwargs
        assert call_kwargs["filter"] == "status_code = 'ERROR'"

    def test_export_filter_combined_with_trace_id(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--filter and --trace-id are ANDed together."""
        response = MagicMock()
        response.spans = []
        mock_client.spans.list.return_value = response

        result = cli_runner.invoke(
            app,
            [
                "export",
                "TW9kZWw6MTIz",
                "--trace-id",
                "t1",
                "--filter",
                "latency_ms > 1000",
                "--stdout",
            ],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.spans.list.call_args.kwargs
        assert call_kwargs["filter"] == (
            "context.trace_id = 't1' AND latency_ms > 1000"
        )

    def test_export_with_custom_limit(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--limit is forwarded to the API call."""
        response = MagicMock()
        response.spans = []
        mock_client.spans.list.return_value = response

        result = cli_runner.invoke(
            app,
            ["export", "TW9kZWw6MTIz", "--limit", "50", "--stdout"],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.spans.list.call_args.kwargs
        assert call_kwargs["limit"] == 50

    def test_export_writes_file_by_default(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """Without --stdout, export writes a JSON file."""
        response = MagicMock()
        response.spans = []
        mock_client.spans.list.return_value = response

        with patch("ax.commands.spans.make_export_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            with patch("ax.commands.spans.write_json_array") as mock_write:
                mock_write.return_value = tmp_path / "spans.json"

                result = cli_runner.invoke(
                    app,
                    [
                        "export",
                        "TW9kZWw6MTIz",
                        "--session-id",
                        "sess-1",
                        "--output-dir",
                        str(tmp_path),
                    ],
                )
                assert result.exit_code == 0
                mock_dir.assert_called_once_with(
                    str(tmp_path), "session", "sess-1"
                )
                mock_write.assert_called_once()

    def test_export_custom_days(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--days flag adjusts the time window."""
        response = MagicMock()
        response.spans = []
        mock_client.spans.list.return_value = response

        result = cli_runner.invoke(
            app,
            [
                "export",
                "TW9kZWw6MTIz",
                "--trace-id",
                "t1",
                "--days",
                "7",
                "--stdout",
            ],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.spans.list.call_args.kwargs
        delta = call_kwargs["end_time"] - call_kwargs["start_time"]
        assert 6 <= delta.days <= 7

    def test_export_rejects_invalid_limit(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--limit 0 or negative is rejected."""
        result = cli_runner.invoke(
            app, ["export", "TW9kZWw6MTIz", "--limit", "0", "--stdout"]
        )
        assert result.exit_code != 0

    def test_export_rejects_invalid_days(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--days 0 or negative is rejected."""
        result = cli_runner.invoke(
            app, ["export", "TW9kZWw6MTIz", "--days", "0", "--stdout"]
        )
        assert result.exit_code != 0

    def test_export_rejects_multiple_id_flags(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Providing more than one ID flag raises an error via CLI."""
        result = cli_runner.invoke(
            app,
            [
                "export",
                "TW9kZWw6MTIz",
                "--trace-id",
                "t1",
                "--span-id",
                "s1",
                "--stdout",
            ],
        )
        assert result.exit_code != 0

    def test_export_passes_project_to_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Project arg is forwarded to spans.list as 'project'."""
        spans_response = MagicMock()
        spans_response.spans = []
        mock_client.spans.list.return_value = spans_response

        result = cli_runner.invoke(
            app,
            ["export", "TW9kZWw6MTIz", "--trace-id", "t1", "--stdout"],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.spans.list.call_args.kwargs
        assert call_kwargs["project"] == "TW9kZWw6MTIz"


class TestExportSpansAll:
    """Tests for the --all flag on 'ax spans export'.

    When --all is used, the CLI calls client.spans.export_to_df directly
    (bypassing spans.list) and converts the DataFrame to JSON.
    """

    def _make_mock_df(self, records: list[dict] | None = None) -> pd.DataFrame:
        """Return a MagicMock that behaves like a pandas DataFrame."""
        return pd.DataFrame(records or [])

    def test_all_calls_export_to_df(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--all calls export_to_df with space_id and project_name."""
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
        mock_client.spans.export_to_df.assert_called_once()
        call_kwargs = mock_client.spans.export_to_df.call_args.kwargs
        assert call_kwargs["space_id"] == "space-abc"
        assert call_kwargs["project_name"] == "my-project"
        mock_client.spans.list.assert_not_called()

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

    def test_all_with_filter(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--all with --filter passes filter as 'where' to export_to_df."""
        mock_client.spans.export_to_df.return_value = self._make_mock_df()

        result = cli_runner.invoke(
            app,
            [
                "export",
                "my-project",
                "--all",
                "--space",
                "space-abc",
                "--filter",
                "status_code = 'ERROR'",
                "--stdout",
            ],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.spans.export_to_df.call_args.kwargs
        assert call_kwargs["where"] == "status_code = 'ERROR'"

    def test_all_outputs_json(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--all with --stdout outputs DataFrame records as JSON."""
        import json

        mock_client.spans.export_to_df.return_value = self._make_mock_df(
            [{"span_id": "s1", "trace_id": "t1"}]
        )

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
        assert len(data) == 1
        assert data[0]["span_id"] == "s1"

    def test_all_writes_file(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """--all without --stdout writes a JSON file."""
        import json

        mock_client.spans.export_to_df.return_value = self._make_mock_df(
            [{"span_id": "s1"}]
        )

        with patch("ax.commands.spans.make_export_dir") as mock_dir:
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

    def test_all_with_limit_warns(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--all with --limit warns the user that limit is ignored."""
        mock_client.spans.export_to_df.return_value = self._make_mock_df()

        result = cli_runner.invoke(
            app,
            [
                "export",
                "my-project",
                "--all",
                "--space",
                "space-abc",
                "--limit",
                "50",
                "--stdout",
            ],
        )
        assert result.exit_code == 0
        assert "--limit is ignored" in result.output

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


_ANNOTATIONS_JSON = (
    '[{"record_id":"span-1","values":[{"name":"quality","score":0.9}]}]'
)


class TestAnnotateSpans:
    """Tests for the 'ax spans annotate' command."""

    def test_annotate_with_stdin_calls_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--file - reads annotations from stdin and calls annotate_spans."""
        mock_client.spans.annotate_spans.return_value = None

        result = cli_runner.invoke(
            app,
            ["annotate", "my-project", "--file", "-"],
            input=_ANNOTATIONS_JSON,
        )
        assert result.exit_code == 0, result.output
        mock_client.spans.annotate_spans.assert_called_once()
        call_kwargs = mock_client.spans.annotate_spans.call_args.kwargs
        assert call_kwargs["project"] == "my-project"
        assert len(call_kwargs["annotations"]) == 1
        assert call_kwargs["annotations"][0].record_id == "span-1"

    def test_annotate_with_file_calls_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """--file with a valid JSON file calls client.spans.annotate_spans."""
        mock_client.spans.annotate_spans.return_value = None
        json_file = tmp_path / "annotations.json"
        json_file.write_text(_ANNOTATIONS_JSON)

        result = cli_runner.invoke(
            app,
            ["annotate", "my-project", "--file", str(json_file)],
        )
        assert result.exit_code == 0, result.output
        mock_client.spans.annotate_spans.assert_called_once()

    def test_annotate_with_space(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--space is forwarded to the SDK."""
        mock_client.spans.annotate_spans.return_value = None

        result = cli_runner.invoke(
            app,
            [
                "annotate",
                "my-project",
                "--file",
                "-",
                "--space",
                "my-space",
            ],
            input=_ANNOTATIONS_JSON,
        )
        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.spans.annotate_spans.call_args.kwargs
        assert call_kwargs["space"] == "my-space"

    def test_annotate_with_start_and_end_time(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--start-time and --end-time are parsed and forwarded."""
        mock_client.spans.annotate_spans.return_value = None

        result = cli_runner.invoke(
            app,
            [
                "annotate",
                "my-project",
                "--file",
                "-",
                "--start-time",
                "2024-01-01T00:00:00Z",
                "--end-time",
                "2024-01-31T00:00:00Z",
            ],
            input=_ANNOTATIONS_JSON,
        )
        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.spans.annotate_spans.call_args.kwargs
        assert call_kwargs["start_time"] is not None
        assert call_kwargs["end_time"] is not None

    def test_annotate_with_days(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--days computes start_time relative to now; end_time stays None."""
        from datetime import datetime, timezone

        mock_client.spans.annotate_spans.return_value = None

        result = cli_runner.invoke(
            app,
            [
                "annotate",
                "my-project",
                "--file",
                "-",
                "--days",
                "7",
            ],
            input=_ANNOTATIONS_JSON,
        )
        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.spans.annotate_spans.call_args.kwargs
        assert call_kwargs["start_time"] is not None
        # end_time is None — the SDK will default to now server-side
        assert call_kwargs["end_time"] is None
        # start_time should be ~7 days before now
        now = datetime.now(tz=timezone.utc)
        delta = now - call_kwargs["start_time"]
        assert 6 <= delta.days <= 8

    def test_annotate_requires_file(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Providing no --file results in a non-zero exit."""
        result = cli_runner.invoke(app, ["annotate", "my-project"])
        assert result.exit_code != 0

    def test_annotate_sdk_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """An SDK error results in a non-zero exit code."""
        mock_client.spans.annotate_spans.side_effect = RuntimeError("API error")
        json_file = tmp_path / "annotations.json"
        json_file.write_text(_ANNOTATIONS_JSON)

        result = cli_runner.invoke(
            app,
            ["annotate", "my-project", "--file", str(json_file)],
        )
        assert result.exit_code != 0

    def test_annotate_success_message(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """A success message is shown after annotating."""
        mock_client.spans.annotate_spans.return_value = None

        result = cli_runner.invoke(
            app,
            ["annotate", "my-project", "--file", "-"],
            input=_ANNOTATIONS_JSON,
        )
        assert result.exit_code == 0, result.output
        assert "span" in result.output.lower()
