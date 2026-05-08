"""Role management commands."""

from typing import Annotated

import typer
from arize.roles.types import Permission

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
from ax.utils.file_io import parse_output_option

# Create roles subcommand app
app = typer.Typer(
    name="roles",
    help="Manage roles",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


def _parse_permissions(permissions: list[str] | None) -> list[Permission]:
    """Validate and convert a list of permission strings to Permission enum values."""
    if not permissions:
        return []
    result = []
    for p in (s.strip() for s in permissions if s.strip()):
        try:
            result.append(Permission(p))
        except ValueError as e:  # noqa: PERF203
            raise typer.BadParameter(
                f"Invalid permission: '{p}'. "
                "Use uppercase identifiers such as PROJECT_READ, DATASET_CREATE, etc. "
                f"({e})"
            ) from e
    return result


@app.command("list")
@handle_errors
def list_roles(
    is_predefined: Annotated[
        bool | None,
        typer.Option(
            "--is-predefined/--is-custom",
            help=(
                "Filter by role type: true for system-defined predefined roles, "
                "false for custom roles. Omit to return all."
            ),
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of roles to return",
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
    """List roles for the authenticated user's account."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching roles"):
            response = client.roles.list(
                limit=limit,
                cursor=cursor,
                is_predefined=is_predefined,
            )
    except Exception as e:
        raise APIError(f"Failed to list roles: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("get")
@handle_errors
def get_role(
    role: Annotated[
        str,
        typer.Argument(help="Role name or ID"),
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
    """Get a role by name or ID."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching role"):
            result = client.roles.get(role=role)
    except Exception as e:
        raise APIError(f"Failed to get role: {e}") from e
    else:
        output_data(
            result,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("create")
@handle_errors
def create_role(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Role name (must be unique within the account, max 255 characters)",
        ),
    ],
    permissions: Annotated[
        str | None,
        typer.Option(
            "--permissions",
            help=(
                "Comma-separated list of permissions to grant, "
                "e.g. PROJECT_READ,DATASET_CREATE. At least one is required."
            ),
        ),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            help="Optional description of the role's purpose (max 1000 characters)",
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
    """Create a new custom role.

    At least one --permissions entry must be provided. Role names must be unique
    within the account.
    """
    parsed_permissions = _parse_permissions(
        [s for s in permissions.split(",") if s.strip()]
        if permissions
        else None
    )
    if not parsed_permissions:
        raise typer.BadParameter(
            "At least one permission is required.",
            param_hint="'--permissions'",
        )

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Creating role", success_msg="Role created successfully"):
            role = client.roles.create(
                name=name,
                permissions=parsed_permissions,
                description=description,
            )
    except Exception as e:
        raise APIError(f"Failed to create role: {e}") from e
    else:
        output_data(
            role,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("update")
@handle_errors
def update_role(
    role: Annotated[
        str,
        typer.Argument(help="Role name or ID"),
    ],
    new_name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="New role name (max 255 characters)",
        ),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            help="New description (max 1000 characters)",
        ),
    ] = None,
    permissions: Annotated[
        str | None,
        typer.Option(
            "--permissions",
            help=(
                "Comma-separated replacement permissions, e.g. PROJECT_READ,DATASET_CREATE. "
                "When provided, fully replaces existing permissions."
            ),
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
    """Update a custom role.

    At least one of --name, --description, or --permissions must be provided.
    When --permissions is given, it fully replaces the existing permission set.
    Predefined (system-managed) roles cannot be updated.
    """
    if new_name is None and description is None and not permissions:
        raise typer.BadParameter(
            "At least one of --name, --description, or --permissions must be provided.",
            param_hint="'--name / --description / --permissions'",
        )

    if permissions:
        parsed_permissions = _parse_permissions(
            [s for s in permissions.split(",") if s.strip()]
        )
    else:
        parsed_permissions = None

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Updating role", success_msg="Role updated successfully"):
            updated_role = client.roles.update(
                role=role,
                name=new_name,
                description=description,
                permissions=parsed_permissions,
            )
    except Exception as e:
        raise APIError(f"Failed to update role: {e}") from e
    else:
        output_data(
            updated_role,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("delete")
@handle_errors
def delete_role(
    role: Annotated[
        str,
        typer.Argument(help="Role name or ID"),
    ],
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Skip confirmation prompt (recommended for automated/agent usage)",
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
    """Delete a custom role.

    Predefined (system-managed) roles cannot be deleted.
    Pass --force to skip the confirmation prompt.
    """
    setup_logging(verbose)
    client, _ = make_client()

    if not force:
        warning("This will permanently delete the role")

        if not confirm("Are you sure?", default=False):
            info("Role not deleted")
            raise typer.Exit()

    try:
        with spinner(
            "Deleting role",
            success_msg=f"Role '{role}' deleted successfully",
        ):
            client.roles.delete(role=role)
    except Exception as e:
        raise APIError(f"Failed to delete role: {e}") from e
