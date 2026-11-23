"""SAML CLI routing and input handling."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from arize._generated.api_client import ApiClient, Configuration
from arize._generated.api_client.rest import RESTResponse
from arize.config import SDKConfiguration
from arize.saml_identity_providers.client import SamlIdentityProvidersClient
from arize.saml_identity_providers.types import (
    ListMappingsResponse,
    RoleMapping,
)
from typer.testing import CliRunner
from urllib3 import HTTPResponse

from ax.commands.saml_identity_providers import app

runner = CliRunner()


@pytest.mark.parametrize(
    "command",
    [
        ["list"],
        ["get", "idp"],
        ["role-mappings", "list", "idp"],
        ["delete", "idp", "--force"],
        ["role-mappings", "remove", "idp", "mapping", "--force"],
    ],
)
def test_commands_use_sdk(command) -> None:
    client = MagicMock()
    config = MagicMock()
    config.output.format = "json"
    with (
        patch(
            "ax.commands.saml_identity_providers.make_client",
            return_value=(client, config),
        ),
        patch("ax.commands.saml_identity_providers.output_data"),
    ):
        result = runner.invoke(app, command)
    assert result.exit_code == 0
    assert client.saml_identity_providers.mock_calls


def test_mapping_update_preserves_json_fields(tmp_path: Path) -> None:
    body = tmp_path / "patch.json"
    body.write_text(
        '{"is_account_admin":false,"organization":null,"project_roles":[]}',
        encoding="utf-8",
    )
    client = MagicMock()
    config = MagicMock()
    config.output.format = "json"
    with (
        patch(
            "ax.commands.saml_identity_providers.make_client",
            return_value=(client, config),
        ),
        patch("ax.commands.saml_identity_providers.output_data"),
    ):
        result = runner.invoke(
            app,
            [
                "role-mappings",
                "update",
                "idp",
                "mapping",
                "--input-file",
                str(body),
            ],
        )
    assert result.exit_code == 0
    call = client.saml_identity_providers.update_role_mapping.call_args
    assert call.kwargs["idp_id"] == "idp"
    assert call.kwargs["mapping_id"] == "mapping"
    assert call.kwargs["body"].to_dict() == {
        "is_account_admin": False,
        "organization": None,
        "project_roles": [],
    }


def test_delete_requires_confirmation() -> None:
    with patch("ax.commands.saml_identity_providers.make_client") as factory:
        result = runner.invoke(app, ["delete", "idp"], input="n\n")
    assert result.exit_code == 0
    factory.assert_not_called()


@pytest.mark.parametrize("project_roles", [None, []])
def test_read_edit_save_preserves_project_role_management(
    tmp_path: Path, project_roles
) -> None:
    mapping = {
        "id": "mapping",
        "attributes": {"groups": "admins"},
        "is_account_admin": True,
        "space_roles": [],
        "project_roles": project_roles,
    }
    client = MagicMock()
    client.saml_identity_providers.list_role_mappings.return_value = (
        ListMappingsResponse.model_validate(
            {"data": [mapping], "pagination": {"has_more": False}}
        )
    )
    client.saml_identity_providers.update_role_mapping.return_value = (
        RoleMapping.model_validate(mapping)
    )
    config = MagicMock()
    config.output.format = "json"
    with patch(
        "ax.commands.saml_identity_providers.make_client",
        return_value=(client, config),
    ):
        listed = runner.invoke(
            app, ["role-mappings", "list", "idp", "--output", "json"]
        )
        assert listed.exit_code == 0, listed.output
        saved = json.loads(listed.stdout)["data"][0]
        assert "Fetching SAML role mappings" in listed.stderr
        assert saved["project_roles"] == project_roles
        assert "project_roles_managed" not in saved
        body = {
            "attributes": {"groups": "changed"},
            "project_roles": saved["project_roles"],
        }
        request = tmp_path / "mapping.json"
        request.write_text(json.dumps(body), encoding="utf-8")
        result = runner.invoke(
            app,
            [
                "role-mappings",
                "update",
                "idp",
                "mapping",
                "--input-file",
                str(request),
                "--output",
                "json",
            ],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["project_roles"] == project_roles
        assert "Updating SAML role mapping" in result.stderr
    call = client.saml_identity_providers.update_role_mapping.call_args
    assert call.kwargs["idp_id"] == "idp"
    assert call.kwargs["mapping_id"] == "mapping"
    assert call.kwargs["body"].to_dict() == body


@pytest.mark.parametrize(
    "command,body,field",
    [
        (["create"], {}, "enforce_saml"),
        (["update", "idp"], {"sync_user_roles": "false"}, "sync_user_roles"),
        (
            ["role-mappings", "add", "idp"],
            {"attributes": {"groups": "admins"}, "is_account_admin": "false"},
            "is_account_admin",
        ),
        (
            ["role-mappings", "update", "idp", "mapping"],
            {"is_account_admin": "false"},
            "is_account_admin",
        ),
        (["update", "idp"], {"unsupported_option": True}, "unsupported_option"),
    ],
)
def test_invalid_request_reports_field_before_api_call(
    tmp_path: Path, command, body, field
) -> None:
    request = tmp_path / "invalid.json"
    request.write_text(json.dumps(body), encoding="utf-8")
    with patch("ax.commands.saml_identity_providers.make_client") as factory:
        result = runner.invoke(app, [*command, "--input-file", str(request)])
    assert result.exit_code == 2, result.output
    assert field in result.output
    assert "pydantic.dev" not in result.output
    factory.assert_not_called()


def test_request_file_accepts_utf8_bom(tmp_path: Path) -> None:
    request = tmp_path / "mapping.json"
    body = {"project_roles": None, "is_account_admin": False}
    request.write_text(json.dumps(body), encoding="utf-8-sig")
    client = MagicMock()
    with (
        patch(
            "ax.commands.saml_identity_providers.make_client",
            return_value=(client, MagicMock()),
        ),
        patch("ax.commands.saml_identity_providers.output_data"),
    ):
        result = runner.invoke(
            app,
            [
                "role-mappings",
                "update",
                "idp",
                "mapping",
                "--input-file",
                str(request),
                "--output",
                "json",
            ],
        )
    assert result.exit_code == 0, result.output
    forwarded = client.saml_identity_providers.update_role_mapping.call_args
    assert forwarded.kwargs["body"].to_dict() == body


@pytest.mark.parametrize("content", [b"[]", b"{", b"\xff"])
def test_invalid_json_file_is_usage_error(tmp_path: Path, content) -> None:
    request = tmp_path / "invalid.json"
    request.write_bytes(content)
    with patch("ax.commands.saml_identity_providers.make_client") as factory:
        result = runner.invoke(
            app, ["update", "idp", "--input-file", str(request)]
        )
    assert result.exit_code == 2, result.output
    assert "Unexpected error" not in result.output
    factory.assert_not_called()


@pytest.mark.parametrize(
    "command",
    [
        ["get", ""],
        ["role-mappings", "list", ""],
        ["role-mappings", "remove", "idp", ""],
    ],
)
def test_empty_id_is_usage_error(command) -> None:
    with patch("ax.commands.saml_identity_providers.make_client") as factory:
        result = runner.invoke(app, command)
    assert result.exit_code == 2, result.output
    assert "ID must not be empty" in result.output
    factory.assert_not_called()


@pytest.mark.parametrize(
    "command,status", [(["create"], 201), (["get", "idp"], 200)]
)
def test_invalid_response_is_api_error(tmp_path: Path, command, status) -> None:
    request = tmp_path / "create.json"
    request.write_text(
        json.dumps(
            {
                "email_domains": ["example.com"],
                "metadata_xml": "metadata",
                "enforce_saml": False,
                "sync_user_roles": False,
                "sign_authn": False,
                "allow_login_with_defaults": False,
            }
        ),
        encoding="utf-8",
    )
    if command == ["create"]:
        command = [*command, "--input-file", str(request)]
    response = RESTResponse(
        HTTPResponse(
            body=b'{"enforce_saml":"not-a-boolean"}',
            status=status,
            headers={"content-type": "application/json"},
        )
    )
    with ApiClient(Configuration(host="http://api.test/v2")) as generated:
        sdk = SamlIdentityProvidersClient(
            sdk_config=SDKConfiguration(api_key="test"),
            generated_client=generated,
        )
        with (
            patch(
                "ax.commands.saml_identity_providers.make_client",
                return_value=(
                    SimpleNamespace(saml_identity_providers=sdk),
                    MagicMock(),
                ),
            ),
            patch.object(
                generated.rest_client, "request", return_value=response
            ) as http,
        ):
            result = runner.invoke(app, command)
    http.assert_called_once()
    assert result.exit_code == 4, result.output
    assert "operation may have succeeded" in result.output
    assert "422" not in result.output
    assert "Invalid SAML request input" not in result.output
    assert "pydantic.dev" not in result.output


def test_metadata_validation_command_is_not_exposed() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "validate-metadata" not in result.output
