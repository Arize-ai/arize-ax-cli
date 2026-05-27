"""API key management commands."""

from typing import Annotated

import typer
from arize.api_keys.types import (
    ApiKeyAccountRole,
    ApiKeyOrganizationRole,
    ApiKeySpaceRole,
    ApiKeyStatus,
    ApiKeyType,
)

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
from ax.utils.datetime_parse import parse_optional_iso8601
from ax.utils.file_io import parse_output_option

# Create api-keys subcommand app
app = typer.Typer(
    name="api-keys",
    help="Manage API keys",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


@app.command("list")
@handle_errors
def list_api_keys(
    key_type: Annotated[
        ApiKeyType | None,
        typer.Option(
            "--key-type",
            help="Filter by key type: 'user' or 'service'",
        ),
    ] = None,
    status: Annotated[
        ApiKeyStatus | None,
        typer.Option(
            "--status",
            help="Filter by status: 'active' or 'deleted'",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of API keys to return",
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
    """List API keys for the authenticated user."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching API keys"):
            response = client.api_keys.list(
                key_type=key_type,
                status=status,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list API keys: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("create")
@handle_errors
def create_api_key(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Name for the API key (max 256 characters)",
        ),
    ],
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            help="Optional description (max 1000 characters)",
        ),
    ] = None,
    expires_at: Annotated[
        str | None,
        typer.Option(
            "--expires-at",
            help=(
                "Expiration datetime in ISO 8601 format "
                "(e.g. '2025-12-31T23:59:59'). If omitted, key never expires."
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
    """Create a new user API key.

    Authenticates as you with your full permissions. The raw key value is
    printed once after creation — save it securely, it will not be shown again.

    To create a space-scoped service key, use ``create-service-key`` instead.
    """
    expires_at_dt = parse_optional_iso8601(expires_at)

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Creating API key", success_msg="API key created successfully"
        ):
            key_created = client.api_keys.create(
                name=name,
                description=description,
                expires_at=expires_at_dt,
            )
    except Exception as e:
        raise APIError(f"Failed to create API key: {e}") from e
    else:
        warning("Save this API key now — it will not be shown again.")
        output_data(
            key_created,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("create-service-key")
@handle_errors
def create_service_api_key(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Name for the API key (max 256 characters)",
        ),
    ],
    space: Annotated[
        str,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID the service key is scoped to",
        ),
    ],
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            help="Optional description (max 1000 characters)",
        ),
    ] = None,
    expires_at: Annotated[
        str | None,
        typer.Option(
            "--expires-at",
            help=(
                "Expiration datetime in ISO 8601 format "
                "(e.g. '2025-12-31T23:59:59'). If omitted, key never expires."
            ),
        ),
    ] = None,
    space_role: Annotated[
        ApiKeySpaceRole | None,
        typer.Option(
            "--space-role",
            help="Space role for the bot user: admin, member, or read-only",
        ),
    ] = None,
    org_role: Annotated[
        ApiKeyOrganizationRole | None,
        typer.Option(
            "--org-role",
            help="Organization role for the bot user: admin, member, or read-only",
        ),
    ] = None,
    account_role: Annotated[
        ApiKeyAccountRole | None,
        typer.Option(
            "--account-role",
            help="Account role for the bot user: admin or member",
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
    """Create a new service API key scoped to a space.

    Service keys are backed by a dedicated bot user with configurable roles.
    When no roles are specified the server applies its defaults
    (space_role=member, org_role=read-only, account_role=member).

    The raw key value is printed once after creation — save it securely,
    it will not be shown again.
    """
    expires_at_dt = parse_optional_iso8601(expires_at)

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Creating service API key",
            success_msg="Service API key created successfully",
        ):
            key_created = client.api_keys.create_service_key(
                name=name,
                space=space,
                description=description,
                expires_at=expires_at_dt,
                space_role=space_role,
                org_role=org_role,
                account_role=account_role,
            )
    except Exception as e:
        raise APIError(f"Failed to create service API key: {e}") from e
    else:
        warning("Save this API key now — it will not be shown again.")
        output_data(
            key_created,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("delete")
@handle_errors
def delete_api_key(
    id: Annotated[
        str,
        typer.Argument(help="API key ID"),
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
    """Delete an API key.

    The key is deleted immediately and permanently.
    """
    setup_logging(verbose)
    client, _ = make_client()

    if not force:
        warning("This will permanently delete the API key")

        if not confirm("Are you sure?", default=False):
            info("API key not deleted")
            raise typer.Exit()

    try:
        with spinner(
            "Deleting API key",
            success_msg=f"API key with ID '{id}' deleted successfully",
        ):
            client.api_keys.delete(api_key_id=id)
    except Exception as e:
        raise APIError(f"Failed to delete API key: {e}") from e


@app.command("refresh")
@handle_errors
def refresh_api_key(
    id: Annotated[
        str,
        typer.Argument(help="API key ID to refresh"),
    ],
    expires_at: Annotated[
        str | None,
        typer.Option(
            "--expires-at",
            help=(
                "New expiration datetime in ISO 8601 format "
                "(e.g. '2025-12-31T23:59:59'). If omitted, replacement key "
                "never expires."
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
    """Refresh an API key.

    Atomically revokes the old key and issues a replacement with the same
    name, description, type, and scope.

    The new raw key value is printed once. Save it securely —
    it will not be shown again.
    """
    expires_at_dt = parse_optional_iso8601(expires_at)

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Refreshing API key", success_msg="API key refreshed successfully"
        ):
            key_created = client.api_keys.refresh(
                api_key_id=id,
                expires_at=expires_at_dt,
            )
    except Exception as e:
        raise APIError(f"Failed to refresh API key: {e}") from e
    else:
        warning("Save this API key now — it will not be shown again.")
        output_data(
            key_created,
            format_type=output_format,
            output_file=output_file,
        )
