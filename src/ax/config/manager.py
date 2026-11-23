"""Configuration file management with profile support."""

import os
import re
from pathlib import Path
from typing import Any, TypeVar, overload

import tomli_w
import tomllib
from arize import Region
from pydantic import ValidationError

from ax.config.schema import AuthConfig, AuthMethod, Config, RoutingConfig
from ax.core.error_formatter import format_validation_error
from ax.core.exceptions import ConfigError, RoutingConfigError

T = TypeVar("T")


class ConfigManager:
    """Manage configuration files and profiles."""

    CONFIG_DIR = Path.home() / ".arize"
    PROFILES_DIR = CONFIG_DIR / "profiles"
    ACTIVE_PROFILE_FILE = CONFIG_DIR / ".active_profile"

    @classmethod
    def list_profiles(cls) -> list[str]:
        """List all available profiles.

        Returns:
            List of profile names
        """
        profiles: list[str] = []

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
            Active profile name
        """
        # Check active profile file
        if cls.ACTIVE_PROFILE_FILE.exists():
            try:
                return cls.ACTIVE_PROFILE_FILE.read_text().strip()
            except OSError as e:
                raise ConfigError(
                    f"Failed to read active profile file: {e}"
                ) from e
            except Exception:
                return ""

        return ""

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
        try:
            cls.ACTIVE_PROFILE_FILE.write_text(profile)
        except OSError as e:
            raise ConfigError(
                f"Failed to write active profile file: {e}"
            ) from e

    @classmethod
    def delete_profile(cls, profile: str) -> None:
        """Delete a profile.

        Args:
            profile: Profile name to delete

        Raises:
            ConfigError: If profile does not exist or active profile
        """
        if not cls.exists(profile):
            raise ConfigError(
                f"Profile '{profile}' does not exist.\n"
                f"Available profiles: {', '.join(cls.list_profiles())}"
            )

        if profile == cls.get_active_profile():
            raise ConfigError(
                f"Cannot delete active profile '{profile}'. "
                "Switch to another profile first."
            )

        cls._get_config_path(profile).unlink()

    @classmethod
    def load(cls, profile: str = "", expand_env_vars: bool = True) -> Config:
        """Load configuration from file with env var expansion.

        Expands ${VAR} and ${VAR:default} references in string values.

        Args:
            profile: Profile name. If empty, uses active profile.
            expand_env_vars: Whether to expand environment variable references

        Returns:
            Config object

        Raises:
            ConfigError: If config file doesn't exist or is invalid
        """
        if not profile:
            profile = cls.get_active_profile()
            if not profile:
                raise ConfigError(
                    "No active profile configured.\n\n"
                    "Run 'ax profiles create' to create a configuration.\n"
                )

        config_path = cls._get_config_path(profile)

        if not config_path.exists():
            raise ConfigError(
                f"Profile '{profile}' not found.\n\n"
                "Run 'ax profiles create' to create a configuration,\n"
                "or run 'ax profiles use <name>' to switch the active profile."
            )

        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)

            if expand_env_vars:
                # Expand environment variable references
                data = _expand_config_dict(data)

            return Config(**data)
        except ValidationError as e:
            raise ConfigError(
                f"Profile '{profile}' has an invalid configuration:\n\n"
                f"{format_validation_error(e)}\n\n"
                "Run 'ax profiles create' to recreate it.\n"
                "To remove local credentials, switch to another profile "
                "and run 'ax profiles delete <name>'."
            ) from e
        except ValueError as e:
            raise ConfigError(
                f"Profile '{profile}' references an unset environment variable:\n\n"
                f"{e}\n\n"
                "Set the variable or run 'ax profiles create' to update the profile."
            ) from e
        except Exception as e:
            raise ConfigError(f"Failed to load config: {e}") from e

    @classmethod
    def save(cls, config: Config, profile: str) -> None:
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
    def clear_oauth_credentials(
        cls, profile: str
    ) -> tuple[AuthConfig, object, object]:
        """Clear local OAuth tokens without requiring valid routing settings.

        Args:
            profile: Profile name whose local tokens must be removed.

        Returns:
            Previous authentication credentials and the raw routing and
            security settings.

        Raises:
            ConfigError: If the profile cannot be read, parsed, or saved.
        """
        if not profile:
            raise ConfigError("No active profile configured.")
        path = cls._get_config_path(profile)
        try:
            with path.open("rb") as f:
                data = tomllib.load(f)
            auth = AuthConfig.model_validate(data.get("auth", {}))
            if auth.uses_oauth and auth.oauth is not None:
                data["auth"]["auth_method"] = AuthMethod.OAUTH.value
                data["auth"].pop("oauth", None)
                path.write_text(tomli_w.dumps(data), encoding="utf-8")
            return auth, data.get("routing", {}), data.get("security", {})
        except ValidationError as e:
            raise ConfigError(format_validation_error(e)) from e
        except (OSError, ValueError) as e:
            raise ConfigError(
                f"Cannot clear credentials for profile '{profile}': {e}"
            ) from e

    @staticmethod
    def profile_path(name: str) -> Path:
        """Return the TOML file path for *name*.

        Convenience wrapper around ``_get_config_path`` for use outside this
        class (e.g. by ``get_active_bearer``).

        Args:
            name: Profile name

        Returns:
            Path to the profile's TOML file
        """
        return ConfigManager.PROFILES_DIR / f"{name}.toml"

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
    if isinstance(value, int | float):
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
    """Recursively expand environment variables in a config dictionary."""
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


def resolve_oauth_app_url(routing: object) -> str:
    """Expand and validate routing before selecting the OAuth server URL."""
    data = (
        routing.model_dump() if isinstance(routing, RoutingConfig) else routing
    )
    if not isinstance(data, dict):
        raise RoutingConfigError("OAuth routing must be a configuration table.")
    try:
        resolved = RoutingConfig(**_expand_config_dict(data))
    except ValidationError as e:
        raise RoutingConfigError(
            f"Invalid OAuth routing: {format_validation_error(e)}"
        ) from e
    except ValueError as e:
        raise RoutingConfigError(f"Cannot resolve OAuth routing: {e}") from e
    if resolved.single_host:
        # single_port is part of the single-endpoint override: on-prem
        # deployments serve the app (and thus OAuth) on this host:port.
        # Dropping it here makes the browser flow fall back to the scheme
        # default (80/443) even though the user configured e.g. :4040.
        if resolved.single_port:
            return f"{resolved.app_scheme}://{resolved.single_host}:{resolved.single_port}"
        return f"{resolved.app_scheme}://{resolved.single_host}"
    if resolved.base_domain:
        return f"https://app.{resolved.base_domain}"
    if resolved.region == Region.US.value:
        return "https://app.arize.com"
    if resolved.region:
        return f"https://app.{resolved.region}.arize.com"
    return f"{resolved.app_scheme}://{resolved.app_host}"
