"""Configuration management commands."""

import os
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from ax.ascii_art import DEFAULT_BANNER
from ax.config.manager import ConfigManager
from ax.config.schema import (
    AuthConfig,
    Config,
)
from ax.config.setup import (
    create_config_from_env_vars,
    create_config_interactively,
    detect_env_vars,
)
from ax.core.decorators import handle_errors
from ax.utils.console import (
    confirm,
    emphasis,
    info,
    mask,
    new_line,
    success,
    text,
    text_bold,
    text_dimmed,
)

# Create config subcommand app
app = typer.Typer(
    name="config",
    help="Manage Arize CLI configuration",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)

console = Console()


@app.command("init")
@handle_errors
def init(
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
) -> None:
    """Initialize Arize CLI configuration interactively.

    Creates a new configuration profile with API key, defaults, and
    preferences. Detects existing ARIZE_* environment variables and offers
    to create config from them.
    """
    existing_profiles = ConfigManager.list_profiles()

    # Profile Selection
    profile = "default"
    if existing_profiles:
        # profiles exist - prompt for name
        emphasis("Create a new configuration profile")
        text(f"existing profiles: {', '.join(existing_profiles)}\n")
        profile = typer.prompt("profile name")
        new_line()
    else:
        # Display ASCII art welcome banner
        new_line()
        text(DEFAULT_BANNER)
        new_line()
        emphasis("Welcome to Arize AX CLI!")
        text("No configuration found. Let's set it up!\n")

    # Check if profile already exists
    if ConfigManager.exists(profile) and not confirm(
        f"Profile '{profile}' already exists. Overwrite?",
        default=False,
    ):
        info("Configuration unchanged")
        raise typer.Exit()

    # Environment Variable Detection
    detected_env_vars = detect_env_vars()
    use_env_vars = False
    if detected_env_vars:
        emphasis("Environment Variable Detection\n")
        for field, env_var in detected_env_vars.items():
            value = os.environ.get(env_var, "")
            # Mask API key for display
            if field == "api_key":
                value = mask(value)
            console.print(f"  [green]✓[/green] Detected {env_var} = {value}")

        console.print()
        use_env_vars = confirm(
            "Create config from detected environment variables?",
            default=True,
        )
        console.print()

    config = (
        create_config_from_env_vars(profile, detected_env_vars)
        if use_env_vars
        else create_config_interactively(profile)
    )

    # Save configuration
    ConfigManager.save(config, profile)

    # Set as active profile if not default
    if profile != "default":
        ConfigManager.set_active_profile(profile)

    # Summary
    new_line()
    success(f"Configuration saved to profile '{profile}'")
    new_line()
    text_dimmed("You're ready to go! Try: ax datasets list")


@app.command("list")
@handle_errors
def list_profiles(
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
) -> None:
    """List all available configuration profiles.

    Shows all profiles with the active profile marked.
    """
    profiles = ConfigManager.list_profiles()

    if not profiles:
        info("No profiles found. Run 'ax config init' to create one.")
        raise typer.Exit()

    active = ConfigManager.get_active_profile()

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Profile")
    table.add_column("Status")

    for profile in profiles:
        status = "[green]active[/green]" if profile == active else ""
        table.add_row(profile, status)

    console.print(table)
    new_line()


@app.command("show")
@handle_errors
def show_profile(
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            help="Profile to show (uses active if not specified)",
        ),
    ] = "",
    all_sections: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Show all sections including defaults",
        ),
    ] = False,
    expand_vars: Annotated[
        bool,
        typer.Option(
            "--expand",
            help="Expand environment variable references",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
) -> None:
    """Show configuration for a profile.

    By default shows env var references like ${ARIZE_API_KEY}.
    Use --expand to show expanded values.
    Use --all to show all sections including defaults.
    """
    # Use profile from context if not specified
    config = ConfigManager.load(profile, expand_vars)

    # Display configuration
    text_bold(f"\nProfile: {profile}")
    if profile == ConfigManager.get_active_profile():
        console.print("[green](active)[/green]")
    new_line()

    # Determine which sections to show
    default_config = Config(
        auth=AuthConfig(api_key="dummy"),
    )

    def is_customized(section_name: str) -> bool:
        """Check if a section has customized (non-default) values."""
        if section_name == "profile" or section_name == "auth":
            return True  # Always show these
        config_section = getattr(config, section_name)
        default_section = getattr(default_config, section_name, None)
        if default_section is None:
            return True
        return config_section != default_section

    # Auth section (always shown)
    emphasis("Authentication:")
    key = config.auth.api_key
    key = key if _is_env_var_ref(key) else mask(key)
    text(f"  API Key: {key}")

    # Routing section
    if all_sections or is_customized("routing"):
        emphasis("\nRouting:")
        if config.routing.region:
            text(f"  Region: {config.routing.region}")
        if config.routing.single_host:
            text(f"  Single Host: {config.routing.single_host}")
        if config.routing.single_port:
            text(f"  Single Port: {config.routing.single_port}")
        if config.routing.base_domain:
            text(f"  Base Domain: {config.routing.base_domain}")
        if not (
            config.routing.region
            or config.routing.single_host
            or config.routing.base_domain
        ):
            text(f"  API Scheme: {config.routing.api_scheme}")
            text(f"  API Host: {config.routing.api_host}")
            text(f"  OTLP Scheme: {config.routing.otlp_scheme}")
            text(f"  OTLP Host: {config.routing.otlp_host}")
            text(f"  Flight Scheme: {config.routing.flight_scheme}")
            text(f"  Flight Host: {config.routing.flight_host}")
            text(f"  Flight Port: {config.routing.flight_port}")

    # Transport section
    if all_sections or is_customized("transport"):
        emphasis("\nTransport:")
        text(f"  Stream Max Workers: {config.transport.stream_max_workers}")
        text(
            f"  Stream Max Queue Bound: {config.transport.stream_max_queue_bound}"
        )
        text(
            f"  PyArrow Max Chunksize: {config.transport.pyarrow_max_chunksize}"
        )
        text(
            f"  Max HTTP Payload Size: {config.transport.max_http_payload_size_mb} MB"
        )

    # Security section
    if all_sections or is_customized("security"):
        emphasis("\nSecurity:")
        val = config.security.request_verify
        if _is_bool(str(config.security.request_verify)):
            val = bool(config.security.request_verify)
        text(f"  Request Verify: {val}")

    # Storage section
    if all_sections or is_customized("storage"):
        emphasis("\nStorage:")
        text(f"  Directory: {config.storage.directory}")
        text(f"  Cache: {config.storage.cache_enabled}")

    # Output section (always shown)
    emphasis("\nOutput:")
    text(f"  Format: {config.output.format}")

    new_line()


@app.command("use")
@handle_errors
def use_profile(
    profile: Annotated[
        str,
        typer.Argument(help="Profile name to activate"),
    ],
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
) -> None:
    """Switch to a different configuration profile.

    Makes the specified profile active for all future commands.
    """
    ConfigManager.set_active_profile(profile)
    success(f"Switched to profile '{profile}'")


@app.command("delete")
@handle_errors
def delete_profile(
    profile: Annotated[
        str,
        typer.Argument(help="Profile name to delete"),
    ],
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Skip confirmation",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
) -> None:
    """Delete a configuration profile.

    Cannot delete the default profile or currently active profile.
    """
    if not force and not confirm(
        f"Delete profile '{profile}'?",
        default=False,
    ):
        info("Profile not deleted")
        raise typer.Exit()

    ConfigManager.delete_profile(profile)
    success(f"Deleted profile '{profile}'")


def _is_bool(val: str) -> bool:
    """Check if a string represents a boolean value."""
    return val.lower() in ("true", "false")


def _is_env_var_ref(val: str) -> bool:
    """Check if a string is an environment variable reference."""
    return val.startswith("${") and val.endswith("}")
