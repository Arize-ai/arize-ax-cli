"""Input readers for various configuration fields using questionary.

Provides interactive prompts to gather configuration values from the user.

It supports reading from user input and environment variables.
"""

from enum import Enum
from typing import Literal

import questionary
from arize import Region
from rich.console import Console

from ax.config.schema import (
    RoutingConfig,
    SecurityConfig,
    TransportConfig,
)
from ax.utils.console import prompt

console = Console()

INSERT_VALUE = "Insert value"
USE_ENV_VAR = "Use environment variable"
UNSET_REGION_MSG = "(leave empty for unset)"


class AdvancedRoutingOpts(Enum):
    """Options for advanced routing configuration."""

    NONE = "0 - No override (use defaults)"
    REGION = "1 - Region (for region-based routing)"
    SINGLE_ENDPOINT = "2 - Single endpoint (typical for on-prem deployments)"
    BASE_DOMAIN = "3 - Base Domain (for Private Connect)"
    CUSTOM_ENDPOINTS = "4 - Custom endpoints & ports"


def read_str_field(
    msg: str, example: str, env_var: str, hide_input: bool = False
) -> str:
    """Read a string field from user input or environment variable."""
    choices = [
        INSERT_VALUE,
        USE_ENV_VAR,
    ]
    choice = questionary.select(
        f"{msg}:",
        choices=choices,
        default=choices[0],
    ).ask()
    if choice == USE_ENV_VAR:
        choice = prompt(
            f"Environment variable name for {msg}",
            default=env_var,
        )
        value = f"${{{choice}}}"
    else:
        value = prompt(f"{msg} (e.g., {example})", hide_input=hide_input)

    return value


def read_int_field(
    msg: str, example: str, env_var: str, hide_input: bool = False
) -> int | str:
    """Read an integer field from user input or environment variable."""
    choices = [
        INSERT_VALUE,
        USE_ENV_VAR,
    ]
    choice = questionary.select(
        f"{msg}:",
        choices=choices,
        default=choices[0],
    ).ask()
    if choice == USE_ENV_VAR:
        choice = prompt(
            f"Environment variable name for {msg}",
            default=env_var,
        )
        value = f"${{{choice}}}"
    else:
        value = prompt(f"{msg} (e.g., {example})", hide_input=hide_input)

    return value


def read_api_key() -> str:
    """Read the API key from user input or environment variable."""
    return read_str_field(
        "API Key",
        example="ak-123...",
        env_var="ARIZE_API_KEY",
        hide_input=True,
    )


def read_region() -> str:
    """Read the region from user selection or environment variable."""
    choices = [
        UNSET_REGION_MSG,
        *Region.list_regions(),
        USE_ENV_VAR,
    ]
    region_choice = questionary.select(
        "Region:",
        choices=choices,
        default=choices[0],
    ).ask()
    if region_choice == USE_ENV_VAR:
        region_choice = prompt(
            "Environment variable name for region", default="ARIZE_REGION"
        )
        region = f"${{{region_choice}}}"
    else:
        region = "" if region_choice == UNSET_REGION_MSG else region_choice

    return region


def read_routing() -> RoutingConfig:
    """Read routing configuration from user input."""
    choices = [opt.value for opt in AdvancedRoutingOpts]
    choice = questionary.select(
        "What type of override should we setup?",
        choices=choices,
    ).ask()
    match choice:
        case AdvancedRoutingOpts.REGION.value:
            return RoutingConfig(region=read_region())
        case AdvancedRoutingOpts.SINGLE_ENDPOINT.value:
            single_host = read_str_field(
                msg="Single endpoint host",
                example="api.my.company.com",
                env_var="ARIZE_SINGLE_HOST",
            )
            single_port = read_str_field(
                msg="Single endpoint port",
                example="443",
                env_var="ARIZE_SINGLE_PORT",
            )
            return RoutingConfig(
                single_host=single_host,
                single_port=single_port,
            )
        case AdvancedRoutingOpts.BASE_DOMAIN.value:
            base_domain = read_str_field(
                msg="Base domain",
                example="my.company.com",
                env_var="ARIZE_BASE_DOMAIN",
            )
            return RoutingConfig(base_domain=base_domain)
        case AdvancedRoutingOpts.CUSTOM_ENDPOINTS.value:
            api_scheme = read_str_field(
                msg="API scheme",
                example="https, http",
                env_var="ARIZE_API_SCHEME",
            )
            api_host = read_str_field(
                msg="API host",
                example="custom-api.my.company.com",
                env_var="ARIZE_API_HOST",
            )
            otlp_scheme = read_str_field(
                msg="OTLP scheme",
                example="https, http",
                env_var="ARIZE_OTLP_SCHEME",
            )
            otlp_host = read_str_field(
                msg="OTLP host",
                example="custom-otlp.my.company.com",
                env_var="ARIZE_OTLP_HOST",
            )
            flight_scheme = read_str_field(
                msg="Flight scheme",
                example="grpc+tls, grpc",
                env_var="ARIZE_FLIGHT_SCHEME",
            )
            flight_host = read_str_field(
                msg="Flight host",
                example="custom-flight.my.company.com",
                env_var="ARIZE_FLIGHT_HOST",
            )
            flight_port = read_str_field(
                msg="Flight port",
                example="443",
                env_var="ARIZE_FLIGHT_PORT",
            )
            return RoutingConfig(
                api_scheme=api_scheme,
                api_host=api_host,
                otlp_scheme=otlp_scheme,
                otlp_host=otlp_host,
                flight_scheme=flight_scheme,
                flight_host=flight_host,
                flight_port=flight_port,
            )

    return RoutingConfig()


def read_request_verify() -> bool | str:
    """Read TLS certificate verification setting from user input."""
    choices = [
        "Enabled",
        "Disabled",
        USE_ENV_VAR,
    ]
    msg = "TLS Certificate Verification"
    choice = questionary.select(
        f"{msg}:",
        choices=choices,
        default=choices[0],
    ).ask()
    if choice == USE_ENV_VAR:
        choice = prompt(
            f"Environment variable name for {msg}",
            default="ARIZE_REQUEST_VERIFY",
        )
        value = f"${{{choice}}}"
    else:
        value = choice == "Enabled"

    return value


def read_security() -> SecurityConfig:
    """Read security configuration from user input."""
    return SecurityConfig(
        request_verify=read_request_verify(),
    )


def read_transport() -> TransportConfig:
    """Read transport configuration from user input."""
    stream_max_workers = read_int_field(
        msg="Transport stream max workers",
        example="8",
        env_var="ARIZE_STREAM_MAX_WORKERS",
    )
    stream_max_queue_bound = read_int_field(
        msg="Transport stream max queue bound",
        example="5000",
        env_var="ARIZE_STREAM_MAX_QUEUE_BOUND",
    )
    pyarrow_max_chunksize = read_int_field(
        msg="Transport pyarrow max chunksize",
        example="10000",
        env_var="ARIZE_MAX_CHUNKSIZE",
    )
    max_http_payload_size_mb = read_int_field(
        msg="Transport max HTTP payload size (MB)",
        example="100",
        env_var="ARIZE_MAX_HTTP_PAYLOAD_SIZE_MB",
    )
    return TransportConfig(
        stream_max_workers=stream_max_workers,
        stream_max_queue_bound=stream_max_queue_bound,
        pyarrow_max_chunksize=pyarrow_max_chunksize,
        max_http_payload_size_mb=max_http_payload_size_mb,
    )


def read_output_format() -> Literal["table", "json", "csv", "parquet"]:
    """Read the default output format from user selection."""
    return questionary.select(
        "Default output format:",
        choices=["table", "json", "csv", "parquet"],
        default="table",
    ).ask()
