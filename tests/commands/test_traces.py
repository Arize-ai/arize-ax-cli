"""Tests for traces CLI commands."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from arize._generated.api_client.models.span_kind import SpanKind
from arize._generated.api_client.models.span_status_code import SpanStatusCode
from pydantic import BaseModel, Field
from typer.testing import CliRunner

from ax.commands.traces import (
    _append_span_tree_lines,
    _build_trace_id_in_filter,
    _trace_lines,
    app,
)


class _LimitModel(BaseModel):
    """Mirrors the generated SDK's list_traces ``limit`` query-param constraint.

    ``limit`` is a query parameter on ``/v2/traces`` (not part of the
    ``ListTracesRequest`` body) and is capped at 50 by the generated
    ``TracesApi.list_traces`` signature
    (``Annotated[int, Field(le=50, strict=True, ge=1)]``).
    """

    limit: Annotated[int, Field(le=50, ge=1)]


def _list_traces_validation_error() -> Exception:
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


class TestListTraces:
    """Tests for 'ax traces list', which delegates to client.traces.list."""

    def _traces_response(self) -> MagicMock:
        """A minimal ListTracesResponse-shaped mock (``.traces`` + ``.pagination``)."""
        response = MagicMock()
        response.traces = []
        response.pagination = MagicMock()
        return response

    def test_out_of_range_limit_shows_friendly_error(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A --limit above the server's max (50) surfaces a clean message
        instead of a raw pydantic ValidationError traceback (regression test
        for the 'ax traces list limit must be <= 50 (no user-friendly error)'
        bug).

        ``sys.argv`` is pinned to a non-verbose invocation because
        ``is_verbose_mode()`` inspects the real process argv, which
        otherwise picks up pytest's own ``-v``/``--verbose`` flag when this
        suite is run verbosely.
        """
        monkeypatch.setattr(
            sys, "argv", ["ax", "traces", "list", "TW9kZWw6MTIz"]
        )
        mock_client.traces.list.side_effect = _list_traces_validation_error()

        result = cli_runner.invoke(
            app,
            ["list", "TW9kZWw6MTIz", "--limit", "99999"],
        )

        assert result.exit_code == 4
        assert "limit" in result.output
        assert "less than or equal to 50" in result.output
        assert "pydantic.dev" not in result.output
        assert "TracesApi" not in result.output
        assert "type=less_than_equal" not in result.output

    def test_default_limit_is_15(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Without --limit, client.traces.list is called with limit=15."""
        mock_client.traces.list.return_value = self._traces_response()

        result = cli_runner.invoke(app, ["list", "TW9kZWw6MTIz"])
        assert result.exit_code == 0
        mock_client.traces.list.assert_called_once()
        assert mock_client.traces.list.call_args.kwargs["limit"] == 15

    def test_calls_traces_list_not_spans_list(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """The list command hits client.traces.list, never client.spans.list."""
        mock_client.traces.list.return_value = self._traces_response()

        result = cli_runner.invoke(app, ["list", "TW9kZWw6MTIz"])
        assert result.exit_code == 0
        mock_client.traces.list.assert_called_once()
        mock_client.spans.list.assert_not_called()

    def test_filter_passed_through_untouched(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """A user --filter reaches the SDK verbatim — no parent_id = null AND."""
        mock_client.traces.list.return_value = self._traces_response()

        result = cli_runner.invoke(
            app,
            [
                "list",
                "TW9kZWw6MTIz",
                "--filter",
                "status_code = 'ERROR'",
            ],
        )
        assert result.exit_code == 0
        kwargs = mock_client.traces.list.call_args.kwargs
        assert kwargs["filter"] == "status_code = 'ERROR'"
        assert "parent_id" not in (kwargs["filter"] or "")

    def test_no_filter_passes_none(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Without --filter, the SDK receives filter=None (no injection)."""
        mock_client.traces.list.return_value = self._traces_response()

        result = cli_runner.invoke(app, ["list", "TW9kZWw6MTIz"])
        assert result.exit_code == 0
        assert mock_client.traces.list.call_args.kwargs["filter"] is None

    def test_default_output_renders_graph(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Without --output, the branch-graph view renders, not a formatter."""
        mock_client.traces.list.return_value = self._traces_response()

        with (
            patch("ax.commands.traces._render_traces_graph") as mock_graph,
            patch("ax.commands.traces.output_data") as mock_output_data,
        ):
            result = cli_runner.invoke(app, ["list", "TW9kZWw6MTIz"])

        assert result.exit_code == 0
        mock_graph.assert_called_once()
        mock_output_data.assert_not_called()

    def test_explicit_output_format_bypasses_graph(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--output json (or table/csv/parquet) still uses the formatter path."""
        mock_client.traces.list.return_value = self._traces_response()

        with (
            patch("ax.commands.traces._render_traces_graph") as mock_graph,
            patch("ax.commands.traces.output_data") as mock_output_data,
        ):
            result = cli_runner.invoke(
                app, ["list", "TW9kZWw6MTIz", "--output", "json"]
            )

        assert result.exit_code == 0
        mock_output_data.assert_called_once()
        mock_graph.assert_not_called()

    def test_default_view_matches_phoenix_trace_shape(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """The default view frames traces and nests status-marked spans."""

        def make_span(
            span_id: str,
            parent_id: str | None,
            name: str,
            kind: SpanKind,
            start: datetime,
            end: datetime,
            status: SpanStatusCode = SpanStatusCode.OK,
            attributes: dict[str, object] | None = None,
        ) -> MagicMock:
            span = MagicMock()
            span.context.span_id = span_id
            span.parent_id = parent_id
            span.name = name
            span.kind = kind
            span.start_time = start
            span.end_time = end
            span.status_code = status
            span.status_message = (
                "boom" if status == SpanStatusCode.ERROR else None
            )
            span.attributes = attributes
            return span

        base = datetime(2026, 8, 7, 14, 22, 1, tzinfo=timezone.utc)
        root = make_span(
            "root-span",
            None,
            "agent_run",
            SpanKind.AGENT,
            base,
            base.replace(microsecond=500000),
            attributes={
                "input.value": '{"question": "hello"}',
                "output.value": "world",
            },
        )
        child = make_span(
            "child-span",
            "root-span",
            "tool_search_docs",
            SpanKind.TOOL,
            base,
            base.replace(microsecond=250000),
            status=SpanStatusCode.ERROR,
        )

        trace = MagicMock()
        trace.trace_id = "4092f45122283e075dab37195cc2c347"
        trace.root_span_id = "root-span"
        trace.spans = [root, child]
        trace.spans_truncated = False
        trace.start_time = base
        trace.end_time = base

        response = self._traces_response()
        response.traces = [trace]
        response.pagination.has_more = True
        response.pagination.next_cursor = "eyJvZmZzZXQiOjUwfQ=="
        mock_client.traces.list.return_value = response

        result = cli_runner.invoke(app, ["list", "TW9kZWw6MTIz"])

        assert result.exit_code == 0
        assert "Resolving project: TW9kZWw6MTIz" in result.output
        assert "Fetching last 15 trace(s)" in result.output
        assert "Found 1 trace(s)" in result.output
        assert "┌─ Trace: 4092f45122283e075dab37195cc2c347" in result.output
        assert '│  Input: {"question": "hello"}' in result.output
        assert "│  Output: world" in result.output
        assert "│  Spans:" in result.output
        assert "│  Start: 2026-08-07 14:22:01" in result.output
        assert "│  └─ root-sp (AGENT) ✓ agent_run - 500ms" in result.output
        assert (
            "│     └─ child-s (TOOL) ✗ tool_search_docs - 250ms"
            in result.output
        )
        assert "└─" in result.output
        assert "eyJvZmZzZXQiOjUwfQ==" in result.output
        assert "┌─ Trace: 4092f45122283e075dab37195cc2c347" in result.stdout
        assert "Resolving project: TW9kZWw6MTIz" in result.stderr
        assert "Resolving project" not in result.stdout

    def test_default_view_omits_missing_input_and_output(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Missing root input/output does not render empty labeled rows."""
        base = datetime(2026, 8, 7, 14, 22, 1, tzinfo=timezone.utc)
        root = MagicMock()
        root.context.span_id = "root-span"
        root.parent_id = None
        root.name = "main"
        root.kind = SpanKind.UNKNOWN
        root.start_time = base
        root.end_time = base
        root.status_code = SpanStatusCode.OK
        root.status_message = None
        root.attributes = {}

        trace = MagicMock()
        trace.trace_id = "trace-id"
        trace.root_span_id = "root-span"
        trace.spans = [root]
        trace.spans_truncated = False
        trace.start_time = base
        trace.end_time = base

        response = self._traces_response()
        response.traces = [trace]
        response.pagination.has_more = False
        mock_client.traces.list.return_value = response

        result = cli_runner.invoke(app, ["list", "project-id"])

        assert result.exit_code == 0
        assert "Input:" not in result.output
        assert "Output:" not in result.output
        assert "│  └─ root-sp (UNKNOWN) ✓ main - 0ms" in result.output

    def test_verbose_default_view_shows_full_span_id(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verbose graph output keeps the complete span ID."""
        base = datetime(2026, 8, 7, 14, 22, 1, tzinfo=timezone.utc)
        root = MagicMock()
        root.context.span_id = "1234567890abcdef"
        root.parent_id = None
        root.name = "main"
        root.kind = SpanKind.CHAIN
        root.start_time = base
        root.end_time = base
        root.status_code = SpanStatusCode.OK
        root.status_message = None
        root.attributes = {}

        trace = MagicMock()
        trace.trace_id = "trace-id"
        trace.root_span_id = "1234567890abcdef"
        trace.spans = [root]
        trace.spans_truncated = False
        trace.start_time = base
        trace.end_time = base

        response = self._traces_response()
        response.traces = [trace]
        response.pagination.has_more = False
        mock_client.traces.list.return_value = response

        result = cli_runner.invoke(app, ["list", "project-id", "--verbose"])

        assert result.exit_code == 0
        assert "│  └─ 1234567890abcdef (CHAIN) ✓ main - 0ms" in result.output

    def test_default_view_shows_summed_trace_cost(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Cost sums the ``llm.cost.total`` attribute across a trace's spans."""
        base = datetime(2026, 8, 7, 14, 22, 1, tzinfo=timezone.utc)
        root = MagicMock()
        root.context.span_id = "root-span"
        root.parent_id = None
        root.name = "llm_call"
        root.kind = SpanKind.LLM
        root.start_time = base
        root.end_time = base
        root.status_code = SpanStatusCode.OK
        root.status_message = None
        root.attributes = {"llm.cost.total": 0.0012}

        child = MagicMock()
        child.context.span_id = "child-span"
        child.parent_id = "root-span"
        child.name = "sub_llm_call"
        child.kind = SpanKind.LLM
        child.start_time = base
        child.end_time = base
        child.status_code = SpanStatusCode.OK
        child.status_message = None
        child.attributes = {"llm.cost.total": 0.0008}

        trace = MagicMock()
        trace.trace_id = "trace-with-cost"
        trace.root_span_id = "root-span"
        trace.spans = [root, child]
        trace.spans_truncated = False
        trace.start_time = base
        trace.end_time = base

        response = self._traces_response()
        response.traces = [trace]
        response.pagination.has_more = False
        mock_client.traces.list.return_value = response

        result = cli_runner.invoke(app, ["list", "project-id"])

        assert result.exit_code == 0
        assert "Cost: $0.002000" in result.output

    def test_default_view_omits_cost_when_no_span_reports_it(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """No ``llm.cost.total`` attribute anywhere means no Cost line at all."""
        base = datetime(2026, 8, 7, 14, 22, 1, tzinfo=timezone.utc)
        root = MagicMock()
        root.context.span_id = "root-span"
        root.parent_id = None
        root.name = "main"
        root.kind = SpanKind.CHAIN
        root.start_time = base
        root.end_time = base
        root.status_code = SpanStatusCode.OK
        root.status_message = None
        root.attributes = {}

        trace = MagicMock()
        trace.trace_id = "trace-without-cost"
        trace.root_span_id = "root-span"
        trace.spans = [root]
        trace.spans_truncated = False
        trace.start_time = base
        trace.end_time = base

        response = self._traces_response()
        response.traces = [trace]
        response.pagination.has_more = False
        mock_client.traces.list.return_value = response

        result = cli_runner.invoke(app, ["list", "project-id"])

        assert result.exit_code == 0
        assert "Cost:" not in result.output
        assert "Start: 2026-08-07 14:22:01" in result.output

    def test_verbose_wraps_input_output_instead_of_truncating(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--verbose shows the full Input/Output value (wrapped, not
        ellipsized), even on a narrow or non-tty-detected terminal
        (regression test for input/output being cut off mid-value).
        """
        monkeypatch.setattr(
            "ax.commands.traces.shutil.get_terminal_size",
            lambda fallback=(200, 24): os.terminal_size((30, 24)),
        )
        base = datetime(2026, 8, 7, 14, 22, 1, tzinfo=timezone.utc)
        long_value = "x" * 200
        root = MagicMock()
        root.context.span_id = "root-span"
        root.parent_id = None
        root.name = "main"
        root.kind = SpanKind.CHAIN
        root.start_time = base
        root.end_time = base
        root.status_code = SpanStatusCode.OK
        root.status_message = None
        root.attributes = {"input.value": long_value}

        trace = MagicMock()
        trace.trace_id = "trace-id"
        trace.root_span_id = "root-span"
        trace.spans = [root]
        trace.spans_truncated = False
        trace.start_time = base
        trace.end_time = base

        response = self._traces_response()
        response.traces = [trace]
        response.pagination.has_more = False
        mock_client.traces.list.return_value = response

        non_verbose = cli_runner.invoke(app, ["list", "project-id"])
        verbose = cli_runner.invoke(app, ["list", "project-id", "--verbose"])

        assert non_verbose.exit_code == 0
        assert "…" in non_verbose.output
        assert long_value not in non_verbose.output.replace("\n", "")

        assert verbose.exit_code == 0
        assert long_value in verbose.output.replace("\n", "")
        value_lines = [
            line for line in verbose.output.splitlines() if "x" in line
        ]
        assert value_lines and all("…" not in line for line in value_lines)

    def test_default_view_handles_one_thousand_nested_spans(self) -> None:
        """The endpoint's maximum-depth trace does not exhaust Python's stack."""
        base = datetime(2026, 8, 7, 14, 22, 1, tzinfo=timezone.utc)
        spans: list[MagicMock] = []
        for index in range(1000):
            span = MagicMock()
            span.context.span_id = f"span-{index}"
            span.parent_id = None if index == 0 else f"span-{index - 1}"
            span.name = f"span {index}"
            span.kind = SpanKind.CHAIN
            span.start_time = base
            span.end_time = base
            span.status_code = SpanStatusCode.OK
            span.attributes = {}
            spans.append(span)

        trace = MagicMock()
        trace.trace_id = "deep-trace"
        trace.root_span_id = "span-0"
        trace.spans = spans
        trace.spans_truncated = False

        try:
            lines = _trace_lines(trace, full_span_ids=True)
        except RecursionError:
            pytest.fail("trace rendering must not depend on Python recursion")

        assert len(lines) == 1004
        assert "span-0" in lines[3]
        assert "span-999" in lines[-2]

    def test_default_view_handles_missing_root_span(self) -> None:
        """A trace whose root span was dropped (e.g. the server's per-trace
        span cap discarded it) renders the remaining spans as top-level
        branches with a warning, instead of raising ``StopIteration``.
        """
        base = datetime(2026, 8, 7, 14, 22, 1, tzinfo=timezone.utc)
        orphan = MagicMock()
        orphan.context.span_id = "orphan-span"
        orphan.parent_id = "missing-root"
        orphan.name = "orphaned_child"
        orphan.kind = SpanKind.TOOL
        orphan.start_time = base
        orphan.end_time = base
        orphan.status_code = SpanStatusCode.OK
        orphan.status_message = None
        orphan.attributes = {}

        trace = MagicMock()
        trace.trace_id = "trace-with-dropped-root"
        trace.root_span_id = "missing-root"
        trace.spans = [orphan]
        trace.spans_truncated = True

        lines = _trace_lines(trace)

        assert "orphaned_child" in "\n".join(lines)
        assert "Root span not included in this page" in "\n".join(lines)
        assert "Spans truncated" in "\n".join(lines)

    def test_default_view_handles_trace_with_no_spans(self) -> None:
        """An empty ``trace.spans`` renders a clear message instead of
        raising ``StopIteration``.
        """
        trace = MagicMock()
        trace.trace_id = "empty-trace"
        trace.root_span_id = "missing-root"
        trace.spans = []
        trace.spans_truncated = False

        lines = _trace_lines(trace)

        assert "No spans returned for this trace" in "\n".join(lines)

    def test_default_view_renders_each_span_once(self) -> None:
        """Duplicate graph references do not duplicate rendered spans."""
        base = datetime(2026, 8, 7, 14, 22, 1, tzinfo=timezone.utc)
        root = MagicMock()
        root.context.span_id = "root"
        root.name = "root"
        root.kind = SpanKind.CHAIN
        root.start_time = base
        root.end_time = base
        root.status_code = SpanStatusCode.OK

        child = MagicMock()
        child.context.span_id = "child"
        child.name = "child"
        child.kind = SpanKind.TOOL
        child.start_time = base
        child.end_time = base
        child.status_code = SpanStatusCode.OK

        lines: list[str] = []
        _append_span_tree_lines(
            lines,
            root,
            {"root": [child, child]},
            full_span_ids=True,
        )

        assert len(lines) == 2
        assert sum(" child " in line for line in lines) == 1

    def test_span_tree_orders_siblings_by_ascending_start_time(self) -> None:
        """Depth-first traversal visits earlier sibling subtrees first."""
        base = datetime(2026, 8, 7, 14, 22, 1, tzinfo=timezone.utc)

        def span(span_id: str, start_time: datetime) -> MagicMock:
            item = MagicMock()
            item.context.span_id = span_id
            item.name = span_id
            item.kind = SpanKind.CHAIN
            item.start_time = start_time
            item.end_time = start_time
            item.status_code = SpanStatusCode.OK
            return item

        root = span("root", base)
        earlier = span("earlier", base.replace(second=2))
        later = span("later", base.replace(second=3))
        lines: list[str] = []

        _append_span_tree_lines(
            lines,
            root,
            {"root": [later, earlier]},
            full_span_ids=True,
        )

        assert "earlier" in lines[1]
        assert "later" in lines[2]

    def test_space_start_end_cursor_forwarded(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--space, --start-time, --end-time and --cursor reach the SDK."""
        mock_client.traces.list.return_value = self._traces_response()

        result = cli_runner.invoke(
            app,
            [
                "list",
                "my-project",
                "--space",
                "sp-abc",
                "--start-time",
                "2026-07-06T00:00:00",
                "--end-time",
                "2026-07-07T00:00:00",
                "--cursor",
                "abc123",
            ],
        )
        assert result.exit_code == 0
        kwargs = mock_client.traces.list.call_args.kwargs
        assert kwargs["project"] == "my-project"
        assert kwargs["space"] == "sp-abc"
        assert kwargs["start_time"] == datetime(2026, 7, 6, tzinfo=timezone.utc)
        assert kwargs["end_time"] == datetime(2026, 7, 7, tzinfo=timezone.utc)
        assert kwargs["cursor"] == "abc123"


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

    def test_naive_time_window_normalized_to_utc(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Naive --start-time/--end-time reach the SDK as tz-aware UTC."""
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
                "--start-time",
                "2026-07-06T00:00:00",
                "--end-time",
                "2026-07-07T00:00:00",
                "--stdout",
            ],
        )

        assert result.exit_code == 0
        phase1_kwargs = mock_client.spans.list.call_args_list[0].kwargs
        assert phase1_kwargs["start_time"] == datetime(
            2026, 7, 6, tzinfo=timezone.utc
        )
        assert phase1_kwargs["end_time"] == datetime(
            2026, 7, 7, tzinfo=timezone.utc
        )

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
