"""Role binding management commands."""

from dataclasses import asdict
from typing import Annotated

import typer
from arize import ArizeClient
from arize.role_bindings.types import RoleBindingResourceType

from ax.config.manager import ConfigManager
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

# Create role-bindings subcommand app
app = typer.Typer(
    name="role-bindings",
    help="Manage role bindings",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


@app.command("create")
@handle_errors
def create_role_binding(
    user_id: Annotated[
        str,
        typer.Option(
            "--user-id",
            help="Global ID of the user to bind the role to",
            prompt=True,
        ),
    ],
    role_id: Annotated[
        str,
        typer.Option(
            "--role-id",
            help="Global ID of the role to assign",
            prompt=True,
        ),
    ],
    resource_type: Annotated[
        RoleBindingResourceType,
        typer.Option(
            "--resource-type",
            help="Resource type to bind the role on",
            prompt=True,
        ),
    ],
    resource_id: Annotated[
        str,
        typer.Option(
            "--resource-id",
            help="Global ID of the resource to bind the role on",
            prompt=True,
        ),
    ],
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help="Configuration profile to use",
        ),
    ] = "",
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
    """Create a new role binding.

    Assigns a role to a user on the specified resource. Only one binding per
    user per resource is allowed. If a binding already exists for the user on
    the resource, the command exits without error.
    """
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Creating role binding",
            success_msg="Role binding created successfully",
        ):
            response = client.role_bindings.create(
                user_id=user_id,
                role_id=role_id,
                resource_type=resource_type,
                resource_id=resource_id,
            )
    except Exception as e:
        raise APIError(f"Failed to create role binding: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("get")
@handle_errors
def get_role_binding(
    binding_id: Annotated[
        str,
        typer.Argument(help="Role binding ID"),
    ],
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help="Configuration profile to use",
        ),
    ] = "",
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
    """Get a role binding by ID."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching role binding"):
            response = client.role_bindings.get(binding_id=binding_id)
    except Exception as e:
        raise APIError(f"Failed to get role binding: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("update")
@handle_errors
def update_role_binding(
    binding_id: Annotated[
        str,
        typer.Argument(help="Role binding ID"),
    ],
    role_id: Annotated[
        str,
        typer.Option(
            "--role-id",
            help="New role ID to assign",
            prompt=True,
        ),
    ],
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help="Configuration profile to use",
        ),
    ] = "",
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
    """Update a role binding by replacing its assigned role."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Updating role binding",
            success_msg="Role binding updated successfully",
        ):
            response = client.role_bindings.update(
                binding_id=binding_id,
                role_id=role_id,
            )
    except Exception as e:
        raise APIError(f"Failed to update role binding: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("delete")
@handle_errors
def delete_role_binding(
    binding_id: Annotated[
        str,
        typer.Argument(help="Role binding ID"),
    ],
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Skip confirmation prompt",
        ),
    ] = False,
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help="Configuration profile to use",
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
    """Delete a role binding by ID."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    if not force:
        warning("This will permanently delete the role binding")

        if not confirm("Are you sure?", default=False):
            info("Role binding not deleted")
            raise typer.Exit()

    try:
        with spinner(
            "Deleting role binding",
            success_msg=f"Role binding '{binding_id}' deleted successfully",
        ):
            client.role_bindings.delete(binding_id=binding_id)
    except Exception as e:
        raise APIError(f"Failed to delete role binding: {e}") from e
