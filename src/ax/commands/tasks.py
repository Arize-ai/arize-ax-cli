"""Task management commands."""

from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Any

import typer
from arize import ArizeClient
from arize._generated.api_client.models.tasks_create_request_evaluators_inner import (
    TasksCreateRequestEvaluatorsInner,
)
from arize.tasks.client import RunStatus, TaskType

from ax.config.manager import ConfigManager
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
from ax.utils.file_io import parse_output_option
from ax.utils.json_source import load_json
from ax.utils.projects import resolve_project_id

app = typer.Typer(
    name="tasks",
    help="Manage evaluation tasks",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)


def _build_evaluators(
    parsed: dict[str, Any] | list[dict[str, Any]],
) -> list[TasksCreateRequestEvaluatorsInner]:
    """Parse a JSON string into a list of TasksCreateRequestEvaluatorsInner."""
    if not isinstance(parsed, list) or not parsed:
        raise typer.BadParameter(
            "--evaluators must be a non-empty JSON array of evaluator objects"
        )
    try:
        evaluators = [
            TasksCreateRequestEvaluatorsInner.from_dict(e) for e in parsed
        ]
    except Exception as exc:
        raise typer.BadParameter(f"Failed to parse evaluators: {exc}") from exc

    none_indices = [i for i, e in enumerate(evaluators) if e is None]
    if none_indices:
        raise typer.BadParameter(
            f"Failed to parse evaluator(s) at index(es): {none_indices}"
        )
    return evaluators  # type: ignore[return-value]


def _parse_experiment_ids(value: str | None) -> list[str] | None:
    """Parse a comma-separated string of experiment IDs into a list."""
    if not value:
        return None
    return [e.strip() for e in value.split(",") if e.strip()]


# ---------------------------------------------------------------------------
# Task commands
# ---------------------------------------------------------------------------


@app.command("list")
@handle_errors
def list_tasks(
    space_id: Annotated[
        str | None,
        typer.Option("--space-id", help="Filter tasks by space ID"),
    ] = None,
    project_id: Annotated[
        str | None,
        typer.Option(
            "--project-id", help="Filter tasks by project name or ID (base64)"
        ),
    ] = None,
    dataset_id: Annotated[
        str | None,
        typer.Option(
            "--dataset-id", help="Filter tasks by dataset global ID (base64)"
        ),
    ] = None,
    task_type: Annotated[
        TaskType | None,
        typer.Option(
            "--task-type",
            help="Filter by task type: template_evaluation or code_evaluation",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Maximum number of tasks to return"),
    ] = 15,
    cursor: Annotated[
        str | None,
        typer.Option("--cursor", help="Pagination cursor for next page"),
    ] = None,
    profile: Annotated[
        str,
        typer.Option("--profile", "-p", help="Configuration profile to use"),
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
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """List evaluation tasks."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    if project_id is not None:
        project_id = resolve_project_id(client, project_id, space_id)

    try:
        with spinner("Fetching tasks"):
            response = client.tasks.list(
                space_id=space_id,
                project_id=project_id,
                dataset_id=dataset_id,
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
    task_id: Annotated[str, typer.Argument(help="Task global ID (base64)")],
    profile: Annotated[
        str,
        typer.Option("--profile", "-p", help="Configuration profile to use"),
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
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Get a task by ID."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching task"):
            task = client.tasks.get(task_id=task_id)
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
            help="Task type: template_evaluation or code_evaluation",
        ),
    ],
    evaluators: Annotated[
        str,
        typer.Option(
            "--evaluators",
            help=(
                "JSON array of evaluator configs. Find evaluator IDs with `ax evaluators list`. "
                'Example: \'[{"evaluator_id": "RXZhbaGWx9yOjEyMzQ1", '
                '"query_filter": "tag[environment] = \'production\'", '
                '"column_mappings": {"input": "user_query", "output": "model_response"}}]\'. '
                "Fields: evaluator_id (required, base64 ID from ax evaluators list), "
                "query_filter (optional per-evaluator filter string), "
                "column_mappings (optional dict remapping column names)."
            ),
        ),
    ],
    project_id: Annotated[
        str | None,
        typer.Option(
            "--project-id",
            help="Project name or ID (base64); mutually exclusive with --dataset-id",
        ),
    ] = None,
    space_id: Annotated[
        str | None,
        typer.Option(
            "--space-id",
            help="Space ID (required when using a project name instead of ID)",
        ),
    ] = None,
    dataset_id: Annotated[
        str | None,
        typer.Option(
            "--dataset-id",
            help="Dataset global ID (base64); mutually exclusive with --project-id",
        ),
    ] = None,
    experiment_ids: Annotated[
        str | None,
        typer.Option(
            "--experiment-ids",
            help="Comma-separated experiment global IDs (required for dataset-based tasks)",
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
    profile: Annotated[
        str,
        typer.Option("--profile", "-p", help="Configuration profile to use"),
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
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Create a new evaluation task."""
    setup_logging(verbose)

    if project_id is None and dataset_id is None:
        raise UsageError("One of --project-id or --dataset-id must be provided")
    if project_id is not None and dataset_id is not None:
        raise UsageError("--project-id and --dataset-id are mutually exclusive")
    if sampling_rate is not None and not (0.0 <= sampling_rate <= 1.0):
        raise UsageError("--sampling-rate must be between 0.0 and 1.0")

    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    if project_id is not None:
        project_id = resolve_project_id(client, project_id, space_id)

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    parsed_evaluators = _build_evaluators(load_json(evaluators))

    try:
        with spinner("Creating task", success_msg="Task created successfully"):
            task = client.tasks.create(
                name=name,
                task_type=task_type,
                evaluators=parsed_evaluators,
                project_id=project_id,
                dataset_id=dataset_id,
                experiment_ids=_parse_experiment_ids(experiment_ids),
                sampling_rate=sampling_rate,
                is_continuous=is_continuous,
                query_filter=query_filter,
            )
    except Exception as e:
        raise APIError(f"Failed to create task: {e}") from e
    else:
        output_data(task, format_type=output_format, output_file=output_file)


# ---------------------------------------------------------------------------
# Task run commands
# ---------------------------------------------------------------------------


@app.command("trigger-run")
@handle_errors
def trigger_run(
    task_id: Annotated[str, typer.Argument(help="Task global ID (base64)")],
    data_start_time: Annotated[
        datetime | None,
        typer.Option(
            "--data-start-time",
            help="ISO 8601 start of the data window to evaluate",
        ),
    ] = None,
    data_end_time: Annotated[
        datetime | None,
        typer.Option(
            "--data-end-time",
            help="ISO 8601 end of the data window (defaults to now)",
        ),
    ] = None,
    max_spans: Annotated[
        int | None,
        typer.Option(
            "--max-spans",
            help="Maximum number of spans to process (default 10 000)",
        ),
    ] = None,
    override_evaluations: Annotated[
        bool | None,
        typer.Option(
            "--override-evaluations/--no-override-evaluations",
            help="Re-evaluate data that already has evaluation labels",
        ),
    ] = None,
    experiment_ids: Annotated[
        str | None,
        typer.Option(
            "--experiment-ids",
            help="Comma-separated experiment global IDs; dataset-based tasks only",
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
    profile: Annotated[
        str,
        typer.Option("--profile", "-p", help="Configuration profile to use"),
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
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Trigger an on-demand run for a task."""
    setup_logging(verbose)
    if not wait and (poll_interval != 5.0 or timeout != 600.0):
        warning("--poll-interval and --timeout have no effect without --wait")
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Triggering task run", success_msg="Task run triggered"):
            run = client.tasks.trigger_run(
                task_id=task_id,
                data_start_time=data_start_time,
                data_end_time=data_end_time,
                max_spans=max_spans,
                override_evaluations=override_evaluations,
                experiment_ids=_parse_experiment_ids(experiment_ids),
            )
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
    task_id: Annotated[str, typer.Argument(help="Task global ID (base64)")],
    status: Annotated[
        RunStatus | None,
        typer.Option(
            "--status",
            help="Filter by run status: pending, running, completed, failed, cancelled",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Maximum number of runs to return"),
    ] = 15,
    cursor: Annotated[
        str | None,
        typer.Option("--cursor", help="Pagination cursor for next page"),
    ] = None,
    profile: Annotated[
        str,
        typer.Option("--profile", "-p", help="Configuration profile to use"),
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
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """List runs for a task."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching task runs"):
            response = client.tasks.list_runs(
                task_id=task_id,
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
    run_id: Annotated[str, typer.Argument(help="Task run global ID (base64)")],
    profile: Annotated[
        str,
        typer.Option("--profile", "-p", help="Configuration profile to use"),
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
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Get a task run by ID."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

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
    run_id: Annotated[str, typer.Argument(help="Task run global ID (base64)")],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt"),
    ] = False,
    profile: Annotated[
        str,
        typer.Option("--profile", "-p", help="Configuration profile to use"),
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

    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

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
    run_id: Annotated[str, typer.Argument(help="Task run global ID (base64)")],
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
    profile: Annotated[
        str,
        typer.Option("--profile", "-p", help="Configuration profile to use"),
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
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Wait for a task run to reach a terminal state (completed, failed, or cancelled)."""
    setup_logging(verbose)
    config = ConfigManager.load(profile, expand_env_vars=True)
    client = ArizeClient(**asdict(config.to_sdk_config()))

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
