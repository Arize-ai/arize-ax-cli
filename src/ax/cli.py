"""Main CLI entry point using Typer."""

import logging
from typing import Annotated

import typer
from arize.logging import configure_logging

from ax.ascii_art import DEFAULT_BANNER
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
        console.print(DEFAULT_BANNER)
        console.print()
        console.print(ctx.get_help())


# Import and register command groups
# These will be implemented in separate files
def register_commands() -> None:
    """Register all command groups."""
    from ax.commands.cache import app as cache_app
    from ax.commands.datasets import app as datasets_app
    from ax.commands.experiments import app as experiments_app
    from ax.commands.profiles import app as profiles_app
    from ax.commands.projects import app as projects_app
    from ax.commands.spans import app as spans_app
    from ax.commands.traces import app as traces_app

    # Sorted alphabetically for consistency
    app.add_typer(cache_app)
    app.add_typer(datasets_app)
    app.add_typer(experiments_app)
    app.add_typer(profiles_app)
    app.add_typer(projects_app)
    app.add_typer(spans_app)
    app.add_typer(traces_app)


# Register commands on module import
register_commands()


if __name__ == "__main__":
    app()
