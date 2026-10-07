"""Tests for webhooks CLI commands."""

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from arize.webhooks.types import (
    CreateWebhookResponse,
    ListWebhookDeliveryAttemptsResponse,
    ListWebhooksResponse,
    ListWebhookSubscriptionsResponse,
    PaginationMetadata,
    Webhook,
    WebhookAuthType,
    WebhookDeliveryAttempt,
    WebhookEventType,
    WebhookSourceType,
    WebhookSubscription,
)
from arize.webhooks.types import TestWebhookResponse as WebhookTestResponse
from typer.testing import CliRunner

from ax.cli import app
from ax.commands.webhooks import app as webhooks_app

# ---------------------------------------------------------------------------
# Helpers to build realistic SDK response objects
# ---------------------------------------------------------------------------

_CREATED_AT = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_AUTH_TOKEN = "Bearer s3cr3t-token-value"
_HEADER_VALUE = "hdr-s3cr3t-value"
_SIGNING_SECRET = "whsec_0123456789abcdef"


def _make_webhook(
    id: str = "wh_1",
    name: str = "My Hook",
    auth_type: WebhookAuthType = WebhookAuthType.BEARER,
) -> Webhook:
    return Webhook(
        id=id,
        organization_id="org_1",
        name=name,
        description="",
        url="https://example.com/hook",
        auth_type=auth_type,
        timeout_ms=30000,
        created_at=_CREATED_AT,
        updated_at=_CREATED_AT,
    )


def _make_created(
    auth_type: WebhookAuthType,
    signing_secret: str | None = None,
) -> CreateWebhookResponse:
    return CreateWebhookResponse(
        id="wh_new",
        organization_id="org_1",
        name="New Hook",
        description="",
        url="https://example.com/hook",
        auth_type=auth_type,
        signing_secret=signing_secret,
        signing_secret_hint=(
            f"****{signing_secret[-4:]}" if signing_secret else None
        ),
        timeout_ms=30000,
        created_at=_CREATED_AT,
        updated_at=_CREATED_AT,
    )


def _make_webhook_list(
    *webhooks: Webhook,
    has_more: bool = False,
    next_cursor: str | None = None,
) -> ListWebhooksResponse:
    return ListWebhooksResponse(
        webhooks=list(webhooks),
        pagination=PaginationMetadata(
            has_more=has_more, next_cursor=next_cursor
        ),
    )


def _read_csv(stdout: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(stdout)))


def _make_attempt(event_id: str = "evt_1") -> WebhookDeliveryAttempt:
    return WebhookDeliveryAttempt(
        event_id=event_id,
        attempt_number=1,
        payload={"event": "PROMPT_VERSION_CREATED"},
        status_code=200,
        error_message=None,
        created_at=_CREATED_AT,
    )


def _make_attempt_list(
    *attempts: WebhookDeliveryAttempt,
) -> ListWebhookDeliveryAttemptsResponse:
    return ListWebhookDeliveryAttemptsResponse(
        delivery_attempts=list(attempts),
        pagination=PaginationMetadata(has_more=False),
    )


def _make_subscription(id: str = "sub_1") -> WebhookSubscription:
    return WebhookSubscription(
        id=id,
        webhook_id="wh_1",
        source_type=WebhookSourceType.EVALUATOR,
        source_id="ev_1",
        event=WebhookEventType.EVALUATOR_VERSION_CREATED,
        created_at=_CREATED_AT,
    )


def _make_subscription_list(
    *subscriptions: WebhookSubscription,
) -> ListWebhookSubscriptionsResponse:
    return ListWebhookSubscriptionsResponse(
        subscriptions=list(subscriptions),
        pagination=PaginationMetadata(has_more=False),
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestWebhookCommandsRegistered:
    def test_expected_commands_registered(self) -> None:
        names = {cmd.name for cmd in webhooks_app.registered_commands}
        assert names == {
            "list",
            "get",
            "create",
            "update",
            "delete",
            "test",
            "deliveries",
        }
        group_names = {
            g.typer_instance.info.name for g in webhooks_app.registered_groups
        }
        assert group_names == {"subscriptions"}

    def test_subscription_commands_registered(self) -> None:
        (group,) = webhooks_app.registered_groups
        names = {cmd.name for cmd in group.typer_instance.registered_commands}
        assert names == {"list", "create", "get", "delete"}

    def test_webhooks_in_root_help(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "webhooks" in result.output

    def test_subscriptions_help(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(app, ["webhooks", "subscriptions", "--help"])
        assert result.exit_code == 0
        for name in ("list", "create", "get", "delete"):
            assert name in result.output


# ---------------------------------------------------------------------------
# ax webhooks list
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("patch_config_and_client")
class TestListWebhooks:
    def test_defaults_forwarded(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.list.return_value = _make_webhook_list()

        result = cli_runner.invoke(app, ["webhooks", "list"])

        assert result.exit_code == 0, result.output
        mock_client.webhooks.list.assert_called_once_with(
            organization=None, name=None, limit=15, cursor=None
        )

    def test_filters_forwarded(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.list.return_value = _make_webhook_list()

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "list",
                "--organization",
                "Acme",
                "--name",
                "prod",
                "--limit",
                "5",
                "--cursor",
                "tok",
            ],
        )

        assert result.exit_code == 0, result.output
        mock_client.webhooks.list.assert_called_once_with(
            organization="Acme", name="prod", limit=5, cursor="tok"
        )

    def test_table_output_lists_names(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.list.return_value = _make_webhook_list(
            _make_webhook(id="wh_a", name="Alpha"),
            _make_webhook(id="wh_b", name="Beta"),
        )

        result = cli_runner.invoke(app, ["webhooks", "list"])

        assert result.exit_code == 0, result.output
        assert "Alpha" in result.output
        assert "Beta" in result.output

    def test_json_output(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.list.return_value = _make_webhook_list(
            _make_webhook(name="Alpha")
        )

        result = cli_runner.invoke(
            app, ["webhooks", "list", "--output", "json"]
        )

        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert data["webhooks"][0]["name"] == "Alpha"
        assert data["pagination"]["has_more"] is False

    def test_csv_output_has_one_row_per_webhook(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.list.return_value = _make_webhook_list(
            _make_webhook(id="wh_a", name="Alpha"),
            _make_webhook(id="wh_b", name="Beta"),
        )

        result = cli_runner.invoke(app, ["webhooks", "list", "-o", "csv"])

        assert result.exit_code == 0, result.output
        rows = _read_csv(result.stdout)
        assert [row["name"] for row in rows] == ["Alpha", "Beta"]
        assert "num_webhooks" not in result.stdout

    def test_table_shows_cursor_hint_when_more_pages(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.list.return_value = _make_webhook_list(
            _make_webhook(), has_more=True, next_cursor="NEXT"
        )

        result = cli_runner.invoke(app, ["webhooks", "list"])

        assert result.exit_code == 0, result.output
        assert "--cursor" in result.output
        assert "NEXT" in result.output
        assert "Details" not in result.output

    @pytest.mark.parametrize("limit", ["0", "101"])
    def test_limit_out_of_range_exits_2(
        self, cli_runner: CliRunner, mock_client: MagicMock, limit: str
    ) -> None:
        result = cli_runner.invoke(app, ["webhooks", "list", "--limit", limit])

        assert result.exit_code == 2, result.output
        mock_client.webhooks.list.assert_not_called()

    def test_sdk_error_exits_4(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.list.side_effect = RuntimeError("boom")

        result = cli_runner.invoke(app, ["webhooks", "list"])

        assert result.exit_code == 4
        assert "Failed to list webhooks" in result.output


# ---------------------------------------------------------------------------
# ax webhooks get
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("patch_config_and_client")
class TestGetWebhook:
    def test_get_by_id(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.get.return_value = _make_webhook(
            id="wh_xyz", name="Special"
        )

        result = cli_runner.invoke(app, ["webhooks", "get", "wh_xyz"])

        assert result.exit_code == 0, result.output
        mock_client.webhooks.get.assert_called_once_with(
            webhook="wh_xyz", organization=None
        )
        assert "Special" in result.output

    def test_get_by_name_with_organization(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.get.return_value = _make_webhook(name="Special")

        result = cli_runner.invoke(
            app, ["webhooks", "get", "Special", "--organization", "org_1"]
        )

        assert result.exit_code == 0, result.output
        mock_client.webhooks.get.assert_called_once_with(
            webhook="Special", organization="org_1"
        )

    def test_get_json_output(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.get.return_value = _make_webhook(id="wh_xyz")

        result = cli_runner.invoke(
            app, ["webhooks", "get", "wh_xyz", "--output", "json"]
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["id"] == "wh_xyz"

    def test_get_missing_argument_exits_2(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        result = cli_runner.invoke(app, ["webhooks", "get"])

        assert result.exit_code == 2
        mock_client.webhooks.get.assert_not_called()

    def test_get_sdk_error_exits_4(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.get.side_effect = RuntimeError("boom")

        result = cli_runner.invoke(app, ["webhooks", "get", "wh_1"])

        assert result.exit_code == 4

    def test_get_by_name_without_organization_exits_4(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.get.side_effect = ValueError(
            "'organization' is required when 'webhook' is a name"
        )

        result = cli_runner.invoke(app, ["webhooks", "get", "My Hook"])

        assert result.exit_code == 4
        assert "Failed to get webhook" in result.output
        assert "organization" in result.output


# ---------------------------------------------------------------------------
# ax webhooks create
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("patch_config_and_client")
class TestCreateWebhook:
    def test_minimal_create_defaults_forwarded(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.create.return_value = _make_created(
            WebhookAuthType.BEARER
        )

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "create",
                "--organization",
                "org_1",
                "--name",
                "New Hook",
                "--url",
                "https://example.com/hook",
            ],
        )

        assert result.exit_code == 0, result.output
        mock_client.webhooks.create.assert_called_once_with(
            organization="org_1",
            name="New Hook",
            url="https://example.com/hook",
            description=None,
            auth_type=WebhookAuthType.BEARER,
            auth_token=None,
            timeout_ms=None,
            headers=None,
        )
        assert "New Hook" in result.output

    def test_all_options_forwarded(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.create.return_value = _make_created(
            WebhookAuthType.BEARER
        )

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "create",
                "--organization",
                "Acme",
                "--name",
                "New Hook",
                "--url",
                "https://example.com/hook",
                "--description",
                "desc",
                "--auth-type",
                "BEARER",
                "--auth-token",
                _AUTH_TOKEN,
                "--timeout-ms",
                "5000",
                "--header",
                f"X-One={_HEADER_VALUE}",
                "--header",
                "X-Two=a=b",
            ],
        )

        assert result.exit_code == 0, result.output
        mock_client.webhooks.create.assert_called_once_with(
            organization="Acme",
            name="New Hook",
            url="https://example.com/hook",
            description="desc",
            auth_type=WebhookAuthType.BEARER,
            auth_token=_AUTH_TOKEN,
            timeout_ms=5000,
            headers={"X-One": _HEADER_VALUE, "X-Two": "a=b"},
        )

    def test_secrets_redacted_from_sdk_error(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.create.side_effect = RuntimeError(
            f"422 for auth_token={_AUTH_TOKEN} headers=X-One:{_HEADER_VALUE}"
        )

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "create",
                "--organization",
                "org_1",
                "--name",
                "New Hook",
                "--url",
                "https://example.com/hook",
                "--auth-token",
                _AUTH_TOKEN,
                "--header",
                f"X-One={_HEADER_VALUE}",
            ],
        )

        assert result.exit_code == 4
        assert "Failed to create webhook" in result.output
        assert _AUTH_TOKEN not in result.output
        assert _HEADER_VALUE not in result.output
        assert "***" in result.output

    def test_header_key_and_value_are_stripped(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.create.return_value = _make_created(
            WebhookAuthType.BEARER
        )

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "create",
                "--organization",
                "org_1",
                "--name",
                "New Hook",
                "--url",
                "https://example.com/hook",
                "--header",
                " X-Env = prod ",
            ],
        )

        assert result.exit_code == 0, result.output
        _, kwargs = mock_client.webhooks.create.call_args
        assert kwargs["headers"] == {"X-Env": "prod"}

    def test_empty_header_value_forwarded(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.create.return_value = _make_created(
            WebhookAuthType.BEARER
        )

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "create",
                "--organization",
                "org_1",
                "--name",
                "New Hook",
                "--url",
                "https://example.com/hook",
                "--header",
                "X-A=",
            ],
        )

        assert result.exit_code == 0, result.output
        _, kwargs = mock_client.webhooks.create.call_args
        assert kwargs["headers"] == {"X-A": ""}

    def test_duplicate_header_keys_exit_2(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "create",
                "--organization",
                "org_1",
                "--name",
                "New Hook",
                "--url",
                "https://example.com/hook",
                "--header",
                "X-Env=prod",
                "--header",
                "x-env=staging",
            ],
        )

        assert result.exit_code == 2, result.output
        assert "Duplicate --header" in result.output
        mock_client.webhooks.create.assert_not_called()

    def test_auth_token_with_hmac_exits_2(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "create",
                "--organization",
                "org_1",
                "--name",
                "New Hook",
                "--url",
                "https://example.com/hook",
                "--auth-type",
                "HMAC_SHA256",
                "--auth-token",
                _AUTH_TOKEN,
            ],
        )

        assert result.exit_code == 2, result.output
        assert "--auth-token is only valid with --auth-type BEARER" in (
            result.output
        )
        assert _AUTH_TOKEN not in result.output
        mock_client.webhooks.create.assert_not_called()

    @pytest.mark.parametrize("timeout", ["999", "60001"])
    def test_timeout_out_of_range_exits_2(
        self, cli_runner: CliRunner, mock_client: MagicMock, timeout: str
    ) -> None:
        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "create",
                "--organization",
                "org_1",
                "--name",
                "New Hook",
                "--url",
                "https://example.com/hook",
                "--timeout-ms",
                timeout,
            ],
        )

        assert result.exit_code == 2, result.output
        mock_client.webhooks.create.assert_not_called()

    def test_hmac_prints_signing_secret_and_warning(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.create.return_value = _make_created(
            WebhookAuthType.HMAC_SHA256, signing_secret=_SIGNING_SECRET
        )

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "create",
                "--organization",
                "org_1",
                "--name",
                "New Hook",
                "--url",
                "https://example.com/hook",
                "--auth-type",
                "HMAC_SHA256",
            ],
        )

        assert result.exit_code == 0, result.output
        _, kwargs = mock_client.webhooks.create.call_args
        assert kwargs["auth_type"] == WebhookAuthType.HMAC_SHA256
        assert _SIGNING_SECRET in result.output
        assert "Save this signing secret now" in result.output

    def test_hmac_json_output_carries_signing_secret(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.create.return_value = _make_created(
            WebhookAuthType.HMAC_SHA256, signing_secret=_SIGNING_SECRET
        )

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "create",
                "--organization",
                "org_1",
                "--name",
                "New Hook",
                "--url",
                "https://example.com/hook",
                "--auth-type",
                "HMAC_SHA256",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["signing_secret"] == _SIGNING_SECRET

    def test_bearer_prints_no_secret_and_no_warning(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.create.return_value = _make_created(
            WebhookAuthType.BEARER
        )

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "create",
                "--organization",
                "org_1",
                "--name",
                "New Hook",
                "--url",
                "https://example.com/hook",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "signing_secret" not in json.loads(result.stdout)
        assert "Save this signing secret now" not in result.output

    def test_hmac_output_file_holds_secret_and_suppresses_warning(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_client.webhooks.create.return_value = _make_created(
            WebhookAuthType.HMAC_SHA256, signing_secret=_SIGNING_SECRET
        )
        out_file = str(tmp_path / "hook.json")

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "create",
                "--organization",
                "org_1",
                "--name",
                "New Hook",
                "--url",
                "https://example.com/hook",
                "--auth-type",
                "HMAC_SHA256",
                "--output",
                out_file,
            ],
        )

        assert result.exit_code == 0, result.output
        assert "Save this signing secret now" not in result.output
        assert _SIGNING_SECRET not in result.output
        saved = json.loads(Path(out_file).read_text())
        assert saved["signing_secret"] == _SIGNING_SECRET

    @pytest.mark.parametrize("bad_header", ["NoEqualsSign", "=value", ""])
    def test_malformed_header_exits_2(
        self, cli_runner: CliRunner, mock_client: MagicMock, bad_header: str
    ) -> None:
        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "create",
                "--organization",
                "org_1",
                "--name",
                "New Hook",
                "--url",
                "https://example.com/hook",
                "--header",
                bad_header,
            ],
        )

        assert result.exit_code == 2, result.output
        assert "KEY=VALUE" in result.output
        mock_client.webhooks.create.assert_not_called()

    def test_invalid_auth_type_exits_2(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "create",
                "--organization",
                "org_1",
                "--name",
                "New Hook",
                "--url",
                "https://example.com/hook",
                "--auth-type",
                "BASIC",
            ],
        )

        assert result.exit_code == 2
        mock_client.webhooks.create.assert_not_called()

    @pytest.mark.parametrize(
        "args",
        [
            ["--name", "n", "--url", "https://example.com"],
            ["--organization", "org_1", "--url", "https://example.com"],
            ["--organization", "org_1", "--name", "n"],
        ],
    )
    def test_missing_required_option_exits_2(
        self, cli_runner: CliRunner, mock_client: MagicMock, args: list[str]
    ) -> None:
        result = cli_runner.invoke(app, ["webhooks", "create", *args])

        assert result.exit_code == 2
        mock_client.webhooks.create.assert_not_called()

    def test_sdk_error_exits_4(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.create.side_effect = RuntimeError("boom")

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "create",
                "--organization",
                "org_1",
                "--name",
                "n",
                "--url",
                "https://example.com",
            ],
        )

        assert result.exit_code == 4
        assert "Failed to create webhook" in result.output


# ---------------------------------------------------------------------------
# ax webhooks update
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("patch_config_and_client")
class TestUpdateWebhook:
    def test_only_given_options_forwarded(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.update.return_value = _make_webhook(name="Renamed")

        result = cli_runner.invoke(
            app, ["webhooks", "update", "wh_1", "--name", "Renamed"]
        )

        assert result.exit_code == 0, result.output
        mock_client.webhooks.update.assert_called_once_with(
            webhook="wh_1", organization=None, name="Renamed"
        )
        assert "Renamed" in result.output

    def test_all_options_forwarded(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.update.return_value = _make_webhook()

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "update",
                "My Hook",
                "--organization",
                "Acme",
                "--name",
                "Renamed",
                "--description",
                "new desc",
                "--url",
                "https://example.com/new",
                "--auth-token",
                _AUTH_TOKEN,
                "--timeout-ms",
                "10000",
                "--header",
                f"X-One={_HEADER_VALUE}",
            ],
        )

        assert result.exit_code == 0, result.output
        mock_client.webhooks.update.assert_called_once_with(
            webhook="My Hook",
            organization="Acme",
            name="Renamed",
            description="new desc",
            url="https://example.com/new",
            auth_token=_AUTH_TOKEN,
            timeout_ms=10000,
            headers={"X-One": _HEADER_VALUE},
        )
        assert _AUTH_TOKEN not in result.output
        assert _HEADER_VALUE not in result.output

    def test_empty_description_clears(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.update.return_value = _make_webhook()

        result = cli_runner.invoke(
            app, ["webhooks", "update", "wh_1", "--description", ""]
        )

        assert result.exit_code == 0, result.output
        mock_client.webhooks.update.assert_called_once_with(
            webhook="wh_1", organization=None, description=""
        )

    def test_no_options_exits_2(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        result = cli_runner.invoke(app, ["webhooks", "update", "wh_1"])

        assert result.exit_code == 2, result.output
        assert "At least one" in result.output
        assert "--clear-headers" in result.output
        mock_client.webhooks.update.assert_not_called()

    def test_clear_headers_sends_empty_map(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.update.return_value = _make_webhook()

        result = cli_runner.invoke(
            app, ["webhooks", "update", "wh_1", "--clear-headers"]
        )

        assert result.exit_code == 0, result.output
        mock_client.webhooks.update.assert_called_once_with(
            webhook="wh_1", organization=None, headers={}
        )

    def test_clear_headers_with_header_exits_2(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "update",
                "wh_1",
                "--clear-headers",
                "--header",
                "X-A=1",
            ],
        )

        assert result.exit_code == 2, result.output
        assert "--clear-headers" in result.output
        mock_client.webhooks.update.assert_not_called()

    def test_secrets_redacted_from_sdk_error(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.update.side_effect = RuntimeError(
            f"422 for auth_token={_AUTH_TOKEN} headers=X-One:{_HEADER_VALUE}"
        )

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "update",
                "wh_1",
                "--auth-token",
                _AUTH_TOKEN,
                "--header",
                f"X-One={_HEADER_VALUE}",
            ],
        )

        assert result.exit_code == 4
        assert _AUTH_TOKEN not in result.output
        assert _HEADER_VALUE not in result.output
        assert "***" in result.output

    def test_update_by_name_without_organization_exits_4(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.update.side_effect = ValueError(
            "'organization' is required when 'webhook' is a name"
        )

        result = cli_runner.invoke(
            app, ["webhooks", "update", "My Hook", "--name", "Renamed"]
        )

        assert result.exit_code == 4
        assert "Failed to update webhook" in result.output

    def test_duplicate_header_keys_exit_2(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "update",
                "wh_1",
                "--header",
                "A=1",
                "--header",
                "A=2",
            ],
        )

        assert result.exit_code == 2, result.output
        mock_client.webhooks.update.assert_not_called()

    @pytest.mark.parametrize("timeout", ["999", "60001"])
    def test_timeout_out_of_range_exits_2(
        self, cli_runner: CliRunner, mock_client: MagicMock, timeout: str
    ) -> None:
        result = cli_runner.invoke(
            app, ["webhooks", "update", "wh_1", "--timeout-ms", timeout]
        )

        assert result.exit_code == 2, result.output
        mock_client.webhooks.update.assert_not_called()

    def test_organization_alone_is_not_an_update(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        result = cli_runner.invoke(
            app, ["webhooks", "update", "wh_1", "--organization", "org_1"]
        )

        assert result.exit_code == 2, result.output
        mock_client.webhooks.update.assert_not_called()

    def test_malformed_header_exits_2(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        result = cli_runner.invoke(
            app, ["webhooks", "update", "wh_1", "--header", "nope"]
        )

        assert result.exit_code == 2, result.output
        mock_client.webhooks.update.assert_not_called()

    def test_json_output(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.update.return_value = _make_webhook(name="Renamed")

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "update",
                "wh_1",
                "--name",
                "Renamed",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["name"] == "Renamed"

    def test_sdk_error_exits_4(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.update.side_effect = RuntimeError("boom")

        result = cli_runner.invoke(
            app, ["webhooks", "update", "wh_1", "--name", "x"]
        )

        assert result.exit_code == 4


# ---------------------------------------------------------------------------
# ax webhooks delete
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("patch_config_and_client")
class TestDeleteWebhook:
    def test_force_skips_confirmation(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        result = cli_runner.invoke(
            app, ["webhooks", "delete", "wh_1", "--force"]
        )

        assert result.exit_code == 0, result.output
        mock_client.webhooks.delete.assert_called_once_with(
            webhook="wh_1", organization=None
        )
        assert "Are you sure" not in result.output

    def test_confirm_yes_calls_sdk_with_organization(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        result = cli_runner.invoke(
            app,
            ["webhooks", "delete", "My Hook", "--organization", "org_1"],
            input="y\n",
        )

        assert result.exit_code == 0, result.output
        assert "permanently delete" in result.output
        mock_client.webhooks.delete.assert_called_once_with(
            webhook="My Hook", organization="org_1"
        )

    def test_decline_does_not_call_sdk(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        result = cli_runner.invoke(
            app, ["webhooks", "delete", "wh_1"], input="n\n"
        )

        assert result.exit_code == 0, result.output
        assert "not deleted" in result.output
        mock_client.webhooks.delete.assert_not_called()

    def test_sdk_error_exits_4(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.delete.side_effect = RuntimeError("boom")

        result = cli_runner.invoke(
            app, ["webhooks", "delete", "wh_1", "--force"]
        )

        assert result.exit_code == 4


# ---------------------------------------------------------------------------
# ax webhooks test
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("patch_config_and_client")
class TestTestWebhook:
    def test_forwards_and_prints_status(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.test.return_value = WebhookTestResponse(
            status_code=200, error_message=None
        )

        result = cli_runner.invoke(
            app, ["webhooks", "test", "My Hook", "--organization", "org_1"]
        )

        assert result.exit_code == 0, result.output
        mock_client.webhooks.test.assert_called_once_with(
            webhook="My Hook", organization="org_1"
        )
        assert "200" in result.output

    def test_json_output(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.test.return_value = WebhookTestResponse(
            status_code=502, error_message="connection refused"
        )

        result = cli_runner.invoke(
            app, ["webhooks", "test", "wh_1", "--output", "json"]
        )

        assert result.exit_code == 1, result.output
        data = json.loads(result.stdout)
        assert data == {
            "status_code": 502,
            "error_message": "connection refused",
        }

    @pytest.mark.parametrize("status_code", [301, 404, 500, 502])
    def test_non_2xx_exits_1_after_printing_result(
        self, cli_runner: CliRunner, mock_client: MagicMock, status_code: int
    ) -> None:
        mock_client.webhooks.test.return_value = WebhookTestResponse(
            status_code=status_code, error_message="nope"
        )

        result = cli_runner.invoke(app, ["webhooks", "test", "wh_1"])

        assert result.exit_code == 1, result.output
        assert str(status_code) in result.output
        assert "nope" in result.output

    @pytest.mark.parametrize("status_code", [200, 204, 299])
    def test_2xx_exits_0(
        self, cli_runner: CliRunner, mock_client: MagicMock, status_code: int
    ) -> None:
        mock_client.webhooks.test.return_value = WebhookTestResponse(
            status_code=status_code, error_message=None
        )

        result = cli_runner.invoke(app, ["webhooks", "test", "wh_1"])

        assert result.exit_code == 0, result.output

    def test_sdk_error_exits_4(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.test.side_effect = RuntimeError("boom")

        result = cli_runner.invoke(app, ["webhooks", "test", "wh_1"])

        assert result.exit_code == 4


# ---------------------------------------------------------------------------
# ax webhooks deliveries
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("patch_config_and_client")
class TestListDeliveries:
    def test_csv_output_has_one_row_per_attempt(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.list_delivery_attempts.return_value = (
            _make_attempt_list(_make_attempt("evt_1"), _make_attempt("evt_2"))
        )

        result = cli_runner.invoke(
            app, ["webhooks", "deliveries", "wh_1", "-o", "csv"]
        )

        assert result.exit_code == 0, result.output
        rows = _read_csv(result.stdout)
        assert [row["event_id"] for row in rows] == ["evt_1", "evt_2"]
        assert "num_delivery_attempts" not in result.stdout

    @pytest.mark.parametrize("limit", ["0", "501"])
    def test_limit_out_of_range_exits_2(
        self, cli_runner: CliRunner, mock_client: MagicMock, limit: str
    ) -> None:
        result = cli_runner.invoke(
            app, ["webhooks", "deliveries", "wh_1", "--limit", limit]
        )

        assert result.exit_code == 2, result.output
        mock_client.webhooks.list_delivery_attempts.assert_not_called()

    def test_defaults_forwarded(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.list_delivery_attempts.return_value = (
            _make_attempt_list(_make_attempt())
        )

        result = cli_runner.invoke(app, ["webhooks", "deliveries", "wh_1"])

        assert result.exit_code == 0, result.output
        mock_client.webhooks.list_delivery_attempts.assert_called_once_with(
            webhook="wh_1", organization=None, limit=15, cursor=None
        )
        assert "evt_1" in result.output

    def test_options_forwarded(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.list_delivery_attempts.return_value = (
            _make_attempt_list()
        )

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "deliveries",
                "My Hook",
                "--organization",
                "org_1",
                "--limit",
                "500",
                "--cursor",
                "tok",
            ],
        )

        assert result.exit_code == 0, result.output
        mock_client.webhooks.list_delivery_attempts.assert_called_once_with(
            webhook="My Hook", organization="org_1", limit=500, cursor="tok"
        )

    def test_json_output(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.list_delivery_attempts.return_value = (
            _make_attempt_list(_make_attempt(event_id="evt_9"))
        )

        result = cli_runner.invoke(
            app, ["webhooks", "deliveries", "wh_1", "--output", "json"]
        )

        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert data["delivery_attempts"][0]["event_id"] == "evt_9"

    def test_missing_argument_exits_2(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        result = cli_runner.invoke(app, ["webhooks", "deliveries"])

        assert result.exit_code == 2
        mock_client.webhooks.list_delivery_attempts.assert_not_called()

    def test_sdk_error_exits_4(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.list_delivery_attempts.side_effect = RuntimeError(
            "boom"
        )

        result = cli_runner.invoke(app, ["webhooks", "deliveries", "wh_1"])

        assert result.exit_code == 4


# ---------------------------------------------------------------------------
# ax webhooks subscriptions list
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("patch_config_and_client")
class TestListSubscriptions:
    def test_no_source_lists_all(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.list_subscriptions.return_value = (
            _make_subscription_list(_make_subscription())
        )

        result = cli_runner.invoke(app, ["webhooks", "subscriptions", "list"])

        assert result.exit_code == 0, result.output
        mock_client.webhooks.list_subscriptions.assert_called_once_with(
            source_type=None, source_id=None, limit=15, cursor=None
        )

    def test_csv_output_has_one_row_per_subscription(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.list_subscriptions.return_value = (
            _make_subscription_list(
                _make_subscription("sub_1"), _make_subscription("sub_2")
            )
        )

        result = cli_runner.invoke(
            app, ["webhooks", "subscriptions", "list", "-o", "csv"]
        )

        assert result.exit_code == 0, result.output
        rows = _read_csv(result.stdout)
        assert [row["id"] for row in rows] == ["sub_1", "sub_2"]
        assert "num_subscriptions" not in result.stdout

    def test_help_warns_about_short_pages(self, cli_runner: CliRunner) -> None:
        result = cli_runner.invoke(
            app, ["webhooks", "subscriptions", "list", "--help"]
        )

        assert result.exit_code == 0
        assert "has_more" in result.output

    @pytest.mark.parametrize("limit", ["0", "101"])
    def test_limit_out_of_range_exits_2(
        self, cli_runner: CliRunner, mock_client: MagicMock, limit: str
    ) -> None:
        result = cli_runner.invoke(
            app, ["webhooks", "subscriptions", "list", "--limit", limit]
        )

        assert result.exit_code == 2, result.output
        mock_client.webhooks.list_subscriptions.assert_not_called()

    def test_defaults_forwarded(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.list_subscriptions.return_value = (
            _make_subscription_list(_make_subscription())
        )

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "subscriptions",
                "list",
                "--source-type",
                "EVALUATOR",
                "--source-id",
                "ev_1",
            ],
        )

        assert result.exit_code == 0, result.output
        mock_client.webhooks.list_subscriptions.assert_called_once_with(
            source_type=WebhookSourceType.EVALUATOR,
            source_id="ev_1",
            limit=15,
            cursor=None,
        )
        assert "sub_1" in result.output

    def test_options_forwarded(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.list_subscriptions.return_value = (
            _make_subscription_list()
        )

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "subscriptions",
                "list",
                "--source-type",
                "PROMPT",
                "--source-id",
                "pr_1",
                "--limit",
                "3",
                "--cursor",
                "tok",
            ],
        )

        assert result.exit_code == 0, result.output
        mock_client.webhooks.list_subscriptions.assert_called_once_with(
            source_type=WebhookSourceType.PROMPT,
            source_id="pr_1",
            limit=3,
            cursor="tok",
        )

    def test_json_output(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.list_subscriptions.return_value = (
            _make_subscription_list(_make_subscription(id="sub_7"))
        )

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "subscriptions",
                "list",
                "--source-type",
                "EVALUATOR",
                "--source-id",
                "ev_1",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert data["subscriptions"][0]["id"] == "sub_7"

    @pytest.mark.parametrize(
        "args",
        [
            ["--source-type", "PROMPT"],
            ["--source-id", "pr_1"],
            ["--source-type", "MONITOR", "--source-id", "x"],
        ],
    )
    def test_lone_or_invalid_source_exits_2(
        self, cli_runner: CliRunner, mock_client: MagicMock, args: list[str]
    ) -> None:
        result = cli_runner.invoke(
            app, ["webhooks", "subscriptions", "list", *args]
        )

        assert result.exit_code == 2, result.output
        mock_client.webhooks.list_subscriptions.assert_not_called()

    def test_sdk_error_exits_4(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.list_subscriptions.side_effect = RuntimeError(
            "boom"
        )

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "subscriptions",
                "list",
                "--source-type",
                "PROMPT",
                "--source-id",
                "pr_1",
            ],
        )

        assert result.exit_code == 4


# ---------------------------------------------------------------------------
# ax webhooks subscriptions create
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("patch_config_and_client")
class TestCreateSubscription:
    def test_options_forwarded(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.create_subscription.return_value = (
            _make_subscription(id="sub_new")
        )

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "subscriptions",
                "create",
                "--webhook",
                "My Hook",
                "--organization",
                "org_1",
                "--source-type",
                "EVALUATOR",
                "--source-id",
                "ev_1",
                "--event",
                "EVALUATOR_VERSION_CREATED",
            ],
        )

        assert result.exit_code == 0, result.output
        mock_client.webhooks.create_subscription.assert_called_once_with(
            webhook="My Hook",
            source_type=WebhookSourceType.EVALUATOR,
            source_id="ev_1",
            event=WebhookEventType.EVALUATOR_VERSION_CREATED,
            organization="org_1",
        )
        assert "sub_new" in result.output

    def test_organization_defaults_to_none(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.create_subscription.return_value = (
            _make_subscription()
        )

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "subscriptions",
                "create",
                "--webhook",
                "wh_1",
                "--source-type",
                "PROMPT",
                "--source-id",
                "pr_1",
                "--event",
                "PROMPT_VERSION_LABELED",
                "--output",
                "json",
            ],
        )

        assert result.exit_code == 0, result.output
        mock_client.webhooks.create_subscription.assert_called_once_with(
            webhook="wh_1",
            source_type=WebhookSourceType.PROMPT,
            source_id="pr_1",
            event=WebhookEventType.PROMPT_VERSION_LABELED,
            organization=None,
        )
        assert json.loads(result.stdout)["id"] == "sub_1"

    @pytest.mark.parametrize(
        "args",
        [
            [
                "--source-type",
                "PROMPT",
                "--source-id",
                "pr_1",
                "--event",
                "PROMPT_VERSION_CREATED",
            ],
            [
                "--webhook",
                "wh_1",
                "--source-id",
                "pr_1",
                "--event",
                "PROMPT_VERSION_CREATED",
            ],
            [
                "--webhook",
                "wh_1",
                "--source-type",
                "PROMPT",
                "--event",
                "PROMPT_VERSION_CREATED",
            ],
            [
                "--webhook",
                "wh_1",
                "--source-type",
                "PROMPT",
                "--source-id",
                "pr_1",
            ],
            [
                "--webhook",
                "wh_1",
                "--source-type",
                "PROMPT",
                "--source-id",
                "pr_1",
                "--event",
                "NOPE",
            ],
        ],
    )
    def test_missing_or_invalid_option_exits_2(
        self, cli_runner: CliRunner, mock_client: MagicMock, args: list[str]
    ) -> None:
        result = cli_runner.invoke(
            app, ["webhooks", "subscriptions", "create", *args]
        )

        assert result.exit_code == 2, result.output
        mock_client.webhooks.create_subscription.assert_not_called()

    def test_sdk_error_exits_4(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.create_subscription.side_effect = RuntimeError(
            "boom"
        )

        result = cli_runner.invoke(
            app,
            [
                "webhooks",
                "subscriptions",
                "create",
                "--webhook",
                "wh_1",
                "--source-type",
                "PROMPT",
                "--source-id",
                "pr_1",
                "--event",
                "PROMPT_VERSION_CREATED",
            ],
        )

        assert result.exit_code == 4
        assert "Failed to create webhook subscription" in result.output


# ---------------------------------------------------------------------------
# ax webhooks subscriptions get
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("patch_config_and_client")
class TestGetSubscription:
    def test_forwards_id(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.get_subscription.return_value = _make_subscription(
            id="sub_9"
        )

        result = cli_runner.invoke(
            app, ["webhooks", "subscriptions", "get", "sub_9"]
        )

        assert result.exit_code == 0, result.output
        mock_client.webhooks.get_subscription.assert_called_once_with(
            subscription_id="sub_9"
        )
        assert "sub_9" in result.output

    def test_json_output(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.get_subscription.return_value = _make_subscription(
            id="sub_9"
        )

        result = cli_runner.invoke(
            app,
            ["webhooks", "subscriptions", "get", "sub_9", "--output", "json"],
        )

        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout)
        assert data["id"] == "sub_9"
        assert data["event"] == "EVALUATOR_VERSION_CREATED"

    def test_missing_argument_exits_2(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        result = cli_runner.invoke(app, ["webhooks", "subscriptions", "get"])

        assert result.exit_code == 2
        mock_client.webhooks.get_subscription.assert_not_called()

    def test_sdk_error_exits_4(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.get_subscription.side_effect = RuntimeError("boom")

        result = cli_runner.invoke(
            app, ["webhooks", "subscriptions", "get", "sub_9"]
        )

        assert result.exit_code == 4


# ---------------------------------------------------------------------------
# ax webhooks subscriptions delete
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("patch_config_and_client")
class TestDeleteSubscription:
    def test_force_skips_confirmation(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        result = cli_runner.invoke(
            app, ["webhooks", "subscriptions", "delete", "sub_1", "--force"]
        )

        assert result.exit_code == 0, result.output
        mock_client.webhooks.delete_subscription.assert_called_once_with(
            subscription_id="sub_1"
        )
        assert "Are you sure" not in result.output

    def test_confirm_yes_calls_sdk(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        result = cli_runner.invoke(
            app,
            ["webhooks", "subscriptions", "delete", "sub_1"],
            input="y\n",
        )

        assert result.exit_code == 0, result.output
        mock_client.webhooks.delete_subscription.assert_called_once_with(
            subscription_id="sub_1"
        )

    def test_decline_does_not_call_sdk(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        result = cli_runner.invoke(
            app,
            ["webhooks", "subscriptions", "delete", "sub_1"],
            input="n\n",
        )

        assert result.exit_code == 0, result.output
        assert "not deleted" in result.output
        mock_client.webhooks.delete_subscription.assert_not_called()

    def test_sdk_error_exits_4(
        self, cli_runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.webhooks.delete_subscription.side_effect = RuntimeError(
            "boom"
        )

        result = cli_runner.invoke(
            app, ["webhooks", "subscriptions", "delete", "sub_1", "--force"]
        )

        assert result.exit_code == 4
