"""Main CLI entry point using Typer."""

import logging
from typing import Annotated

import typer
from arize.logging import configure_logging

from ax.ascii_art import WELCOME_BANNER
from ax.utils.console import console, text
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
    # Suppress SDK logs by default; subcommands opt in via --verbose
    configure_logging(level=logging.CRITICAL, structured=False)

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
