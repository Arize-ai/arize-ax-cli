"""Integration test configuration and shared fixtures.

Integration tests run against the real Arize API and require:
  - ARIZE_API_KEY environment variable set to a valid API key
  - (Optional) ARIZE_TEST_SPACE set to a space name or ID to use as the test target.
    If not set, the first space returned by ``ax spaces list`` is used.
  - (Optional) ARIZE_TEST_USER_ID set to a user identifier (base64-encoded).
    Required for role binding lifecycle tests.
  - (Optional) ARIZE_TEST_ROLE_ID set to a role identifier (base64-encoded).
    Required for role binding lifecycle tests.
  - (Optional) ARIZE_TEST_EVALUATOR_ID set to an evaluator identifier
    (base64-encoded). Required for task lifecycle tests.

Run::

    ARIZE_API_KEY=<key> pytest tests/integration/ -m integration -v

Skip integration tests (default, excluded from ``task test``)::

    pytest -m "not integration"
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from collections.abc import Generator
from typing import Any

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-skip integration tests when ARIZE_API_KEY is not set."""
    if not os.environ.get("ARIZE_API_KEY"):
        skip = pytest.mark.skip(reason="ARIZE_API_KEY not set")
        for item in items:
            if item.get_closest_marker("integration"):
                item.add_marker(skip)


# ---------------------------------------------------------------------------
# CLI invocation helpers (imported by all integration test files)
# ---------------------------------------------------------------------------


def ax(
    *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Invoke the ``ax`` CLI and return the completed process."""
    merged_env = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, "-m", "ax", *args],
        capture_output=True,
        text=True,
        env=merged_env,
        cwd="/tmp",
    )


def ax_json(*args: str) -> Any:
    """Run an ``ax`` command with ``--output json`` and parse stdout as JSON."""
    result = ax(*args, "--output", "json")
    assert result.returncode == 0, (
        f"Command failed: ax {' '.join(args)}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def api_key() -> str:
    """Return the API key, skipping the test if not set."""
    key = os.environ.get("ARIZE_API_KEY", "")
    if not key:
        pytest.skip("ARIZE_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def first_space(api_key: str) -> dict[str, Any]:
    """Return the first space accessible to the authenticated user."""
    result = ax("spaces", "list", "--limit", "1", "--output", "json")
    if result.returncode != 0:
        pytest.fail(f"Cannot reach Arize API:\n{result.stderr.strip()}")
    spaces = json.loads(result.stdout).get("spaces") or []
    if not spaces:
        pytest.skip(
            "No spaces found for this API key — skipping integration tests"
        )
    return spaces[0]


@pytest.fixture(scope="session")
def test_space_id(first_space: dict[str, Any]) -> str:
    """Return the test space ID, preferring the ARIZE_TEST_SPACE env var."""
    return os.environ.get("ARIZE_TEST_SPACE") or first_space["id"]


@pytest.fixture(scope="session")
def first_project(test_space_id: str) -> dict[str, Any]:
    """Return the first project in the test space."""
    data = ax_json("projects", "list", "--space", test_space_id, "--limit", "1")
    projects = data.get("projects") or []
    if not projects:
        pytest.skip("No projects found in the test space — skipping")
    return projects[0]


@pytest.fixture(scope="session")
def test_user_id() -> str:
    """Return the test user ID from ARIZE_TEST_USER_ID, skipping if not set."""
    user_id = os.environ.get("ARIZE_TEST_USER_ID", "")
    if not user_id:
        pytest.skip("ARIZE_TEST_USER_ID not set")
    return user_id


@pytest.fixture(scope="session")
def test_role_id() -> str:
    """Return the test role ID from ARIZE_TEST_ROLE_ID, skipping if not set."""
    role_id = os.environ.get("ARIZE_TEST_ROLE_ID", "")
    if not role_id:
        pytest.skip("ARIZE_TEST_ROLE_ID not set")
    return role_id


@pytest.fixture(scope="session")
def test_evaluator_id() -> str:
    """Return the test evaluator ID from ARIZE_TEST_EVALUATOR_ID, skipping if not set."""
    evaluator_id = os.environ.get("ARIZE_TEST_EVALUATOR_ID", "")
    if not evaluator_id:
        pytest.skip("ARIZE_TEST_EVALUATOR_ID not set")
    return evaluator_id


@pytest.fixture
def created_dataset_id(test_space_id: str) -> Generator[str, None, None]:
    """Create a temporary dataset and yield its ID, deleting it on teardown."""
    ds_name = f"ax-cli-exp-ds-{uuid.uuid4().hex[:8]}"
    examples = json.dumps(
        [
            {"question": "What is 1+1?"},
            {"question": "What is the capital of France?"},
        ]
    )
    result = ax(
        "datasets",
        "create",
        "--name",
        ds_name,
        "--space",
        test_space_id,
        "--json",
        examples,
        "--output",
        "json",
    )
    assert result.returncode == 0, f"Dataset create failed:\n{result.stderr}"
    created = json.loads(result.stdout)
    dataset_id = created.get("id") or created.get("dataset_id")
    assert dataset_id
    yield dataset_id
    ax("datasets", "delete", dataset_id, "--space", test_space_id, "--force")
