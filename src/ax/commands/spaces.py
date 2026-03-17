"""Space management commands."""

from dataclasses import asdict
from typing import Annotated

import typer
from arize import ArizeClient

from ax.config.manager import ConfigManager
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError
from ax.core.output import output_data
from ax.utils.console import (
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
            "-n",
            help="Maximum number of spaces to return",
        ),
    ] = 15,
    cursor: Annotated[
        str | None,
        typer.Option(
            "--cursor",
            help="Pagination cursor for next page",
        ),
    ] = None,
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
    """List spaces."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

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
    id: Annotated[
        str,
        typer.Argument(help="Space ID"),
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
    """Get a space by ID."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        space = client.spaces.get(space_id=id)
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
    """Create a new space."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

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
    id: Annotated[
        str,
        typer.Argument(help="Space ID"),
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
    """Update a space by ID."""
    if name is None and description is None:
        warning("At least one of --name or --description must be provided")
        raise typer.Exit(code=1)

    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Updating space", success_msg="Space updated successfully"
        ):
            space = client.spaces.update(
                space_id=id,
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
