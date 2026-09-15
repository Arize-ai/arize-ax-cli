"""Tests for dataset CLI commands."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ax.commands.datasets import (
    _validate_examples_structure,
    app,
)


class TestDatasetCommands:
    """Verify dataset subcommands are registered with the correct names."""

    def test_expected_commands_registered(self) -> None:
        """Check that get, export, append, list, create, delete, rename are present."""
        names = [cmd.name for cmd in app.registered_commands]
        for expected in (
            "get",
            "export",
            "append",
            "list",
            "create",
            "delete",
            "update",
            "update-examples",
            "delete-examples",
        ):
            assert expected in names
        assert "list_examples" not in names
        assert "list-examples" not in names


class TestListDatasets:
    """Tests for the 'ax datasets list' command."""

    def test_calls_client_datasets_list(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'list' with defaults and verify the SDK call."""
        mock_client.datasets.list.return_value = MagicMock(
            model_dump=MagicMock(return_value={"datasets": []})
        )
        result = cli_runner.invoke(app, ["list"])
        assert result.exit_code == 0
        mock_client.datasets.list.assert_called_once_with(
            name=None,
            space=None,
            limit=15,
            cursor=None,
        )

    def test_list_with_space(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify --space is forwarded."""
        mock_client.datasets.list.return_value = MagicMock(
            model_dump=MagicMock(return_value={"datasets": []})
        )
        result = cli_runner.invoke(app, ["list", "--space", "space-abc"])
        assert result.exit_code == 0
        mock_client.datasets.list.assert_called_once_with(
            name=None,
            space="space-abc",
            limit=15,
            cursor=None,
        )

    def test_list_with_limit(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify --limit / -n is forwarded."""
        mock_client.datasets.list.return_value = MagicMock(
            model_dump=MagicMock(return_value={"datasets": []})
        )
        result = cli_runner.invoke(app, ["list", "-l", "5"])
        assert result.exit_code == 0
        mock_client.datasets.list.assert_called_once_with(
            name=None,
            space=None,
            limit=5,
            cursor=None,
        )

    def test_list_with_cursor(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify --cursor for pagination is forwarded."""
        mock_client.datasets.list.return_value = MagicMock(
            model_dump=MagicMock(return_value={"datasets": []})
        )
        result = cli_runner.invoke(app, ["list", "--cursor", "cursor-xyz"])
        assert result.exit_code == 0
        mock_client.datasets.list.assert_called_once_with(
            name=None,
            space=None,
            limit=15,
            cursor="cursor-xyz",
        )

    def test_list_with_name_filter(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify --name filter is forwarded to the SDK."""
        mock_client.datasets.list.return_value = MagicMock(
            model_dump=MagicMock(return_value={"datasets": []})
        )
        result = cli_runner.invoke(app, ["list", "--name", "eval"])
        assert result.exit_code == 0
        mock_client.datasets.list.assert_called_once_with(
            name="eval",
            space=None,
            limit=15,
            cursor=None,
        )

    def test_list_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """API failure should result in a non-zero exit code."""
        mock_client.datasets.list.side_effect = Exception("connection refused")
        result = cli_runner.invoke(app, ["list"])
        assert result.exit_code != 0


class TestGetDataset:
    """Tests for the 'ax datasets get' command."""

    def test_calls_client_datasets_get(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'get' and verify the SDK call."""
        mock_client.datasets.get.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "ds-1", "name": "test"})
        )
        result = cli_runner.invoke(app, ["get", "ds-1"])
        assert result.exit_code == 0
        mock_client.datasets.get.assert_called_once_with(
            dataset="ds-1", space=None
        )


class TestExportDataset:
    """Tests for the 'ax datasets export' command."""

    def test_export_defaults_to_rest(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify export defaults to one REST page."""
        response = MagicMock()
        response.examples = []
        mock_client.datasets.list_examples.return_value = response

        result = cli_runner.invoke(app, ["export", "ds-1", "--stdout"])
        assert result.exit_code == 0
        mock_client.datasets.list_examples.assert_called_once_with(
            dataset="ds-1",
            space=None,
            dataset_version_id=None,
            cursor=None,
            all=False,
        )

    def test_export_with_limit(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify --limit is forwarded as the page size."""
        response = MagicMock()
        response.examples = []
        mock_client.datasets.list_examples.return_value = response

        result = cli_runner.invoke(
            app, ["export", "ds-1", "--stdout", "--limit", "25"]
        )
        assert result.exit_code == 0
        mock_client.datasets.list_examples.assert_called_once_with(
            dataset="ds-1",
            space=None,
            dataset_version_id=None,
            limit=25,
            cursor=None,
            all=False,
        )

    def test_export_with_cursor(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify --cursor selects the page to export."""
        response = MagicMock()
        response.examples = []
        mock_client.datasets.list_examples.return_value = response

        result = cli_runner.invoke(
            app,
            ["export", "ds-1", "--stdout", "--cursor", "cursor-2"],
        )
        assert result.exit_code == 0
        mock_client.datasets.list_examples.assert_called_once_with(
            dataset="ds-1",
            space=None,
            dataset_version_id=None,
            cursor="cursor-2",
            all=False,
        )

    def test_export_does_not_follow_next_cursor(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify export writes one page even when another page is available."""
        response = MagicMock()
        response.examples = [
            MagicMock(model_dump=MagicMock(return_value={"id": "1"}))
        ]
        response.pagination.has_more = True
        response.pagination.next_cursor = "cursor-2"
        mock_client.datasets.list_examples.return_value = response

        result = cli_runner.invoke(app, ["export", "ds-1", "--stdout"])
        assert result.exit_code == 0
        assert json.loads(result.stdout) == [{"id": "1"}]
        mock_client.datasets.list_examples.assert_called_once_with(
            dataset="ds-1",
            space=None,
            dataset_version_id=None,
            cursor=None,
            all=False,
        )

    def test_export_all_uses_flight(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify --all passes all=True to SDK (Flight path)."""
        response = MagicMock()
        response.examples = []
        mock_client.datasets.list_examples.return_value = response

        result = cli_runner.invoke(app, ["export", "ds-1", "--all", "--stdout"])
        assert result.exit_code == 0
        mock_client.datasets.list_examples.assert_called_once_with(
            dataset="ds-1",
            space=None,
            dataset_version_id=None,
            cursor=None,
            all=True,
        )

    def test_export_with_version_id(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify --version-id is forwarded to list_examples."""
        response = MagicMock()
        response.examples = []
        mock_client.datasets.list_examples.return_value = response

        result = cli_runner.invoke(
            app,
            ["export", "ds-1", "--version-id", "v2", "--stdout"],
        )
        assert result.exit_code == 0
        mock_client.datasets.list_examples.assert_called_once_with(
            dataset="ds-1",
            space=None,
            dataset_version_id="v2",
            cursor=None,
            all=False,
        )

    def test_export_writes_file(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """Verify export writes the returned page to disk."""
        response = MagicMock()
        example = MagicMock(model_dump=MagicMock(return_value={"id": "1"}))
        response.examples = [example]
        mock_client.datasets.list_examples.return_value = response

        with patch("ax.commands.datasets.make_export_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            result = cli_runner.invoke(
                app,
                ["export", "ds-1", "--output-dir", str(tmp_path)],
            )
            assert result.exit_code == 0
            written = json.loads((tmp_path / "examples.json").read_text())
            assert written == [{"id": "1"}]

    def test_export_limit_rejects_non_positive_values(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--limit 0 or negative must be rejected before any SDK call."""
        result = cli_runner.invoke(
            app, ["export", "ds-1", "--stdout", "--limit", "0"]
        )
        assert result.exit_code != 0
        mock_client.datasets.list_examples.assert_not_called()

    def test_export_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify API failures produce a non-zero exit code."""
        mock_client.datasets.list_examples.side_effect = RuntimeError("failed")

        result = cli_runner.invoke(app, ["export", "ds-1", "--stdout"])
        assert result.exit_code != 0


class TestCreateDataset:
    """Tests for the 'ax datasets create' command."""

    def test_create_with_file(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """Verify create reads a CSV file and calls the SDK."""
        mock_client.datasets.create.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "ds-1", "name": "test"})
        )
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("question,answer\nWhat is 2+2?,4\n")

        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "test",
                "--space",
                "sp-1",
                "--file",
                str(csv_file),
            ],
        )
        assert result.exit_code == 0
        mock_client.datasets.create.assert_called_once()
        call_kwargs = mock_client.datasets.create.call_args[1]
        assert call_kwargs["name"] == "test"
        assert call_kwargs["space"] == "sp-1"

    def test_create_with_json_inline(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify create accepts inline JSON via --json."""
        mock_client.datasets.create.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "ds-1", "name": "test"})
        )
        payload = json.dumps([{"question": "What is 2+2?", "answer": "4"}])
        result = cli_runner.invoke(
            app,
            ["create", "--name", "test", "--space", "sp-1", "--json", payload],
        )
        assert result.exit_code == 0
        mock_client.datasets.create.assert_called_once()
        call_kwargs = mock_client.datasets.create.call_args[1]
        assert call_kwargs["examples"] == [
            {"question": "What is 2+2?", "answer": "4"}
        ]

    def test_create_with_stdin_dash(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify '--file -' reads JSON array from stdin."""
        mock_client.datasets.create.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "ds-1", "name": "test"})
        )
        stdin_data = '[{"question": "What is 2+2?", "answer": "4"}]'
        result = cli_runner.invoke(
            app,
            ["create", "--name", "test", "--space", "sp-1", "--file", "-"],
            input=stdin_data,
        )
        assert result.exit_code == 0
        mock_client.datasets.create.assert_called_once()

    def test_create_with_stdin_dev_stdin(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify '--file /dev/stdin' is treated as a stdin path."""
        mock_client.datasets.create.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "ds-1", "name": "test"})
        )
        stdin_data = '[{"question": "hi", "answer": "bye"}]'
        with patch("ax.utils.file_io._is_stdin_path", return_value=True):
            result = cli_runner.invoke(
                app,
                [
                    "create",
                    "--name",
                    "test",
                    "--space",
                    "sp-1",
                    "--file",
                    "/dev/stdin",
                ],
                input=stdin_data,
            )
        assert result.exit_code == 0

    def test_create_missing_file_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Non-existent file path should fail with non-zero exit."""
        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "test",
                "--space",
                "sp-1",
                "--file",
                "/nonexistent/path/data.csv",
            ],
        )
        assert result.exit_code != 0


class TestAppendDataset:
    """Tests for the 'ax datasets append' command."""

    def test_append_with_json_string(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify append forwards inline JSON to the SDK."""
        mock_client.datasets.append_examples.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "ds-1", "name": "test"})
        )
        examples = [{"question": "What is 2+2?", "answer": "4"}]
        result = cli_runner.invoke(
            app,
            ["append", "ds-1", "--json", json.dumps(examples)],
        )
        assert result.exit_code == 0
        mock_client.datasets.append_examples.assert_called_once_with(
            dataset="ds-1",
            space=None,
            dataset_version_id="",
            examples=examples,
        )

    def test_append_with_file(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """Verify append reads a CSV file and forwards parsed examples."""
        mock_client.datasets.append_examples.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "ds-1", "name": "test"})
        )
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("question,answer\nWhat is 2+2?,4\n")

        result = cli_runner.invoke(
            app,
            ["append", "ds-1", "--file", str(csv_file)],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.datasets.append_examples.call_args[1]
        assert call_kwargs["dataset"] == "ds-1"
        assert call_kwargs["examples"][0]["question"] == "What is 2+2?"

    def test_append_with_version_id(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify --version-id is forwarded to append_examples."""
        mock_client.datasets.append_examples.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "ds-1", "name": "test"})
        )
        examples = [{"q": "hello"}]
        result = cli_runner.invoke(
            app,
            [
                "append",
                "ds-1",
                "--json",
                json.dumps(examples),
                "--version-id",
                "v2",
            ],
        )
        assert result.exit_code == 0
        mock_client.datasets.append_examples.assert_called_once_with(
            dataset="ds-1",
            space=None,
            dataset_version_id="v2",
            examples=examples,
        )

    def test_append_requires_exactly_one_input(
        self,
        cli_runner: CliRunner,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """Neither or both inputs should fail."""
        result_none = cli_runner.invoke(app, ["append", "ds-1"])
        assert result_none.exit_code != 0

        csv_file = tmp_path / "data.csv"
        csv_file.write_text("a,b\n1,2\n")
        result_both = cli_runner.invoke(
            app,
            ["append", "ds-1", "--json", '[{"a":1}]', "--file", str(csv_file)],
        )
        assert result_both.exit_code != 0

    def test_append_rejects_bad_json(
        self,
        cli_runner: CliRunner,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Malformed JSON and non-array JSON both fail."""
        result_bad = cli_runner.invoke(
            app, ["append", "ds-1", "--json", "not json"]
        )
        assert result_bad.exit_code != 0
        assert "Invalid JSON" in result_bad.output

        result_obj = cli_runner.invoke(
            app, ["append", "ds-1", "--json", '{"a": 1}']
        )
        assert result_obj.exit_code != 0
        assert "JSON array" in result_obj.output

    def test_append_with_stdin_dash(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify '--file -' reads JSON from stdin."""
        mock_client.datasets.append_examples.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "ds-1", "name": "test"})
        )
        stdin_data = '[{"question": "What is 2+2?", "answer": "4"}]'
        result = cli_runner.invoke(
            app,
            ["append", "ds-1", "--file", "-"],
            input=stdin_data,
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.datasets.append_examples.call_args[1]
        assert call_kwargs["examples"][0]["question"] == "What is 2+2?"


class TestUpdateExamplesDataset:
    """Tests for the 'ax datasets update-examples' command."""

    def test_update_with_json_string(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify update-examples forwards inline JSON to the SDK."""
        mock_client.datasets.update_examples.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "ds-1", "name": "test"})
        )
        examples = [{"id": "ex-1", "answer": "4"}]
        result = cli_runner.invoke(
            app,
            ["update-examples", "ds-1", "--json", json.dumps(examples)],
        )
        assert result.exit_code == 0
        mock_client.datasets.update_examples.assert_called_once_with(
            dataset="ds-1",
            space=None,
            dataset_version_id="",
            examples=examples,
            new_version=None,
        )

    def test_update_with_file(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """Verify update-examples reads a CSV file and forwards parsed examples."""
        mock_client.datasets.update_examples.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "ds-1", "name": "test"})
        )
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("id,answer\nex-1,4\n")

        result = cli_runner.invoke(
            app,
            ["update-examples", "ds-1", "--file", str(csv_file)],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.datasets.update_examples.call_args.kwargs
        assert call_kwargs["dataset"] == "ds-1"
        assert call_kwargs["examples"][0]["id"] == "ex-1"
        assert call_kwargs["examples"][0]["answer"] == 4

    def test_update_with_version_and_new_version(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify --version-id and --new-version are forwarded."""
        mock_client.datasets.update_examples.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "ds-1", "name": "test"})
        )
        examples = [{"id": "ex-1", "q": "hello"}]
        result = cli_runner.invoke(
            app,
            [
                "update-examples",
                "ds-1",
                "--json",
                json.dumps(examples),
                "--version-id",
                "v2",
                "--new-version",
                "snapshot",
            ],
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.datasets.update_examples.call_args.kwargs
        assert call_kwargs["dataset_version_id"] == "v2"
        assert call_kwargs["new_version"] == "snapshot"

    def test_update_requires_exactly_one_input(
        self,
        cli_runner: CliRunner,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """Neither or both inputs should fail."""
        result_none = cli_runner.invoke(app, ["update-examples", "ds-1"])
        assert result_none.exit_code != 0

        csv_file = tmp_path / "data.csv"
        csv_file.write_text("id,b\nex-1,2\n")
        result_both = cli_runner.invoke(
            app,
            [
                "update-examples",
                "ds-1",
                "--json",
                '[{"id":"ex-1"}]',
                "--file",
                str(csv_file),
            ],
        )
        assert result_both.exit_code != 0

    def test_update_with_stdin_dash(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify '--file -' reads JSON from stdin."""
        mock_client.datasets.update_examples.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "ds-1", "name": "test"})
        )
        stdin_data = '[{"id": "ex-1", "answer": "4"}]'
        result = cli_runner.invoke(
            app,
            ["update-examples", "ds-1", "--file", "-"],
            input=stdin_data,
        )
        assert result.exit_code == 0
        call_kwargs = mock_client.datasets.update_examples.call_args.kwargs
        assert call_kwargs["examples"][0]["id"] == "ex-1"


class TestDeleteDataset:
    """Tests for the 'ax datasets delete' command."""

    def test_delete_force_skips_confirmation(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--force bypasses the prompt and deletes the dataset."""
        result = cli_runner.invoke(app, ["delete", "ds-1", "--force"])
        assert result.exit_code == 0
        mock_client.datasets.delete.assert_called_once_with(
            dataset="ds-1", space=None
        )

    def test_delete_confirms_yes_calls_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Confirming the prompt proceeds with deletion."""
        result = cli_runner.invoke(app, ["delete", "ds-1"], input="y\n")
        assert result.exit_code == 0
        mock_client.datasets.delete.assert_called_once_with(
            dataset="ds-1", space=None
        )

    def test_delete_declines_does_not_call_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Declining the confirmation leaves the dataset untouched."""
        result = cli_runner.invoke(app, ["delete", "ds-1"], input="n\n")
        assert result.exit_code == 0
        mock_client.datasets.delete.assert_not_called()

    def test_delete_with_space(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--space is forwarded when deleting by name."""
        result = cli_runner.invoke(
            app,
            ["delete", "my-dataset", "--force", "--space", "space-abc"],
        )
        assert result.exit_code == 0
        mock_client.datasets.delete.assert_called_once_with(
            dataset="my-dataset", space="space-abc"
        )

    def test_delete_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """API failure results in a non-zero exit code."""
        mock_client.datasets.delete.side_effect = Exception("not found")
        result = cli_runner.invoke(app, ["delete", "ds-1", "--force"])
        assert result.exit_code != 0


class TestUpdateDataset:
    """Tests for the 'ax datasets update' command."""

    def test_update_calls_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify update forwards name_or_id and --name to the SDK."""
        mock_client.datasets.update.return_value = MagicMock(
            model_dump=MagicMock(
                return_value={"id": "ds-1", "name": "new-name"}
            )
        )
        result = cli_runner.invoke(
            app, ["update", "ds-1", "--name", "new-name"]
        )
        assert result.exit_code == 0
        mock_client.datasets.update.assert_called_once_with(
            dataset="ds-1", space=None, name="new-name"
        )

    def test_update_with_space(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify --space is forwarded when updating by name."""
        mock_client.datasets.update.return_value = MagicMock(
            model_dump=MagicMock(
                return_value={"id": "ds-1", "name": "new-name"}
            )
        )
        result = cli_runner.invoke(
            app,
            [
                "update",
                "my-dataset",
                "--name",
                "new-name",
                "--space",
                "space-abc",
            ],
        )
        assert result.exit_code == 0
        mock_client.datasets.update.assert_called_once_with(
            dataset="my-dataset", space="space-abc", name="new-name"
        )

    def test_update_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """API failure results in a non-zero exit code."""
        mock_client.datasets.update.side_effect = Exception("not found")
        result = cli_runner.invoke(
            app, ["update", "ds-1", "--name", "new-name"]
        )
        assert result.exit_code != 0


class TestValidateExamplesStructure:
    """Tests for the _validate_examples_structure function."""

    def test_valid_examples_accepted(self) -> None:
        """Well-formed examples should pass without error."""
        _validate_examples_structure([{"question": "What?", "answer": "That."}])
        _validate_examples_structure(
            [{"data": {"nested": True}, "tags": ["a", "b"]}]
        )

    @pytest.mark.parametrize(
        "examples,match",
        [
            ([], "empty"),
            ([{}], "index 0"),
            (["not a dict"], "not a JSON object"),
        ],
    )
    def test_structural_errors_rejected(
        self, examples: list, match: str
    ) -> None:
        """Empty, non-dict, and empty-dict examples should raise."""
        with pytest.raises(Exception, match=match):
            _validate_examples_structure(examples)


# ---------------------------------------------------------------------------
# ax datasets annotate-examples
# ---------------------------------------------------------------------------

_ANNOTATIONS_JSON = (
    '[{"record_id":"ex-1","values":[{"name":"quality","score":0.9}]}]'
)


class TestAnnotateDatasetExamples:
    """Tests for the 'ax datasets annotate-examples' command."""

    def test_annotate_command_registered(self) -> None:
        """Verify 'annotate-examples' is registered as a subcommand."""
        names = [cmd.name for cmd in app.registered_commands]
        assert "annotate-examples" in names
        assert "annotate" not in names

    def test_annotate_with_stdin_calls_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--file - reads annotations from stdin and calls annotate_examples."""
        mock_client.datasets.annotate_examples.return_value = None

        result = cli_runner.invoke(
            app,
            ["annotate-examples", "my-dataset", "--file", "-"],
            input=_ANNOTATIONS_JSON,
        )
        assert result.exit_code == 0, result.output
        mock_client.datasets.annotate_examples.assert_called_once()
        call_kwargs = mock_client.datasets.annotate_examples.call_args.kwargs
        assert call_kwargs["dataset"] == "my-dataset"
        assert len(call_kwargs["annotations"]) == 1
        assert call_kwargs["annotations"][0].record_id == "ex-1"

    def test_annotate_with_file_calls_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """--file with a valid JSON file calls client.datasets.annotate_examples."""
        mock_client.datasets.annotate_examples.return_value = None
        json_file = tmp_path / "annotations.json"
        json_file.write_text(_ANNOTATIONS_JSON)

        result = cli_runner.invoke(
            app,
            ["annotate-examples", "my-dataset", "--file", str(json_file)],
        )
        assert result.exit_code == 0, result.output
        mock_client.datasets.annotate_examples.assert_called_once()

    def test_annotate_with_space(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--space is forwarded to the SDK."""
        mock_client.datasets.annotate_examples.return_value = None

        result = cli_runner.invoke(
            app,
            [
                "annotate-examples",
                "my-dataset",
                "--file",
                "-",
                "--space",
                "my-space",
            ],
            input=_ANNOTATIONS_JSON,
        )
        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.datasets.annotate_examples.call_args.kwargs
        assert call_kwargs["space"] == "my-space"

    def test_annotate_requires_file(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Providing no --file results in a non-zero exit."""
        result = cli_runner.invoke(app, ["annotate-examples", "my-dataset"])
        assert result.exit_code != 0

    def test_annotate_sdk_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """An SDK error results in a non-zero exit code."""
        mock_client.datasets.annotate_examples.side_effect = RuntimeError(
            "API error"
        )
        json_file = tmp_path / "annotations.json"
        json_file.write_text(_ANNOTATIONS_JSON)

        result = cli_runner.invoke(
            app,
            ["annotate-examples", "my-dataset", "--file", str(json_file)],
        )
        assert result.exit_code != 0

    def test_annotate_success_message(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """A success message is shown after annotating."""
        mock_client.datasets.annotate_examples.return_value = None

        result = cli_runner.invoke(
            app,
            ["annotate-examples", "my-dataset", "--file", "-"],
            input=_ANNOTATIONS_JSON,
        )
        assert result.exit_code == 0, result.output
        assert "example" in result.output.lower()


class TestDeleteDatasetExamples:
    """Tests for the 'ax datasets delete-examples' command."""

    def test_delete_examples_force_calls_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--example-ids forwards ids/version to the SDK and skips prompt."""
        mock_client.datasets.delete_examples.return_value = MagicMock(
            model_dump=MagicMock(
                return_value={
                    "completed": True,
                    "deleted_example_ids": ["a", "b"],
                    "not_deleted_example_ids": [],
                }
            )
        )
        result = cli_runner.invoke(
            app,
            [
                "delete-examples",
                "ds-1",
                "--version-id",
                "v1",
                "--example-ids",
                '["a", "b"]',
                "--force",
                "--output",
                "json",
            ],
        )
        assert result.exit_code == 0, result.output
        mock_client.datasets.delete_examples.assert_called_once_with(
            dataset="ds-1",
            space=None,
            dataset_version_id="v1",
            examples=["a", "b"],
        )

    def test_delete_examples_confirms_yes_calls_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Confirming the prompt proceeds with deletion."""
        mock_client.datasets.delete_examples.return_value = MagicMock(
            model_dump=MagicMock(
                return_value={
                    "completed": True,
                    "deleted_example_ids": ["a", "b"],
                    "not_deleted_example_ids": [],
                }
            )
        )
        result = cli_runner.invoke(
            app,
            [
                "delete-examples",
                "ds-1",
                "--version-id",
                "v1",
                "--example-ids",
                '["a"]',
                "--output",
                "json",
            ],
            input="y\n",
        )
        assert result.exit_code == 0, result.output
        mock_client.datasets.delete_examples.assert_called_once_with(
            dataset="ds-1",
            space=None,
            dataset_version_id="v1",
            examples=["a"],
        )

    def test_delete_examples_declines_does_not_call_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Declining the confirmation leaves the examples untouched."""
        result = cli_runner.invoke(
            app,
            [
                "delete-examples",
                "ds-1",
                "--version-id",
                "v1",
                "--example-ids",
                '["a"]',
            ],
            input="n\n",
        )
        assert result.exit_code == 0
        mock_client.datasets.delete_examples.assert_not_called()

    def test_delete_examples_with_space(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--space is forwarded when deleting by dataset name."""
        mock_client.datasets.delete_examples.return_value = MagicMock(
            model_dump=MagicMock(
                return_value={
                    "completed": True,
                    "deleted_example_ids": ["a", "b"],
                    "not_deleted_example_ids": [],
                }
            )
        )
        result = cli_runner.invoke(
            app,
            [
                "delete-examples",
                "my-dataset",
                "--version-id",
                "v1",
                "--example-ids",
                '["a"]',
                "--force",
                "--space",
                "space-abc",
                "--output",
                "json",
            ],
        )
        assert result.exit_code == 0, result.output
        mock_client.datasets.delete_examples.assert_called_once_with(
            dataset="my-dataset",
            space="space-abc",
            dataset_version_id="v1",
            examples=["a"],
        )

    def test_delete_examples_missing_input_errors(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Omitting --example-ids fails before any SDK call."""
        result = cli_runner.invoke(
            app,
            ["delete-examples", "ds-1", "--version-id", "v1", "--force"],
        )
        assert result.exit_code != 0
        mock_client.datasets.delete_examples.assert_not_called()

    def test_delete_examples_invalid_json_errors(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Malformed --example-ids JSON fails before any SDK call."""
        result = cli_runner.invoke(
            app,
            [
                "delete-examples",
                "ds-1",
                "--version-id",
                "v1",
                "--example-ids",
                "not-json",
                "--force",
            ],
        )
        assert result.exit_code != 0
        mock_client.datasets.delete_examples.assert_not_called()

    def test_delete_examples_api_error_exits_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """An SDK error results in a non-zero exit code."""
        mock_client.datasets.delete_examples.side_effect = Exception(
            "not found"
        )
        result = cli_runner.invoke(
            app,
            [
                "delete-examples",
                "ds-1",
                "--version-id",
                "v1",
                "--example-ids",
                '["a"]',
                "--force",
            ],
        )
        assert result.exit_code != 0


def _api_error(status: int):
    """Build an SDK ApiException carrying an HTTP status."""
    from arize import ApiException

    exc = ApiException(status=status, reason="test")
    exc.headers = None
    return exc


def _append_response(ids: list[str] | None = None, version: str = "v1"):
    """Build a stand-in for the SDK's append_examples response."""
    return MagicMock(
        id="ds-1",
        dataset_version_id=version,
        example_ids=list(ids or []),
        model_dump=MagicMock(return_value={"id": "ds-1", "name": "test"}),
    )


def _examples(count: int) -> list[dict[str, object]]:
    """Build `count` distinct examples."""
    return [{"q": f"question-{n}", "a": f"answer-{n}"} for n in range(count)]


@pytest.fixture
def _no_sleep():
    """Skip backoff waits so retry tests stay fast."""
    with patch("ax.utils.batching.time.sleep") as sleep:
        yield sleep


class TestAppendBatching:
    """Tests for batched uploads in 'ax datasets append'."""

    def test_large_payload_is_split_into_batches(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """120 examples go out as 50 + 50 + 20 instead of one oversized call."""
        mock_client.datasets.append_examples.return_value = _append_response()
        examples = _examples(120)

        result = cli_runner.invoke(
            app, ["append", "ds-1", "--json", json.dumps(examples)]
        )

        assert result.exit_code == 0
        sizes = [
            len(call.kwargs["examples"])
            for call in mock_client.datasets.append_examples.call_args_list
        ]
        assert sizes == [50, 50, 20]

    def test_every_example_is_sent_exactly_once(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Splitting must not drop, duplicate, or reorder rows."""
        mock_client.datasets.append_examples.return_value = _append_response()
        examples = _examples(120)

        result = cli_runner.invoke(
            app, ["append", "ds-1", "--json", json.dumps(examples)]
        )

        assert result.exit_code == 0
        sent = [
            row
            for call in mock_client.datasets.append_examples.call_args_list
            for row in call.kwargs["examples"]
        ]
        assert sent == examples

    def test_custom_batch_size_is_honored(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--batch-size controls how many examples go per call."""
        mock_client.datasets.append_examples.return_value = _append_response()

        result = cli_runner.invoke(
            app,
            [
                "append",
                "ds-1",
                "--json",
                json.dumps(_examples(25)),
                "--batch-size",
                "10",
            ],
        )

        assert result.exit_code == 0
        sizes = [
            len(call.kwargs["examples"])
            for call in mock_client.datasets.append_examples.call_args_list
        ]
        assert sizes == [10, 10, 5]

    def test_batch_size_zero_sends_one_call(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--batch-size 0 is the escape hatch back to a single request."""
        mock_client.datasets.append_examples.return_value = _append_response()
        examples = _examples(120)

        result = cli_runner.invoke(
            app,
            [
                "append",
                "ds-1",
                "--json",
                json.dumps(examples),
                "--batch-size",
                "0",
            ],
        )

        assert result.exit_code == 0
        mock_client.datasets.append_examples.assert_called_once()
        assert (
            mock_client.datasets.append_examples.call_args.kwargs["examples"]
            == examples
        )

    def test_later_batches_pin_to_the_resolved_dataset_and_version(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """All batches land in one version, addressed by ID after the first."""
        mock_client.datasets.append_examples.return_value = _append_response(
            version="ver-7"
        )

        result = cli_runner.invoke(
            app,
            [
                "append",
                "my-dataset",
                "--space",
                "sp-1",
                "--json",
                json.dumps(_examples(120)),
            ],
        )

        assert result.exit_code == 0
        calls = mock_client.datasets.append_examples.call_args_list
        assert calls[0].kwargs["dataset"] == "my-dataset"
        assert calls[0].kwargs["dataset_version_id"] == ""
        for call in calls[1:]:
            assert call.kwargs["dataset"] == "ds-1"
            assert call.kwargs["dataset_version_id"] == "ver-7"

    def test_explicit_version_is_used_for_every_batch(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--version-id still targets the version the user asked for."""
        mock_client.datasets.append_examples.return_value = _append_response(
            version="v2"
        )

        result = cli_runner.invoke(
            app,
            [
                "append",
                "ds-1",
                "--json",
                json.dumps(_examples(120)),
                "--version-id",
                "v2",
            ],
        )

        assert result.exit_code == 0
        versions = {
            call.kwargs["dataset_version_id"]
            for call in mock_client.datasets.append_examples.call_args_list
        }
        assert versions == {"v2"}

    def test_rate_limited_batch_is_retried(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        _no_sleep: MagicMock,
    ) -> None:
        """A 429 is waited out rather than surfaced to the user."""
        mock_client.datasets.append_examples.side_effect = [
            _api_error(429),
            _append_response(),
        ]

        result = cli_runner.invoke(
            app, ["append", "ds-1", "--json", json.dumps(_examples(3))]
        )

        assert result.exit_code == 0
        assert mock_client.datasets.append_examples.call_count == 2
        assert _no_sleep.call_count == 1

    def test_transient_server_error_is_retried(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        _no_sleep: MagicMock,
    ) -> None:
        """A 503 gets another go before the command gives up."""
        mock_client.datasets.append_examples.side_effect = [
            _api_error(503),
            _append_response(),
        ]

        result = cli_runner.invoke(
            app, ["append", "ds-1", "--json", json.dumps(_examples(3))]
        )

        assert result.exit_code == 0
        assert mock_client.datasets.append_examples.call_count == 2

    def test_rejected_payload_is_not_retried(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        _no_sleep: MagicMock,
    ) -> None:
        """A 400 means the payload is wrong; resending it only wastes time."""
        mock_client.datasets.append_examples.side_effect = _api_error(400)

        result = cli_runner.invoke(
            app, ["append", "ds-1", "--json", json.dumps(_examples(3))]
        )

        assert result.exit_code != 0
        assert mock_client.datasets.append_examples.call_count == 1

    def test_exhausted_retries_exit_nonzero(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        _no_sleep: MagicMock,
    ) -> None:
        """Persistent rate limiting fails the command instead of hanging."""
        mock_client.datasets.append_examples.side_effect = _api_error(429)

        result = cli_runner.invoke(
            app,
            [
                "append",
                "ds-1",
                "--json",
                json.dumps(_examples(3)),
                "--max-retries",
                "2",
            ],
        )

        assert result.exit_code != 0
        assert mock_client.datasets.append_examples.call_count == 3

    def test_partial_failure_reports_what_landed(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        _no_sleep: MagicMock,
    ) -> None:
        """A mid-upload failure must say how much got through, and exit non-zero."""
        mock_client.datasets.append_examples.side_effect = [
            _append_response(),
            _api_error(500),
        ]

        result = cli_runner.invoke(
            app,
            [
                "append",
                "ds-1",
                "--json",
                json.dumps(_examples(120)),
                "--max-retries",
                "0",
            ],
        )

        assert result.exit_code != 0
        assert "50 of 120" in result.output

    def test_example_ids_from_every_batch_are_reported(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """The printed response covers the whole upload, not just its last batch."""
        mock_client.datasets.append_examples.side_effect = [
            _append_response(["a", "b"]),
            _append_response(["c", "d"]),
            _append_response(["e"]),
        ]

        with patch("ax.commands.datasets.output_data") as output:
            result = cli_runner.invoke(
                app,
                [
                    "append",
                    "ds-1",
                    "--json",
                    json.dumps(_examples(25)),
                    "--batch-size",
                    "10",
                ],
            )

        assert result.exit_code == 0
        assert output.call_args.args[0].example_ids == ["a", "b", "c", "d", "e"]

    def test_batching_flags_are_documented(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Both knobs show up in --help."""
        result = cli_runner.invoke(app, ["append", "--help"])
        assert "--batch-size" in result.output
        assert "--max-retries" in result.output


class TestCreateBatching:
    """Tests for batched uploads in 'ax datasets create'."""

    def test_small_payload_is_created_in_one_call(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Payloads that fit stay on the original single-request path."""
        mock_client.datasets.create.return_value = MagicMock(
            id="ds-1",
            model_dump=MagicMock(return_value={"id": "ds-1", "name": "test"}),
        )

        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "test",
                "--space",
                "sp-1",
                "--json",
                json.dumps(_examples(10)),
            ],
        )

        assert result.exit_code == 0
        mock_client.datasets.create.assert_called_once()
        mock_client.datasets.append_examples.assert_not_called()

    def test_large_payload_creates_then_appends_the_rest(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """The first batch creates the dataset; the rest are appended to it."""
        mock_client.datasets.create.return_value = MagicMock(
            id="ds-new",
            model_dump=MagicMock(return_value={"id": "ds-new", "name": "test"}),
        )
        mock_client.datasets.append_examples.return_value = _append_response()
        examples = _examples(120)

        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "test",
                "--space",
                "sp-1",
                "--json",
                json.dumps(examples),
            ],
        )

        assert result.exit_code == 0
        assert (
            mock_client.datasets.create.call_args.kwargs["examples"]
            == examples[:50]
        )
        appended = [
            row
            for call in mock_client.datasets.append_examples.call_args_list
            for row in call.kwargs["examples"]
        ]
        assert appended == examples[50:]
        assert (
            mock_client.datasets.append_examples.call_args_list[0].kwargs[
                "dataset"
            ]
            == "ds-new"
        )

    def test_batch_size_zero_creates_in_one_call(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--batch-size 0 restores the original whole-payload behaviour."""
        mock_client.datasets.create.return_value = MagicMock(
            id="ds-1",
            model_dump=MagicMock(return_value={"id": "ds-1", "name": "test"}),
        )
        examples = _examples(120)

        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "test",
                "--space",
                "sp-1",
                "--json",
                json.dumps(examples),
                "--batch-size",
                "0",
            ],
        )

        assert result.exit_code == 0
        assert (
            mock_client.datasets.create.call_args.kwargs["examples"] == examples
        )
        mock_client.datasets.append_examples.assert_not_called()

    def test_file_payload_is_batched(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """A large CSV is split the same way inline JSON is."""
        mock_client.datasets.create.return_value = MagicMock(
            id="ds-new",
            model_dump=MagicMock(return_value={"id": "ds-new", "name": "test"}),
        )
        mock_client.datasets.append_examples.return_value = _append_response()
        csv_file = tmp_path / "big.csv"
        csv_file.write_text(
            "question,answer\n" + "".join(f"q{n},a{n}\n" for n in range(120))
        )

        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "test",
                "--space",
                "sp-1",
                "--file",
                str(csv_file),
            ],
        )

        assert result.exit_code == 0
        assert (
            len(mock_client.datasets.create.call_args.kwargs["examples"]) == 50
        )
        assert mock_client.datasets.append_examples.call_count == 2

    def test_failed_append_points_at_the_created_dataset(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        _no_sleep: MagicMock,
    ) -> None:
        """A half-uploaded dataset must be resumable, not silently wrong."""
        mock_client.datasets.create.return_value = MagicMock(
            id="ds-new",
            model_dump=MagicMock(return_value={"id": "ds-new", "name": "test"}),
        )
        mock_client.datasets.append_examples.side_effect = _api_error(500)

        result = cli_runner.invoke(
            app,
            [
                "create",
                "--name",
                "test",
                "--space",
                "sp-1",
                "--json",
                json.dumps(_examples(120)),
                "--max-retries",
                "0",
            ],
        )

        assert result.exit_code != 0
        assert "ds-new" in result.output
        assert "50 of 120" in result.output
        assert "ax datasets append" in result.output

    def test_batching_flags_are_documented(
        self,
        cli_runner: CliRunner,
    ) -> None:
        """Both knobs show up in --help."""
        result = cli_runner.invoke(app, ["create", "--help"])
        assert "--batch-size" in result.output
        assert "--max-retries" in result.output
