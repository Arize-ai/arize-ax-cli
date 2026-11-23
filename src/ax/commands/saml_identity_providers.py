"""Account-scoped SAML administration commands."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 -- Typer resolves annotations at runtime
from typing import TYPE_CHECKING, Annotated, Any, TypeVar

import typer
from arize._generated.api_client.exceptions import ApiException
from arize.saml_identity_providers.types import (
    CreateMappingRequest,
    CreateRequest,
    UpdateMappingRequest,
    UpdateRequest,
)
from pydantic import BaseModel, RootModel, ValidationError

from ax.core.client_factory import make_client
from ax.core.decorators import handle_errors
from ax.core.error_formatter import format_validation_error
from ax.core.exceptions import APIError, APIResponseError, UsageError
from ax.core.output import output_data
from ax.utils.console import confirm, setup_logging, spinner
from ax.utils.file_io import parse_output_option
from ax.utils.json_source import load_json

if TYPE_CHECKING:
    from collections.abc import Callable

    from arize.saml_identity_providers.client import SamlIdentityProvidersClient

app = typer.Typer(
    name="saml-identity-providers",
    help="Manage SAML configurations with Enterprise account-admin access",
    no_args_is_help=True,
)
mappings = typer.Typer(
    name="role-mappings", help="Manage SAML role mappings", no_args_is_help=True
)
app.add_typer(mappings)


def _required_id(value: str) -> str:
    if not value:
        raise typer.BadParameter("ID must not be empty")
    return value


Output = Annotated[
    str,
    typer.Option(
        "--output", "-o", "--format", help="Output format or file path"
    ),
]
Verbose = Annotated[
    bool, typer.Option("--verbose", "-v", help="Enable verbose logs")
]
Limit = Annotated[int, typer.Option("--limit", "-l", min=1, max=100)]
Cursor = Annotated[str | None, typer.Option("--cursor", "-c")]
IdentityProviderID = Annotated[
    str, typer.Argument(help="Identity provider ID", callback=_required_id)
]
MappingID = Annotated[
    str,
    typer.Argument(help="Mapping ID from list or add", callback=_required_id),
]
Force = Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")]
_Result = TypeVar("_Result", bound=BaseModel | None)
_Request = TypeVar("_Request", bound=BaseModel)


class _RemovalResult(BaseModel):
    removed: bool = True


def _body(path: Path, model: type[_Request]) -> _Request:
    try:
        value = load_json(str(path.resolve()))
    except UnicodeError as exc:
        raise UsageError("Input must be a UTF-8 JSON object") from exc
    if not isinstance(value, dict):
        raise UsageError("Input must be a JSON object")
    unknown = set(value) - set(model.model_fields)
    if unknown:
        raise UsageError(
            f"Unsupported SAML request fields: {', '.join(sorted(unknown))}"
        )
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        raise UsageError(
            f"Invalid SAML request input: {format_validation_error(exc)}"
        ) from exc


def _execute(
    operation: Callable[[SamlIdentityProvidersClient], _Result],
    output: str,
    verbose: bool,
    *,
    spinner_message: str,
) -> _Result:
    setup_logging(verbose)
    client, config = make_client()
    try:
        with spinner(spinner_message):
            result = operation(client.saml_identity_providers)
    except ApiException as exc:
        raise APIError("SAML request failed") from exc
    except (ValidationError, ValueError, TypeError) as exc:
        raise APIResponseError(
            "SAML response could not be read. The operation may have succeeded; "
            "check the resource before retrying."
        ) from exc
    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )
    display: BaseModel = (
        result if isinstance(result, BaseModel) else _RemovalResult()
    )
    if output_format == "json":
        display = RootModel[dict[str, Any]](
            display.model_dump(mode="json", exclude_none=False)
        )
    output_data(
        display,
        format_type=output_format,
        output_file=output_file,
    )
    return result


@app.command("list")
@handle_errors
def list_identity_providers(
    limit: Limit = 100,
    cursor: Cursor = None,
    output: Output = "",
    verbose: Verbose = False,
) -> None:
    """List the authenticated account's SAML configurations."""
    _execute(
        lambda client: client.list(limit=limit, cursor=cursor),
        output,
        verbose,
        spinner_message="Fetching SAML configurations",
    )


@app.command("get")
@handle_errors
def get_identity_provider(
    idp_id: IdentityProviderID, output: Output = "", verbose: Verbose = False
) -> None:
    """Read a database or file-managed configuration."""
    _execute(
        lambda client: client.get(idp_id=idp_id),
        output,
        verbose,
        spinner_message="Fetching SAML configuration",
    )


@app.command("create")
@handle_errors
def create_identity_provider(
    input_file: Annotated[
        Path,
        typer.Option(
            "--input-file",
            help="JSON request file; omitted fields remain unchanged on update",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    output: Output = "",
    verbose: Verbose = False,
) -> None:
    """Create a configuration from a JSON request file."""
    body = _body(input_file, CreateRequest)
    _execute(
        lambda client: client.create(body=body),
        output,
        verbose,
        spinner_message="Creating SAML configuration",
    )


@app.command("update")
@handle_errors
def update_identity_provider(
    idp_id: IdentityProviderID,
    input_file: Annotated[
        Path,
        typer.Option(
            "--input-file",
            help="JSON request file; omitted fields remain unchanged on update",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    output: Output = "",
    verbose: Verbose = False,
) -> None:
    """Update supplied configuration fields from a JSON file."""
    body = _body(input_file, UpdateRequest)
    _execute(
        lambda client: client.update(idp_id=idp_id, body=body),
        output,
        verbose,
        spinner_message="Updating SAML configuration",
    )


@app.command("delete")
@handle_errors
def delete_identity_provider(
    idp_id: IdentityProviderID,
    force: Force = False,
    output: Output = "",
    verbose: Verbose = False,
) -> None:
    """Remove a database configuration after enforcement is disabled."""
    if not force and not confirm(
        f"Remove SAML configuration '{idp_id}'?", default=False
    ):
        raise typer.Exit()
    _execute(
        lambda client: client.delete(idp_id=idp_id),
        output,
        verbose,
        spinner_message="Deleting SAML configuration",
    )


@mappings.command("list")
@handle_errors
def list_role_mappings(
    idp_id: IdentityProviderID,
    limit: Limit = 100,
    cursor: Cursor = None,
    output: Output = "",
    verbose: Verbose = False,
) -> None:
    """List mappings in configuration order."""
    _execute(
        lambda client: client.list_role_mappings(
            idp_id=idp_id, limit=limit, cursor=cursor
        ),
        output,
        verbose,
        spinner_message="Fetching SAML role mappings",
    )


@mappings.command("add")
@handle_errors
def add_role_mapping(
    idp_id: IdentityProviderID,
    input_file: Annotated[
        Path,
        typer.Option(
            "--input-file",
            help="JSON request file; omitted fields remain unchanged on update",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    output: Output = "",
    verbose: Verbose = False,
) -> None:
    """Add a mapping from JSON and return its persistent ID."""
    body = _body(input_file, CreateMappingRequest)
    _execute(
        lambda client: client.add_role_mapping(idp_id=idp_id, body=body),
        output,
        verbose,
        spinner_message="Adding SAML role mapping",
    )


@mappings.command("update")
@handle_errors
def update_role_mapping(
    idp_id: IdentityProviderID,
    mapping_id: MappingID,
    input_file: Annotated[
        Path,
        typer.Option(
            "--input-file",
            help="JSON request file; omitted fields remain unchanged on update",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    output: Output = "",
    verbose: Verbose = False,
) -> None:
    """Update supplied mapping fields and retain its ID."""
    body = _body(input_file, UpdateMappingRequest)
    _execute(
        lambda client: client.update_role_mapping(
            idp_id=idp_id, mapping_id=mapping_id, body=body
        ),
        output,
        verbose,
        spinner_message="Updating SAML role mapping",
    )


@mappings.command("remove")
@handle_errors
def remove_role_mapping(
    idp_id: IdentityProviderID,
    mapping_id: MappingID,
    force: Force = False,
    output: Output = "",
    verbose: Verbose = False,
) -> None:
    """Remove a mapping while retaining required login and admin mappings."""
    if not force and not confirm(
        f"Remove SAML mapping '{mapping_id}'?", default=False
    ):
        raise typer.Exit()
    _execute(
        lambda client: client.remove_role_mapping(
            idp_id=idp_id, mapping_id=mapping_id
        ),
        output,
        verbose,
        spinner_message="Removing SAML role mapping",
    )
