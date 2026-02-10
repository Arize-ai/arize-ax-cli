"""Project management commands."""

from dataclasses import asdict
from typing import Annotated

import typer
from arize import ArizeClient
from click import confirm
from rich.console import Console

from ax.config.manager import ConfigManager
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError
from ax.core.output import output_data
from ax.utils.console import info, spinner, success, warning
from ax.utils.file_io import (
    parse_output_option,
)

# Create projects subcommand app
app = typer.Typer(
    name="projects",
    help="Manage projects",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)

console = Console()


@app.command("list")
@handle_errors
def list_projects(
    space_id: Annotated[
        str | None,
        typer.Option(
            "--space-id",
            help="Space ID to list projects from",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum number of projects to return",
        ),
    ] = 15,
    cursor: Annotated[
        str | None,
        typer.Option(
            "--cursor",
            help="Pagination cursor for next page",
        ),
    ] = None,
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help="Configuration profile to use",
        ),
    ] = "",
    output: Annotated[
        str,
        typer.Option(
            "--output",
            "-o",
            help="Output format (table, json, csv, parquet) or file path",
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
    """List projects in a space."""
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    # Resolve with helper functions
    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching projects"):
            response = client.projects.list(
                space_id=space_id,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list projects: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )
        if output_file:
            success(f"Saved projects to {output_file}")


@app.command("create")
@handle_errors
def create_project(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Project name",
            prompt=True,
        ),
    ],
    space_id: Annotated[
        str,
        typer.Option(
            "--space-id",
            help="Space ID",
            prompt=True,
        ),
    ],
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help="Configuration profile to use",
        ),
    ] = "",
    output: Annotated[
        str,
        typer.Option(
            "--output",
            "-o",
            help="Output format (table, json, csv, parquet) or file path",
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
    """Create a new project."""
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )
    try:
        # Create project
        with spinner(
            "Creating project",
            success_msg="Project created successfully",
        ):
            project = client.projects.create(
                name=name,
                space_id=space_id,
            )
    except Exception as e:
        raise APIError(f"Failed to create project: {e}") from e
    else:
        output_data(
            project,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("get")
@handle_errors
def get_project(
    id: Annotated[
        str,
        typer.Argument(help="Project ID"),
    ],
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help="Configuration profile to use",
        ),
    ] = "",
    output: Annotated[
        str,
        typer.Option(
            "--output",
            "-o",
            help="Output format (table, json, csv, parquet) or file path",
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
    """Get a project by ID."""
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    # Resolve with helper functions
    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        project = client.projects.get(project_id=id)
    except Exception as e:
        raise APIError(f"Failed to get project: {e}") from e
    else:
        output_data(
            project,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("delete")
@handle_errors
def delete_project(
    id: Annotated[
        str,
        typer.Argument(help="Project ID"),
    ],
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Skip confirmation prompt",
        ),
    ] = False,
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help="Configuration profile to use",
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
    """Delete a project by ID."""
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    # Confirm deletion
    if not force:
        warning("Warning: This will permanently delete the project")

        if not confirm("Are you sure?", default=False):
            info("Project not deleted")
            raise typer.Exit()

    # Delete project
    try:
        client.projects.delete(project_id=id)
    except Exception as e:
        raise APIError(f"Failed to delete project: {e}") from e
    else:
        success(f"Project with ID '{id}' deleted successfully")
