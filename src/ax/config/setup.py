import os
from enum import Enum
from pathlib import Path
from typing import Any

import questionary
import tomllib
import typer
from pydantic import ValidationError

from ax.config.input_readers import (
    read_api_key,
    read_network,
    read_output_format,
    read_region,
    read_routing,
    read_security,
    read_transport,
)
from ax.config.schema import (
    AuthConfig,
    AuthMethod,
    Config,
    NetworkConfig,
    OutputConfig,
    ProfileConfig,
    RoutingConfig,
    SecurityConfig,
    StorageConfig,
    TransportConfig,
)
from ax.core.error_formatter import format_validation_error
from ax.core.exceptions import ConfigError

# Standard environment variable names for detection
ENV_VAR_MAPPING = {
    "api_key": "ARIZE_API_KEY",
    "region": "ARIZE_REGION",
    "single_host": "ARIZE_SINGLE_HOST",
    "single_port": "ARIZE_SINGLE_PORT",
    "base_domain": "ARIZE_BASE_DOMAIN",
    "api_host": "ARIZE_API_HOST",
    "api_scheme": "ARIZE_API_SCHEME",
    "otlp_host": "ARIZE_OTLP_HOST",
    "otlp_scheme": "ARIZE_OTLP_SCHEME",
    "flight_host": "ARIZE_FLIGHT_HOST",
    "flight_port": "ARIZE_FLIGHT_PORT",
    "flight_scheme": "ARIZE_FLIGHT_SCHEME",
    "stream_max_workers": "ARIZE_STREAM_MAX_WORKERS",
    "stream_max_queue_bound": "ARIZE_STREAM_MAX_QUEUE_BOUND",
    "pyarrow_max_chunksize": "ARIZE_MAX_CHUNKSIZE",
    "max_http_payload_size_mb": "ARIZE_MAX_HTTP_PAYLOAD_SIZE_MB",
    "request_verify": "ARIZE_REQUEST_VERIFY",
    "proxy_url": "ARIZE_PROXY_URL",
    "no_proxy": "ARIZE_NO_PROXY",
    "ca_bundle": "ARIZE_SSL_CA_CERT",
}


class SetupMode(Enum):
    """Configuration setup mode."""

    SIMPLE = "simple"
    ADVANCED = "advanced"


def create_config_interactively(
    profile: str,
    auth_method: AuthMethod = AuthMethod.API_KEY,
) -> Config:
    """Create a configuration interactively by prompting the user.

    For ``auth_method="oauth"`` the returned Config has an empty (logged-out)
    OAuth AuthConfig — the caller is expected to run the browser flow against
    ``config.routing.resolve_app_url()`` and populate ``config.auth.oauth``
    before persisting.
    """
    mode = SetupMode.SIMPLE
    mode_choice = questionary.select(
        "Choose configuration mode:",
        choices=[
            "Simple (recommended)",
            "Advanced",
        ],
        default="Simple (recommended)",
    ).ask()
    if mode_choice is None:
        raise typer.Abort()
    mode = SetupMode.SIMPLE if "Simple" in mode_choice else SetupMode.ADVANCED

    if mode == SetupMode.SIMPLE:
        return simple_setup(profile, auth_method)

    return advanced_setup(profile, auth_method)


def _interactive_auth(auth_method: AuthMethod) -> AuthConfig:
    """Build an AuthConfig for the interactive flow.

    api-key → prompt for the key. oauth → return a logged-out shell; the
    caller runs the browser flow once routing is known.
    """
    if auth_method == AuthMethod.OAUTH:
        return AuthConfig(auth_method=AuthMethod.OAUTH)
    return AuthConfig(auth_method=AuthMethod.API_KEY, api_key=read_api_key())


def simple_setup(
    profile: str,
    auth_method: AuthMethod = AuthMethod.API_KEY,
) -> Config:
    """Create a simple configuration with basic settings."""
    auth_config = _interactive_auth(auth_method)
    routing_config = RoutingConfig(
        region=read_region(),
    )
    output_config = OutputConfig(
        format=read_output_format(),
    )

    return Config(
        profile=ProfileConfig(name=profile),
        auth=auth_config,
        routing=routing_config,
        output=output_config,
    )


def advanced_setup(
    profile: str,
    auth_method: AuthMethod = AuthMethod.API_KEY,
) -> Config:
    """Create an advanced configuration with all settings."""
    auth_config = _interactive_auth(auth_method)
    routing_config = read_routing()
    transport_config = read_transport()
    security_config = read_security()
    network_config = read_network()
    storage_config = StorageConfig()
    output_config = OutputConfig(
        format=read_output_format(),
    )
    return Config(
        profile=ProfileConfig(name=profile),
        auth=auth_config,
        routing=routing_config,
        transport=transport_config,
        security=security_config,
        network=network_config,
        storage=storage_config,
        output=output_config,
    )


def detect_env_vars() -> dict[str, str]:
    """Detect existing ARIZE_* environment variables.

    Returns:
        Dict mapping field names to detected env var names
    """
    return {
        field: env_var
        for field, env_var in ENV_VAR_MAPPING.items()
        if env_var in os.environ
    }


def create_config_from_toml(toml_path: str, profile: str) -> Config:
    """Parse a TOML config file and return a validated Config.

    Args:
        toml_path: Path to the TOML configuration file. Supports ``~``.
        profile: Profile name to embed in the returned Config.

    Returns:
        A validated Config object. Env var references
        (e.g. ``${ARIZE_API_KEY}``) are preserved as plain strings.

    Raises:
        FileNotFoundError: If the file does not exist.
        ConfigError: If the file cannot be parsed as valid TOML or fails
            schema validation.
    """
    path = Path(toml_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"TOML config file not found: {path}")
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(
            f"Failed to parse TOML config file '{path}': {e}"
        ) from e

    data["profile"] = {"name": profile}
    try:
        return Config.model_validate(data)
    except ValidationError as e:
        raise ConfigError(format_validation_error(e)) from e


_ROUTING_KEYS = (
    "region",
    "single_host",
    "single_port",
    "base_domain",
    "api_host",
    "api_scheme",
    "otlp_host",
    "otlp_scheme",
    "flight_host",
    "flight_port",
    "flight_scheme",
)
_TRANSPORT_KEYS = (
    "stream_max_workers",
    "stream_max_queue_bound",
    "pyarrow_max_chunksize",
    "max_http_payload_size_mb",
)
_STORAGE_KEYS = ("directory", "cache_enabled")
_NETWORK_KEYS = ("proxy_mode", "proxy_url", "no_proxy", "ca_bundle")


def create_config_from_flags(
    profile: str,
    flat: dict[str, Any],
) -> Config:
    """Build a Config from a flat dict of CLI flag values.

    Args:
        profile: Profile name to embed in the returned Config.
        flat: Flat mapping of flag-name to value. None values must be excluded
            by the caller; only keys that were explicitly set should be present.

    Returns:
        A validated Config object.

    Raises:
        ConfigError: If required fields are missing or Pydantic validation fails.
    """
    data: dict[str, Any] = {"profile": {"name": profile}}

    if "api_key" in flat:
        data["auth"] = {"api_key": flat["api_key"]}

    routing = {k: flat[k] for k in _ROUTING_KEYS if k in flat}
    if routing:
        data["routing"] = routing

    transport = {k: flat[k] for k in _TRANSPORT_KEYS if k in flat}
    if transport:
        data["transport"] = transport

    if "request_verify" in flat:
        data["security"] = {"request_verify": flat["request_verify"]}

    network = {k: flat[k] for k in _NETWORK_KEYS if k in flat}
    if network:
        data["network"] = network

    storage = {k: flat[k] for k in _STORAGE_KEYS if k in flat}
    if storage:
        data["storage"] = storage

    if "output_format" in flat:
        data["output"] = {"format": flat["output_format"]}

    try:
        return Config.model_validate(data)
    except ValidationError as e:
        raise ConfigError(format_validation_error(e)) from e


def merge_config_with_flags(existing: Config, flat: dict[str, Any]) -> Config:
    """Merge CLI flag values into an existing Config, returning an updated copy.

    Only fields present in ``flat`` are updated; all others retain their
    current values from ``existing``.

    Args:
        existing: The current Config to update.
        flat: Flat mapping of flag-name to value. None values must be excluded
            by the caller; only keys that were explicitly set should be present.

    Returns:
        A validated Config object with the merged values.

    Raises:
        ConfigError: If the resulting config fails Pydantic validation.
    """
    data = existing.model_dump()

    if "api_key" in flat:
        data["auth"]["api_key"] = flat["api_key"]

    data["routing"].update({k: flat[k] for k in _ROUTING_KEYS if k in flat})
    data["transport"].update({k: flat[k] for k in _TRANSPORT_KEYS if k in flat})

    if "request_verify" in flat:
        data["security"]["request_verify"] = flat["request_verify"]

    data["network"].update({k: flat[k] for k in _NETWORK_KEYS if k in flat})

    data["storage"].update({k: flat[k] for k in _STORAGE_KEYS if k in flat})

    if "output_format" in flat:
        data["output"]["format"] = flat["output_format"]

    try:
        return Config.model_validate(data)
    except ValidationError as e:
        raise ConfigError(format_validation_error(e)) from e


_ENV_ROUTING_FIELDS = frozenset(_ROUTING_KEYS)
_ENV_TRANSPORT_FIELDS = frozenset(_TRANSPORT_KEYS)
_ENV_NETWORK_FIELDS = frozenset(_NETWORK_KEYS)


def _env_ref(env_var_name: str) -> str:
    """Convert an env var name to a ``${NAME}`` reference string."""
    return f"${{{env_var_name}}}"


def routing_from_env(env_vars: dict[str, str]) -> RoutingConfig:
    """Build a RoutingConfig populated with current literal env values.

    Use this when you need the *current* routing values (e.g. for an OAuth
    browser flow's base_url). The returned config does NOT contain ``${VAR}``
    references; it captures the values at this moment.
    """
    kwargs = {
        field: os.environ[env_vars[field]]
        for field in _ENV_ROUTING_FIELDS
        if field in env_vars
    }
    return RoutingConfig(**kwargs)


def create_config_from_env_vars(
    profile: str,
    env_vars: dict[str, str],
    auth: AuthConfig,
) -> Config:
    """Create a Config from detected env vars, with the given AuthConfig.

    Routing/transport/security fields become ``${ARIZE_*}`` references so the
    saved profile re-reads the env at runtime. Auth is supplied by the caller
    (api-key path passes an env-ref; OAuth path passes browser-flow tokens).

    Args:
        profile: Profile name
        env_vars: Dict mapping field names to env var names for detected env vars
        auth: Pre-built AuthConfig (api-key or OAuth)
    """
    # Build RoutingConfig
    routing_kwargs = {
        field: _env_ref(env_vars[field])
        for field in _ENV_ROUTING_FIELDS
        if field in env_vars
    }
    routing_config = RoutingConfig(**routing_kwargs)

    # Build TransportConfig
    transport_kwargs = {
        field: _env_ref(env_vars[field])
        for field in _ENV_TRANSPORT_FIELDS
        if field in env_vars
    }
    transport_config = TransportConfig(**transport_kwargs)

    # Build SecurityConfig
    security_kwargs = {}
    if "request_verify" in env_vars:
        security_kwargs["request_verify"] = _env_ref(env_vars["request_verify"])
    security_config = SecurityConfig(**security_kwargs)

    network_kwargs: dict[str, Any] = {
        field: _env_ref(env_vars[field])
        for field in _ENV_NETWORK_FIELDS
        if field in env_vars
    }
    network_config = NetworkConfig(**network_kwargs)

    storage_config = StorageConfig()
    output_config = OutputConfig(
        format=read_output_format(),
    )
    return Config(
        profile=ProfileConfig(name=profile),
        auth=auth,
        routing=routing_config,
        transport=transport_config,
        security=security_config,
        network=network_config,
        storage=storage_config,
        output=output_config,
    )
