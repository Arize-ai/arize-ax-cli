"""Resource restriction management commands."""

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

# Create resource-restrictions subcommand app
app = typer.Typer(
    name="resource-restrictions",
    help="Manage resource restrictions",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


@app.command("restrict")
@handle_errors
def restrict_resource(
    resource_id: Annotated[
        str,
        typer.Option(
            "--resource-id",
            help="Global ID of the resource to restrict",
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
    """Restrict a resource.

    Restricting a resource prevents roles bound at higher hierarchy levels
    (space, org, account) from granting access to it. Currently only PROJECT
    resources are supported. This operation is idempotent.
    """
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Restricting resource",
            success_msg="Resource restricted successfully",
        ):
            response = client.resource_restrictions.restrict(
                resource_id=resource_id,
            )
    except Exception as e:
        raise APIError(f"Failed to restrict resource: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("unrestrict")
@handle_errors
def unrestrict_resource(
    resource_id: Annotated[
        str,
        typer.Option(
            "--resource-id",
            help="Global ID of the resource to unrestrict",
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
    """Remove restriction from a resource.

    Removing a restriction means that roles bound at other levels of the
    hierarchy (space, org, account) can once again grant access to the resource.
    """
    setup_logging(verbose)
    client, _ = make_client()

    if not force:
        warning("This will remove the restriction from the resource")

        if not confirm("Are you sure?", default=False):
            info("Resource not unrestricted")
            raise typer.Exit()

    try:
        with spinner(
            "Unrestricting resource",
            success_msg="Resource unrestricted successfully",
        ):
            client.resource_restrictions.unrestrict(resource_id=resource_id)
    except Exception as e:
        raise APIError(f"Failed to unrestrict resource: {e}") from e
