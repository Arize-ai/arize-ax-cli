"""Tests for ax upgrade command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ax.cli import app
from ax.config.schema import (
    AuthConfig,
    Config,
    NetworkConfig,
    ProfileConfig,
    ProxyMode,
)

runner = CliRunner()


def _assert_upgrade_subprocess(mock_run: MagicMock, command: list[str]) -> None:
    """Assert a package-manager command receives an explicit child environment."""
    args, kwargs = mock_run.call_args
    assert args == (command,)
    assert kwargs["check"] is False
    assert isinstance(kwargs["env"], dict)


@pytest.mark.unit
def test_upgrade_already_on_latest() -> None:
    """Shows success message when already on latest version."""
    with (
        patch("ax.commands.upgrade.__version__", "0.14.0"),
        patch("ax.commands.upgrade.fetch_pypi_version", return_value="0.14.0"),
        patch("ax.cli._start_upgrade_check"),
    ):
        result = runner.invoke(app, ["upgrade"])
    assert result.exit_code == 0
    assert "already on the latest version" in result.output


@pytest.mark.unit
def test_upgrade_pip_flag() -> None:
    """--pip flag runs pip install --upgrade arize-ax-cli."""
    with (
        patch("ax.commands.upgrade.__version__", "0.13.0"),
        patch("ax.commands.upgrade.fetch_pypi_version", return_value="0.14.0"),
        patch("ax.cli._start_upgrade_check"),
        patch(
            "ax.commands.upgrade.subprocess.run",
            return_value=MagicMock(returncode=0),
        ) as mock_run,
    ):
        result = runner.invoke(app, ["upgrade", "--pip"])
    assert result.exit_code == 0
    _assert_upgrade_subprocess(
        mock_run, ["pip", "install", "--upgrade", "arize-ax-cli"]
    )


@pytest.mark.unit
def test_upgrade_pipx_flag() -> None:
    """--pipx flag runs pipx upgrade arize-ax-cli."""
    with (
        patch("ax.commands.upgrade.__version__", "0.13.0"),
        patch("ax.commands.upgrade.fetch_pypi_version", return_value="0.14.0"),
        patch("ax.cli._start_upgrade_check"),
        patch(
            "ax.commands.upgrade.subprocess.run",
            return_value=MagicMock(returncode=0),
        ) as mock_run,
    ):
        result = runner.invoke(app, ["upgrade", "--pipx"])
    assert result.exit_code == 0
    _assert_upgrade_subprocess(mock_run, ["pipx", "upgrade", "arize-ax-cli"])


@pytest.mark.unit
def test_upgrade_uv_flag() -> None:
    """--uv flag runs uv tool upgrade arize-ax-cli."""
    with (
        patch("ax.commands.upgrade.__version__", "0.13.0"),
        patch("ax.commands.upgrade.fetch_pypi_version", return_value="0.14.0"),
        patch("ax.cli._start_upgrade_check"),
        patch(
            "ax.commands.upgrade.subprocess.run",
            return_value=MagicMock(returncode=0),
        ) as mock_run,
    ):
        result = runner.invoke(app, ["upgrade", "--uv"])
    assert result.exit_code == 0
    _assert_upgrade_subprocess(
        mock_run, ["uv", "tool", "upgrade", "arize-ax-cli"]
    )


@pytest.mark.unit
def test_upgrade_no_flag_prompts_user() -> None:
    """No flag triggers a questionary prompt and runs the selected command."""
    with (
        patch("ax.commands.upgrade.__version__", "0.13.0"),
        patch("ax.commands.upgrade.fetch_pypi_version", return_value="0.14.0"),
        patch("ax.cli._start_upgrade_check"),
        patch("questionary.select") as mock_select,
        patch(
            "ax.commands.upgrade.subprocess.run",
            return_value=MagicMock(returncode=0),
        ) as mock_run,
    ):
        mock_select.return_value.ask.return_value = "pipx"
        result = runner.invoke(app, ["upgrade"])
    assert result.exit_code == 0
    mock_select.assert_called_once()
    _assert_upgrade_subprocess(mock_run, ["pipx", "upgrade", "arize-ax-cli"])


@pytest.mark.unit
def test_upgrade_passes_profile_network_policy_to_package_manager(
    tmp_path,
) -> None:
    """The download subprocess receives proxy, bypass, and CA configuration."""
    ca_bundle = tmp_path / "corporate-ca.pem"
    ca_bundle.write_text("placeholder")
    config = Config(
        profile=ProfileConfig(name="proxy"),
        auth=AuthConfig(auth_method="api-key", api_key="ak-test"),
        network=NetworkConfig(
            proxy_mode=ProxyMode.URL,
            proxy_url="http://profile-proxy.example.com:8080",
            no_proxy="localhost",
            ca_bundle=str(ca_bundle),
        ),
    )
    with (
        patch("ax.commands.upgrade.__version__", "0.13.0"),
        patch("ax.commands.upgrade.ConfigManager.load", return_value=config),
        patch("ax.commands.upgrade.fetch_pypi_version", return_value="0.14.0"),
        patch("ax.cli._start_upgrade_check"),
        patch(
            "ax.commands.upgrade.subprocess.run",
            return_value=MagicMock(returncode=0),
        ) as mock_run,
    ):
        result = runner.invoke(app, ["upgrade", "--pip"])

    assert result.exit_code == 0
    environment = mock_run.call_args.kwargs["env"]
    assert environment["HTTPS_PROXY"] == "http://profile-proxy.example.com:8080"
    assert environment["NO_PROXY"] == "localhost"
    assert environment["PIP_CERT"] == str(ca_bundle)


@pytest.mark.unit
def test_upgrade_subprocess_failure_exits_nonzero() -> None:
    """Non-zero subprocess exit code propagates as CLI exit code."""
    with (
        patch("ax.commands.upgrade.__version__", "0.13.0"),
        patch("ax.commands.upgrade.fetch_pypi_version", return_value="0.14.0"),
        patch("ax.cli._start_upgrade_check"),
        patch(
            "ax.commands.upgrade.subprocess.run",
            return_value=MagicMock(returncode=1),
        ),
    ):
        result = runner.invoke(app, ["upgrade", "--pip"])
    assert result.exit_code == 1


@pytest.mark.unit
def test_upgrade_pypi_failure_exits_nonzero() -> None:
    """PyPI fetch failure prints a warning and exits non-zero."""
    with (
        patch("ax.commands.upgrade.fetch_pypi_version", return_value=None),
        patch("ax.cli._start_upgrade_check"),
    ):
        result = runner.invoke(app, ["upgrade", "--pip"])
    assert result.exit_code == 1
    assert "Could not reach PyPI" in result.output


@pytest.mark.unit
def test_upgrade_mutual_exclusion() -> None:
    """Passing two flags at once exits with a usage error."""
    with (
        patch("ax.cli._start_upgrade_check"),
        patch("ax.commands.upgrade.fetch_pypi_version", return_value="0.14.0"),
    ):
        result = runner.invoke(app, ["upgrade", "--pip", "--pipx"])
    assert result.exit_code != 0
    assert "Specify at most one" in result.output


@pytest.mark.unit
def test_upgrade_no_flag_user_cancels() -> None:
    """Questionary returning None (Ctrl+C) exits with code 0."""
    with (
        patch("ax.commands.upgrade.__version__", "0.13.0"),
        patch("ax.commands.upgrade.fetch_pypi_version", return_value="0.14.0"),
        patch("ax.cli._start_upgrade_check"),
        patch("questionary.select") as mock_select,
        patch("ax.commands.upgrade.subprocess.run") as mock_run,
    ):
        mock_select.return_value.ask.return_value = None
        result = runner.invoke(app, ["upgrade"])
    assert result.exit_code == 0
    mock_run.assert_not_called()


@pytest.mark.unit
def test_upgrade_success_updates_cache() -> None:
    """Successful upgrade writes latest version to cache."""
    from ax.utils.upgrade_check import _DEFAULT_CACHE_PATH

    with (
        patch("ax.commands.upgrade.__version__", "0.13.0"),
        patch("ax.commands.upgrade.fetch_pypi_version", return_value="0.14.0"),
        patch("ax.cli._start_upgrade_check"),
        patch(
            "ax.commands.upgrade.subprocess.run",
            return_value=MagicMock(returncode=0),
        ),
        patch("ax.commands.upgrade._write_cache") as mock_write,
        patch("ax.commands.upgrade.time.time", return_value=9999.0),
    ):
        runner.invoke(app, ["upgrade", "--pip"])
    mock_write.assert_called_once_with(
        _DEFAULT_CACHE_PATH,
        {"last_check": 9999.0, "latest_version": "0.14.0"},
    )


@pytest.mark.unit
def test_upgrade_failure_does_not_update_cache() -> None:
    """Failed upgrade does not write to cache."""
    with (
        patch("ax.commands.upgrade.__version__", "0.13.0"),
        patch("ax.commands.upgrade.fetch_pypi_version", return_value="0.14.0"),
        patch("ax.cli._start_upgrade_check"),
        patch(
            "ax.commands.upgrade.subprocess.run",
            return_value=MagicMock(returncode=1),
        ),
        patch("ax.commands.upgrade._write_cache") as mock_write,
    ):
        runner.invoke(app, ["upgrade", "--pip"])
    mock_write.assert_not_called()
