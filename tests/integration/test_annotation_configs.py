"""Integration tests for ``ax annotation-configs`` commands."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest

from tests.integration.conftest import ax, ax_json

pytestmark = pytest.mark.integration


class TestAnnotationConfigsUpdate:
    """ax annotation-configs update — real create → update → verify lifecycle.

    Unit tests mock the SDK, so only an integration test proves the CLI's
    update subcommands send the right fields and the server actually persists
    them. Each test creates a config, updates it, then re-reads from the server
    to confirm the change stuck.
    """

    @staticmethod
    def _create(space_id: str, config_type: str, *args: str) -> dict[str, Any]:
        """Run ``annotation-configs create <type>`` and return the parsed config."""
        result = ax(
            "annotation-configs",
            "create",
            config_type,
            "--space",
            space_id,
            "--output",
            "json",
            *args,
        )
        assert result.returncode == 0, (
            f"annotation-configs create failed:\n{result.stderr}"
        )
        return json.loads(result.stdout)

    @staticmethod
    def _delete(config_id: str, space_id: str) -> None:
        """Best-effort teardown for a config by ID."""
        ax(
            "annotation-configs",
            "delete",
            config_id,
            "--space",
            space_id,
            "--force",
        )

    def test_update_continuous_changes_all_fields(
        self, test_space_id: str
    ) -> None:
        """Updating a continuous config changes every field and persists it."""
        name = f"ax-cli-cfg-cont-{uuid.uuid4().hex[:8]}"
        created = self._create(
            test_space_id,
            "continuous",
            "--name",
            name,
            "--min-score",
            "0",
            "--max-score",
            "1",
        )
        config_id = created["id"]
        new_name = f"{name}-renamed"
        try:
            result = ax(
                "annotation-configs",
                "update",
                "continuous",
                config_id,
                "--space",
                test_space_id,
                "--new-name",
                new_name,
                "--min-score",
                "0.5",
                "--max-score",
                "10",
                "--optimization-direction",
                "MAXIMIZE",
                "--output",
                "json",
            )
            assert result.returncode == 0, (
                f"update continuous failed:\n{result.stderr}"
            )
            payload: dict[str, Any] = json.loads(result.stdout)
            assert payload["id"] == config_id
            assert payload["name"] == new_name
            assert float(payload["minimum_score"]) == 0.5
            assert float(payload["maximum_score"]) == 10
            assert payload["optimization_direction"] == "MAXIMIZE"

            # Confirm the server persisted the change, not just the response.
            fetched = ax_json(
                "annotation-configs",
                "get",
                config_id,
                "--space",
                test_space_id,
            )
            assert fetched["name"] == new_name
            assert float(fetched["minimum_score"]) == 0.5
            assert float(fetched["maximum_score"]) == 10
            assert fetched["optimization_direction"] == "MAXIMIZE"
        finally:
            self._delete(config_id, test_space_id)

    def test_update_continuous_partial_leaves_other_fields(
        self, test_space_id: str
    ) -> None:
        """Passing only --new-name leaves min/max scores unchanged."""
        name = f"ax-cli-cfg-partial-{uuid.uuid4().hex[:8]}"
        created = self._create(
            test_space_id,
            "continuous",
            "--name",
            name,
            "--min-score",
            "2",
            "--max-score",
            "8",
        )
        config_id = created["id"]
        new_name = f"{name}-renamed"
        try:
            result = ax(
                "annotation-configs",
                "update",
                "continuous",
                config_id,
                "--space",
                test_space_id,
                "--new-name",
                new_name,
                "--output",
                "json",
            )
            assert result.returncode == 0, (
                f"partial update failed:\n{result.stderr}"
            )
            payload: dict[str, Any] = json.loads(result.stdout)
            assert payload["name"] == new_name
            # Untouched fields must retain their original values.
            assert float(payload["minimum_score"]) == 2
            assert float(payload["maximum_score"]) == 8
        finally:
            self._delete(config_id, test_space_id)

    def test_update_categorical_replaces_values(
        self, test_space_id: str
    ) -> None:
        """Updating a categorical config replaces its label set."""
        name = f"ax-cli-cfg-cat-{uuid.uuid4().hex[:8]}"
        created = self._create(
            test_space_id,
            "categorical",
            "--name",
            name,
            "--value",
            "good",
            "--value",
            "bad",
        )
        config_id = created["id"]
        new_name = f"{name}-renamed"
        try:
            result = ax(
                "annotation-configs",
                "update",
                "categorical",
                config_id,
                "--space",
                test_space_id,
                "--new-name",
                new_name,
                "--value",
                "yes",
                "--value",
                "no",
                "--output",
                "json",
            )
            assert result.returncode == 0, (
                f"update categorical failed:\n{result.stderr}"
            )
            payload: dict[str, Any] = json.loads(result.stdout)
            assert payload["name"] == new_name
            labels = {v["label"] for v in payload.get("values", [])}
            assert labels == {"yes", "no"}
        finally:
            self._delete(config_id, test_space_id)

    def test_update_freeform_renames(self, test_space_id: str) -> None:
        """Updating a freeform config renames it and persists server-side."""
        name = f"ax-cli-cfg-free-{uuid.uuid4().hex[:8]}"
        created = self._create(test_space_id, "freeform", "--name", name)
        config_id = created["id"]
        new_name = f"{name}-renamed"
        try:
            result = ax(
                "annotation-configs",
                "update",
                "freeform",
                config_id,
                "--space",
                test_space_id,
                "--new-name",
                new_name,
                "--output",
                "json",
            )
            assert result.returncode == 0, (
                f"update freeform failed:\n{result.stderr}"
            )
            assert json.loads(result.stdout)["name"] == new_name

            fetched = ax_json(
                "annotation-configs",
                "get",
                config_id,
                "--space",
                test_space_id,
            )
            assert fetched["name"] == new_name
        finally:
            self._delete(config_id, test_space_id)

    def test_update_nonexistent_config_fails(self, test_space_id: str) -> None:
        """Updating a nonexistent annotation config exits non-zero."""
        result = ax(
            "annotation-configs",
            "update",
            "continuous",
            f"nonexistent-{uuid.uuid4().hex[:8]}",
            "--space",
            test_space_id,
            "--new-name",
            "whatever",
        )
        assert result.returncode != 0
