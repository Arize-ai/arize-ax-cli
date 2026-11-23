"""Input readers for various configuration fields using questionary.

Provides interactive prompts to gather configuration values from the user.

It supports reading from user input and environment variables.
"""

from enum import Enum
from typing import Literal

import questionary
import typer
from arize import Region

from ax.config.schema import (
    RoutingConfig,
    SecurityConfig,
    TransportConfig,
)
from ax.utils.console import console, prompt

INSERT_VALUE = "Insert value"
USE_ENV_VAR = "Use environment variable"
NO_VALUE = "None"
US_REGION_LABEL = "US (United States, default)"

REGION_LABELS: dict[str, str] = {
    Region.US.value: US_REGION_LABEL,
    Region.EU.value: "EU (Europe)",
    Region.CA.value: "CA (Canada)",
}


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
    if choice is None:
        raise typer.Abort()
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
    if choice is None:
        raise typer.Abort()
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
    console.print(
        "\n[bold]Where to find your API key[/bold]\n"
        "  Visit [cyan]https://app.arize.com[/cyan] and go to [bold]Settings[/bold].\n"
        "  Two key types are available:\n"
        "  • [bold green]Service key[/bold green] [dim](recommended)[/dim] — "
        "space-scoped and not tied to a personal account, safer for programmatic use. "
        "Make sure to copy the key for the correct space.\n"
        "  • [bold]User key[/bold] — grants the same access you already have as a user\n"
    )
    return read_str_field(
        "API Key",
        example="ak-123...",
        env_var="ARIZE_API_KEY",
        hide_input=True,
    )


def read_region() -> str:
    """Read the region from user selection or environment variable."""
    region_by_label = {label: region for region, label in REGION_LABELS.items()}
    choices = [
        *region_by_label,
        USE_ENV_VAR,
    ]
    region_choice = questionary.select(
        "Region:",
        choices=choices,
        default=US_REGION_LABEL,
    ).ask()
    if region_choice is None:
        raise typer.Abort()
    if region_choice == USE_ENV_VAR:
        region_choice = prompt(
            "Environment variable name for region", default="ARIZE_REGION"
        )
        region = f"${{{region_choice}}}"
    else:
        region = region_by_label[region_choice]

    return region


def read_routing() -> RoutingConfig:
    """Read routing configuration from user input."""
    choices = [opt.value for opt in AdvancedRoutingOpts]
    choice = questionary.select(
        "What type of override should we set up?",
        choices=choices,
    ).ask()
    if choice is None:
        raise typer.Abort()
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
            scheme = read_str_field(
                msg="URL scheme",
                example="https, http",
                env_var="ARIZE_API_SCHEME",
            )
            flight_scheme = "grpc" if scheme == "http" else "grpc+tls"
            return RoutingConfig(
                single_host=single_host,
                single_port=single_port,
                api_scheme=scheme,
                app_scheme=scheme,
                otlp_scheme=scheme,
                flight_scheme=flight_scheme,
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
                example="api-mycompany.dev.arize.com",
                env_var="ARIZE_API_HOST",
            )
            app_scheme = read_str_field(
                msg="App scheme",
                example="https, http",
                env_var="ARIZE_APP_SCHEME",
            )
            app_host = read_str_field(
                msg="App host",
                example="app-mycompany.dev.arize.com",
                env_var="ARIZE_APP_HOST",
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
                app_scheme=app_scheme,
                app_host=app_host,
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
    if choice is None:
        raise typer.Abort()
    if choice == USE_ENV_VAR:
        choice = prompt(
            f"Environment variable name for {msg}",
            default="ARIZE_REQUEST_VERIFY",
        )
        value = f"${{{choice}}}"
    else:
        value = choice == "Enabled"

    return value


def _read_optional_path(msg: str, env_var: str, example: str) -> str:
    """Read an optional file path from user input or an env var reference."""
    choices = [NO_VALUE, INSERT_VALUE, USE_ENV_VAR]
    choice = questionary.select(
        f"{msg}:",
        choices=choices,
        default=choices[0],
    ).ask()
    if choice is None:
        raise typer.Abort()
    if choice == NO_VALUE:
        return ""
    if choice == USE_ENV_VAR:
        name = prompt(f"Environment variable name for {msg}", default=env_var)
        return f"${{{name}}}"
    return prompt(f"{msg} path (e.g., {example})")


def read_client_cert_pair() -> tuple[str, str]:
    """Read the mutual TLS client certificate and key paths."""
    msg = "Client certificate for mutual TLS"
    choices = [NO_VALUE, INSERT_VALUE, USE_ENV_VAR]
    choice = questionary.select(
        f"{msg}:",
        choices=choices,
        default=choices[0],
    ).ask()
    if choice is None:
        raise typer.Abort()
    if choice == NO_VALUE:
        return "", ""
    if choice == USE_ENV_VAR:
        cert = prompt(
            "Environment variable name for the client certificate",
            default="ARIZE_CLIENT_CERT",
        )
        key = prompt(
            "Environment variable name for the client key",
            default="ARIZE_CLIENT_KEY",
        )
        return f"${{{cert}}}", f"${{{key}}}"
    cert = prompt("Client certificate path (e.g., ~/.arize/client.crt)")
    key = prompt("Client key path, unencrypted (e.g., ~/.arize/client.key)")
    return cert, key


def read_security() -> SecurityConfig:
    """Read security configuration from user input."""
    request_verify = read_request_verify()
    ssl_ca_cert = _read_optional_path(
        "Custom CA bundle",
        env_var="ARIZE_SSL_CA_CERT",
        example="/etc/ssl/certs/corp-ca.pem",
    )
    client_cert, client_key = read_client_cert_pair()
    return SecurityConfig(
        request_verify=request_verify,
        ssl_ca_cert=ssl_ca_cert,
        client_cert=client_cert,
        client_key=client_key,
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
    choice = questionary.select(
        "Default output format:",
        choices=["table", "json", "csv", "parquet"],
        default="table",
    ).ask()
    if choice is None:
        raise typer.Abort()
    return choice
