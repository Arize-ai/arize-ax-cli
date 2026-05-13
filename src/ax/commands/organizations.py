"""Organization management commands."""

from typing import Annotated

import typer

from ax.core.client_factory import make_client
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError
from ax.core.output import output_data
from ax.utils.console import confirm, info, setup_logging, spinner, warning
from ax.utils.file_io import parse_output_option

# Create organizations subcommand app
app = typer.Typer(
    name="organizations",
    help="Manage organizations",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


@app.command("list")
@handle_errors
def list_organizations(
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Filter organizations by name (case-insensitive substring match)",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of organizations to return (1-100)",
        ),
    ] = 50,
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
    """List organizations the authenticated user has access to."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching organizations"):
            response = client.organizations.list(
                name=name,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list organizations: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("get")
@handle_errors
def get_organization(
    organization: Annotated[
        str,
        typer.Argument(help="Organization name or ID"),
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
    """Get an organization by name or ID."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching organization"):
            result = client.organizations.get(organization=organization)
    except Exception as e:
        raise APIError(f"Failed to get organization: {e}") from e
    else:
        output_data(
            result,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("create")
@handle_errors
def create_organization(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Organization name (must be unique, max 255 characters)",
        ),
    ],
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            help="Optional description of the organization (max 1000 characters)",
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
    """Create a new organization.

    Organization names must be unique within the account.
    """
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Creating organization",
            success_msg="Organization created successfully",
        ):
            org = client.organizations.create(
                name=name,
                description=description,
            )
    except Exception as e:
        raise APIError(f"Failed to create organization: {e}") from e
    else:
        output_data(
            org,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("update")
@handle_errors
def update_organization(
    organization: Annotated[
        str,
        typer.Argument(help="Organization name or ID"),
    ],
    new_name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="New organization name (max 255 characters)",
        ),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            help="New description (max 1000 characters). Pass an empty string to clear.",
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
    """Update an organization's metadata.

    At least one of --name or --description must be provided.
    """
    if new_name is None and description is None:
        raise typer.BadParameter(
            "At least one of --name or --description must be provided.",
            param_hint="'--name / --description'",
        )

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Updating organization",
            success_msg="Organization updated successfully",
        ):
            updated_org = client.organizations.update(
                organization=organization,
                name=new_name,
                description=description,
            )
    except Exception as e:
        raise APIError(f"Failed to update organization: {e}") from e
    else:
        output_data(
            updated_org,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("add-user")
@handle_errors
def add_user_to_organization(
    organization: Annotated[
        str,
        typer.Argument(help="Organization name or ID"),
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
            help="Predefined organization role: admin, member, read-only, or annotator",
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
    """Add a user to an organization (or update their role if already a member).

    If the user is already a member, their role is updated (upsert semantics).
    """
    from arize.organizations.types import (
        OrganizationRole,
        PredefinedOrgRole,
    )

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Adding user to organization",
            success_msg="User added to organization successfully",
        ):
            membership = client.organizations.add_user(
                organization=organization,
                user_id=user_id,
                role=PredefinedOrgRole(name=OrganizationRole(role)),
            )
    except Exception as e:
        raise APIError(f"Failed to add user to organization: {e}") from e
    else:
        output_data(
            membership,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("remove-user")
@handle_errors
def remove_user_from_organization(
    organization: Annotated[
        str,
        typer.Argument(help="Organization name or ID"),
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
    """Remove a user from an organization.

    Also removes the user from all child spaces (membership cascade).
    """
    setup_logging(verbose)
    client, _ = make_client()

    if not force:
        warning(
            f"This will remove user '{user_id}' from organization '{organization}' and all its spaces"
        )

        if not confirm("Are you sure?", default=False):
            info("User not removed")
            raise typer.Exit()

    try:
        with spinner(
            "Removing user from organization",
            success_msg="User removed from organization successfully",
        ):
            client.organizations.remove_user(
                organization=organization,
                user_id=user_id,
            )
    except Exception as e:
        raise APIError(f"Failed to remove user from organization: {e}") from e
