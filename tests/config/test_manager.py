"""Tests for configuration manager module."""

import os
from pathlib import Path

import pytest

from ax.config.manager import (
    ConfigManager,
    _expand_config_dict,
    _expand_env_var,
    _remove_empty_values,
    _to_bool,
    _to_float,
    _to_int,
)
from ax.config.schema import AuthConfig, Config, ProfileConfig, RoutingConfig
from ax.core.exceptions import ConfigError


class TestConfigManager:
    """Tests for ConfigManager class."""

    def test_list_profiles_empty(self, mock_config_dir: Path) -> None:
        """Test listing profiles when none exist."""
        profiles = ConfigManager.list_profiles()
        assert profiles == []

    def test_list_profiles_with_default(self, mock_config_dir: Path) -> None:
        """Test listing profiles when default exists."""
        ConfigManager.DEFAULT_CONFIG_FILE.touch()
        profiles = ConfigManager.list_profiles()
        assert profiles == ["default"]

    def test_list_profiles_with_multiple(self, mock_config_dir: Path) -> None:
        """Test listing profiles with multiple profiles."""
        ConfigManager.DEFAULT_CONFIG_FILE.touch()
        (ConfigManager.PROFILES_DIR / "dev.toml").touch()
        (ConfigManager.PROFILES_DIR / "prod.toml").touch()
        profiles = ConfigManager.list_profiles()
        assert sorted(profiles) == ["default", "dev", "prod"]

    def test_exists_returns_false_for_missing(
        self, mock_config_dir: Path
    ) -> None:
        """Test exists returns False for missing profile."""
        assert not ConfigManager.exists("nonexistent")

    def test_exists_returns_true_for_default(
        self, mock_config_dir: Path
    ) -> None:
        """Test exists returns True for existing default profile."""
        ConfigManager.DEFAULT_CONFIG_FILE.touch()
        assert ConfigManager.exists("default")

    def test_exists_returns_true_for_named_profile(
        self, mock_config_dir: Path
    ) -> None:
        """Test exists returns True for existing named profile."""
        (ConfigManager.PROFILES_DIR / "prod.toml").touch()
        assert ConfigManager.exists("prod")

    def test_get_active_profile_default_when_no_file(
        self, mock_config_dir: Path
    ) -> None:
        """Test get_active_profile returns default when no file exists."""
        assert ConfigManager.get_active_profile() == "default"

    def test_get_active_profile_from_file(self, mock_config_dir: Path) -> None:
        """Test get_active_profile reads from file."""
        ConfigManager.ACTIVE_PROFILE_FILE.write_text("production")
        assert ConfigManager.get_active_profile() == "production"

    def test_get_active_profile_handles_exception(
        self, mock_config_dir: Path
    ) -> None:
        """Test get_active_profile returns default on exception."""
        # Create a directory instead of a file to cause an error
        ConfigManager.ACTIVE_PROFILE_FILE.mkdir()
        assert ConfigManager.get_active_profile() == "default"

    def test_set_active_profile(self, mock_config_dir: Path) -> None:
        """Test setting active profile."""
        (ConfigManager.PROFILES_DIR / "prod.toml").touch()
        ConfigManager.set_active_profile("prod")
        assert ConfigManager.get_active_profile() == "prod"

    def test_set_active_profile_raises_for_missing(
        self, mock_config_dir: Path
    ) -> None:
        """Test set_active_profile raises error for missing profile."""
        with pytest.raises(ConfigError, match="does not exist"):
            ConfigManager.set_active_profile("nonexistent")

    def test_delete_profile(self, mock_config_dir: Path) -> None:
        """Test deleting a profile."""
        profile_file = ConfigManager.PROFILES_DIR / "dev.toml"
        profile_file.touch()
        assert profile_file.exists()

        ConfigManager.delete_profile("dev")
        assert not profile_file.exists()

    def test_delete_profile_raises_for_default(
        self, mock_config_dir: Path
    ) -> None:
        """Test delete_profile raises error for default profile."""
        ConfigManager.DEFAULT_CONFIG_FILE.touch()
        with pytest.raises(ConfigError, match="Cannot delete the default"):
            ConfigManager.delete_profile("default")

    def test_delete_profile_raises_for_active(
        self, mock_config_dir: Path
    ) -> None:
        """Test delete_profile raises error for active profile."""
        (ConfigManager.PROFILES_DIR / "prod.toml").touch()
        ConfigManager.ACTIVE_PROFILE_FILE.write_text("prod")

        with pytest.raises(ConfigError, match="Cannot delete active"):
            ConfigManager.delete_profile("prod")

    def test_save_and_load_config(self, mock_config_dir: Path) -> None:
        """Test saving and loading a config."""
        config = Config(
            auth=AuthConfig(api_key="ak-test123"),
            routing=RoutingConfig(region="us-east-1b"),
        )

        ConfigManager.save(config, profile="default")
        loaded_config = ConfigManager.load(profile="default")

        assert loaded_config.auth.api_key == "ak-test123"
        assert loaded_config.routing.region == "us-east-1b"

    def test_save_updates_profile_name(self, mock_config_dir: Path) -> None:
        """Test that save updates the profile name in config."""
        config = Config(
            profile=ProfileConfig(name="wrong_name"),
            auth=AuthConfig(api_key="ak-test123"),
        )

        ConfigManager.save(config, profile="correct_name")
        loaded_config = ConfigManager.load(profile="correct_name")

        assert loaded_config.profile.name == "correct_name"

    def test_load_raises_for_missing_config(
        self, mock_config_dir: Path
    ) -> None:
        """Test load raises error for missing config."""
        with pytest.raises(ConfigError, match="not found"):
            ConfigManager.load(profile="nonexistent")

    def test_load_uses_active_profile_when_empty(
        self, mock_config_dir: Path
    ) -> None:
        """Test load uses active profile when profile param is empty."""
        config = Config(auth=AuthConfig(api_key="ak-test123"))
        ConfigManager.save(config, profile="default")
        ConfigManager.ACTIVE_PROFILE_FILE.write_text("default")

        loaded_config = ConfigManager.load(profile="")
        assert loaded_config.auth.api_key == "ak-test123"

    def test_load_expands_env_vars(self, mock_config_dir: Path) -> None:
        """Test load expands environment variables."""
        os.environ["TEST_API_KEY"] = "ak-from-env"

        config = Config(auth=AuthConfig(api_key="${TEST_API_KEY}"))
        ConfigManager.save(config, profile="default")

        loaded_config = ConfigManager.load(profile="default")
        assert loaded_config.auth.api_key == "ak-from-env"

        # Cleanup
        del os.environ["TEST_API_KEY"]

    def test_load_without_env_var_expansion(
        self, mock_config_dir: Path
    ) -> None:
        """Test load without env var expansion."""
        config = Config(auth=AuthConfig(api_key="${TEST_API_KEY}"))
        ConfigManager.save(config, profile="default")

        loaded_config = ConfigManager.load(
            profile="default", expand_env_vars=False
        )
        assert loaded_config.auth.api_key == "${TEST_API_KEY}"

    def test_save_removes_empty_values(self, mock_config_dir: Path) -> None:
        """Test that save removes empty string values."""
        config = Config(
            auth=AuthConfig(api_key="ak-test123"),
            routing=RoutingConfig(region=""),  # Empty string
        )

        ConfigManager.save(config, profile="default")

        # Read the raw TOML to verify empty strings are not saved
        import tomllib

        with open(ConfigManager.DEFAULT_CONFIG_FILE, "rb") as f:
            data = tomllib.load(f)

        # Empty string should not be present in saved file
        assert "region" not in data.get("routing", {})

    def test_get_config_path_default(self, mock_config_dir: Path) -> None:
        """Test _get_config_path returns correct path for default."""
        path = ConfigManager._get_config_path("default")
        assert path == ConfigManager.DEFAULT_CONFIG_FILE

    def test_get_config_path_named_profile(self, mock_config_dir: Path) -> None:
        """Test _get_config_path returns correct path for named profile."""
        path = ConfigManager._get_config_path("prod")
        assert path == ConfigManager.PROFILES_DIR / "prod.toml"


class TestHelperFunctions:
    """Tests for helper functions in manager module."""

    def test_to_int_from_int(self) -> None:
        """Test _to_int converts int to int."""
        assert _to_int(42) == 42

    def test_to_int_from_str(self) -> None:
        """Test _to_int converts str to int."""
        assert _to_int("42") == 42

    def test_to_int_raises_for_invalid(self) -> None:
        """Test _to_int raises ValueError for invalid string."""
        with pytest.raises(ValueError):
            _to_int("not_a_number")

    def test_to_float_from_int(self) -> None:
        """Test _to_float converts int to float."""
        assert _to_float(42) == 42.0

    def test_to_float_from_float(self) -> None:
        """Test _to_float converts float to float."""
        assert _to_float(42.5) == 42.5

    def test_to_float_from_str(self) -> None:
        """Test _to_float converts str to float."""
        assert _to_float("42.5") == 42.5

    def test_to_float_raises_for_invalid(self) -> None:
        """Test _to_float raises ValueError for invalid string."""
        with pytest.raises(ValueError):
            _to_float("not_a_number")

    def test_to_bool_from_bool(self) -> None:
        """Test _to_bool converts bool to bool."""
        assert _to_bool(True) is True
        assert _to_bool(False) is False

    def test_to_bool_from_str_true(self) -> None:
        """Test _to_bool converts true strings to True."""
        assert _to_bool("true") is True
        assert _to_bool("TRUE") is True
        assert _to_bool("True") is True
        assert _to_bool("1") is True
        assert _to_bool("yes") is True
        assert _to_bool("YES") is True
        assert _to_bool("on") is True
        assert _to_bool("ON") is True

    def test_to_bool_from_str_false(self) -> None:
        """Test _to_bool converts false strings to False."""
        assert _to_bool("false") is False
        assert _to_bool("FALSE") is False
        assert _to_bool("0") is False
        assert _to_bool("no") is False
        assert _to_bool("off") is False
        assert _to_bool("other") is False

    def test_remove_empty_values_dict(self) -> None:
        """Test _remove_empty_values removes empty strings and None."""
        data = {
            "key1": "value1",
            "key2": "",
            "key3": None,
            "key4": 0,
            "key5": False,
        }
        result = _remove_empty_values(data)
        assert result == {
            "key1": "value1",
            "key4": 0,
            "key5": False,
        }

    def test_remove_empty_values_nested(self) -> None:
        """Test _remove_empty_values handles nested dicts."""
        data = {
            "outer": {
                "key1": "value1",
                "key2": "",
                "key3": None,
            }
        }
        result = _remove_empty_values(data)
        assert result == {"outer": {"key1": "value1"}}

    def test_remove_empty_values_non_dict(self) -> None:
        """Test _remove_empty_values returns non-dict unchanged."""
        assert _remove_empty_values("string") == "string"
        assert _remove_empty_values(42) == 42
        assert _remove_empty_values([1, 2, 3]) == [1, 2, 3]

    def test_expand_env_var_simple(self) -> None:
        """Test _expand_env_var expands simple variable."""
        os.environ["TEST_VAR"] = "test_value"
        result = _expand_env_var("${TEST_VAR}")
        assert result == "test_value"
        del os.environ["TEST_VAR"]

    def test_expand_env_var_with_default(self) -> None:
        """Test _expand_env_var uses default when var not set."""
        result = _expand_env_var("${NONEXISTENT_VAR:default_value}")
        assert result == "default_value"

    def test_expand_env_var_no_default_raises(self) -> None:
        """Test _expand_env_var raises when var not set and no default."""
        with pytest.raises(ValueError, match="is not set"):
            _expand_env_var("${NONEXISTENT_VAR}")

    def test_expand_env_var_literal_value(self) -> None:
        """Test _expand_env_var returns literal value unchanged."""
        result = _expand_env_var("literal_value")
        assert result == "literal_value"

    def test_expand_env_var_multiple_vars(self) -> None:
        """Test _expand_env_var expands multiple variables."""
        os.environ["VAR1"] = "value1"
        os.environ["VAR2"] = "value2"
        result = _expand_env_var("${VAR1}-${VAR2}")
        assert result == "value1-value2"
        del os.environ["VAR1"]
        del os.environ["VAR2"]

    def test_expand_config_dict(self) -> None:
        """Test _expand_config_dict expands variables in nested dict."""
        os.environ["API_KEY"] = "ak-from-env"
        os.environ["REGION"] = "US"

        data = {
            "auth": {"api_key": "${API_KEY}"},
            "routing": {"region": "${REGION}"},
            "output": {"format": "table"},  # Not an env var
        }

        result = _expand_config_dict(data)
        assert result == {
            "auth": {"api_key": "ak-from-env"},
            "routing": {"region": "US"},
            "output": {"format": "table"},
        }

        del os.environ["API_KEY"]
        del os.environ["REGION"]

    def test_expand_config_dict_preserves_non_string_values(self) -> None:
        """Test _expand_config_dict preserves non-string values."""
        data = {
            "transport": {
                "stream_max_workers": 8,
                "cache_enabled": True,
            }
        }

        result = _expand_config_dict(data)
        assert result == data
