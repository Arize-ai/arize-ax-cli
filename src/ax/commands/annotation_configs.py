"""Annotation config management commands."""

from typing import Annotated, cast

import typer
from arize.annotation_configs.types import (
    AnnotationConfigType,
    CategoricalAnnotationConfig,
    CategoricalAnnotationValue,
    ContinuousAnnotationConfig,
    FreeformAnnotationConfig,
    OptimizationDirection,
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
from ax.utils.file_io import parse_output_option

# Create annotation-configs subcommand app
app = typer.Typer(
    name="annotation-configs",
    help="Manage annotation configs",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


@app.command("list")
@handle_errors
def list_annotation_configs(
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Case-insensitive substring filter on annotation config name",
        ),
    ] = None,
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of annotation configs to return",
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
    """List annotation configs in a space."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching annotation configs"):
            response = client.annotation_configs.list(
                name=name,
                space=space,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list annotation configs: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("get")
@handle_errors
def get_annotation_config(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Annotation config name or ID"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using annotation config name instead of ID)",
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
    """Get an annotation config by name or ID."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching annotation config"):
            annotation_config = client.annotation_configs.get(
                annotation_config=name_or_id,
                space=space,
            )
    except Exception as e:
        raise APIError(f"Failed to get annotation config: {e}") from e
    else:
        output_data(
            annotation_config,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("create")
@handle_errors
def create_annotation_config(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Annotation config name",
            prompt=True,
        ),
    ],
    space: Annotated[
        str,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID",
            prompt=True,
        ),
    ],
    annotation_type: Annotated[
        AnnotationConfigType,
        typer.Option(
            "--type",
            "-t",
            help="Annotation config type (CONTINUOUS, CATEGORICAL, FREEFORM)",
            prompt=True,
        ),
    ],
    min_score: Annotated[
        float | None,
        typer.Option(
            "--min-score",
            help="Minimum score (required for continuous type)",
        ),
    ] = None,
    max_score: Annotated[
        float | None,
        typer.Option(
            "--max-score",
            help="Maximum score (required for continuous type)",
        ),
    ] = None,
    values: Annotated[
        list[str] | None,
        typer.Option(
            "--value",
            help="Label value for categorical type (repeat for multiple, e.g. --value good --value bad)",
        ),
    ] = None,
    optimization_direction: Annotated[
        OptimizationDirection | None,
        typer.Option(
            "--optimization-direction",
            help="Optimization direction (MAXIMIZE, MINIMIZE, or NONE)",
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
    """Create a new annotation config.

    Type-specific requirements:

    - CONTINUOUS: --min-score and --max-score are required
    - CATEGORICAL: --value is required (repeat for multiple labels)
    - FREEFORM: no additional options required
    """
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    categorical_values: list[CategoricalAnnotationValue] | None = None
    if values:
        categorical_values = [
            CategoricalAnnotationValue(label=v) for v in values
        ]

    if annotation_type == AnnotationConfigType.CONTINUOUS and (
        min_score is None or max_score is None
    ):
        raise typer.BadParameter(
            "--min-score and --max-score are required for continuous annotation configs."
        )
    if (
        annotation_type == AnnotationConfigType.CATEGORICAL
        and not categorical_values
    ):
        raise typer.BadParameter(
            "--value is required (at least one) for categorical annotation configs."
        )

    annotation_config: (
        ContinuousAnnotationConfig
        | CategoricalAnnotationConfig
        | FreeformAnnotationConfig
    )
    try:
        with spinner(
            "Creating annotation config",
            success_msg="Annotation config created successfully",
        ):
            if annotation_type == AnnotationConfigType.CONTINUOUS:
                annotation_config = client.annotation_configs.create_continuous(
                    name=name,
                    space=space,
                    minimum_score=cast("float", min_score),
                    maximum_score=cast("float", max_score),
                    optimization_direction=optimization_direction,
                )
            elif annotation_type == AnnotationConfigType.CATEGORICAL:
                annotation_config = (
                    client.annotation_configs.create_categorical(
                        name=name,
                        space=space,
                        values=cast(
                            "list[CategoricalAnnotationValue]",
                            categorical_values,
                        ),
                        optimization_direction=optimization_direction,
                    )
                )
            else:
                annotation_config = client.annotation_configs.create_freeform(
                    name=name,
                    space=space,
                )
    except Exception as e:
        raise APIError(f"Failed to create annotation config: {e}") from e
    else:
        output_data(
            annotation_config,
            format_type=output_format,
            output_file=output_file,
        )


# ---------------------------------------------------------------------------
# ax annotation-configs update <type>
# ---------------------------------------------------------------------------

update_app = typer.Typer(
    name="update",
    help="Update an annotation config (choose the subcommand for its type)",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)
app.add_typer(update_app)

# Shared option types for the update subcommands.
NameOrIdArg = Annotated[
    str, typer.Argument(help="Annotation config name or ID")
]
SpaceOpt = Annotated[
    str | None,
    typer.Option(
        "--space",
        "-s",
        help="Space name or ID (required if using a name instead of an ID)",
    ),
]
NewNameOpt = Annotated[
    str | None,
    typer.Option("--new-name", help="New name for the annotation config"),
]
OutputOpt = Annotated[
    str,
    typer.Option(
        "--output",
        "-o",
        help="Output format (table, json, csv, parquet) or file path",
    ),
]
VerboseOpt = Annotated[
    bool,
    typer.Option("--verbose", "-v", help="Enable verbose logs"),
]


def _emit_updated(
    updated_config: (
        ContinuousAnnotationConfig
        | CategoricalAnnotationConfig
        | FreeformAnnotationConfig
    ),
    output: str,
) -> None:
    """Render an updated annotation config using the configured output format."""
    _, config = make_client()
    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )
    output_data(
        updated_config,
        format_type=output_format,
        output_file=output_file,
    )


@update_app.command("continuous")
@handle_errors
def update_continuous_annotation_config(
    name_or_id: NameOrIdArg,
    space: SpaceOpt = None,
    new_name: NewNameOpt = None,
    min_score: Annotated[
        float | None,
        typer.Option("--min-score", help="New minimum score"),
    ] = None,
    max_score: Annotated[
        float | None,
        typer.Option("--max-score", help="New maximum score"),
    ] = None,
    optimization_direction: Annotated[
        OptimizationDirection | None,
        typer.Option(
            "--optimization-direction",
            help="New optimization direction (MAXIMIZE, MINIMIZE, or NONE)",
        ),
    ] = None,
    output: OutputOpt = "",
    verbose: VerboseOpt = False,
) -> None:
    """Update a CONTINUOUS annotation config.

    Only the fields you pass are changed; omitted fields are left unchanged.
    """
    setup_logging(verbose)
    client, _ = make_client()

    try:
        with spinner(
            "Updating annotation config",
            success_msg="Annotation config updated successfully",
        ):
            updated_config = client.annotation_configs.update_continuous(
                annotation_config=name_or_id,
                space=space,
                name=new_name,
                minimum_score=min_score,
                maximum_score=max_score,
                optimization_direction=optimization_direction,
            )
    except Exception as e:
        raise APIError(f"Failed to update annotation config: {e}") from e
    else:
        _emit_updated(updated_config, output)


@update_app.command("categorical")
@handle_errors
def update_categorical_annotation_config(
    name_or_id: NameOrIdArg,
    space: SpaceOpt = None,
    new_name: NewNameOpt = None,
    values: Annotated[
        list[str] | None,
        typer.Option(
            "--value",
            help="Replacement label value (repeat for multiple)",
        ),
    ] = None,
    optimization_direction: Annotated[
        OptimizationDirection | None,
        typer.Option(
            "--optimization-direction",
            help="New optimization direction (MAXIMIZE, MINIMIZE, or NONE)",
        ),
    ] = None,
    output: OutputOpt = "",
    verbose: VerboseOpt = False,
) -> None:
    """Update a CATEGORICAL annotation config.

    Only the fields you pass are changed; omitted fields are left unchanged.
    """
    setup_logging(verbose)
    client, _ = make_client()

    categorical_values: list[CategoricalAnnotationValue] | None = None
    if values:
        categorical_values = [
            CategoricalAnnotationValue(label=v) for v in values
        ]

    try:
        with spinner(
            "Updating annotation config",
            success_msg="Annotation config updated successfully",
        ):
            updated_config = client.annotation_configs.update_categorical(
                annotation_config=name_or_id,
                space=space,
                name=new_name,
                values=categorical_values,
                optimization_direction=optimization_direction,
            )
    except Exception as e:
        raise APIError(f"Failed to update annotation config: {e}") from e
    else:
        _emit_updated(updated_config, output)


@update_app.command("freeform")
@handle_errors
def update_freeform_annotation_config(
    name_or_id: NameOrIdArg,
    space: SpaceOpt = None,
    new_name: NewNameOpt = None,
    output: OutputOpt = "",
    verbose: VerboseOpt = False,
) -> None:
    """Update a FREEFORM annotation config.

    Only the fields you pass are changed; omitted fields are left unchanged.
    """
    setup_logging(verbose)
    client, _ = make_client()

    try:
        with spinner(
            "Updating annotation config",
            success_msg="Annotation config updated successfully",
        ):
            updated_config = client.annotation_configs.update_freeform(
                annotation_config=name_or_id,
                space=space,
                name=new_name,
            )
    except Exception as e:
        raise APIError(f"Failed to update annotation config: {e}") from e
    else:
        _emit_updated(updated_config, output)


@app.command("delete")
@handle_errors
def delete_annotation_config(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Annotation config name or ID"),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required if using annotation config name instead of ID)",
        ),
    ] = None,
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
    """Delete an annotation config by name or ID."""
    setup_logging(verbose)
    client, _ = make_client()

    if not force:
        warning("This will permanently delete the annotation config")

        if not confirm("Are you sure?", default=False):
            info("Annotation config not deleted")
            raise typer.Exit()

    try:
        with spinner(
            "Deleting annotation config",
            success_msg=f"Annotation config '{name_or_id}' deleted successfully",
        ):
            client.annotation_configs.delete(
                annotation_config=name_or_id,
                space=space,
            )
    except Exception as e:
        raise APIError(f"Failed to delete annotation config: {e}") from e
