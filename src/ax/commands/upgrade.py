"""Upgrade command for the ax CLI."""

from __future__ import annotations

import subprocess
import time
from typing import Annotated

import questionary
import typer
from packaging.version import Version

from ax.core.decorators import handle_errors
from ax.utils.console import info, success, warning
from ax.utils.upgrade_check import (
    _DEFAULT_CACHE_PATH,
    _write_cache,
    fetch_pypi_version,
)
from ax.version import __version__

app = typer.Typer(
    name="upgrade",
    help="Upgrade ax CLI to the latest version",
    invoke_without_command=True,
    no_args_is_help=False,
    context_settings={"help_option_names": ["--help", "-h"]},
)

_UPGRADE_COMMANDS: dict[str, list[str]] = {
    "pip": ["pip", "install", "--upgrade", "arize-ax-cli"],
    "pipx": ["pipx", "upgrade", "arize-ax-cli"],
    "uv": ["uv", "tool", "upgrade", "arize-ax-cli"],
}


@app.callback()
@handle_errors
def upgrade(
    pip: Annotated[
        bool,
        typer.Option("--pip", help="Upgrade using pip", is_flag=True),
    ] = False,
    pipx: Annotated[
        bool,
        typer.Option("--pipx", help="Upgrade using pipx", is_flag=True),
    ] = False,
    uv: Annotated[
        bool,
        typer.Option("--uv", help="Upgrade using uv tool", is_flag=True),
    ] = False,
) -> None:
    """Upgrade ax to the latest version.

    Fetches the latest version from PyPI and runs the appropriate upgrade
    command based on the selected package manager.

    Args:
        pip: Upgrade using pip.
        pipx: Upgrade using pipx.
        uv: Upgrade using uv tool.

    Raises:
        typer.BadParameter: If more than one package manager flag is specified.
        typer.Exit: After running the upgrade command or on error.
    """
    if sum([pip, pipx, uv]) > 1:
        raise typer.BadParameter(
            "Specify at most one of --pip, --pipx, or --uv."
        )

    latest = fetch_pypi_version()
    if latest is None:
        warning(
            "Could not reach PyPI to check the latest version. Check your network connection."
        )
        raise typer.Exit(code=1)

    if Version(latest) <= Version(__version__):
        success("You're already on the latest version.")
        return

    info(f"Current version: {__version__}")
    info(f"Latest version:  {latest}")

    manager = next(
        (m for m, flag in [("pip", pip), ("pipx", pipx), ("uv", uv)] if flag),
        None,
    )
    if manager is None:
        manager = questionary.select(
            "How did you install ax?", choices=["pip", "pipx", "uv"]
        ).ask()
        if manager is None:
            raise typer.Exit(code=0)

    result = subprocess.run(_UPGRADE_COMMANDS[manager], check=False)  # noqa: S603
    if result.returncode == 0:
        _write_cache(
            _DEFAULT_CACHE_PATH,
            {"last_check": time.time(), "latest_version": latest},
        )
    raise typer.Exit(code=result.returncode)
