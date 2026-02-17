import os
from enum import Enum

import questionary
from rich.console import Console

from ax.config.input_readers import (
    read_api_key,
    read_output_format,
    read_region,
    read_routing,
    read_security,
    read_transport,
)
from ax.config.schema import (
    AuthConfig,
    Config,
    OutputConfig,
    ProfileConfig,
    RoutingConfig,
    SecurityConfig,
    StorageConfig,
    TransportConfig,
)

console = Console()


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
}


class SetupMode(Enum):
    """Configuration setup mode."""

    SIMPLE = "simple"
    ADVANCED = "advanced"


def create_config_interactively(
    profile: str,
) -> Config:
    """Create a configuration interactively by prompting the user."""
    mode = SetupMode.SIMPLE
    mode = questionary.select(
        "Choose configuration mode:",
        choices=[
            "Simple (recommended)",
            "Advanced",
        ],
        default="Simple (recommended)",
    ).ask()
    mode = SetupMode.SIMPLE if "Simple" in mode else SetupMode.ADVANCED

    if mode == SetupMode.SIMPLE:
        return simple_setup(profile)

    return advanced_setup(profile)


def simple_setup(profile: str) -> Config:
    """Create a simple configuration with basic settings."""
    auth_config = AuthConfig(api_key=read_api_key())
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


def advanced_setup(profile: str) -> Config:
    """Create an advanced configuration with all settings."""
    auth_config = AuthConfig(api_key=read_api_key())

    routing_config = read_routing()

    transport_config = read_transport()
    security_config = read_security()
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


def create_config_from_env_vars(
    profile: str, env_vars: dict[str, str]
) -> Config:
    """Create a Config object with environment variable references.

    Args:
        profile: Profile name
        env_vars: Dict mapping field names to env var names for detected env vars

    Returns:
        Config object with env var references (e.g., "${ARIZE_API_KEY}")
    """

    def env_ref(env_var_name: str) -> str:
        """Convert env var name to reference string."""
        return f"${{{env_var_name}}}"

    # Build AuthConfig
    auth_kwargs = {}
    if "api_key" in env_vars:
        auth_kwargs["api_key"] = env_ref(env_vars["api_key"])
    else:
        # api_key is required - this shouldn't happen but handle gracefully
        raise ValueError("api_key must be present in detected env vars")

    auth_config = AuthConfig(**auth_kwargs)

    # Build RoutingConfig
    routing_kwargs = {}
    routing_fields = {
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
    }
    for field in routing_fields:
        if field in env_vars:
            routing_kwargs[field] = env_ref(env_vars[field])

    routing_config = RoutingConfig(**routing_kwargs)

    # Build TransportConfig
    transport_kwargs = {}
    transport_fields = {
        "stream_max_workers",
        "stream_max_queue_bound",
        "pyarrow_max_chunksize",
        "max_http_payload_size_mb",
    }
    for field in transport_fields:
        if field in env_vars:
            transport_kwargs[field] = env_ref(env_vars[field])

    transport_config = TransportConfig(**transport_kwargs)

    # Build SecurityConfig
    security_kwargs = {}
    if "request_verify" in env_vars:
        security_kwargs["request_verify"] = env_ref(env_vars["request_verify"])

    security_config = SecurityConfig(**security_kwargs)

    storage_config = StorageConfig()
    output_config = OutputConfig(
        format=read_output_format(),
    )
    # Build Config with all sections
    return Config(
        profile=ProfileConfig(name=profile),
        auth=auth_config,
        routing=routing_config,
        transport=transport_config,
        security=security_config,
        storage=storage_config,
        output=output_config,
    )
