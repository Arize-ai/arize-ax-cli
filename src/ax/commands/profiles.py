"""Configuration management commands."""

import os
import re
from typing import Annotated, Literal, cast

import questionary
import typer
from rich.console import Console
from rich.table import Table

from ax.ascii_art import WELCOME_BANNER
from ax.commands.auth import perform_oauth_login
from ax.config.manager import ConfigManager
from ax.config.schema import (
    AuthConfig,
    AuthMethod,
    Config,
    OutputConfig,
    ProfileConfig,
    RoutingConfig,
)
from ax.config.setup import (
    create_config_from_env_vars,
    create_config_from_flags,
    create_config_from_toml,
    create_config_interactively,
    detect_env_vars,
    merge_config_with_flags,
    routing_from_env,
)
from ax.core.decorators import handle_errors
from ax.core.exceptions import ConfigError
from ax.utils.console import (
    confirm,
    emphasis,
    info,
    mask,
    new_line,
    setup_logging,
    success,
    text,
    text_dimmed,
)

# Create profile subcommand app
app = typer.Typer(
    name="profiles",
    help="Manage Arize CLI configuration profiles",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)

console = Console(stderr=True)


@app.command("create")
@handle_errors
def create(
    profile_name: Annotated[
        str,
        typer.Argument(
            help=("Profile name"),
        ),
    ] = "",
    from_file: Annotated[
        str | None,
        typer.Option(
            "--from-file",
            "-f",
            help="Path to a TOML config file to load values from.",
        ),
    ] = None,
    # --- Auth ---
    api_key: Annotated[
        str | None,
        typer.Option("--api-key", help="Arize API key."),
    ] = None,
    auth_method: Annotated[
        AuthMethod | None,
        typer.Option(
            "--auth-method",
            help="Authentication method to use. If omitted, prompts interactively.",
        ),
    ] = None,
    # --- Routing ---
    region: Annotated[
        str | None,
        typer.Option("--region", help="Routing region (e.g. us-east-1b)."),
    ] = None,
    single_host: Annotated[
        str | None,
        typer.Option(
            "--single-host",
            help="Single endpoint host for on-prem deployments (e.g. arize.yourcompany.com).",
        ),
    ] = None,
    single_port: Annotated[
        str | None,
        typer.Option(
            "--single-port",
            help="Single endpoint port for on-prem deployments (e.g. 443).",
        ),
    ] = None,
    # --- Output ---
    output_format: Annotated[
        str | None,
        typer.Option(
            "--output-format", help="Output format: table, json, csv, parquet."
        ),
    ] = None,
    # --- Misc ---
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
    utm_params: Annotated[
        str | None,
        typer.Option("--utm-params", hidden=True),
    ] = None,
) -> None:
    """Create Arize CLI configuration interactively or from flags/file.

    Creates a new configuration profile with API key or OAuth credentials,
    routing defaults, and preferences. Non-interactive CLI flags are limited
    to --api-key, --auth-method, --region, --single-host, --single-port, and
    --output-format; use --from-file (TOML) or interactive setup for hosts,
    storage, security, transport, and other sections. Detects existing ARIZE_*
    environment variables when running interactively (only when neither flags
    nor --from-file are used).

    Precedence (highest to lowest): CLI flags > --from-file (TOML) >
    interactive prompts.
    """
    setup_logging(verbose)

    # Typer validates auth_method against the AuthMethod enum; only the
    # cross-field check (oauth + --api-key) needs to live here.
    if auth_method == AuthMethod.OAUTH and api_key is not None:
        raise ConfigError(
            "--auth-method oauth and --api-key are mutually exclusive. "
            "Choose one authentication method."
        )

    existing_profiles = ConfigManager.list_profiles()

    if existing_profiles:
        emphasis("Create a new configuration profile")
        text(f"existing profiles: {', '.join(existing_profiles)}\n")
    else:
        new_line()
        text(WELCOME_BANNER)
        new_line()
        emphasis("Welcome to Arize AX CLI!")
        text("No configuration profile found. Let's set one up!\n")

    # --- Build flat flags dict (only explicitly-set values) ---
    # Note: auth_method is handled separately and not included in flat_flags.
    flat_flags = {
        k: v
        for k, v in {
            "api_key": api_key,
            "region": region,
            "single_host": single_host,
            "single_port": single_port,
            "output_format": output_format,
        }.items()
        if v is not None
    }

    # --- Resolve profile name ---
    if profile_name:
        profile = profile_name
    else:
        default_exists = ConfigManager.exists("default")
        # If this is the first profile, we can offer "default" as the default name;
        # otherwise require explicit name to avoid confusion.
        if default_exists:
            profile = typer.prompt("profile name")
        else:
            profile = typer.prompt("profile name", default="default")
        new_line()

    # Validate profile name (alphanumeric, hyphens, and underscores)
    if not re.match(r"^[A-Za-z0-9_-]+$", profile):
        raise ConfigError(
            f"Invalid profile name: {profile!r}. "
            "Profile names may only contain letters, numbers, hyphens, and underscores."
        )

    # Check if profile already exists
    if ConfigManager.exists(profile):
        # Non-interactive sources (flags, --auth-method, or --from-file): do not
        # prompt to overwrite; raise so scripts fail clearly.
        if flat_flags or auth_method or from_file:
            raise ConfigError(
                f"Profile '{profile}' already exists. You can use a different name, "
                "edit the profile using `ax profiles update <name>`, or "
                "remove it using 'ax profiles delete <name>'."
            )
        if not confirm(
            f"Profile '{profile}' already exists. Overwrite?",
            default=True,
        ):
            info("Configuration unchanged")
            raise typer.Exit()

    # --- Choose creation path ---
    if from_file:
        config = create_config_from_toml(from_file, profile)
        if flat_flags:
            config = merge_config_with_flags(config, flat_flags)
    elif auth_method == AuthMethod.OAUTH:
        # Explicit OAuth path: build routing from flags, then browser login.
        routing_flags = {
            k: v
            for k, v in {
                "region": region,
                "single_host": single_host,
                "single_port": single_port,
            }.items()
            if v is not None
        }
        routing_cfg = RoutingConfig(**routing_flags)
        base_url = routing_cfg.resolve_app_url()

        oauth_creds = perform_oauth_login(
            base_url=base_url, utm_params=utm_params
        )
        auth_cfg = AuthConfig(auth_method=AuthMethod.OAUTH, oauth=oauth_creds)

        # output_format is `str | None` from typer but OutputConfig.format
        # is a Literal — Pydantic validates the value at runtime.
        output_cfg = (
            OutputConfig(
                format=cast(
                    "Literal['table', 'json', 'csv', 'parquet']", output_format
                )
            )
            if output_format
            else OutputConfig()
        )
        config = Config(
            profile=ProfileConfig(name=profile),
            auth=auth_cfg,
            routing=routing_cfg,
            output=output_cfg,
        )
    elif flat_flags:
        config = create_config_from_flags(profile, flat_flags)
    else:
        # Fully interactive flow: prompt for auth method first (if not given via flag)
        if auth_method is None:
            chosen = questionary.select(
                "Which authentication method?",
                choices=[
                    questionary.Choice("API key", value=AuthMethod.API_KEY),
                    questionary.Choice(
                        "OAuth (browser login)", value=AuthMethod.OAUTH
                    ),
                ],
                default=AuthMethod.API_KEY,
            ).ask()
            if chosen is None:
                raise typer.Abort()
            auth_method = chosen

        # Detect ARIZE_* env vars relevant to this auth method. OAuth
        # credentials are never env-derived, so api_key is excluded for OAuth.
        detected_env_vars = detect_env_vars()
        if auth_method == AuthMethod.OAUTH:
            detected_env_vars = {
                k: v for k, v in detected_env_vars.items() if k != "api_key"
            }

        use_env_vars = False
        if detected_env_vars:
            emphasis("Environment Variable Detection\n")
            for field, env_var in detected_env_vars.items():
                value = os.environ.get(env_var, "")
                if field == "api_key":
                    value = mask(value)
                console.print(
                    f"  [green]✓[/green] Detected {env_var} = {value}"
                )
            console.print()
            use_env_vars = confirm(
                "Create config from detected environment variables?",
                default=True,
            )
            console.print()

        # Build the base config the same way for both auth methods. For OAuth
        # the AuthConfig is a logged-out shell at this point — we'll fill in
        # tokens after running the browser flow below.
        if use_env_vars:
            if auth_method == AuthMethod.OAUTH:
                placeholder_auth = AuthConfig(auth_method=AuthMethod.OAUTH)
            else:
                api_key_env = detected_env_vars["api_key"]
                placeholder_auth = AuthConfig(
                    auth_method=AuthMethod.API_KEY,
                    api_key=f"${{{api_key_env}}}",
                )
            config = create_config_from_env_vars(
                profile, detected_env_vars, placeholder_auth
            )
        else:
            # auth_method is validated above to be 'api-key' or 'oauth'.
            config = create_config_interactively(profile, auth_method)

        # For OAuth, run the browser flow last (before save) so a failed
        # login does not leave a half-configured profile on disk. Resolve
        # routing now in case it contains ${VAR} refs.
        if auth_method == AuthMethod.OAUTH:
            base_url = (
                routing_from_env(detected_env_vars).resolve_app_url()
                if use_env_vars
                else config.routing.resolve_app_url()
            )
            oauth_creds = perform_oauth_login(
                base_url=base_url, utm_params=utm_params
            )
            config = config.model_copy(
                update={
                    "auth": AuthConfig(
                        auth_method=AuthMethod.OAUTH, oauth=oauth_creds
                    )
                }
            )

    # --- Save and finalize ---
    ConfigManager.save(config, profile)

    new_line()
    success(f"Configuration saved to profile '{profile}'")

    ConfigManager.set_active_profile(profile)
    success(f"Active profile set to '{profile}'")

    new_line()
    text_dimmed("You're ready to go! Try: ax spaces list")


@app.command("update")
@handle_errors
def update(
    profile_arg: Annotated[
        str,
        typer.Argument(
            help="Profile to update (uses active if omitted).",
        ),
    ] = "",
    from_file: Annotated[
        str | None,
        typer.Option(
            "--from-file",
            "-f",
            help="Path to a TOML config file. Completely replaces the existing profile.",
        ),
    ] = None,
    # --- Auth ---
    api_key: Annotated[
        str | None,
        typer.Option("--api-key", help="Arize API key."),
    ] = None,
    # --- Routing ---
    region: Annotated[
        str | None,
        typer.Option("--region", help="Routing region (e.g. us-east-1b)."),
    ] = None,
    single_host: Annotated[
        str | None,
        typer.Option(
            "--single-host",
            help="Single endpoint host for on-prem deployments (e.g. arize.yourcompany.com).",
        ),
    ] = None,
    single_port: Annotated[
        str | None,
        typer.Option(
            "--single-port",
            help="Single endpoint port for on-prem deployments (e.g. 443).",
        ),
    ] = None,
    # --- Output ---
    output_format: Annotated[
        str | None,
        typer.Option(
            "--output-format", help="Output format: table, json, csv, parquet."
        ),
    ] = None,
    # --- Misc ---
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logs."),
    ] = False,
) -> None:
    """Update an existing configuration profile.

    CLI flags are limited to --api-key, --region, --single-host, --single-port,
    and --output-format; use --from-file (TOML) for other fields. With
    --from-file, the profile is replaced by the file contents; any flags you
    pass are applied on top (CLI overrides file). With flags only, only the
    specified fields are updated; all others are preserved.
    """
    setup_logging(verbose)

    profile = profile_arg or ConfigManager.get_active_profile()

    if not ConfigManager.exists(profile):
        if profile:
            raise ConfigError(
                f"Profile '{profile}' does not exist.\n"
                "Run 'ax profiles create' to create one."
            )
        raise ConfigError(
            "No active profile configured.\n"
            "Run 'ax profiles create' to create one."
        )

    flat_flags = {
        k: v
        for k, v in {
            "api_key": api_key,
            "region": region,
            "single_host": single_host,
            "single_port": single_port,
            "output_format": output_format,
        }.items()
        if v is not None
    }

    if not from_file and not flat_flags:
        raise ConfigError(
            "Nothing to update. Provide --from-file or at least one field flag."
        )

    if from_file:
        config = create_config_from_toml(from_file, profile)
        if flat_flags:
            config = merge_config_with_flags(config, flat_flags)
    else:
        existing = ConfigManager.load(profile)
        config = merge_config_with_flags(existing, flat_flags)

    ConfigManager.save(config, profile)
    new_line()
    success(f"Profile '{profile}' updated.")


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
    setup_logging(verbose)
    profiles = ConfigManager.list_profiles()

    if not profiles:
        info("No profiles found. Run 'ax profiles create' to create one.")
        raise typer.Exit()

    active = ConfigManager.get_active_profile()

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Profile")

    for profile in profiles:
        if profile == active:
            table.add_row(f"[bold]{profile}[/bold] [green]●[/green]")
        else:
            table.add_row(profile)

    console.print(table)
    new_line()


@app.command("show")
@handle_errors
def show_profile(
    profile_arg: Annotated[
        str,
        typer.Argument(
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
    setup_logging(verbose)
    config = ConfigManager.load(profile_arg, expand_vars)
    profile_name = config.profile.name

    from rich.panel import Panel

    # Display profile header
    active_badge = (
        " [green]● active[/green]"
        if profile_name == ConfigManager.get_active_profile()
        else ""
    )
    new_line()
    console.print(f"[bold]Profile:[/bold] {profile_name}{active_badge}")
    new_line()

    # Sentinel Config used only as a baseline for diffing — the name and
    # api_key are placeholders and never written or displayed.
    default_config = Config(
        profile=ProfileConfig(name="_default"),
        auth=AuthConfig(auth_method=AuthMethod.API_KEY, api_key="dummy"),
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

    def kv(label: str, value: object) -> str:
        return f"[bold cyan]{label}:[/bold cyan] {value}"

    # Build panel lines
    lines: list[str] = []

    # Auth section (always shown)
    lines.append("[bold]Authentication[/bold]")
    if config.auth.uses_oauth:
        lines.append(kv("  Method", "OAuth (browser login)"))
        if config.auth.is_logged_out:
            lines.append(
                kv(
                    "  Status",
                    "[yellow]logged out — run 'ax auth login' to sign in[/yellow]",
                )
            )
        else:
            # Invariant: uses_oauth and not is_logged_out → oauth populated.
            oauth = config.auth.oauth
            assert oauth is not None  # noqa: S101
            lines.append(kv("  User", oauth.user_email))
            lines.append(kv("  Access token", mask(oauth.access_token)))
            lines.append(kv("  Refresh token", mask(oauth.refresh_token)))
            lines.append(kv("  Token expires at", oauth.expires_at.isoformat()))
    else:
        lines.append(kv("  Method", "API key"))
        # api-key profiles always have a non-empty api_key (enforced by
        # AuthConfig._validate_method_consistency).
        key = config.auth.api_key
        assert key is not None  # noqa: S101
        key = key if _is_env_var_ref(key) else mask(key)
        lines.append(kv("  API Key", key))

    # Output section (always shown)
    lines.append("")
    lines.append("[bold]Output[/bold]")
    lines.append(kv("  Format", config.output.format))

    # Routing section
    if all_sections or is_customized("routing"):
        lines.append("")
        lines.append("[bold]Routing[/bold]")
        if config.routing.region:
            lines.append(kv("  Region", config.routing.region))
        if config.routing.single_host:
            lines.append(kv("  Single Host", config.routing.single_host))
        if config.routing.single_port:
            lines.append(kv("  Single Port", config.routing.single_port))
        if config.routing.base_domain:
            lines.append(kv("  Base Domain", config.routing.base_domain))
        if not (
            config.routing.region
            or config.routing.single_host
            or config.routing.base_domain
        ):
            lines.append(kv("  API Scheme", config.routing.api_scheme))
            lines.append(kv("  API Host", config.routing.api_host))
            lines.append(kv("  OTLP Scheme", config.routing.otlp_scheme))
            lines.append(kv("  OTLP Host", config.routing.otlp_host))
            lines.append(kv("  Flight Scheme", config.routing.flight_scheme))
            lines.append(kv("  Flight Host", config.routing.flight_host))
            lines.append(kv("  Flight Port", config.routing.flight_port))

    # Transport section
    if all_sections or is_customized("transport"):
        lines.append("")
        lines.append("[bold]Transport[/bold]")
        lines.append(
            kv("  Stream Max Workers", config.transport.stream_max_workers)
        )
        lines.append(
            kv(
                "  Stream Max Queue Bound",
                config.transport.stream_max_queue_bound,
            )
        )
        lines.append(
            kv(
                "  PyArrow Max Chunksize",
                config.transport.pyarrow_max_chunksize,
            )
        )
        lines.append(
            kv(
                "  Max HTTP Payload Size",
                f"{config.transport.max_http_payload_size_mb} MB",
            )
        )

    # Security section
    if all_sections or is_customized("security"):
        lines.append("")
        lines.append("[bold]Security[/bold]")
        val = config.security.request_verify
        if isinstance(val, str) and _is_bool(val):
            val = val.lower() == "true"
        lines.append(kv("  Request Verify", val))

    console.print(
        Panel(
            "\n".join(lines),
            title=f"[bold]Profile: {profile_name}[/bold]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
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
    setup_logging(verbose)
    ConfigManager.set_active_profile(profile)
    success(f"Switched to profile '{profile}'")


@app.command("validate")
@handle_errors
def validate_profile(
    profile: Annotated[
        str,
        typer.Argument(
            help="Profile to validate (uses active if not specified)",
        ),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose logs",
        ),
    ] = False,
) -> None:
    """Validate a configuration profile.

    Checks the profile for missing or incorrect configuration and reports
    any issues found. Run 'ax profiles create' to fix problems.
    """
    setup_logging(verbose)
    profile = profile or ConfigManager.get_active_profile()
    try:
        ConfigManager.load(profile)
        success(f"Profile '{profile}' is valid.")
    except ConfigError as e:
        console.print(f"[red]Invalid profile '{profile}':[/red] {e}")
        info("Run 'ax profiles create' to recreate the profile.")
        raise typer.Exit(code=1)  # noqa: B904


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

    Cannot delete the currently active profile.
    """
    setup_logging(verbose)

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


def _is_env_var_ref(val: str | None) -> bool:
    """Check if a string is an environment variable reference."""
    if not val:
        return False
    return val.startswith("${") and val.endswith("}")
