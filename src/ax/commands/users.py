"""User management commands."""

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
from ax.utils.file_io import parse_output_option

# Create users subcommand app
app = typer.Typer(
    name="users",
    help="Manage users",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


@app.command("list")
@handle_errors
def list_users(
    email: Annotated[
        str | None,
        typer.Option(
            "--email",
            "-e",
            help="Filter users by email (case-insensitive substring match)",
        ),
    ] = None,
    status: Annotated[
        list[str] | None,
        typer.Option(
            "--status",
            "-s",
            help="Filter by status (active, invited). Can be specified multiple times.",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of users to return (1-100)",
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
    """List users in the account."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    from arize.users.types import UserStatus

    status_enums = [UserStatus(s) for s in status] if status else None

    try:
        with spinner("Fetching users"):
            response = client.users.list(
                email=email,
                status=status_enums,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list users: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("get")
@handle_errors
def get_user(
    user: Annotated[
        str,
        typer.Argument(help="User ID or email address"),
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
    """Get a user by ID or email address."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching user"):
            result = client.users.get(user=user)
    except Exception as e:
        raise APIError(f"Failed to get user: {e}") from e
    else:
        if result is None:
            raise APIError(f"User '{user}' not found")
        output_data(
            result,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("create")
@handle_errors
def create_user(
    full_name: Annotated[
        str,
        typer.Option(
            "--full-name",
            "-n",
            help="Full name for the user (1-255 characters)",
            prompt=True,
        ),
    ],
    email: Annotated[
        str,
        typer.Option(
            "--email",
            "-e",
            help="Email address (used as the idempotency key)",
            prompt=True,
        ),
    ],
    role: Annotated[
        str,
        typer.Option(
            "--role",
            "-r",
            help="Account-level predefined role (admin, member, annotator)",
            prompt=True,
        ),
    ],
    invite_mode: Annotated[
        str,
        typer.Option(
            "--invite-mode",
            help="Invite mode: none, email_link, or temporary_password",
            prompt=True,
        ),
    ],
    is_not_developer: Annotated[
        bool,
        typer.Option(
            "--is-not-developer",
            help=(
                "Disable developer permissions. By default, new users are granted developer "
                "permissions to use the Arize API."
            ),
        ),
    ] = False,
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
    """Create a new user with a builtin account-level role.

    The --role flag accepts predefined role names: admin, member, or annotator.
    """
    from arize.users.types import InviteMode, PredefinedUserRole, UserRole

    try:
        invite_mode_enum = InviteMode(invite_mode)
    except ValueError:
        valid = ", ".join(m.value for m in InviteMode)
        raise typer.BadParameter(
            f"Invalid invite mode '{invite_mode}'. Must be one of: {valid}",
            param_hint="'--invite-mode'",
        ) from None

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Creating user", success_msg="User created successfully"):
            user = client.users.create(
                name=full_name,
                email=email,
                role=PredefinedUserRole(name=UserRole(role)),
                invite_mode=invite_mode_enum,
                is_developer=not is_not_developer,
            )
    except Exception as e:
        raise APIError(f"Failed to create user: {e}") from e
    else:
        output_data(
            user,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("update")
@handle_errors
def update_user(
    user_id: Annotated[
        str,
        typer.Argument(help="User ID"),
    ],
    full_name: Annotated[
        str | None,
        typer.Option(
            "--full-name",
            "-n",
            help="New full name for the user",
        ),
    ] = None,
    is_developer: Annotated[
        bool | None,
        typer.Option(
            "--is-developer/--is-not-developer",
            help="Update developer permission flag",
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
    """Update a user's full name or developer permission flag.

    At least one of --full-name or --is-developer/--is-not-developer must be provided.
    """
    if full_name is None and is_developer is None:
        raise typer.BadParameter(
            "At least one of --full-name or --is-developer/--is-not-developer must be provided.",
            param_hint="'--full-name / --is-developer'",
        )

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Updating user", success_msg="User updated successfully"):
            updated = client.users.update(
                user_id=user_id,
                name=full_name,
                is_developer=is_developer,
            )
    except Exception as e:
        raise APIError(f"Failed to update user: {e}") from e
    else:
        output_data(
            updated,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("delete")
@handle_errors
def delete_user(
    user_id: Annotated[
        str,
        typer.Argument(help="User ID"),
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
    """Delete a user by ID.

    This deletes the user and cascades to organization memberships,
    space memberships, API keys, and role bindings.
    """
    setup_logging(verbose)
    client, _ = make_client()

    if not force:
        warning(
            "This will permanently delete the user and cascade to all"
            " memberships, API keys, and role bindings"
        )

        if not confirm("Are you sure?", default=False):
            info("User not deleted")
            raise typer.Exit()

    try:
        with spinner(
            "Deleting user",
            success_msg=f"User '{user_id}' deleted successfully",
        ):
            client.users.delete(user_id=user_id)
    except Exception as e:
        raise APIError(f"Failed to delete user: {e}") from e


@app.command("resend-invitation")
@handle_errors
def resend_invitation(
    user_id: Annotated[
        str,
        typer.Argument(help="User ID"),
    ],
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
) -> None:
    """Resend an invitation email for a pending (invited) user."""
    setup_logging(verbose)
    client, _ = make_client()

    try:
        with spinner(
            "Resending invitation",
            success_msg="Invitation resent successfully",
        ):
            client.users.resend_invitation(user_id=user_id)
    except Exception as e:
        raise APIError(f"Failed to resend invitation: {e}") from e


@app.command("reset-password")
@handle_errors
def reset_password(
    user_id: Annotated[
        str,
        typer.Argument(help="User ID"),
    ],
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
) -> None:
    """Send a password-reset email to a user.

    The user must authenticate via password (not SSO/SAML) and must have
    already verified their account.
    """
    setup_logging(verbose)
    client, _ = make_client()

    try:
        with spinner(
            "Sending password reset email",
            success_msg="Password reset email sent successfully",
        ):
            client.users.reset_password(user_id=user_id)
    except Exception as e:
        raise APIError(f"Failed to reset password: {e}") from e
