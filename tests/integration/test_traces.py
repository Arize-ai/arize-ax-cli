"""Integration tests for ``ax traces`` commands.

These exercise the ``ax traces list`` command end-to-end, which delegates to
the Python SDK's ``client.traces.list`` (the ``/v2/traces`` endpoint). They are
gated on ``ARIZE_API_KEY`` (see ``tests/integration/conftest.py``, which
auto-skips every ``@pytest.mark.integration`` test when that env var is unset)
and use the shared ``first_project`` / ``test_space_id`` session fixtures.

Run::

    ARIZE_API_KEY=<key> pytest tests/integration/test_traces.py -m integration -v
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.conftest import ax_json

pytestmark = pytest.mark.integration


class TestTracesList:
    """ax traces list — smoke tests against a known project."""

    @pytest.mark.integration
    def test_list_returns_traces_and_pagination(
        self, first_project: dict[str, Any], test_space_id: str
    ) -> None:
        """``ax traces list`` returns a body with ``traces`` and ``pagination``.

        Exercises ``client.traces.list`` via the CLI. The traces list may be
        empty for the default time window, but the response always carries
        both keys.
        """
        project_id = first_project["id"]
        data = ax_json("traces", "list", project_id, "--space", test_space_id)
        assert "traces" in data
        assert "pagination" in data
        assert isinstance(data["traces"], list)

    @pytest.mark.integration
    def test_list_with_filter_untouched(
        self, first_project: dict[str, Any], test_space_id: str
    ) -> None:
        """A user ``--filter`` is accepted (forwarded untouched to the SDK)."""
        project_id = first_project["id"]
        data = ax_json(
            "traces",
            "list",
            project_id,
            "--space",
            test_space_id,
            "--filter",
            "status_code = 'ERROR'",
            "--limit",
            "50",
        )
        assert "traces" in data
        assert "pagination" in data
