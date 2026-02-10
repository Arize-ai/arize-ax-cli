"""Configuration file management with profile support."""

import os
import re
from pathlib import Path
from typing import Any, TypeVar, overload

import tomli_w
import tomllib
from pydantic import ValidationError

from ax.config.schema import Config
from ax.core.exceptions import ConfigError

T = TypeVar("T")


class ConfigManager:
    """Manage configuration files and profiles."""

    CONFIG_DIR = Path.home() / ".arize"
    PROFILES_DIR = CONFIG_DIR / "profiles"
    DEFAULT_CONFIG_FILE = CONFIG_DIR / "config.toml"
    ACTIVE_PROFILE_FILE = CONFIG_DIR / ".active_profile"

    @classmethod
    def list_profiles(cls) -> list[str]:
        """List all available profiles.

        Returns:
            List of profile names
        """
        profiles = ["default"] if cls.DEFAULT_CONFIG_FILE.exists() else []

        if cls.PROFILES_DIR.exists():
            profiles.extend(
                path.stem for path in cls.PROFILES_DIR.glob("*.toml")
            )

        return sorted(profiles)

    @classmethod
    def exists(cls, profile: str) -> bool:
        """Check if a config file exists for a profile.

        Args:
            profile: Profile name

        Returns:
            True if config exists
        """
        return cls._get_config_path(profile).exists()

    @classmethod
    def get_active_profile(cls) -> str:
        """Get the currently active profile.

        Returns:
            Active profile name (defaults to "default")
        """
        # Check active profile file
        if cls.ACTIVE_PROFILE_FILE.exists():
            try:
                return cls.ACTIVE_PROFILE_FILE.read_text().strip()
            except Exception:
                return "default"

        return "default"

    @classmethod
    def set_active_profile(cls, profile: str) -> None:
        """Set the active profile.

        Args:
            profile: Profile name to activate

        Raises:
            ConfigError: If profile doesn't exist
        """
        if not cls.exists(profile):
            raise ConfigError(
                f"Profile '{profile}' does not exist.\n"
                f"Available profiles: {', '.join(cls.list_profiles())}"
            )
        cls.ACTIVE_PROFILE_FILE.write_text(profile)

    @classmethod
    def delete_profile(cls, profile: str) -> None:
        """Delete a profile.

        Args:
            profile: Profile name to delete

        Raises:
            ConfigError: If trying to delete default or active profile
        """
        if profile == "default":
            raise ConfigError("Cannot delete the default profile")

        if profile == cls.get_active_profile():
            raise ConfigError(
                f"Cannot delete active profile '{profile}'. "
                "Switch to another profile first."
            )

        config_path = cls._get_config_path(profile)
        if config_path.exists():
            config_path.unlink()

    @classmethod
    def load(cls, profile: str, expand_env_vars: bool = True) -> Config:
        """Load configuration from file with env var expansion.

        Expands ${VAR} and ${VAR:default} references in string values.

        Args:
            profile: Profile name. If empty, uses active profile or default.
            expand_env_vars: Whether to expand environment variable references

        Returns:
            Config object

        Raises:
            ConfigError: If config file doesn't exist or is invalid
        """
        if not profile:
            profile = cls.get_active_profile()

        config_path = cls._get_config_path(profile)

        if not config_path.exists():
            raise ConfigError(
                f"Profile '{profile}' not found.\n\n"
                "Run 'ax config init' to create a configuration.\n"
                "Or specify a different profile with --profile"
            )

        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)

            if expand_env_vars:
                # Expand environment variable references
                data = _expand_config_dict(data)

            return Config(**data)
        except ValidationError as e:
            raise ConfigError(f"Invalid config file: {e}") from e
        except Exception as e:
            raise ConfigError(f"Failed to load config: {e}") from e

    @classmethod
    def save(cls, config: Config, profile: str = "default") -> None:
        """Save configuration to file.

        Args:
            config: Config object to save
            profile: Profile name

        Raises:
            ConfigError: If save fails
        """
        cls._ensure_dirs()
        config_path = cls._get_config_path(profile)

        try:
            # Update profile name in config
            config.profile.name = profile

            # Convert to dict and write using tomli-w
            data = config.model_dump(mode="json", exclude_none=True)
            data = _remove_empty_values(data)

            with open(config_path, "wb") as f:
                tomli_w.dump(data, f)
        except Exception as e:
            raise ConfigError(f"Failed to save config: {e}") from e

    @classmethod
    def _ensure_dirs(cls) -> None:
        """Ensure config directories exist."""
        cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cls.PROFILES_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _get_config_path(cls, profile: str) -> Path:
        """Get config file path for a profile.

        Args:
            profile: Profile name

        Returns:
            Path to config file
        """
        if profile == "default":
            return cls.DEFAULT_CONFIG_FILE
        return cls.PROFILES_DIR / f"{profile}.toml"


def _to_int(value: int | str) -> int:
    """Convert int|str to int.

    Args:
        value: Value to convert

    Returns:
        Integer value

    Raises:
        ValueError: If conversion fails
    """
    if isinstance(value, int):
        return value
    return int(value)


def _to_float(value: int | float | str) -> float:
    """Convert int|float|str to float.

    Args:
        value: Value to convert

    Returns:
        Float value

    Raises:
        ValueError: If conversion fails
    """
    if isinstance(value, (int, float)):
        return float(value)
    return float(value)


def _to_bool(value: bool | str) -> bool:
    """Convert bool|str to bool.

    Parses boolean from strings: "1", "true", "yes", "on" (case-insensitive) → True

    Args:
        value: Value to convert

    Returns:
        Boolean value
    """
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@overload
def _remove_empty_values(obj: dict[str, Any]) -> dict[str, Any]: ...


@overload
def _remove_empty_values(obj: T) -> T: ...


def _remove_empty_values(
    obj: dict[str, Any] | T,
) -> dict[str, Any] | T:
    """Recursively remove None and empty string values from nested dicts.

    This creates cleaner TOML output by excluding unset optional fields.
    When loading configs, Pydantic will apply default values for missing fields.

    Args:
        obj: Dictionary or other object to process

    Returns:
        Filtered dictionary with None and empty strings removed
    """
    if isinstance(obj, dict):
        return {
            k: _remove_empty_values(v)
            for k, v in obj.items()
            if v != "" and v is not None
        }
    return obj


def _expand_config_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively expand environment variables in a config dictionary.

    Args:
        data: Configuration dictionary

    Returns:
        Dictionary with all ${VAR} references expanded
    """
    result: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = _expand_config_dict(value)
        elif isinstance(value, str):
            result[key] = _expand_env_var(value)
        else:
            result[key] = value
    return result


def _expand_env_var(value: str) -> str:
    """Expand environment variable references in a string.

    Supports:
    - ${VAR_NAME} - expands to env var value, raises error if not set
    - ${VAR_NAME:default} - expands to env var value or default if not set
    - literal values - returned as-is

    Args:
        value: String value that may contain ${VAR} references

    Returns:
        Expanded string value

    Raises:
        ValueError: If required env var is not set
    """
    if not isinstance(value, str):
        return value

    # Pattern: ${VAR_NAME} or ${VAR_NAME:default}
    pattern = r"\$\{([^}:]+)(?::([^}]*))?\}"

    def replace_var(match: re.Match) -> str:
        var_name = match.group(1)
        default_value = match.group(2)

        env_value = os.environ.get(var_name)

        if env_value is not None:
            return env_value
        if default_value is not None:
            return default_value
        raise ValueError(
            f"Environment variable {var_name} is not set and no default provided"
        )

    return re.sub(pattern, replace_var, value)
