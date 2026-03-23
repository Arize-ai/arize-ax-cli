"""Tests for evaluator CLI commands."""

from unittest.mock import MagicMock, patch

import pytest
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
            "create",
            "update",
            "delete",
            "list-versions",
            "get-version",
            "create-version",
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
            space_id=None,
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
        """Invoke 'list' with --space-id and verify it is passed to SDK."""
        mock_client.evaluators.list.return_value = MagicMock(
            model_dump=MagicMock(return_value={"evaluators": []})
        )

        result = cli_runner.invoke(app, ["list", "--space-id", "space-1"])
        assert result.exit_code == 0
        mock_client.evaluators.list.assert_called_once_with(
            space_id="space-1",
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
            evaluator_id="eval-1",
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
            evaluator_id="eval-1",
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
            evaluator_id="eval-1",
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
            evaluator_id="eval-1",
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
            evaluator_id="eval-1"
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
            evaluator_id="eval-1"
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
            evaluator_id="eval-1",
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


class TestCreateEvaluator:
    """Tests for the 'ax evaluators create' command."""

    @pytest.mark.unit
    def test_calls_client_create_evaluator(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'create' with required args and verify SDK call."""
        mock_client.evaluators.create.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "eval-new"})
        )

        with patch(
            "ax.commands.evaluators._build_template_config"
        ) as mock_build:
            mock_template_config = MagicMock()
            mock_build.return_value = mock_template_config

            result = cli_runner.invoke(
                app,
                [
                    "create",
                    "--name",
                    "My Evaluator",
                    "--space-id",
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
        mock_client.evaluators.create.assert_called_once_with(
            name="My Evaluator",
            space_id="space-1",
            commit_message="Initial version",
            template_config=mock_template_config,
            description=None,
        )

    @pytest.mark.unit
    def test_create_with_description(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'create' with --description and verify it is passed to SDK."""
        mock_client.evaluators.create.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "eval-new"})
        )

        with patch("ax.commands.evaluators._build_template_config"):
            result = cli_runner.invoke(
                app,
                [
                    "create",
                    "--name",
                    "My Evaluator",
                    "--space-id",
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
        mock_client.evaluators.create.assert_called_once()
        _, kwargs = mock_client.evaluators.create.call_args
        assert kwargs["description"] == "Evaluates relevance"

    @pytest.mark.unit
    def test_create_passes_classification_choices_to_build(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """--classification-choices and related flags reach _build_template_config."""
        mock_client.evaluators.create.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "eval-new"})
        )

        with patch(
            "ax.commands.evaluators._build_template_config"
        ) as mock_build:
            mock_build.return_value = MagicMock()
            result = cli_runner.invoke(
                app,
                [
                    "create",
                    "--name",
                    "My Evaluator",
                    "--space-id",
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


class TestCreateVersion:
    """Tests for the 'ax evaluators create-version' command."""

    @pytest.mark.unit
    def test_calls_client_create_version(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """Invoke 'create-version' with required args and verify SDK call."""
        mock_client.evaluators.create_version.return_value = MagicMock(
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
                    "create-version",
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
        mock_client.evaluators.create_version.assert_called_once_with(
            evaluator_id="eval-1",
            commit_message="v2 update",
            template_config=mock_template_config,
        )

    @pytest.mark.unit
    def test_create_version_passes_classification_choices_to_build(
        self,
        cli_runner: CliRunner,
        mock_client: MagicMock,
        patch_config_and_client: tuple[MagicMock, MagicMock],
    ) -> None:
        """New template flags are forwarded on create-version."""
        mock_client.evaluators.create_version.return_value = MagicMock(
            model_dump=MagicMock(return_value={"id": "v-2"})
        )

        with patch(
            "ax.commands.evaluators._build_template_config"
        ) as mock_build:
            mock_build.return_value = MagicMock()
            result = cli_runner.invoke(
                app,
                [
                    "create-version",
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
        import click

        from ax.commands.evaluators import _build_template_config

        with pytest.raises(click.exceptions.BadParameter):
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
        import click

        from ax.commands.evaluators import _build_template_config

        with pytest.raises(click.exceptions.BadParameter):
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
            direction="minimize",
            data_granularity="trace",
        )
        assert cfg.classification_choices == {"relevant": 1, "irrelevant": 0}
        assert cfg.direction == "minimize"
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
    def test_invalid_direction_raises_usage_error(self) -> None:
        """Direction must be maximize or minimize."""
        from ax.commands.evaluators import _build_template_config
        from ax.core.exceptions import UsageError

        with pytest.raises(
            UsageError, match="--direction must be 'maximize' or 'minimize'"
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
                classification_choices_str=None,
                direction="sideways",
                data_granularity=None,
            )

    @pytest.mark.unit
    def test_invalid_data_granularity_raises_usage_error(self) -> None:
        """data_granularity must be span, trace, or session."""
        from ax.commands.evaluators import _build_template_config
        from ax.core.exceptions import UsageError

        with pytest.raises(
            UsageError,
            match="--data-granularity must be span, trace, or session",
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
                classification_choices_str=None,
                direction=None,
                data_granularity="record",
            )

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
    def test_direction_normalized_to_lowercase(self) -> None:
        """Mixed-case direction values are accepted and normalized."""
        from ax.commands.evaluators import _parse_optional_direction

        assert _parse_optional_direction("Maximize") == "maximize"
        assert _parse_optional_direction("MINIMIZE") == "minimize"

    @pytest.mark.unit
    def test_data_granularity_normalized_to_lowercase(self) -> None:
        """Mixed-case granularity values are accepted and normalized."""
        from ax.commands.evaluators import _parse_optional_data_granularity

        assert _parse_optional_data_granularity("Span") == "span"
        assert _parse_optional_data_granularity("TRACE") == "trace"
        assert _parse_optional_data_granularity("Session") == "session"
