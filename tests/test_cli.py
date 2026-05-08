"""Integration tests for the main CLI app and auto-discovery registration."""

import importlib
import pkgutil
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

import ax.commands as commands_pkg
from ax.cli import app

runner = CliRunner()


def _discoverable_command_names() -> set[str]:
    """Return the names of all Typer apps found in ax.commands at runtime.

    This mirrors what register_commands() does, so tests stay in sync with
    the package automatically — no hardcoded list to maintain.
    """
    names = set()
    for module_info in pkgutil.iter_modules(commands_pkg.__path__):
        module = importlib.import_module(f"ax.commands.{module_info.name}")
        command_app = getattr(module, "app", None)
        if isinstance(command_app, typer.Typer) and command_app.info.name:
            names.add(command_app.info.name)
    return names


class TestCommandRegistration:
    """Verify auto-discovery registers the expected command groups."""

    def test_all_commands_appear_in_help(self) -> None:
        """Every discoverable command group is listed in 'ax --help' output."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for name in _discoverable_command_names():
            assert name in result.output, (
                f"Command '{name}' missing from help output"
            )

    def test_registered_commands_match_package_contents(self) -> None:
        """Registered commands exactly match the Typer apps in ax.commands."""
        registered = {g.typer_instance.info.name for g in app.registered_groups}
        assert registered == _discoverable_command_names()

    def test_commands_registered_in_alphabetical_order(self) -> None:
        """Commands are registered alphabetically (controls help output order)."""
        names = [g.typer_instance.info.name for g in app.registered_groups]
        assert names == sorted(names)

    def test_broken_module_raises_helpful_error(self) -> None:
        """An import error in a command module surfaces a clear RuntimeError."""
        from ax import cli

        fake_module_info = MagicMock()
        fake_module_info.name = "broken_cmd"

        with (
            patch("pkgutil.iter_modules", return_value=[fake_module_info]),
            patch(
                "importlib.import_module",
                side_effect=ImportError("no module named 'missing_dep'"),
            ),
            pytest.raises(RuntimeError, match="broken_cmd"),
        ):
            cli.register_commands()

    def test_module_without_app_attribute_is_skipped(self) -> None:
        """A module in commands/ that has no 'app' attribute is silently ignored."""
        from ax import cli

        fake_module_info = MagicMock()
        fake_module_info.name = "helper"

        fake_module = MagicMock(spec=[])  # no attributes

        with (
            patch("pkgutil.iter_modules", return_value=[fake_module_info]),
            patch("importlib.import_module", return_value=fake_module),
        ):
            # Should complete without error and add nothing
            before = len(app.registered_groups)
            cli.register_commands()
            assert len(app.registered_groups) == before

    def test_module_with_non_typer_app_is_skipped(self) -> None:
        """A module whose 'app' is not a Typer instance is silently ignored."""
        from ax import cli

        fake_module_info = MagicMock()
        fake_module_info.name = "not_a_command"

        fake_module = MagicMock()
        fake_module.app = "not a typer instance"

        with (
            patch("pkgutil.iter_modules", return_value=[fake_module_info]),
            patch("importlib.import_module", return_value=fake_module),
        ):
            before = len(app.registered_groups)
            cli.register_commands()
            assert len(app.registered_groups) == before


class TestMainCLIBehavior:
    """Smoke tests for top-level CLI behavior."""

    def test_version_flag(self) -> None:
        """'ax --version' prints the version string and exits 0."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "ax version" in result.output

    def test_short_version_flag(self) -> None:
        """-v is not defined; should show an error, not crash."""
        result = runner.invoke(app, ["-v"])
        assert result.exit_code != 0

    def test_no_args_shows_banner_and_help(self) -> None:
        """'ax' with no args shows the banner and lists commands."""
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "Arize" in result.output
        assert "datasets" in result.output

    def test_unknown_command_exits_nonzero(self) -> None:
        """An unrecognised command name exits with a non-zero code."""
        result = runner.invoke(app, ["nonexistent-command"])
        assert result.exit_code != 0

    def test_upgrade_warning_shown_after_subcommand(self) -> None:
        """result_callback prints upgrade warning when newer version is available."""
        with (
            patch(
                "ax.utils.upgrade_check.should_upgrade",
                return_value=True,
            ),
            patch("ax.cli._start_upgrade_check"),
            patch("ax.commands.spaces.make_client"),
            patch("ax.config.manager.ConfigManager.load"),
        ):
            result = runner.invoke(app, ["spaces", "list"])
        assert "New version of ax available" in result.output

    def test_upgrade_warning_suppressed_for_upgrade_command(self) -> None:
        """result_callback does not print warning after 'ax upgrade' runs."""
        with (
            patch(
                "ax.utils.upgrade_check.should_upgrade",
                return_value=True,
            ),
            patch("ax.cli._start_upgrade_check"),
            patch(
                "ax.utils.upgrade_check.fetch_pypi_version",
                return_value="9.9.9",
            ),
        ):
            result = runner.invoke(app, ["upgrade", "--help"])
        assert "New version of ax available" not in result.output
