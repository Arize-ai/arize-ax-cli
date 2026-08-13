"""Task management commands."""

from typing import Annotated, Any

import typer
from arize.tasks.types import (
    RunConfigurationRequest,
    RunStatus,
    TaskEvaluatorInput,
    TaskType,
)

from ax.core.client_factory import make_client
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError, UsageError
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
from ax.utils.json_source import load_json

app = typer.Typer(
    name="tasks",
    help="Manage evaluation tasks",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


def _build_evaluators(
    parsed: dict[str, Any] | list[dict[str, Any]],
) -> list[TaskEvaluatorInput]:
    """Parse a JSON string into a list of TaskEvaluatorInput."""
    if not isinstance(parsed, list) or not parsed:
        raise typer.BadParameter(
            "--evaluators must be a non-empty JSON array of evaluator objects"
        )
    try:
        evaluators = [TaskEvaluatorInput.from_dict(e) for e in parsed]
    except Exception as exc:
        raise typer.BadParameter(f"Failed to parse evaluators: {exc}") from exc

    none_indices = [i for i, e in enumerate(evaluators) if e is None]
    if none_indices:
        raise typer.BadParameter(
            f"Failed to parse evaluator(s) at index(es): {none_indices}"
        )
    return evaluators  # type: ignore[return-value]


def _build_run_configuration(
    parsed: dict[str, Any] | list[dict[str, Any]],
) -> RunConfigurationRequest:
    """Parse a dict into a RunConfigurationRequest discriminated-union model."""
    if not isinstance(parsed, dict):
        raise typer.BadParameter(
            "--run-configuration must be a JSON object, not an array"
        )
    try:
        result = RunConfigurationRequest.from_dict(parsed)
    except Exception as exc:
        raise typer.BadParameter(
            f"Failed to parse run configuration: {exc}"
        ) from exc
    if result is None:
        raise typer.BadParameter(
            "Failed to parse run configuration: result was None"
        )
    return result  # type: ignore[return-value]


def _parse_comma_separated_ids(value: str | None) -> list[str] | None:
    """Parse a comma-separated string of IDs into a list."""
    if not value:
        return None
    return [e.strip() for e in value.split(",") if e.strip()]


# ---------------------------------------------------------------------------
# Task commands
# ---------------------------------------------------------------------------


@app.command("list")
@handle_errors
def list_tasks(
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Case-insensitive substring filter on task name",
        ),
    ] = None,
    project: Annotated[
        str | None,
        typer.Option("--project", help="Filter tasks by project name or ID"),
    ] = None,
    dataset: Annotated[
        str | None,
        typer.Option("--dataset", help="Filter tasks by dataset name or ID"),
    ] = None,
    space: Annotated[
        str | None,
        typer.Option("--space", "-s", help="Space name or ID"),
    ] = None,
    task_type: Annotated[
        TaskType | None,
        typer.Option(
            "--task-type",
            help=(
                "Filter by task type: TEMPLATE_EVALUATION, CODE_EVALUATION, "
                "or RUN_EXPERIMENT"
            ),
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of tasks to return",
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
    """List evaluation tasks."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching tasks"):
            response = client.tasks.list(
                name=name,
                space=space,
                project=project,
                dataset=dataset,
                task_type=task_type,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list tasks: {e}") from e
    else:
        output_data(
            response, format_type=output_format, output_file=output_file
        )


@app.command("get")
@handle_errors
def get_task(
    task_id: Annotated[str, typer.Argument(help="Task name or ID")],
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
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Get a task by name or ID."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching task"):
            task = client.tasks.get(task=task_id)
    except Exception as e:
        raise APIError(f"Failed to get task: {e}") from e
    else:
        output_data(task, format_type=output_format, output_file=output_file)


@app.command("create")
@handle_errors
def create_task(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Task name (unique within the space)",
        ),
    ],
    task_type: Annotated[
        TaskType,
        typer.Option(
            "--task-type",
            help=(
                "Task type: TEMPLATE_EVALUATION, CODE_EVALUATION, or RUN_EXPERIMENT"
            ),
        ),
    ],
    evaluators: Annotated[
        str | None,
        typer.Option(
            "--evaluators",
            help=(
                "JSON array of evaluator configs (evaluation tasks only). "
                "Find evaluator IDs with `ax evaluators list`. "
                'Example: \'[{"evaluator_id": "RXZhbaGWx9yOjEyMzQ1", '
                '"query_filter": "tag[environment] = \'production\'", '
                '"column_mappings": {"input": "user_query", "output": "model_response"}}]\'. '
                "Fields: evaluator_id (required, base64 ID from ax evaluators list), "
                "query_filter (optional per-evaluator filter string), "
                "column_mappings (optional dict remapping column names). "
                "[required for evaluation tasks]"
            ),
        ),
    ] = None,
    run_configuration: Annotated[
        str | None,
        typer.Option(
            "--run-configuration",
            help=(
                "JSON object (or @file.json) specifying the run configuration "
                "for run_experiment tasks. "
                'Example: \'{"experiment_type": "LLM_GENERATION", '
                '"ai_integration_id": "...", "model_name": "gpt-4o", '
                '"messages": [{"role": "USER", "content": "{{input}}"}]}\'. '
                "Required when --task-type=RUN_EXPERIMENT."
            ),
        ),
    ] = None,
    project: Annotated[
        str | None,
        typer.Option(
            "--project",
            help="Project name or ID; mutually exclusive with --dataset (evaluation tasks only)",
        ),
    ] = None,
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required when using a project name)",
        ),
    ] = None,
    dataset: Annotated[
        str | None,
        typer.Option(
            "--dataset",
            help=(
                "Dataset name or ID; mutually exclusive with --project for "
                "evaluation tasks, required for run_experiment tasks"
            ),
        ),
    ] = None,
    experiment_ids: Annotated[
        str | None,
        typer.Option(
            "--experiment-ids",
            help="Comma-separated experiment identifiers (evaluation tasks only)",
        ),
    ] = None,
    sampling_rate: Annotated[
        float | None,
        typer.Option(
            "--sampling-rate",
            help="Fraction of data to evaluate (0-1); project evaluation tasks only",
        ),
    ] = None,
    is_continuous: Annotated[
        bool | None,
        typer.Option(
            "--is-continuous/--no-continuous",
            help="Run task continuously on incoming data (evaluation tasks only)",
        ),
    ] = None,
    query_filter: Annotated[
        str | None,
        typer.Option(
            "--query-filter",
            help="Task-level query filter applied to all evaluators (evaluation tasks only)",
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
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Create a new task, dispatching internally based on --task-type.

    Evaluation tasks (TEMPLATE_EVALUATION / CODE_EVALUATION) require --name,
    --task-type, --evaluators, and one of --project / --dataset.

    Run-experiment tasks (RUN_EXPERIMENT) require --name, --task-type,
    --dataset, and --run-configuration. The flags --evaluators, --project,
    --experiment-ids, --sampling-rate, --is-continuous, and --query-filter are
    not valid for this task type.
    """
    setup_logging(verbose)

    match task_type:
        case TaskType.RUN_EXPERIMENT:
            # run_experiment validation
            if dataset is None:
                raise UsageError(
                    "--dataset is required for run_experiment tasks"
                )
            if run_configuration is None:
                raise UsageError(
                    "--run-configuration is required for run_experiment tasks"
                )
            eval_only_flags: dict[str, Any] = {
                "--project": project,
                "--evaluators": evaluators,
                "--experiment-ids": experiment_ids,
                "--sampling-rate": sampling_rate,
                "--is-continuous": is_continuous,
                "--query-filter": query_filter,
            }
            rejected = [k for k, v in eval_only_flags.items() if v is not None]
            if rejected:
                raise UsageError(
                    f"{', '.join(rejected)} "
                    f"{'is' if len(rejected) == 1 else 'are'} not valid "
                    "for run_experiment tasks"
                )
        case _:
            # Evaluation task validation
            if project is None and dataset is None:
                raise UsageError(
                    "One of --project or --dataset must be provided"
                )
            if project is not None and dataset is not None:
                raise UsageError(
                    "--project and --dataset are mutually exclusive"
                )
            if evaluators is None:
                raise UsageError(
                    "--evaluators is required for evaluation tasks"
                )
            if run_configuration is not None:
                raise UsageError(
                    "--run-configuration is only valid for run_experiment tasks"
                )
            if sampling_rate is not None and not (0.0 <= sampling_rate <= 1.0):
                raise UsageError("--sampling-rate must be between 0.0 and 1.0")

    client, config = make_client()
    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Creating task", success_msg="Task created successfully"):
            match task_type:
                case TaskType.RUN_EXPERIMENT:
                    parsed_run_config = _build_run_configuration(
                        load_json(run_configuration)  # type: ignore[arg-type]
                    )
                    task = client.tasks.create_run_experiment_task(
                        name=name,
                        dataset=dataset,  # type: ignore[arg-type]
                        space=space,
                        run_configuration=parsed_run_config,
                    )
                case _:
                    parsed_evaluators = _build_evaluators(
                        load_json(evaluators)  # type: ignore[arg-type]
                    )
                    task = client.tasks.create_evaluation_task(
                        name=name,
                        task_type=task_type,
                        evaluators=parsed_evaluators,
                        project=project,
                        dataset=dataset,
                        space=space,
                        experiment_ids=_parse_comma_separated_ids(
                            experiment_ids
                        ),
                        sampling_rate=sampling_rate,
                        is_continuous=is_continuous,
                        query_filter=query_filter,
                    )
    except (typer.BadParameter, UsageError):
        raise
    except Exception as e:
        raise APIError(f"Failed to create task: {e}") from e
    else:
        output_data(task, format_type=output_format, output_file=output_file)


@app.command("create-evaluation")
@handle_errors
def create_evaluation_task_cmd(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Task name (unique within the space)",
        ),
    ],
    task_type: Annotated[
        TaskType,
        typer.Option(
            "--task-type",
            help="Task type: TEMPLATE_EVALUATION or CODE_EVALUATION",
        ),
    ],
    evaluators: Annotated[
        str,
        typer.Option(
            "--evaluators",
            help=(
                "JSON array of evaluator configs. Find evaluator IDs with "
                "`ax evaluators list`. "
                'Example: \'[{"evaluator_id": "RXZhbaGWx9yOjEyMzQ1", '
                '"column_mappings": {"input": "user_query", "output": "model_response"}}]\'. '
                "Fields: evaluator_id (required), query_filter (optional), "
                "column_mappings (optional)."
            ),
        ),
    ],
    project: Annotated[
        str | None,
        typer.Option(
            "--project",
            help="Project name or ID; mutually exclusive with --dataset",
        ),
    ] = None,
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required when using a project name)",
        ),
    ] = None,
    dataset: Annotated[
        str | None,
        typer.Option(
            "--dataset",
            help="Dataset name or ID; mutually exclusive with --project",
        ),
    ] = None,
    experiment_ids: Annotated[
        str | None,
        typer.Option(
            "--experiment-ids",
            help="Comma-separated experiment identifiers (required for dataset-based tasks)",
        ),
    ] = None,
    sampling_rate: Annotated[
        float | None,
        typer.Option(
            "--sampling-rate",
            help="Fraction of data to evaluate (0-1); project tasks only",
        ),
    ] = None,
    is_continuous: Annotated[
        bool | None,
        typer.Option(
            "--is-continuous/--no-continuous",
            help="Run task continuously on incoming data",
        ),
    ] = None,
    query_filter: Annotated[
        str | None,
        typer.Option(
            "--query-filter",
            help="Task-level query filter applied to all evaluators",
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
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Create a new evaluation task (TEMPLATE_EVALUATION or CODE_EVALUATION).

    Requires --name, --task-type, --evaluators, and one of --project / --dataset.
    """
    setup_logging(verbose)

    if task_type == TaskType.RUN_EXPERIMENT:
        raise UsageError(
            "--task-type RUN_EXPERIMENT is not valid for this command; "
            "use `ax tasks create-run-experiment` instead"
        )
    if project is None and dataset is None:
        raise UsageError("One of --project or --dataset must be provided")
    if project is not None and dataset is not None:
        raise UsageError("--project and --dataset are mutually exclusive")
    if sampling_rate is not None and not (0.0 <= sampling_rate <= 1.0):
        raise UsageError("--sampling-rate must be between 0.0 and 1.0")

    client, config = make_client()
    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    parsed_evaluators = _build_evaluators(load_json(evaluators))

    try:
        with spinner("Creating task", success_msg="Task created successfully"):
            task = client.tasks.create_evaluation_task(
                name=name,
                task_type=task_type,
                evaluators=parsed_evaluators,
                project=project,
                dataset=dataset,
                space=space,
                experiment_ids=_parse_comma_separated_ids(experiment_ids),
                sampling_rate=sampling_rate,
                is_continuous=is_continuous,
                query_filter=query_filter,
            )
    except (typer.BadParameter, UsageError):
        raise
    except Exception as e:
        raise APIError(f"Failed to create task: {e}") from e
    else:
        output_data(task, format_type=output_format, output_file=output_file)


@app.command("create-run-experiment")
@handle_errors
def create_run_experiment_task_cmd(
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Task name (unique within the space)",
        ),
    ],
    dataset: Annotated[
        str,
        typer.Option(
            "--dataset",
            help="Dataset name or ID to run experiments against",
        ),
    ],
    run_configuration: Annotated[
        str,
        typer.Option(
            "--run-configuration",
            help=(
                "JSON object (or @file.json) specifying the run configuration. "
                'Example: \'{"experiment_type": "LLM_GENERATION", '
                '"ai_integration_id": "...", "model_name": "gpt-4o", '
                '"messages": [{"role": "USER", "content": "{{input}}"}]}\'. '
            ),
        ),
    ],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID",
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
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Create a new run_experiment task.

    Requires --name, --dataset, and --run-configuration.
    """
    setup_logging(verbose)
    client, config = make_client()
    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    parsed_run_config = _build_run_configuration(load_json(run_configuration))

    try:
        with spinner("Creating task", success_msg="Task created successfully"):
            task = client.tasks.create_run_experiment_task(
                name=name,
                dataset=dataset,
                space=space,
                run_configuration=parsed_run_config,
            )
    except (typer.BadParameter, UsageError):
        raise
    except Exception as e:
        raise APIError(f"Failed to create task: {e}") from e
    else:
        output_data(task, format_type=output_format, output_file=output_file)


@app.command("update")
@handle_errors
def update_task(
    task: Annotated[str, typer.Argument(help="Task name or ID")],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required when resolving task by name)",
        ),
    ] = None,
    new_name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="New task display name"),
    ] = None,
    sampling_rate: Annotated[
        float | None,
        typer.Option(
            "--sampling-rate",
            help="Sampling rate between 0 and 1 (evaluation tasks only)",
        ),
    ] = None,
    is_continuous: Annotated[
        bool | None,
        typer.Option(
            "--is-continuous/--no-continuous",
            help="Whether the task runs continuously (evaluation tasks only)",
        ),
    ] = None,
    query_filter: Annotated[
        str | None,
        typer.Option(
            "--query-filter",
            help=(
                "Task-level query filter (evaluation tasks only). Pass an empty string with "
                '`--query-filter ""` to clear the existing filter.'
            ),
        ),
    ] = None,
    evaluators: Annotated[
        str | None,
        typer.Option(
            "--evaluators",
            help=(
                "JSON array replacing the full evaluator list (evaluation tasks only). "
                "Same shape as `ax tasks create --evaluators`. Find IDs with `ax evaluators list`."
            ),
        ),
    ] = None,
    run_configuration: Annotated[
        str | None,
        typer.Option(
            "--run-configuration",
            help=(
                "JSON object (or @file.json) replacing the run configuration "
                "(run_experiment tasks only). The entire stored config is atomically replaced."
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
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Update mutable fields on a task.

    The SDK auto-dispatches based on the task's type; providing a field that
    is invalid for the resolved task type will raise an error.
    """
    setup_logging(verbose)

    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    update_kwargs: dict[str, Any] = {"task": task}
    if space is not None:
        update_kwargs["space"] = space

    has_field = False
    if new_name is not None:
        update_kwargs["name"] = new_name
        has_field = True
    if sampling_rate is not None:
        if not (0.0 <= sampling_rate <= 1.0):
            raise UsageError("--sampling-rate must be between 0.0 and 1.0")
        update_kwargs["sampling_rate"] = sampling_rate
        has_field = True
    if is_continuous is not None:
        update_kwargs["is_continuous"] = is_continuous
        has_field = True
    if query_filter is not None:
        update_kwargs["query_filter"] = (
            None if query_filter == "" else query_filter
        )
        has_field = True
    if evaluators is not None:
        update_kwargs["evaluators"] = _build_evaluators(load_json(evaluators))
        has_field = True
    if run_configuration is not None:
        update_kwargs["run_configuration"] = _build_run_configuration(
            load_json(run_configuration)
        )
        has_field = True

    if not has_field:
        raise UsageError(
            "Provide at least one field to update (see --help for available options).",
        )

    try:
        with spinner("Updating task", success_msg="Task updated"):
            updated = client.tasks.update(**update_kwargs)
    except (typer.BadParameter, UsageError):
        raise
    except Exception as e:
        raise APIError(f"Failed to update task: {e}") from e
    else:
        output_data(updated, format_type=output_format, output_file=output_file)


@app.command("delete")
@handle_errors
def delete_task(
    task: Annotated[str, typer.Argument(help="Task name or ID")],
    space: Annotated[
        str | None,
        typer.Option(
            "--space",
            "-s",
            help="Space name or ID (required when resolving task by name)",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Delete an evaluation task (irreversible)."""
    setup_logging(verbose)

    if not force:
        warning("This will permanently delete the task and its configuration")
        if not confirm("Are you sure?", default=False):
            info("Task not deleted")
            raise typer.Exit()

    client, _ = make_client()

    try:
        with spinner("Deleting task", success_msg="Task deleted"):
            client.tasks.delete(task=task, space=space)
    except Exception as e:
        raise APIError(f"Failed to delete task: {e}") from e


# ---------------------------------------------------------------------------
# Task run commands
# ---------------------------------------------------------------------------


@app.command("trigger-run")
@handle_errors
def trigger_run(
    task_id: Annotated[str, typer.Argument(help="Task name or ID")],
    data_start_time: Annotated[
        str | None,
        typer.Option(
            "--data-start-time",
            help="ISO 8601 start of the data window; UTC assumed if no offset (evaluation tasks only)",
        ),
    ] = None,
    data_end_time: Annotated[
        str | None,
        typer.Option(
            "--data-end-time",
            help="ISO 8601 end of the data window; UTC assumed if no offset "
            "(evaluation tasks only, defaults to now)",
        ),
    ] = None,
    max_spans: Annotated[
        int | None,
        typer.Option(
            "--max-spans",
            help="Maximum number of spans to process (evaluation tasks only, default 10 000)",
        ),
    ] = None,
    override_evaluations: Annotated[
        bool | None,
        typer.Option(
            "--override-evaluations/--no-override-evaluations",
            help="Re-evaluate data that already has evaluation labels (evaluation tasks only)",
        ),
    ] = None,
    experiment_ids: Annotated[
        str | None,
        typer.Option(
            "--experiment-ids",
            help="Comma-separated experiment identifiers; dataset-based evaluation tasks only",
        ),
    ] = None,
    example_ids: Annotated[
        str | None,
        typer.Option(
            "--example-ids",
            help=(
                "Comma-separated dataset example global IDs to run against "
                "(run_experiment tasks only). Mutually exclusive with --max-examples."
            ),
        ),
    ] = None,
    evaluation_task_ids: Annotated[
        str | None,
        typer.Option(
            "--evaluation-task-ids",
            help=(
                "Comma-separated task global IDs of evaluation tasks to trigger "
                "after the experiment run completes (run_experiment tasks only)"
            ),
        ),
    ] = None,
    experiment_name: Annotated[
        str | None,
        typer.Option(
            "--experiment-name",
            help=(
                "Display name for the experiment to be created "
                "(run_experiment tasks only, required for that type)"
            ),
        ),
    ] = None,
    dataset_version_id: Annotated[
        str | None,
        typer.Option(
            "--dataset-version-id",
            help=(
                "Dataset version identifier (base64); defaults to the latest version "
                "(run_experiment tasks only)"
            ),
        ),
    ] = None,
    max_examples: Annotated[
        int | None,
        typer.Option(
            "--max-examples",
            help="Maximum number of examples to run (run_experiment tasks only)",
        ),
    ] = None,
    tracing_metadata: Annotated[
        str | None,
        typer.Option(
            "--tracing-metadata",
            help=(
                "JSON object (or @file.json) of key/value pairs attached to "
                "experiment traces (run_experiment tasks only)"
            ),
        ),
    ] = None,
    wait: Annotated[
        bool,
        typer.Option(
            "--wait", "-w", help="Wait for the run to reach a terminal state"
        ),
    ] = False,
    poll_interval: Annotated[
        float,
        typer.Option(
            "--poll-interval",
            help="Seconds between polling attempts (used with --wait)",
        ),
    ] = 5.0,
    timeout: Annotated[
        float,
        typer.Option(
            "--timeout", help="Maximum seconds to wait (used with --wait)"
        ),
    ] = 600.0,
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
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Trigger an on-demand run for a task.

    The SDK auto-dispatches based on the task's type. Providing a flag that
    is invalid for the resolved task type will raise an error.
    """
    setup_logging(verbose)
    if not wait and (poll_interval != 5.0 or timeout != 600.0):
        warning("--poll-interval and --timeout have no effect without --wait")
    if experiment_ids and (
        data_start_time is not None or data_end_time is not None
    ):
        warning(
            "--data-start-time and --data-end-time are ignored when --experiment-ids is provided; "
            "experiment tasks fetch data directly from the experiment, not a time-based scan"
        )
    if example_ids and max_examples is not None:
        raise UsageError(
            "--example-ids and --max-examples are mutually exclusive; provide at most one"
        )

    parsed_tracing_metadata: dict[str, Any] | None = None
    if tracing_metadata is not None:
        raw = load_json(tracing_metadata)
        if not isinstance(raw, dict):
            raise UsageError("--tracing-metadata must be a JSON object")
        parsed_tracing_metadata = raw

    data_start_dt = parse_optional_iso8601(data_start_time)
    data_end_dt = parse_optional_iso8601(data_end_time)

    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Triggering task run", success_msg="Task run triggered"):
            run = client.tasks.trigger_run(
                task=task_id,
                data_start_time=data_start_dt,
                data_end_time=data_end_dt,
                max_spans=max_spans,
                override_evaluations=override_evaluations,
                experiment_ids=_parse_comma_separated_ids(experiment_ids),
                example_ids=_parse_comma_separated_ids(example_ids),
                experiment_name=experiment_name,
                dataset_version_id=dataset_version_id,
                max_examples=max_examples,
                tracing_metadata=parsed_tracing_metadata,
                evaluation_task_ids=_parse_comma_separated_ids(
                    evaluation_task_ids
                ),
            )
    except (typer.BadParameter, UsageError):
        raise
    except Exception as e:
        raise APIError(f"Failed to trigger task run: {e}") from e

    if wait:
        try:
            with spinner("Waiting for task run to complete"):
                run = client.tasks.wait_for_run(
                    run_id=run.id,
                    poll_interval=poll_interval,
                    timeout=timeout,
                )
        except TimeoutError as e:
            msg = str(e)
            raise APIError(msg if msg else "Task run timed out") from e
        except Exception as e:
            raise APIError(f"Failed while waiting for task run: {e}") from e

    output_data(run, format_type=output_format, output_file=output_file)


@app.command("list-runs")
@handle_errors
def list_runs(
    task_id: Annotated[str, typer.Argument(help="Task name or ID")],
    status: Annotated[
        RunStatus | None,
        typer.Option(
            "--status",
            help="Filter by run status: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Maximum number of runs to return"),
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
    """List runs for a task."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching task runs"):
            response = client.tasks.list_runs(
                task=task_id,
                status=status,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list task runs: {e}") from e
    else:
        output_data(
            response, format_type=output_format, output_file=output_file
        )


@app.command("get-run")
@handle_errors
def get_run(
    run_id: Annotated[str, typer.Argument(help="Task run identifier (base64)")],
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
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Get a task run by ID."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching task run"):
            run = client.tasks.get_run(run_id=run_id)
    except Exception as e:
        raise APIError(f"Failed to get task run: {e}") from e
    else:
        output_data(run, format_type=output_format, output_file=output_file)


@app.command("cancel-run")
@handle_errors
def cancel_run(
    run_id: Annotated[str, typer.Argument(help="Task run identifier (base64)")],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt"),
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
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Cancel a task run (only valid when pending or running)."""
    setup_logging(verbose)

    if not force:
        warning("This will cancel the task run")
        if not confirm("Are you sure?", default=False):
            info("Task run not cancelled")
            raise typer.Exit()

    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Cancelling task run", success_msg="Task run cancelled"):
            run = client.tasks.cancel_run(run_id=run_id)
    except Exception as e:
        raise APIError(f"Failed to cancel task run: {e}") from e
    else:
        output_data(run, format_type=output_format, output_file=output_file)


@app.command("wait-for-run")
@handle_errors
def wait_for_run(
    run_id: Annotated[str, typer.Argument(help="Task run identifier (base64)")],
    poll_interval: Annotated[
        float,
        typer.Option(
            "--poll-interval",
            help="Seconds between polling attempts (default 5)",
        ),
    ] = 5.0,
    timeout: Annotated[
        float,
        typer.Option("--timeout", help="Maximum seconds to wait (default 600)"),
    ] = 600.0,
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
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Wait for a task run to reach a terminal state (COMPLETED, FAILED, or CANCELLED)."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Waiting for task run to complete"):
            run = client.tasks.wait_for_run(
                run_id=run_id,
                poll_interval=poll_interval,
                timeout=timeout,
            )
    except TimeoutError as e:
        msg = str(e)
        raise APIError(msg if msg else "Task run timed out") from e
    except Exception as e:
        raise APIError(f"Failed while waiting for task run: {e}") from e
    else:
        output_data(run, format_type=output_format, output_file=output_file)
