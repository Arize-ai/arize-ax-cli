"""Main CLI entry point using Typer."""

import logging
from typing import Annotated

import typer
from arize.logging import configure_logging

from ax.utils.console import text
from ax.version import __version__

# TODO(Kiko): Ensure that every command has @handle_errors decorator

# Create main app
app = typer.Typer(
    name="ax",
    help="Arize CLI - Manage datasets, experiments, and more",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=True,
    context_settings={
        "help_option_names": ["--help", "-h"],
    },
)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        text(f"ax version {__version__}")
        raise typer.Exit()


# This function gets called when `ax COMMAND` is exectuted, included `ax config init`
# which means we can't require config to be present at this point
@app.callback()
def main(
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
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
    # Configure logging for the Arize SDK based on verbose mode
    if verbose:
        # Show all SDK logs in verbose mode
        configure_logging(level=logging.DEBUG, structured=False)
    else:
        # Suppress SDK logs in normal mode to avoid interrupting spinners
        configure_logging(level=logging.CRITICAL, structured=False)


# Import and register command groups
# These will be implemented in separate files
def register_commands() -> None:
    """Register all command groups."""
    from ax.commands.cache import app as cache_app
    from ax.commands.config import app as config_app
    from ax.commands.datasets import app as datasets_app
    from ax.commands.projects import app as projects_app

    app.add_typer(datasets_app, name="datasets", help="Manage datasets")
    app.add_typer(projects_app, name="projects", help="Manage projects")
    app.add_typer(config_app, name="config", help="Manage configuration")
    app.add_typer(cache_app, name="cache", help="Manage cache")


# Register commands on module import
register_commands()


if __name__ == "__main__":
    app()
