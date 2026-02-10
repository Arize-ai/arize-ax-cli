from typing import Annotated

import typer

from ax.config.manager import ConfigManager
from ax.core.decorators import handle_errors
from ax.utils.console import confirm, info, success

# Create config subcommand app
app = typer.Typer(
    name="cache",
    help="Manage Arize cache",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


@app.command("clear")
@handle_errors
def clear_cache(
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help="Profile to show (uses active if not specified)",
        ),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
) -> None:
    """Clear the Arize SDK cache directory.

    Removes all cached data to free up space or force refresh.
    """
    if not confirm("Clear the Arize SDK cache?", default=False):
        info("Cache not cleared")
        raise typer.Exit()

    config = ConfigManager.load(profile)
    cache_dir = config.storage.cache_dir

    if cache_dir.exists() and cache_dir.is_dir():
        import shutil

        shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
    success("Cache cleared successfully")
