"""Tests for evaluator CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from arize.evaluators.types import OptimizationDirection
from typer.testing import CliRunner

from ax.commands.evaluators import app


class TestEvaluatorCommands:
    """Verify evaluator subcommands are registered with the correct names."""

    def test_expected_commands_registered(self) -> None:
        """Check that all expected subcommands are present."""
        names = [cmd.name for cmd in app.registered_commands]
        for expected in (
            "list",
            "get",
            "create-template-evaluator",
            "create-code-evaluator",
            "update",
            "delete",
            "list-versions",
            "get-version",
            "create-template-evaluator-version",
            "create-code-evaluator-version",
        ):
            assert expected in names


class TestListEvaluators:
    """Tests for the 'ax evaluators list' command."""

    @pytest.mark.unit
    def test_calls_client_evaluators_list(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'list' with defaults and verify the SDK call."""
        mock_client.evaluators.list.return_value = MagicMock(
            model_dump=MagicMock(return_value={"evaluators": []})
        )

        result = cli_runner.invoke(app, ["list"])
        assert result.exit_code == 0
        mock_client.evaluators.list.assert_called_once_with(
            name=None,
            space=None,
            limit=15,
            cursor=None,
        )

    @pytest.mark.unit
    def test_calls_client_with_space_id(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'list' with --space and verify it is passed to SDK."""
        mock_client.evaluators.list.return_value = MagicMock(
            model_dump=MagicMock(return_value={"evaluators": []})
        )

        result = cli_runner.invoke(app, ["list", "--space", "space-1"])
        assert result.exit_code == 0
        mock_client.evaluators.list.assert_called_once_with(
            name=None,
            space="space-1",
            limit=15,
            cursor=None,
        )

    @pytest.mark.unit
    def test_list_name_filter_forwarded(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Verify --name filter is forwarded to the SDK."""
        mock_client.evaluators.list.return_value = MagicMock(
            model_dump=MagicMock(return_value={"evaluators": []})
        )

        result = cli_runner.invoke(app, ["list", "--name", "correctness"])
        assert result.exit_code == 0
        mock_client.evaluators.list.assert_called_once_with(
            name="correctness",
            space=None,
            limit=15,
            cursor=None,
        )


class TestGetEvaluator:
    """Tests for the 'ax evaluators get' command."""

    @pytest.mark.unit
    def test_calls_client_evaluators_get(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'get' and verify the SDK call with default latest version."""
        mock_client.evaluators.get.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "eval-1", "name": "test"})
        )

        result = cli_runner.invoke(app, ["get", "eval-1"])
        assert result.exit_code == 0
        mock_client.evaluators.get.assert_called_once_with(
            evaluator="eval-1",
            space=None,
            version_id=None,
        )

    @pytest.mark.unit
    def test_calls_client_with_version_id(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'get' with --version-id and verify it is passed to SDK."""
        mock_client.evaluators.get.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "eval-1"})
        )

        result = cli_runner.invoke(
            app, ["get", "eval-1", "--version-id", "v-42"]
        )
        assert result.exit_code == 0
        mock_client.evaluators.get.assert_called_once_with(
            evaluator="eval-1",
            space=None,
            version_id="v-42",
        )


class TestUpdateEvaluator:
    """Tests for the 'ax evaluators update' command."""

    @pytest.mark.unit
    def test_update_with_name(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'update' with --name and verify the SDK call."""
        mock_client.evaluators.update.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "eval-1", "name": "new"})
        )

        result = cli_runner.invoke(
            app, ["update", "eval-1", "--name", "new name"]
        )
        assert result.exit_code == 0
        mock_client.evaluators.update.assert_called_once_with(
            evaluator="eval-1",
            space=None,
            name="new name",
            description=None,
        )

    @pytest.mark.unit
    def test_update_with_description(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'update' with --description and verify the SDK call."""
        mock_client.evaluators.update.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "eval-1"})
        )

        result = cli_runner.invoke(
            app, ["update", "eval-1", "--description", "new desc"]
        )
        assert result.exit_code == 0
        mock_client.evaluators.update.assert_called_once_with(
            evaluator="eval-1",
            space=None,
            name=None,
            description="new desc",
        )

    @pytest.mark.unit
    def test_update_requires_name_or_description(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """'update' without --name or --description should fail."""
        result = cli_runner.invoke(app, ["update", "eval-1"])
        assert result.exit_code != 0
        assert "At least one of" in result.output
        mock_client.evaluators.update.assert_not_called()


class TestDeleteEvaluator:
    """Tests for the 'ax evaluators delete' command."""

    @pytest.mark.unit
    def test_delete_with_force_skips_confirmation(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'delete --force' and verify it skips confirmation."""
        result = cli_runner.invoke(app, ["delete", "eval-1", "--force"])
        assert result.exit_code == 0
        mock_client.evaluators.delete.assert_called_once_with(
            evaluator="eval-1", space=None
        )

    @pytest.mark.unit
    def test_delete_prompts_confirmation(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'delete' without --force; confirm 'y' to proceed."""
        result = cli_runner.invoke(app, ["delete", "eval-1"], input="y\n")
        assert result.exit_code == 0
        mock_client.evaluators.delete.assert_called_once_with(
            evaluator="eval-1", space=None
        )

    @pytest.mark.unit
    def test_delete_aborts_on_no(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'delete' without --force; answer 'n' to abort."""
        result = cli_runner.invoke(app, ["delete", "eval-1"], input="n\n")
        assert result.exit_code == 0
        mock_client.evaluators.delete.assert_not_called()


class TestListVersions:
    """Tests for the 'ax evaluators list-versions' command."""

    @pytest.mark.unit
    def test_calls_client_list_versions(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'list-versions' and verify the SDK call."""
        mock_client.evaluators.list_versions.return_value = MagicMock(
            model_dump=MagicMock(return_value={"versions": []})
        )

        result = cli_runner.invoke(app, ["list-versions", "eval-1"])
        assert result.exit_code == 0
        mock_client.evaluators.list_versions.assert_called_once_with(
            evaluator="eval-1",
            space=None,
            limit=15,
            cursor=None,
        )


class TestGetVersion:
    """Tests for the 'ax evaluators get-version' command."""

    @pytest.mark.unit
    def test_calls_client_get_version(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'get-version' and verify the SDK call."""
        mock_client.evaluators.get_version.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "v-1"})
        )

        result = cli_runner.invoke(app, ["get-version", "v-1"])
        assert result.exit_code == 0
        mock_client.evaluators.get_version.assert_called_once_with(
            version_id="v-1"
        )


class TestTemplateCreateEvaluator:
    """Tests for the 'ax evaluators template-create' command."""

    @pytest.mark.unit
    def test_calls_client_create_template(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'template-create' with required args and verify SDK call."""
        mock_client.evaluators.create_template_evaluator.return_value = (
            MagicMock(model_dump=MagicMock(return_value={"id": "eval-new"}))
        )

        with patch(
            "ax.commands.evaluators._build_template_config"
        ) as mock_build:
            mock_template_config = MagicMock()
            mock_build.return_value = mock_template_config

            result = cli_runner.invoke(
                app,
                [
                    "create-template-evaluator",
                    "--name",
                    "My Evaluator",
                    "--space",
                    "space-1",
                    "--commit-message",
                    "Initial version",
                    "--template-name",
                    "relevance",
                    "--template",
                    "Is it relevant? {{response}}",
                    "--ai-integration-id",
                    "integ-1",
                    "--model-name",
                    "gpt-4o",
                    "--include-explanations",
                    "--use-function-calling",
                ],
            )

        assert result.exit_code == 0
        mock_build.assert_called_once_with(
            template_name="relevance",
            template="Is it relevant? {{response}}",
            ai_integration_id="integ-1",
            model_name="gpt-4o",
            include_explanations=True,
            use_function_calling=True,
            invocation_params_str="{}",
            provider_params_str="{}",
            classification_choices_str=None,
            direction=None,
            data_granularity=None,
        )
        mock_client.evaluators.create_template_evaluator.assert_called_once_with(
            name="My Evaluator",
            space="space-1",
            commit_message="Initial version",
            template_config=mock_template_config,
            description=None,
        )

    @pytest.mark.unit
    def test_template_create_with_description(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'template-create' with --description and verify it is passed to SDK."""
        mock_client.evaluators.create_template_evaluator.return_value = (
            MagicMock(model_dump=MagicMock(return_value={"id": "eval-new"}))
        )

        with patch("ax.commands.evaluators._build_template_config"):
            result = cli_runner.invoke(
                app,
                [
                    "create-template-evaluator",
                    "--name",
                    "My Evaluator",
                    "--space",
                    "space-1",
                    "--commit-message",
                    "Initial version",
                    "--template-name",
                    "relevance",
                    "--template",
                    "template",
                    "--ai-integration-id",
                    "integ-1",
                    "--model-name",
                    "gpt-4o",
                    "--description",
                    "Evaluates relevance",
                ],
            )

        assert result.exit_code == 0
        mock_client.evaluators.create_template_evaluator.assert_called_once()
        _, kwargs = mock_client.evaluators.create_template_evaluator.call_args
        assert kwargs["description"] == "Evaluates relevance"

    @pytest.mark.unit
    def test_template_create_passes_classification_choices_to_build(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--classification-choices and related flags reach _build_template_config."""
        mock_client.evaluators.create_template_evaluator.return_value = (
            MagicMock(model_dump=MagicMock(return_value={"id": "eval-new"}))
        )

        with patch(
            "ax.commands.evaluators._build_template_config"
        ) as mock_build:
            mock_build.return_value = MagicMock()
            result = cli_runner.invoke(
                app,
                [
                    "create-template-evaluator",
                    "--name",
                    "My Evaluator",
                    "--space",
                    "space-1",
                    "--commit-message",
                    "Initial version",
                    "--template-name",
                    "relevance",
                    "--template",
                    "t",
                    "--ai-integration-id",
                    "integ-1",
                    "--model-name",
                    "gpt-4o",
                    "--classification-choices",
                    '{"relevant":1,"irrelevant":0}',
                    "--direction",
                    "maximize",
                    "--data-granularity",
                    "span",
                ],
            )

        assert result.exit_code == 0
        mock_build.assert_called_once_with(
            template_name="relevance",
            template="t",
            ai_integration_id="integ-1",
            model_name="gpt-4o",
            include_explanations=False,
            use_function_calling=False,
            invocation_params_str="{}",
            provider_params_str="{}",
            classification_choices_str='{"relevant":1,"irrelevant":0}',
            direction="maximize",
            data_granularity="span",
        )


class TestTemplateCreateVersion:
    """Tests for the 'ax evaluators template-create-version' command."""

    @pytest.mark.unit
    def test_calls_client_create_template_version(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'template-create-version' with required args and verify SDK call."""
        mock_client.evaluators.create_template_version.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "v-2"})
        )

        with patch(
            "ax.commands.evaluators._build_template_config"
        ) as mock_build:
            mock_template_config = MagicMock()
            mock_build.return_value = mock_template_config

            result = cli_runner.invoke(
                app,
                [
                    "create-template-evaluator-version",
                    "eval-1",
                    "--commit-message",
                    "v2 update",
                    "--template-name",
                    "relevance",
                    "--template",
                    "Is it relevant? {{response}}",
                    "--ai-integration-id",
                    "integ-1",
                    "--model-name",
                    "gpt-4o",
                    "--include-explanations",
                    "--use-function-calling",
                ],
            )

        assert result.exit_code == 0
        mock_build.assert_called_once_with(
            template_name="relevance",
            template="Is it relevant? {{response}}",
            ai_integration_id="integ-1",
            model_name="gpt-4o",
            include_explanations=True,
            use_function_calling=True,
            invocation_params_str="{}",
            provider_params_str="{}",
            classification_choices_str=None,
            direction=None,
            data_granularity=None,
        )
        mock_client.evaluators.create_template_version.assert_called_once_with(
            evaluator="eval-1",
            space=None,
            commit_message="v2 update",
            template_config=mock_template_config,
        )

    @pytest.mark.unit
    def test_template_create_version_passes_classification_choices(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """New template flags are forwarded on template-create-version."""
        mock_client.evaluators.create_template_version.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "v-2"})
        )

        with patch(
            "ax.commands.evaluators._build_template_config"
        ) as mock_build:
            mock_build.return_value = MagicMock()
            result = cli_runner.invoke(
                app,
                [
                    "create-template-evaluator-version",
                    "eval-1",
                    "--commit-message",
                    "v2",
                    "--template-name",
                    "col",
                    "--template",
                    "t",
                    "--ai-integration-id",
                    "integ-1",
                    "--model-name",
                    "gpt-4o",
                    "--classification-choices",
                    '{"yes":1,"no":0}',
                    "--data-granularity",
                    "session",
                ],
            )

        assert result.exit_code == 0
        mock_build.assert_called_once_with(
            template_name="col",
            template="t",
            ai_integration_id="integ-1",
            model_name="gpt-4o",
            include_explanations=False,
            use_function_calling=False,
            invocation_params_str="{}",
            provider_params_str="{}",
            classification_choices_str='{"yes":1,"no":0}',
            direction=None,
            data_granularity="session",
        )


class TestBuildTemplateConfig:
    """Tests for the _build_template_config helper."""

    @pytest.mark.unit
    def test_invalid_invocation_params_raises_bad_parameter(self) -> None:
        """_build_template_config raises BadParameter for invalid JSON."""
        import typer

        from ax.commands.evaluators import _build_template_config

        with pytest.raises(typer.BadParameter):
            _build_template_config(
                template_name="test",
                template="template",
                ai_integration_id="integ-1",
                model_name="gpt-4o",
                include_explanations=True,
                use_function_calling=True,
                invocation_params_str="{bad json}",
                provider_params_str="{}",
                classification_choices_str=None,
                direction=None,
                data_granularity=None,
            )

    @pytest.mark.unit
    def test_invalid_provider_params_raises_bad_parameter(self) -> None:
        """_build_template_config raises BadParameter for invalid provider JSON."""
        import typer

        from ax.commands.evaluators import _build_template_config

        with pytest.raises(typer.BadParameter):
            _build_template_config(
                template_name="test",
                template="template",
                ai_integration_id="integ-1",
                model_name="gpt-4o",
                include_explanations=True,
                use_function_calling=True,
                invocation_params_str="{}",
                provider_params_str="{bad json}",
                classification_choices_str=None,
                direction=None,
                data_granularity=None,
            )

    @pytest.mark.unit
    def test_invocation_params_array_raises_usage_error(self) -> None:
        """_build_template_config raises UsageError when invocation params is a JSON array."""
        from ax.commands.evaluators import _build_template_config
        from ax.core.exceptions import UsageError

        with pytest.raises(
            UsageError, match="--invocation-params must be a JSON object"
        ):
            _build_template_config(
                template_name="test",
                template="template",
                ai_integration_id="integ-1",
                model_name="gpt-4o",
                include_explanations=True,
                use_function_calling=True,
                invocation_params_str="[]",
                provider_params_str="{}",
                classification_choices_str=None,
                direction=None,
                data_granularity=None,
            )

    @pytest.mark.unit
    def test_provider_params_array_raises_usage_error(self) -> None:
        """_build_template_config raises UsageError when provider params is a JSON array."""
        from ax.commands.evaluators import _build_template_config
        from ax.core.exceptions import UsageError

        with pytest.raises(
            UsageError, match="--provider-params must be a JSON object"
        ):
            _build_template_config(
                template_name="test",
                template="template",
                ai_integration_id="integ-1",
                model_name="gpt-4o",
                include_explanations=True,
                use_function_calling=True,
                invocation_params_str="{}",
                provider_params_str="[]",
                classification_choices_str=None,
                direction=None,
                data_granularity=None,
            )

    @pytest.mark.unit
    def test_classification_choices_applied_to_template_config(self) -> None:
        """Parsed classification choices, direction, and granularity are set."""
        from ax.commands.evaluators import _build_template_config

        cfg = _build_template_config(
            template_name="col",
            template="Hello {{x}}",
            ai_integration_id="integ-1",
            model_name="gpt-4o",
            include_explanations=False,
            use_function_calling=False,
            invocation_params_str="{}",
            provider_params_str="{}",
            classification_choices_str='{"relevant": 1, "irrelevant": 0}',
            direction=OptimizationDirection.MINIMIZE,
            data_granularity="trace",
        )
        assert cfg.classification_choices == {"relevant": 1, "irrelevant": 0}
        assert cfg.direction == OptimizationDirection.MINIMIZE
        assert cfg.data_granularity == "trace"

    @pytest.mark.unit
    def test_classification_choices_json_array_raises_usage_error(self) -> None:
        """classification-choices must be an object, not an array."""
        from ax.commands.evaluators import _build_template_config
        from ax.core.exceptions import UsageError

        with pytest.raises(
            UsageError, match="--classification-choices must be a JSON object"
        ):
            _build_template_config(
                template_name="test",
                template="template",
                ai_integration_id="integ-1",
                model_name="gpt-4o",
                include_explanations=True,
                use_function_calling=True,
                invocation_params_str="{}",
                provider_params_str="{}",
                classification_choices_str="[]",
                direction=None,
                data_granularity=None,
            )

    @pytest.mark.unit
    def test_invalid_direction_rejected_by_cli(self) -> None:
        """Invalid direction values are rejected by the CLI."""
        result = CliRunner().invoke(
            app,
            [
                "create-template-evaluator",
                "--name",
                "test",
                "--template-name",
                "col",
                "--template",
                "Hello",
                "--ai-integration-id",
                "integ-1",
                "--model-name",
                "gpt-4o",
                "--invocation-params",
                "{}",
                "--provider-params",
                "{}",
                "--direction",
                "sideways",
            ],
        )
        assert result.exit_code != 0

    @pytest.mark.unit
    def test_classification_choices_bool_value_raises_usage_error(self) -> None:
        """JSON booleans must not be used as numeric scores."""
        from ax.commands.evaluators import _build_template_config
        from ax.core.exceptions import UsageError

        with pytest.raises(
            UsageError,
            match="--classification-choices values must be numbers",
        ):
            _build_template_config(
                template_name="test",
                template="template",
                ai_integration_id="integ-1",
                model_name="gpt-4o",
                include_explanations=True,
                use_function_calling=True,
                invocation_params_str="{}",
                provider_params_str="{}",
                classification_choices_str='{"ok": true}',
                direction=None,
                data_granularity=None,
            )

    @pytest.mark.unit
    def test_direction_enum_values(self) -> None:
        """OptimizationDirection enum has the expected values."""
        assert OptimizationDirection.MAXIMIZE == "maximize"
        assert OptimizationDirection.MINIMIZE == "minimize"
        assert OptimizationDirection.NONE == "none"


class TestParseStaticParams:
    """Tests for the _parse_static_params helper."""

    @pytest.mark.unit
    def test_returns_none_when_omitted(self) -> None:
        """None input yields None (no static params)."""
        from ax.commands.evaluators import _parse_static_params

        assert _parse_static_params(None) is None
        assert _parse_static_params("") is None

    @pytest.mark.unit
    def test_parses_string_default_value(self) -> None:
        """Items with a string default_value parse into StaticParam."""
        from ax.commands.evaluators import _parse_static_params

        result = _parse_static_params(
            '[{"name": "pattern", "type": "REGEX", "default_value": "^yes"}]'
        )
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "pattern"
        assert result[0].type == "REGEX"

    @pytest.mark.unit
    def test_parses_array_default_value(self) -> None:
        """Items with a string-array default_value parse (STRING_ARRAY type)."""
        from ax.commands.evaluators import _parse_static_params

        result = _parse_static_params(
            '[{"name": "keywords", "type": "STRING_ARRAY", '
            '"default_value": ["a", "b"]}]'
        )
        assert result is not None
        assert result[0].type == "STRING_ARRAY"

    @pytest.mark.unit
    def test_non_list_raises(self) -> None:
        """Non-list input raises UsageError."""
        from ax.commands.evaluators import _parse_static_params
        from ax.core.exceptions import UsageError

        with pytest.raises(UsageError, match="JSON array"):
            _parse_static_params('{"name": "x"}')


class TestParseVariables:
    """Tests for the _parse_variables helper."""

    @pytest.mark.unit
    def test_valid_list_of_strings(self) -> None:
        """Valid JSON list of strings round-trips."""
        from ax.commands.evaluators import _parse_variables

        assert _parse_variables('["a", "b"]') == ["a", "b"]

    @pytest.mark.unit
    def test_non_list_raises(self) -> None:
        """Non-list JSON raises UsageError."""
        from ax.commands.evaluators import _parse_variables
        from ax.core.exceptions import UsageError

        with pytest.raises(UsageError, match="array of strings"):
            _parse_variables('{"a": 1}')

    @pytest.mark.unit
    def test_list_with_non_string_raises(self) -> None:
        """List containing non-string entries raises UsageError."""
        from ax.commands.evaluators import _parse_variables
        from ax.core.exceptions import UsageError

        with pytest.raises(UsageError, match="array of strings"):
            _parse_variables('["a", 2]')


class TestCodeCreateManagedEvaluator:
    """Tests for 'ax evaluators code-create --code-type managed'."""

    @pytest.mark.unit
    def test_builds_managed_code_config_and_calls_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Managed variant dispatches _build_managed_code_config and passes code_config."""
        mock_client.evaluators.create_code_evaluator.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "eval-new"})
        )

        with patch(
            "ax.commands.evaluators._build_managed_code_config"
        ) as mock_build:
            mock_code_config = MagicMock()
            mock_build.return_value = mock_code_config

            result = cli_runner.invoke(
                app,
                [
                    "create-code-evaluator",
                    "--name",
                    "Regex Check",
                    "--space",
                    "space-1",
                    "--commit-message",
                    "Initial version",
                    "--code-type",
                    "managed",
                    "--code-name",
                    "regex_match",
                    "--managed-evaluator",
                    "MatchesRegex",
                    "--variables",
                    '["output"]',
                    "--static-params",
                    '[{"name":"pattern","type":"REGEX","default_value":"^yes"}]',
                    "--data-granularity",
                    "span",
                ],
            )

        assert result.exit_code == 0, result.output
        mock_build.assert_called_once()
        mock_client.evaluators.create_code_evaluator.assert_called_once_with(
            name="Regex Check",
            space="space-1",
            commit_message="Initial version",
            code_config=mock_code_config,
            description=None,
        )

    @pytest.mark.unit
    def test_managed_missing_managed_evaluator_raises(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Managed variant without --managed-evaluator is rejected."""
        result = cli_runner.invoke(
            app,
            [
                "create-code-evaluator",
                "--name",
                "x",
                "--space",
                "space-1",
                "--commit-message",
                "init",
                "--code-type",
                "managed",
                "--code-name",
                "ev",
                "--variables",
                '["output"]',
            ],
        )
        assert result.exit_code != 0
        assert "--managed-evaluator" in result.output


class TestCodeCreateCustomEvaluator:
    """Tests for 'ax evaluators code-create --code-type custom'."""

    @pytest.mark.unit
    def test_inline_code_calls_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Inline --code is forwarded to _build_custom_code_config."""
        mock_client.evaluators.create_code_evaluator.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "eval-new"})
        )

        with patch(
            "ax.commands.evaluators._build_custom_code_config"
        ) as mock_build:
            mock_code_config = MagicMock()
            mock_build.return_value = mock_code_config

            result = cli_runner.invoke(
                app,
                [
                    "create-code-evaluator",
                    "--name",
                    "Custom Eval",
                    "--space",
                    "space-1",
                    "--commit-message",
                    "init",
                    "--code-type",
                    "custom",
                    "--code-name",
                    "my_eval",
                    "--code",
                    "class MyEval: pass",
                    "--variables",
                    '["input","output"]',
                ],
            )

        assert result.exit_code == 0, result.output
        mock_build.assert_called_once()
        _, kwargs = mock_build.call_args
        assert kwargs["code"] == "class MyEval: pass"
        assert kwargs["imports"] is None
        mock_client.evaluators.create_code_evaluator.assert_called_once_with(
            name="Custom Eval",
            space="space-1",
            commit_message="init",
            code_config=mock_code_config,
            description=None,
        )

    @pytest.mark.unit
    def test_code_and_imports_from_at_path_files(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """--code @file.py and --imports @file.py are resolved into CustomCodeConfig."""
        mock_client.evaluators.create_code_evaluator.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "eval-new"})
        )

        code_file = tmp_path / "ev.py"
        code_file.write_text("class LoadedEval: ...\n", encoding="utf-8")
        imports_file = tmp_path / "imp.py"
        imports_file.write_text("import re\n", encoding="utf-8")

        result = cli_runner.invoke(
            app,
            [
                "create-code-evaluator",
                "--name",
                "Custom Eval",
                "--space",
                "space-1",
                "--commit-message",
                "init",
                "--code-type",
                "custom",
                "--code-name",
                "my_eval",
                "--code",
                f"@{code_file}",
                "--imports",
                f"@{imports_file}",
                "--variables",
                '["output"]',
            ],
        )

        assert result.exit_code == 0, result.output
        mock_client.evaluators.create_code_evaluator.assert_called_once()
        _, kwargs = mock_client.evaluators.create_code_evaluator.call_args
        code_config = kwargs["code_config"]
        inner = code_config.actual_instance
        assert inner.type == "custom"
        assert inner.code == "class LoadedEval: ...\n"
        assert inner.imports == "import re\n"

    @pytest.mark.unit
    def test_custom_missing_code_raises(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Custom variant without --code is rejected."""
        result = cli_runner.invoke(
            app,
            [
                "create-code-evaluator",
                "--name",
                "x",
                "--space",
                "space-1",
                "--commit-message",
                "init",
                "--code-type",
                "custom",
                "--code-name",
                "ev",
                "--variables",
                '["output"]',
            ],
        )
        assert result.exit_code != 0
        assert "--code" in result.output


class TestCodeCreateVersionKinds:
    """Tests for 'ax evaluators code-create-version'."""

    @pytest.mark.unit
    def test_managed_version_calls_sdk(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Managed code-create-version forwards code_config to create_code_version."""
        mock_client.evaluators.create_code_version.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "v-2"})
        )

        with patch(
            "ax.commands.evaluators._build_managed_code_config"
        ) as mock_build:
            mock_code_config = MagicMock()
            mock_build.return_value = mock_code_config

            result = cli_runner.invoke(
                app,
                [
                    "create-code-evaluator-version",
                    "eval-1",
                    "--commit-message",
                    "v2",
                    "--code-type",
                    "managed",
                    "--code-name",
                    "regex",
                    "--managed-evaluator",
                    "JSONParseable",
                    "--variables",
                    '["output"]',
                ],
            )

        assert result.exit_code == 0, result.output
        mock_build.assert_called_once()
        mock_client.evaluators.create_code_version.assert_called_once_with(
            evaluator="eval-1",
            space=None,
            commit_message="v2",
            code_config=mock_code_config,
        )

    @pytest.mark.unit
    def test_custom_version_at_path_code(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
        tmp_path: Path,
    ) -> None:
        """Custom code-create-version resolves --code @path/to/file.py."""
        mock_client.evaluators.create_code_version.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "v-2"})
        )

        code_file = tmp_path / "ev.py"
        code_file.write_text("class V2Eval: ...\n", encoding="utf-8")

        result = cli_runner.invoke(
            app,
            [
                "create-code-evaluator-version",
                "eval-1",
                "--commit-message",
                "v2",
                "--code-type",
                "custom",
                "--code-name",
                "my_eval",
                "--code",
                f"@{code_file}",
                "--variables",
                '["output"]',
            ],
        )

        assert result.exit_code == 0, result.output
        mock_client.evaluators.create_code_version.assert_called_once()
        _, kwargs = mock_client.evaluators.create_code_version.call_args
        code_config = kwargs["code_config"]
        assert code_config.actual_instance.code == "class V2Eval: ...\n"
