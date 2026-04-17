"""Main CLI entry point using Typer."""

import logging
import threading
from typing import Annotated

import typer
from arize.logging import configure_logging

from ax.ascii_art import WELCOME_BANNER
from ax.utils.console import console, new_line, text, warning
from ax.version import __version__

# TODO(Kiko): Ensure that every command has @handle_errors decorator

# Create main app
app = typer.Typer(
    name="ax",
    help="Arize CLI - Manage Arize resources from your terminal",
    add_completion=True,
    rich_markup_mode="rich",
    invoke_without_command=True,
    context_settings={
        "help_option_names": ["--help", "-h"],
    },
)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        text(f"ax version {__version__}")
        raise typer.Exit()


def _start_upgrade_check() -> threading.Thread | None:
    """Start background update check using profile config if available."""
    from ax.config.manager import ConfigManager
    from ax.core.exceptions import ConfigError
    from ax.utils.upgrade_check import start_background_check

    try:
        config = ConfigManager.load("")
        return start_background_check(
            enabled=config.update.enabled,
            interval_hours=config.update.check_interval_hours,
        )
    except ConfigError:
        return None


# This function gets called when `ax COMMAND` is executed, including `ax profiles create`
# which means we can't require config to be present at this point
@app.callback()
def main(
    ctx: typer.Context,
    _: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit",
        ),
    ] = False,
) -> None:
    """Arize CLI - Manage datasets, experiments, and more.

    Use 'ax COMMAND --help' for more information on a command.
    """
    configure_logging(level=logging.CRITICAL, structured=False)
    upgrade_thread = _start_upgrade_check()

    invoked = ctx.invoked_subcommand

    def _after_command() -> None:
        if invoked == "upgrade":
            return
        if upgrade_thread is not None:
            from ax.utils.upgrade_check import PYPI_TIMEOUT

            upgrade_thread.join(timeout=PYPI_TIMEOUT)
        from ax.utils.upgrade_check import should_upgrade

        if should_upgrade():
            new_line()
            warning(
                "New version of ax available. This CLI is still in pre-release, you should upgrade.",
            )
            warning("To upgrade, run: 'ax upgrade'", show_symbol=False)

    ctx.call_on_close(_after_command)

    if ctx.invoked_subcommand is None:
        console.print(WELCOME_BANNER)
        console.print()
        console.print(ctx.get_help())


# Import and register command groups
def register_commands() -> None:
    """Auto-discover and register all command groups from ax.commands.

    Any module inside ax/commands/ that exposes a top-level ``app``
    attribute (a ``typer.Typer`` instance) is registered automatically.
    Adding a new command file to that package is sufficient — no changes
    here are required.
    """
    import importlib
    import pkgutil

    import ax.commands as commands_pkg

    for module_info in sorted(
        pkgutil.iter_modules(commands_pkg.__path__), key=lambda m: m.name
    ):
        try:
            module = importlib.import_module(f"ax.commands.{module_info.name}")
        except Exception as e:
            raise RuntimeError(
                f"Failed to load command module 'ax.commands.{module_info.name}': {e}"
            ) from e
        command_app = getattr(module, "app", None)
        if isinstance(command_app, typer.Typer):
            app.add_typer(command_app)


# Register commands on module import
register_commands()


if __name__ == "__main__":
    app()
