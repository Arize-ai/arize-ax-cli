"""Tests for dataset CLI commands."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ax.commands.datasets import _validate_examples_structure, app


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
        """Verify export defaults to all=False (REST)."""
        response = MagicMock()
        response.examples = []
        mock_client.datasets.list_examples.return_value = response

        result = cli_runner.invoke(app, ["export", "ds-1", "--stdout"])
        assert result.exit_code == 0
        mock_client.datasets.list_examples.assert_called_once_with(
            dataset="ds-1",
            space=None,
            dataset_version_id=None,
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
            all=False,
        )

    def test_export_writes_file(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: object,
    ) -> None:
        """Verify export writes to disk when --stdout is not given."""
        response = MagicMock()
        response.examples = []
        mock_client.datasets.list_examples.return_value = response

        with patch("ax.commands.datasets.make_export_dir") as mock_dir:
            mock_dir.return_value = tmp_path  # type: ignore[assignment]
            with patch("ax.commands.datasets.write_json_array") as mock_write:
                mock_write.return_value = tmp_path / "examples.json"  # type: ignore[operator]
                result = cli_runner.invoke(
                    app,
                    ["export", "ds-1", "--output-dir", str(tmp_path)],
                )
                assert result.exit_code == 0
                mock_write.assert_called_once()


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
