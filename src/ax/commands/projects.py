"""Project management commands."""

from typing import Annotated

import typer

from ax.core.client_factory import make_client
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError
from ax.core.output import output_data
from ax.utils.console import (
    confirm,
    info,
    setup_logging,
    spinner,
    warning,
)
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


@app.command("list")
@handle_errors
def list_projects(
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Case-insensitive substring filter on project name",
        ),
    ] = None,
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of projects to return",
        ),
    ] = 15,
    cursor: Annotated[
        str | None,
        typer.Option(
            "--cursor",
            "-c",
            help="Pagination cursor for next page",
        ),
    ] = None,
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
    setup_logging(verbose)
    client, config = make_client()

    # Resolve with helper functions
    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching projects"):
            response = client.projects.list(
                name=name,
                space=space,
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
    space: Annotated[
        str,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID",
            prompt=True,
        ),
    ],
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
    setup_logging(verbose)
    client, config = make_client()

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
                space=space,
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
    name_or_id: Annotated[
        str,
        typer.Argument(help="Project name or ID"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using project name instead of ID)",
        ),
    ] = None,
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
    """Get a project by name or ID."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching project"):
            project = client.projects.get(
                project=name_or_id,
                space=space,
            )
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
    name_or_id: Annotated[
        str,
        typer.Argument(help="Project name or ID"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using project name instead of ID)",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Skip confirmation prompt",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
) -> None:
    """Delete a project by name or ID."""
    setup_logging(verbose)
    client, _ = make_client()

    # Confirm deletion
    if not force:
        warning("This will permanently delete the project")

        if not confirm("Are you sure?", default=False):
            info("Project not deleted")
            raise typer.Exit()

    # Delete project
    try:
        with spinner(
            "Deleting project",
            success_msg=f"Project '{name_or_id}' deleted successfully",
        ):
            client.projects.delete(
                project=name_or_id,
                space=space,
            )
    except Exception as e:
        raise APIError(f"Failed to delete project: {e}") from e
