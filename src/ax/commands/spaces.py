"""Space management commands."""

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

# Create spaces subcommand app
app = typer.Typer(
    name="spaces",
    help="Manage spaces",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


@app.command("list")
@handle_errors
def list_spaces(
    organization_id: Annotated[
        str | None,
        typer.Option(
            "--organization-id",
            help="Organization ID to filter spaces",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of spaces to return",
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
    """List spaces."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching spaces"):
            response = client.spaces.list(
                organization_id=organization_id,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list spaces: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("get")
@handle_errors
def get_space(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Space name or ID"),
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
    """Get a space by name or ID."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching space"):
            space = client.spaces.get(space=name_or_id)
    except Exception as e:
        raise APIError(f"Failed to get space: {e}") from e
    else:
        output_data(
            space,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("create")
@handle_errors
def create_space(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Space name",
            prompt=True,
        ),
    ],
    organization_id: Annotated[
        str,
        typer.Option(
            "--organization-id",
            help="Organization ID",
            prompt=True,
        ),
    ],
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            help="Space description",
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
    """Create a new space."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Creating space", success_msg="Space created successfully"
        ):
            space = client.spaces.create(
                name=name,
                organization_id=organization_id,
                description=description,
            )
    except Exception as e:
        raise APIError(f"Failed to create space: {e}") from e
    else:
        output_data(
            space,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("update")
@handle_errors
def update_space(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Space name or ID"),
    ],
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="New space name",
        ),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            help="New space description",
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
    """Update a space by name or ID."""
    if name is None and description is None:
        warning("At least one of --name or --description must be provided")
        raise typer.Exit(code=1)

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Updating space", success_msg="Space updated successfully"
        ):
            space = client.spaces.update(
                space=name_or_id,
                name=name,
                description=description,
            )
    except Exception as e:
        raise APIError(f"Failed to update space: {e}") from e
    else:
        output_data(
            space,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("delete")
@handle_errors
def delete_space(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Space name or ID"),
    ],
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
    """Delete a space and all resources within it."""
    setup_logging(verbose)
    client, _ = make_client()

    if not force:
        warning("This action is irreversible and will permanently delete:")
        warning(
            "  \u2022 The space and all of its contents",
            show_symbol=False,
        )
        warning(
            "  \u2022 All models, monitors, and dashboards",
            show_symbol=False,
        )
        warning(
            "  \u2022 All datasets, custom metrics, and experiments",
            show_symbol=False,
        )

        confirmation = typer.prompt("\nTo confirm, type the space name or ID")
        if confirmation != name_or_id:
            info("Space not deleted")
            raise typer.Exit()

    try:
        with spinner(
            "Deleting space",
            success_msg=f"Space '{name_or_id}' deleted successfully",
        ):
            client.spaces.delete(space=name_or_id)
    except Exception as e:
        raise APIError(f"Failed to delete space: {e}") from e


@app.command("add-user")
@handle_errors
def add_user_to_space(
    space: Annotated[
        str,
        typer.Argument(help="Space name or ID"),
    ],
    user_id: Annotated[
        str,
        typer.Option(
            "--user-id",
            help="Global ID of the user to add",
            prompt=True,
        ),
    ],
    role: Annotated[
        str,
        typer.Option(
            "--role",
            "-r",
            help="Predefined space role: ADMIN, MEMBER, READ_ONLY, or ANNOTATOR",
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
    """Add a user to a space (or update their role if already a member).

    The user must already be a member of the space's parent organization.
    If the user is already a member of the space, their role is updated (upsert semantics).
    """
    from arize.spaces.types import PredefinedSpaceRole, UserSpaceRole

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Adding user to space",
            success_msg="User added to space successfully",
        ):
            membership = client.spaces.add_user(
                space=space,
                user_id=user_id,
                role=PredefinedSpaceRole(name=UserSpaceRole(role)),
            )
    except Exception as e:
        raise APIError(f"Failed to add user to space: {e}") from e
    else:
        output_data(
            membership,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("remove-user")
@handle_errors
def remove_user_from_space(
    space: Annotated[
        str,
        typer.Argument(help="Space name or ID"),
    ],
    user_id: Annotated[
        str,
        typer.Option(
            "--user-id",
            help="Global ID of the user to remove",
            prompt=True,
        ),
    ],
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
    """Remove a user from a space."""
    setup_logging(verbose)
    client, _ = make_client()

    if not force:
        warning(f"This will remove user '{user_id}' from space '{space}'")

        if not confirm("Are you sure?", default=False):
            info("User not removed")
            raise typer.Exit()

    try:
        with spinner(
            "Removing user from space",
            success_msg="User removed from space successfully",
        ):
            client.spaces.remove_user(space=space, user_id=user_id)
    except Exception as e:
        raise APIError(f"Failed to remove user from space: {e}") from e
