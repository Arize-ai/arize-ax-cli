"""API key management commands."""

from typing import Annotated

import typer
from arize import ArizeClient
from arize._generated.api_client.models.organization_role import (
    OrganizationRole,
)
from arize._generated.api_client.models.user_role import UserRole
from arize._generated.api_client.models.user_space_role import UserSpaceRole
from arize.api_keys.types import (
    ApiKeyStatus,
    ApiKeyType,
    OrganizationRoleAssignment,
    OrgBinding,
    ServiceApiKeyCreated,
    SpaceBinding,
    SpaceRoleAssignment,
    UserApiKeyCreated,
    UserRoleAssignment,
)

from ax.core.client_factory import make_client
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError, FileIOError
from ax.core.output import output_data
from ax.utils.console import (
    confirm,
    info,
    setup_logging,
    spinner,
    success,
    warning,
)
from ax.utils.datetime_parse import parse_optional_iso8601
from ax.utils.dotenv import validate_dotenv_path, write_api_key_to_dotenv
from ax.utils.file_io import parse_output_option
from ax.utils.json_source import load_json

# Create api-keys subcommand app
app = typer.Typer(
    name="api-keys",
    help="Manage API keys",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)

_SAVE_KEY_WARNING = "Save this API key now — it will not be shown again."


def _write_key_to_dotenv_or_revoke(
    client: ArizeClient,
    env_file: str,
    key_created: UserApiKeyCreated | ServiceApiKeyCreated,
) -> None:
    """Write a newly created key to a dotenv file, revoking it on failure.

    The key exists server-side before the file is written and its raw value
    is never printed, so a write failure would strand an unusable, orphaned
    credential. To avoid that, the key is revoked before the error is
    surfaced. Only the key id (not the secret) is ever included in messages.

    Args:
        client: Authenticated SDK client used to revoke on failure.
        env_file: Target dotenv file path.
        key_created: The created key response (provides ``key`` and ``id``).

    Raises:
        FileIOError: If the write fails. The message states whether the key
            was revoked automatically or must be revoked manually.
    """
    api_key = key_created.key
    try:
        write_api_key_to_dotenv(env_file, api_key)
    except (FileIOError, KeyboardInterrupt) as write_error:
        try:
            client.api_keys.revoke(api_key_id=key_created.id)
        except Exception as revoke_error:
            raise FileIOError(
                f"{write_error} The newly created key could not be revoked "
                f"automatically ({revoke_error}); revoke it manually with "
                f"'ax api-keys revoke {key_created.id}'."
            ) from revoke_error
        if isinstance(write_error, KeyboardInterrupt):
            raise
        raise FileIOError(
            f"{write_error} The newly created key was revoked; resolve the "
            f"file issue and re-run."
        ) from write_error


@app.command("list")
@handle_errors
def list_api_keys(
    key_type: Annotated[
        ApiKeyType | None,
        typer.Option(
            "--key-type",
            help="Filter by key type: 'USER' or 'SERVICE'",
        ),
    ] = None,
    status: Annotated[
        ApiKeyStatus | None,
        typer.Option(
            "--status",
            help="Filter by status: 'ACTIVE' or 'REVOKED'",
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
                "Expiration datetime in ISO 8601 format; UTC assumed if no "
                "offset (e.g. '2025-12-31T23:59:59'). If omitted, key never expires."
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
    env_file: Annotated[
        str | None,
        typer.Option(
            "--env-file",
            help="Write the new key to ARIZE_API_KEY in a dotenv or .envrc file",
        ),
    ] = None,
) -> None:
    """Create a new user API key.

    Authenticates as you with your full permissions. The raw key value is
    printed once after creation — save it securely, it will not be shown again.

    To create a space-scoped service key, use ``create-service-key`` instead.
    """
    expires_at_dt = parse_optional_iso8601(expires_at)
    if env_file is not None:
        validate_dotenv_path(env_file)

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Creating API key"):
            key_created = client.api_keys.create(
                name=name,
                description=description,
                expires_at=expires_at_dt,
            )
    except Exception as e:
        raise APIError(f"Failed to create API key: {e}") from e
    else:
        if env_file is not None:
            _write_key_to_dotenv_or_revoke(client, env_file, key_created)
            success(f"API key written to {env_file}")
        else:
            success("API key created successfully")

        if env_file is None or output_file:
            if not output_file:
                warning(_SAVE_KEY_WARNING)
            output_data(
                key_created,
                format_type=output_format,
                output_file=output_file,
            )


_SPACE_ROLES = ", ".join(r.value for r in UserSpaceRole)
_ORG_ROLES = ", ".join(r.value for r in OrganizationRole)


def _build_space_role(
    role_raw: str | dict | None,
) -> SpaceRoleAssignment | None:
    """Build a SpaceRoleAssignment from a predefined role name or custom role dict."""
    if role_raw is None:
        return None
    if isinstance(role_raw, str):
        try:
            UserSpaceRole(role_raw)
        except ValueError as e:
            raise typer.BadParameter(
                f"Invalid space role {role_raw!r}. Valid values: {_SPACE_ROLES}"
            ) from e
        return SpaceRoleAssignment.from_dict(
            {"type": "PREDEFINED", "name": role_raw}
        )
    if isinstance(role_raw, dict):
        role_type = role_raw.get("type", "").upper()
        if role_type == "CUSTOM":
            role_id = role_raw.get("id")
            if not isinstance(role_id, str) or not role_id:
                raise typer.BadParameter(
                    "Custom space role requires a non-empty 'id' field."
                )
            return SpaceRoleAssignment.from_dict(
                {"type": "CUSTOM", "id": role_id}
            )
        raise typer.BadParameter(
            f"Unrecognized space role type {role_type!r}. "
            f"Use a predefined role name ({_SPACE_ROLES}) or "
            '{"type": "CUSTOM", "id": "<role-id>"}.'
        )
    raise typer.BadParameter(
        "Space role must be a predefined role name string or a custom role object."
    )


def _build_org_role(
    role_raw: str | dict | None,
) -> OrganizationRoleAssignment | None:
    """Build an OrganizationRoleAssignment from a predefined role name or custom role dict."""
    if role_raw is None:
        return None
    if isinstance(role_raw, str):
        try:
            OrganizationRole(role_raw)
        except ValueError as e:
            raise typer.BadParameter(
                f"Invalid org role {role_raw!r}. Valid values: {_ORG_ROLES}"
            ) from e
        return OrganizationRoleAssignment.from_dict(
            {"type": "PREDEFINED", "name": role_raw}
        )
    if isinstance(role_raw, dict):
        role_type = role_raw.get("type", "").upper()
        if role_type == "CUSTOM":
            role_id = role_raw.get("id")
            if not isinstance(role_id, str) or not role_id:
                raise typer.BadParameter(
                    "Custom org role requires a non-empty 'id' field."
                )
            return OrganizationRoleAssignment.from_dict(
                {"type": "CUSTOM", "id": role_id}
            )
        raise typer.BadParameter(
            f"Unrecognized org role type {role_type!r}. "
            f"Use a predefined role name ({_ORG_ROLES}) or "
            '{"type": "CUSTOM", "id": "<role-id>"}.'
        )
    raise typer.BadParameter(
        "Org role must be a predefined role name string or a custom role object."
    )


def _build_account_role(name: str | None) -> UserRoleAssignment | None:
    """Wrap a predefined account-role name into a UserRoleAssignment."""
    if name is None:
        return None
    return UserRoleAssignment.from_dict({"type": "PREDEFINED", "name": name})


def _parse_assignments(assignments_raw: str) -> list[OrgBinding]:
    """Parse and validate the --assignments JSON into a list of OrgBinding.

    Accepts an inline JSON string or a filesystem path to a ``.json`` file.

    Args:
        assignments_raw: Raw value of the --assignments option.

    Returns:
        List of :class:`OrgBinding` objects ready to pass to the SDK.

    Raises:
        typer.BadParameter: If the input is not valid JSON, not a list, or any
            entry is structurally invalid.
    """
    parsed = load_json(assignments_raw)

    if not isinstance(parsed, list) or len(parsed) == 0:
        raise typer.BadParameter(
            "--assignments must be a non-empty JSON array of org binding objects."
        )

    org_bindings: list[OrgBinding] = []
    for i, entry in enumerate(parsed):
        if not isinstance(entry, dict):
            raise typer.BadParameter(
                f"--assignments entry {i}: expected an object, "
                f"got {type(entry).__name__}."
            )
        org_id = entry.get("org_id")
        if not isinstance(org_id, str) or not org_id:
            raise typer.BadParameter(
                f"--assignments entry {i}: 'org_id' must be a non-empty string."
            )
        spaces_raw = entry.get("spaces")
        if not spaces_raw or not isinstance(spaces_raw, list):
            raise typer.BadParameter(
                f"--assignments entry {i} (org_id={org_id!r}): "
                "'spaces' must be a non-empty array."
            )

        space_bindings: list[SpaceBinding] = []
        for j, sb in enumerate(spaces_raw):
            # SpaceBinding.space is required by the SDK
            if not isinstance(sb, dict) or "space" not in sb:
                raise typer.BadParameter(
                    f"--assignments entry {i}.spaces[{j}]: "
                    "each space binding must be an object with a 'space' field."
                )
            space_name = sb["space"]
            if not isinstance(space_name, str) or not space_name:
                raise typer.BadParameter(
                    f"--assignments entry {i}.spaces[{j}]: "
                    "'space' must be a non-empty string."
                )
            space_bindings.append(
                SpaceBinding(
                    space=space_name,
                    role=_build_space_role(sb.get("role")),
                )
            )

        org_bindings.append(
            OrgBinding(
                org_id=org_id,
                spaces=space_bindings,
                role=_build_org_role(entry.get("role")),
            )
        )

    return org_bindings


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
    assignments: Annotated[
        str,
        typer.Option(
            "--assignments",
            "-a",
            help=(
                "JSON array describing the org/space assignments for the service "
                "key's bot user, or a path to a .json file. "
                "Each entry: "
                '{"org_id": "<id>", "role": "<org-role>", '
                '"spaces": [{"space": "<name-or-id>", "role": "<space-role>"}]}. '
                "'role' is optional at both levels; omit to use server defaults "
                "(space=MEMBER, org=READ_ONLY). Custom roles use "
                '{"type": "CUSTOM", "id": "<role-id>"}. '
                "Obtain org IDs with: ax organizations list --output json"
            ),
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
                "Expiration datetime in ISO 8601 format; UTC assumed if no "
                "offset (e.g. '2025-12-31T23:59:59'). If omitted, key never expires."
            ),
        ),
    ] = None,
    account_role: Annotated[
        UserRole | None,
        typer.Option(
            "--account-role",
            help=(
                "Account-level role for the bot user: ADMIN, MEMBER, or "
                "ANNOTATOR. Defaults to MEMBER when omitted."
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
    env_file: Annotated[
        str | None,
        typer.Option(
            "--env-file",
            help="Write the new key to ARIZE_API_KEY in a dotenv or .envrc file",
        ),
    ] = None,
) -> None:
    r"""Create a new service API key with org and space assignments.

    Service keys are backed by a dedicated bot user scoped to one or more
    organizations, each containing one or more spaces. Pass ``--assignments``
    as an inline JSON array or a path to a JSON file.

    Example (single org, two spaces)::

        ax api-keys create-service-key \
            --name "CI bot" \
            --assignments '[{"org_id":"T3Jn...","role":"READ_ONLY",
                             "spaces":[{"space":"prod","role":"MEMBER"},
                                       {"space":"staging"}]}]'

    When no role is specified for a space or org the server applies its
    defaults (space=MEMBER, org=READ_ONLY, account=MEMBER).

    The raw key value is printed once after creation — save it securely,
    it will not be shown again.
    """
    expires_at_dt = parse_optional_iso8601(expires_at)
    org_bindings = _parse_assignments(assignments)
    if env_file is not None:
        validate_dotenv_path(env_file)

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Creating service API key"):
            key_created = client.api_keys.create_service_key(
                name=name,
                orgs=org_bindings,
                description=description,
                expires_at=expires_at_dt,
                account_role=_build_account_role(
                    account_role.value if account_role else None
                ),
            )
    except Exception as e:
        raise APIError(f"Failed to create service API key: {e}") from e
    else:
        if env_file is not None:
            _write_key_to_dotenv_or_revoke(client, env_file, key_created)
            success(f"Service API key written to {env_file}")
        else:
            success("Service API key created successfully")

        if env_file is None or output_file:
            if not output_file:
                warning(_SAVE_KEY_WARNING)
            output_data(
                key_created,
                format_type=output_format,
                output_file=output_file,
            )


@app.command("revoke")
@handle_errors
def revoke_api_key(
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
    """Revoke an API key.

    The key's status is set to revoked and it stops working immediately.
    This operation is irreversible. Revoking an already-revoked key is a
    no-op and still succeeds.
    """
    setup_logging(verbose)
    client, _ = make_client()

    if not force:
        warning("This will permanently revoke the API key")

        if not confirm("Are you sure?", default=False):
            info("API key not revoked")
            raise typer.Exit()

    try:
        with spinner(
            "Revoking API key",
            success_msg=f"API key with ID '{id}' revoked successfully",
        ):
            client.api_keys.revoke(api_key_id=id)
    except Exception as e:
        raise APIError(f"Failed to revoke API key: {e}") from e


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
                "New expiration datetime in ISO 8601 format; UTC assumed if no "
                "offset (e.g. '2025-12-31T23:59:59'). If omitted, replacement "
                "key never expires."
            ),
        ),
    ] = None,
    grace_period_seconds: Annotated[
        int | None,
        typer.Option(
            "--grace-period-seconds",
            help=(
                "Seconds the old key remains valid after refresh to allow "
                "clients to rotate. If omitted or 0, the old key is "
                "invalidated immediately."
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

    Use --grace-period-seconds to keep the old key temporarily valid while
    clients rotate to the replacement key.

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
                grace_period_seconds=grace_period_seconds,
            )
    except Exception as e:
        raise APIError(f"Failed to refresh API key: {e}") from e
    else:
        if not output_file:
            warning(_SAVE_KEY_WARNING)
        output_data(
            key_created,
            format_type=output_format,
            output_file=output_file,
        )
