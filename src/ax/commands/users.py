"""User management commands."""

from typing import Annotated

import typer

from ax.core.client_factory import make_client
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError, AxError
from ax.core.output import output_data
from ax.utils.console import (
    confirm,
    error,
    info,
    setup_logging,
    spinner,
    success,
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
            help="Filter by status (ACTIVE, INVITED). Can be specified multiple times.",
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
            help="Account-level predefined role (ADMIN, MEMBER, ANNOTATOR)",
            prompt=True,
        ),
    ],
    invite_mode: Annotated[
        str,
        typer.Option(
            "--invite-mode",
            help="Invite mode: NONE, EMAIL_LINK, or TEMPORARY_PASSWORD",
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

    The --role flag accepts predefined role names: ADMIN, MEMBER, or ANNOTATOR.
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
def delete_users(
    user_ids: Annotated[
        list[str],
        typer.Option(
            "--id",
            help=(
                "User ID to delete"
                "(--id id1,id2,id3); the flag can also be repeated "
                "(--id id1 --id id2)."
            ),
        ),
    ] = [],  # noqa: B006
    emails: Annotated[
        list[str],
        typer.Option(
            "--email",
            "-e",
            help=(
                "User email to resolve and delete"
                "values (--email a@b.com,c@d.com); the flag can also be "
                "repeated (--email a@b.com --email c@d.com)."
            ),
        ),
    ] = [],  # noqa: B006
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Skip confirmation prompt",
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
    r"""Delete one or more users by ID or email address.

    Provide --id and/or --email flags. Both accept repeated flags or
    comma-separated values. Emails are resolved to user IDs before deletion.

    Each deletion is attempted independently; the results table shows the
    outcome (deleted, failed, not_found) for each user.

    \b
    Examples:
        ax users delete --id usr_abc123
        ax users delete --id id1,id2,id3
        ax users delete --email user@example.com
        ax users delete --id id1 --email user@example.com
    """
    setup_logging(verbose)

    flat_ids = [
        uid.strip() for s in user_ids for uid in s.split(",") if uid.strip()
    ]
    flat_emails = [
        em.strip() for s in emails for em in s.split(",") if em.strip()
    ]

    if not flat_ids and not flat_emails:
        error("At least one --id or --email must be provided")
        raise typer.Exit(code=1)

    total = len(flat_ids) + len(flat_emails)

    client, config = make_client()

    if not force:
        warning(
            f"This will permanently delete {total} user(s) and cascade to all"
            " memberships, API keys, and role bindings"
        )

        if not confirm("Are you sure?", default=False):
            info("Users not deleted")
            raise typer.Exit()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Deleting users"):
            results = client.users.bulk_delete(
                user_ids=flat_ids or None,
                emails=flat_emails or None,
            )
    except AxError:
        raise
    except Exception as e:
        raise APIError(f"Failed to delete users: {e}") from e

    from arize.users.types import BulkDeleteResponse, DeletionStatus

    deleted = sum(1 for r in results if r.status == DeletionStatus.DELETED)
    failed = sum(1 for r in results if r.status == DeletionStatus.FAILED)
    not_found = sum(1 for r in results if r.status == DeletionStatus.NOT_FOUND)

    success(
        f"Delete complete: {deleted} deleted, "
        f"{failed} failed, {not_found} not found"
    )

    output_data(
        BulkDeleteResponse(results=results),
        format_type=output_format,
        output_file=output_file,
        status_colors={
            "deleted": "green",
            "failed": "red",
            "not_found": "yellow",
        },
    )


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
