"""Webhook management commands."""

from collections.abc import Iterable
from typing import Annotated, Any

import typer
from arize import make_to_df
from arize.webhooks.types import (
    ListWebhookDeliveryAttemptsResponse,
    ListWebhooksResponse,
    ListWebhookSubscriptionsResponse,
    WebhookAuthType,
    WebhookEventType,
    WebhookSourceType,
)

from ax.core.client_factory import make_client
from ax.core.decorators import handle_errors
from ax.core.exceptions import APIError, UsageError
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

app = typer.Typer(
    name="webhooks",
    help="Manage webhooks and their prompt and evaluator subscriptions",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)

# output_data renders a list response as item rows (table, csv, parquet) only
# when the model has a to_df method; the pinned SDK release does not define
# one for the webhook list models.
ListWebhooksResponse.to_df = make_to_df("webhooks")  # type: ignore[attr-defined]
ListWebhookDeliveryAttemptsResponse.to_df = make_to_df(  # type: ignore[attr-defined]
    "delivery_attempts"
)
ListWebhookSubscriptionsResponse.to_df = make_to_df(  # type: ignore[attr-defined]
    "subscriptions"
)

_SHOWN_ONCE_WARNING = (
    "Save this signing secret now — it will not be shown again."
)

_ORGANIZATION_HELP = (
    "Organization name or ID (required if using webhook name instead of ID)"
)
_HEADER_HELP = (
    "Custom header sent with each delivery as KEY=VALUE (repeat for multiple)"
)
_OUTPUT_HELP = "Output format (table, json, csv, parquet) or file path"
_REDACTED = "***"


def _parse_headers(raw_headers: list[str] | None) -> dict[str, str] | None:
    """Turn repeated ``--header KEY=VALUE`` values into a header map.

    Keys and values are stripped of surrounding whitespace. Header names are
    case-insensitive, so ``A=1`` and ``a=2`` count as the same key.

    Returns:
        The header map, or None when the option was not given.

    Raises:
        UsageError: If a value has no ``=``, an empty key, or a key already
            given.
    """
    if raw_headers is None:
        return None
    headers: dict[str, str] = {}
    seen: set[str] = set()
    for raw in raw_headers:
        key, sep, value = raw.partition("=")
        key = key.strip()
        if not sep or not key:
            raise UsageError(
                f"Invalid --header {raw!r}: expected KEY=VALUE with a "
                "non-empty key"
            )
        if key.lower() in seen:
            raise UsageError(
                f"Duplicate --header key {key!r}: header names are "
                "case-insensitive, give each one once"
            )
        seen.add(key.lower())
        headers[key] = value.strip()
    return headers


def _redact(message: str, secrets: Iterable[str | None]) -> str:
    """Replace every occurrence of each non-empty secret in *message*."""
    for secret in secrets:
        if secret:
            message = message.replace(secret, _REDACTED)
    return message


def _header_secrets(headers: dict[str, str] | None) -> list[str]:
    return list(headers.values()) if headers else []


@app.command("list")
@handle_errors
def list_webhooks(
    organization: Annotated[
        str | None,
        typer.Option(
            "--organization",
            help="Organization name or ID to narrow the list",
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Filter by webhook name (case-insensitive substring match)",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            min=1,
            max=100,
            help="Maximum number of webhooks to return (1-100)",
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
        typer.Option("--output", "-o", help=_OUTPUT_HELP),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """List webhooks you have access to, most recently created first."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching webhooks"):
            response = client.webhooks.list(
                organization=organization,
                name=name,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list webhooks: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("get")
@handle_errors
def get_webhook(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Webhook name or ID"),
    ],
    organization: Annotated[
        str | None,
        typer.Option("--organization", help=_ORGANIZATION_HELP),
    ] = None,
    output: Annotated[
        str,
        typer.Option("--output", "-o", help=_OUTPUT_HELP),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Get a webhook by name or ID.

    Credentials (auth token, header values, signing secret) are never
    returned.
    """
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching webhook"):
            webhook = client.webhooks.get(
                webhook=name_or_id,
                organization=organization,
            )
    except Exception as e:
        raise APIError(f"Failed to get webhook: {e}") from e
    else:
        output_data(
            webhook,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("create")
@handle_errors
def create_webhook(
    organization: Annotated[
        str,
        typer.Option(
            "--organization",
            help="Organization name or ID to create the webhook in",
        ),
    ],
    name: Annotated[
        str,
        typer.Option(
            "--name",
            "-n",
            help="Webhook name (unique within the organization, max 255 chars)",
        ),
    ],
    url: Annotated[
        str,
        typer.Option(
            "--url",
            help="HTTPS endpoint events are delivered to",
        ),
    ],
    description: Annotated[
        str | None,
        typer.Option("--description", help="Optional description"),
    ] = None,
    auth_type: Annotated[
        WebhookAuthType,
        typer.Option(
            "--auth-type",
            help=(
                "How deliveries are authenticated: BEARER or HMAC_SHA256. "
                "Cannot be changed after creation."
            ),
        ),
    ] = WebhookAuthType.BEARER,
    auth_token: Annotated[
        str | None,
        typer.Option(
            "--auth-token",
            help=(
                "Complete Authorization header value sent verbatim with each "
                "delivery, e.g. 'Bearer my-token'. BEARER only; never returned."
            ),
        ),
    ] = None,
    timeout_ms: Annotated[
        int | None,
        typer.Option(
            "--timeout-ms",
            min=1000,
            max=60000,
            help="Delivery timeout in milliseconds (1000-60000, default 30000)",
        ),
    ] = None,
    headers: Annotated[
        list[str] | None,
        typer.Option("--header", help=_HEADER_HELP),
    ] = None,
    output: Annotated[
        str,
        typer.Option("--output", "-o", help=_OUTPUT_HELP),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Create a webhook.

    For HMAC_SHA256 webhooks the signing secret is printed once after
    creation and never again; store it securely. BEARER webhooks have no
    secret to show.
    """
    if auth_token is not None and auth_type is not WebhookAuthType.BEARER:
        raise UsageError("--auth-token is only valid with --auth-type BEARER")
    parsed_headers = _parse_headers(headers)

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Creating webhook"):
            created = client.webhooks.create(
                organization=organization,
                name=name,
                url=url,
                description=description,
                auth_type=auth_type,
                auth_token=auth_token,
                timeout_ms=timeout_ms,
                headers=parsed_headers,
            )
    except Exception as e:
        message = _redact(
            str(e), [auth_token, *_header_secrets(parsed_headers)]
        )
        raise APIError(f"Failed to create webhook: {message}") from e
    else:
        success("Webhook created successfully")
        if created.signing_secret is not None and not output_file:
            warning(_SHOWN_ONCE_WARNING)
        output_data(
            created,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("update")
@handle_errors
def update_webhook(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Webhook name or ID"),
    ],
    organization: Annotated[
        str | None,
        typer.Option("--organization", help=_ORGANIZATION_HELP),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="New webhook name"),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            help='New description. Pass "" (empty string) to clear.',
        ),
    ] = None,
    url: Annotated[
        str | None,
        typer.Option("--url", help="New HTTPS endpoint"),
    ] = None,
    auth_token: Annotated[
        str | None,
        typer.Option(
            "--auth-token",
            help=(
                "Replacement Authorization header value. BEARER webhooks "
                "only; never returned."
            ),
        ),
    ] = None,
    timeout_ms: Annotated[
        int | None,
        typer.Option(
            "--timeout-ms",
            min=1000,
            max=60000,
            help="New delivery timeout in milliseconds (1000-60000)",
        ),
    ] = None,
    headers: Annotated[
        list[str] | None,
        typer.Option(
            "--header",
            help=(
                "Replacement custom header as KEY=VALUE (repeat for multiple). "
                "Replaces the whole header map."
            ),
        ),
    ] = None,
    clear_headers: Annotated[
        bool,
        typer.Option(
            "--clear-headers",
            help="Remove every custom header. Cannot be combined with --header.",
        ),
    ] = False,
    output: Annotated[
        str,
        typer.Option("--output", "-o", help=_OUTPUT_HELP),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Update a webhook by name or ID.

    Only the options you pass are sent; omitted fields are left unchanged.
    At least one option must be given. The auth type cannot be changed and
    an HMAC signing secret cannot be rotated; create a new webhook instead.
    """
    update_kwargs: dict[str, Any] = {}
    if name is not None:
        update_kwargs["name"] = name
    if description is not None:
        update_kwargs["description"] = description
    if url is not None:
        update_kwargs["url"] = url
    if auth_token is not None:
        update_kwargs["auth_token"] = auth_token
    if timeout_ms is not None:
        update_kwargs["timeout_ms"] = timeout_ms
    if clear_headers and headers is not None:
        raise UsageError("--clear-headers cannot be combined with --header.")
    if clear_headers:
        update_kwargs["headers"] = {}
    elif headers is not None:
        update_kwargs["headers"] = _parse_headers(headers)

    if not update_kwargs:
        raise UsageError(
            "At least one of --name, --description, --url, --auth-token, "
            "--timeout-ms, --header, or --clear-headers must be provided."
        )

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Updating webhook", success_msg="Webhook updated successfully"
        ):
            webhook = client.webhooks.update(
                webhook=name_or_id,
                organization=organization,
                **update_kwargs,
            )
    except Exception as e:
        message = _redact(
            str(e),
            [auth_token, *_header_secrets(update_kwargs.get("headers"))],
        )
        raise APIError(f"Failed to update webhook: {message}") from e
    else:
        output_data(
            webhook,
            format_type=output_format,
            output_file=output_file,
        )


@app.command("delete")
@handle_errors
def delete_webhook(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Webhook name or ID"),
    ],
    organization: Annotated[
        str | None,
        typer.Option("--organization", help=_ORGANIZATION_HELP),
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
    """Delete a webhook by name or ID.

    The webhook is detached from every prompt, evaluator, and monitor it was
    subscribed to. This operation is irreversible.
    """
    setup_logging(verbose)
    client, _ = make_client()

    if not force:
        warning("This will permanently delete the webhook")

        if not confirm("Are you sure?", default=False):
            info("Webhook not deleted")
            raise typer.Exit()

    try:
        with spinner(
            "Deleting webhook",
            success_msg=f"Webhook '{name_or_id}' deleted successfully",
        ):
            client.webhooks.delete(
                webhook=name_or_id,
                organization=organization,
            )
    except Exception as e:
        raise APIError(f"Failed to delete webhook: {e}") from e


@app.command("test")
@handle_errors
def test_webhook(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Webhook name or ID"),
    ],
    organization: Annotated[
        str | None,
        typer.Option("--organization", help=_ORGANIZATION_HELP),
    ] = None,
    output: Annotated[
        str,
        typer.Option("--output", "-o", help=_OUTPUT_HELP),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Send a test event to a webhook's endpoint and report the outcome.

    Prints the endpoint's status_code and error_message, then exits 1 when
    the status is not 2xx. status_code is 502 when no response was received.
    Not supported for HMAC_SHA256 webhooks.
    """
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Sending test event"):
            result = client.webhooks.test(
                webhook=name_or_id,
                organization=organization,
            )
    except Exception as e:
        raise APIError(f"Failed to test webhook: {e}") from e
    else:
        output_data(
            result,
            format_type=output_format,
            output_file=output_file,
        )
        if not 200 <= result.status_code < 300:
            error(f"Endpoint answered with HTTP {result.status_code}")
            raise typer.Exit(code=1)


@app.command("deliveries")
@handle_errors
def list_deliveries(
    name_or_id: Annotated[
        str,
        typer.Argument(help="Webhook name or ID"),
    ],
    organization: Annotated[
        str | None,
        typer.Option("--organization", help=_ORGANIZATION_HELP),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            min=1,
            max=500,
            help="Maximum number of delivery attempts to return (1-500)",
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
        typer.Option("--output", "-o", help=_OUTPUT_HELP),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """List a webhook's delivery attempts, most recent first.

    Failed deliveries are retried, so one event may have several attempts.
    """
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching delivery attempts"):
            response = client.webhooks.list_delivery_attempts(
                webhook=name_or_id,
                organization=organization,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list webhook deliveries: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


# ---------------------------------------------------------------------------
# ax webhooks subscriptions <command>
# ---------------------------------------------------------------------------

subscriptions_app = typer.Typer(
    name="subscriptions",
    help="Manage which prompt and evaluator events a webhook receives",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)
app.add_typer(subscriptions_app)


@subscriptions_app.command("list")
@handle_errors
def list_subscriptions(
    source_type: Annotated[
        WebhookSourceType | None,
        typer.Option(
            "--source-type",
            help=(
                "Kind of source to list subscriptions for: PROMPT or "
                "EVALUATOR. Requires --source-id."
            ),
        ),
    ] = None,
    source_id: Annotated[
        str | None,
        typer.Option(
            "--source-id",
            help="ID of the prompt or evaluator. Requires --source-type.",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            min=1,
            max=100,
            help="Maximum number of subscriptions to return (1-100)",
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
        typer.Option("--output", "-o", help=_OUTPUT_HELP),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """List webhook subscriptions, optionally narrowed to one prompt or evaluator.

    Each subscription delivers one event to one webhook, so a webhook that
    receives several events appears once per event. Subscriptions whose
    webhook was deleted are dropped after the page is read, so a page may
    hold fewer than --limit items while has_more is true; keep paging until
    has_more is false.
    """
    if (source_type is None) != (source_id is None):
        raise UsageError("--source-type and --source-id must be given together")

    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching webhook subscriptions"):
            response = client.webhooks.list_subscriptions(
                source_type=source_type,
                source_id=source_id,
                limit=limit,
                cursor=cursor,
            )
    except Exception as e:
        raise APIError(f"Failed to list webhook subscriptions: {e}") from e
    else:
        output_data(
            response,
            format_type=output_format,
            output_file=output_file,
        )


@subscriptions_app.command("create")
@handle_errors
def create_subscription(
    webhook: Annotated[
        str,
        typer.Option("--webhook", help="Webhook name or ID"),
    ],
    source_type: Annotated[
        WebhookSourceType,
        typer.Option(
            "--source-type",
            help="Kind of source to subscribe to: PROMPT or EVALUATOR",
        ),
    ],
    source_id: Annotated[
        str,
        typer.Option("--source-id", help="ID of the prompt or evaluator"),
    ],
    event: Annotated[
        WebhookEventType,
        typer.Option(
            "--event",
            help=(
                "Event to deliver: PROMPT_VERSION_CREATED, "
                "PROMPT_VERSION_LABELED, PROMPT_VERSION_UNLABELED, or "
                "EVALUATOR_VERSION_CREATED"
            ),
        ),
    ],
    organization: Annotated[
        str | None,
        typer.Option("--organization", help=_ORGANIZATION_HELP),
    ] = None,
    output: Annotated[
        str,
        typer.Option("--output", "-o", help=_OUTPUT_HELP),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Subscribe a webhook to one event on a prompt or evaluator.

    Run once per event to deliver several events to the same webhook. Prompt
    events go with PROMPT sources and evaluator events with EVALUATOR sources.
    """
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner(
            "Creating webhook subscription",
            success_msg="Webhook subscription created successfully",
        ):
            subscription = client.webhooks.create_subscription(
                webhook=webhook,
                source_type=source_type,
                source_id=source_id,
                event=event,
                organization=organization,
            )
    except Exception as e:
        raise APIError(f"Failed to create webhook subscription: {e}") from e
    else:
        output_data(
            subscription,
            format_type=output_format,
            output_file=output_file,
        )


@subscriptions_app.command("get")
@handle_errors
def get_subscription(
    subscription_id: Annotated[
        str,
        typer.Argument(help="Subscription ID"),
    ],
    output: Annotated[
        str,
        typer.Option("--output", "-o", help=_OUTPUT_HELP),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Get a webhook subscription by ID."""
    setup_logging(verbose)
    client, config = make_client()

    output_format, output_file = parse_output_option(
        output if output else config.output.format
    )

    try:
        with spinner("Fetching webhook subscription"):
            subscription = client.webhooks.get_subscription(
                subscription_id=subscription_id
            )
    except Exception as e:
        raise APIError(f"Failed to get webhook subscription: {e}") from e
    else:
        output_data(
            subscription,
            format_type=output_format,
            output_file=output_file,
        )


@subscriptions_app.command("delete")
@handle_errors
def delete_subscription(
    subscription_id: Annotated[
        str,
        typer.Argument(help="Subscription ID"),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logs"),
    ] = False,
) -> None:
    """Delete a webhook subscription by ID.

    The webhook stops receiving that event from the source. Other
    subscriptions and the webhook itself are unaffected.
    """
    setup_logging(verbose)
    client, _ = make_client()

    if not force:
        warning("This will permanently delete the webhook subscription")

        if not confirm("Are you sure?", default=False):
            info("Webhook subscription not deleted")
            raise typer.Exit()

    try:
        with spinner(
            "Deleting webhook subscription",
            success_msg=(
                f"Webhook subscription '{subscription_id}' deleted successfully"
            ),
        ):
            client.webhooks.delete_subscription(subscription_id=subscription_id)
    except Exception as e:
        raise APIError(f"Failed to delete webhook subscription: {e}") from e
