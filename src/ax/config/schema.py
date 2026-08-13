"""Configuration schema using Pydantic models."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from arize import Region, SDKConfiguration
from pydantic import BaseModel, Field, field_validator, model_validator

from ax.core.headers import cli_default_headers


class AuthMethod(StrEnum):
    """Authentication method a profile uses."""

    API_KEY = "api-key"
    OAUTH = "oauth"


def _str_to_bool(value: bool | str) -> bool:
    """Convert bool or string to bool, parsing "true"/"false" strings correctly."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class ProfileConfig(BaseModel):
    """Profile metadata."""

    name: str = Field(description="Profile name")

    @field_validator("name")
    @classmethod
    def _nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("profile name must not be empty")
        return v.strip()


class OAuthCredentials(BaseModel):
    """OAuth tokens stored after a successful login."""

    access_token: str = Field(description="OAuth access token (JWT, RS256)")
    refresh_token: str = Field(description="OAuth refresh token (JWT, RS256)")
    expires_at: datetime = Field(description="Access token expiry (UTC)")
    user_email: str = Field(description="Authenticated user email")

    @field_validator("access_token", "refresh_token", "user_email")
    @classmethod
    def _nonempty(cls, v: str) -> str:
        """Validate that the field is not empty.

        Args:
            v: Field value

        Returns:
            Stripped field value

        Raises:
            ValueError: If the field is empty or whitespace-only
        """
        if not v or not v.strip():
            raise ValueError("must not be empty")
        return v.strip()


class AuthConfig(BaseModel):
    """Authentication credentials — exactly one method per profile.

    The chosen method is persisted via ``auth_method`` so a profile remembers
    its identity even when its credentials are cleared (logged out).

    Valid combinations:
      * auth_method="api-key", api_key=non-empty, oauth=None          → API-key
      * auth_method="oauth",   api_key=None,      oauth=tokens         → OAuth, signed in
      * auth_method="oauth",   api_key=None,      oauth=None           → OAuth, logged out

    Backwards compatibility: legacy profiles without auth_method are inferred
    from whichever credential field is populated.
    """

    auth_method: AuthMethod = Field(
        description="The authentication method this profile uses."
    )
    api_key: str | None = Field(default=None, description="Arize API key")
    oauth: OAuthCredentials | None = Field(
        default=None, description="OAuth tokens (None = logged out)"
    )

    # TODO: remove once all users have migrated to profiles that include
    # an explicit ``auth_method`` field (i.e. have re-saved their profile
    # via the current CLI at least once).
    @model_validator(mode="before")
    @classmethod
    def _infer_legacy_method(cls, data: object) -> object:
        """Backfill ``auth_method`` for profiles written before the discriminator existed.

        Older CLI versions wrote profiles without an explicit ``auth_method``
        field. Loading those profiles after we made the field required would
        fail validation, so we infer it here from whichever credential block
        is populated.
        """
        if isinstance(data, dict) and not data.get("auth_method"):
            if data.get("api_key"):
                data["auth_method"] = AuthMethod.API_KEY
            elif data.get("oauth"):
                data["auth_method"] = AuthMethod.OAUTH
        return data

    @field_validator("api_key")
    @classmethod
    def _validate_api_key(cls, v: str | None) -> str | None:
        """Validate API key is not empty when provided."""
        if v is None:
            return None
        if not v.strip():
            raise ValueError("api_key cannot be empty")
        return v.strip()

    @model_validator(mode="after")
    def _validate_method_consistency(self) -> "AuthConfig":
        """Enforce that fields match the declared auth_method."""
        if self.auth_method == AuthMethod.API_KEY:
            if not self.api_key:
                raise ValueError(
                    "auth_method='api-key' requires a non-empty api_key"
                )
            if self.oauth is not None:
                raise ValueError(
                    "auth_method='api-key' must not have an oauth section"
                )
        else:  # AuthMethod.OAUTH
            if self.api_key is not None:
                raise ValueError("auth_method='oauth' must not have an api_key")
            # oauth may be None (logged out) or populated (signed in)
        return self

    @property
    def uses_oauth(self) -> bool:
        """Return True if this profile uses OAuth as its auth method."""
        return self.auth_method == AuthMethod.OAUTH

    @property
    def is_logged_out(self) -> bool:
        """Return True only for OAuth profiles whose tokens have been cleared.

        API-key profiles always have credentials present (api_key is required),
        so they cannot be in a logged-out state.
        """
        return self.auth_method == AuthMethod.OAUTH and self.oauth is None


REGION_ALIASES: dict[str, str] = {
    "US": Region.US_EAST_1B.value,
    "CA": Region.CA_CENTRAL_1A.value,
    "EU": Region.EU_WEST_1A.value,
}


class RoutingConfig(BaseModel):
    """Routing strategy (mutually exclusive options)."""

    # Region override
    region: str = Field(default="", description="Region-based routing")

    # Single endpoint override (on-prem)
    single_host: str = Field(default="", description="Single host override")
    single_port: str = Field(default="", description="Single port override")

    # Base domain override (Private Connect)
    base_domain: str = Field(
        default="", description="Base domain for Private Connect"
    )

    # Custom hosts, ports & schemes
    api_host: str = Field(
        default="api.arize.com", description="Custom API host"
    )
    api_scheme: str = Field(default="https", description="Custom API scheme")
    app_host: str = Field(
        default="app.arize.com",
        description="Custom Arize app (OAuth login) host",
    )
    app_scheme: str = Field(
        default="https", description="Custom Arize app scheme"
    )
    otlp_host: str = Field(
        default="otlp.arize.com", description="Custom OTLP host"
    )
    otlp_scheme: str = Field(default="https", description="Custom OTLP scheme")
    flight_host: str = Field(
        default="flight.arize.com", description="Custom Flight host"
    )
    flight_port: str = Field(default="443", description="Custom Flight port")
    flight_scheme: str = Field(
        default="grpc+tls", description="Custom Flight scheme"
    )

    @field_validator("region")
    @classmethod
    def validate_region(cls, v: str) -> str:
        """Validate region value.

        Args:
            v: Region string

        Returns:
            Validated region string

        Raises:
            ValueError: If region is invalid
        """
        if v == "":
            return v

        # Allow environment variable references
        if v.startswith("${") and v.endswith("}"):
            return v

        # Resolve friendly aliases (e.g. "US", "EU") to canonical zone IDs
        v = REGION_ALIASES.get(v.upper(), v)

        # Validate as a literal region
        valid_regions = Region.list_regions()
        if v not in valid_regions:
            raise ValueError(
                f"Invalid region: {v}. Must be empty string or one of 'US', 'CA', 'EU', "
                f"{', '.join(valid_regions)}"
            )
        return v

    @model_validator(mode="after")
    def validate_mutually_exclusive(self) -> "RoutingConfig":
        """Ensure only one routing strategy is active.

        Returns:
            Validated RoutingConfig

        Raises:
            ValueError: If multiple routing strategies are active
        """
        has_region = bool(self.region)
        has_single = bool(self.single_host) or bool(self.single_port)
        has_base_domain = bool(self.base_domain)

        active_count = sum([has_region, has_single, has_base_domain])
        if active_count > 1:
            raise ValueError(
                "Only one routing option allowed: region, single_host/port, "
                "or base_domain"
            )
        return self

    def resolve_app_url(self) -> str:
        """Derive the Arize app (OAuth login) URL from this routing config.

        Precedence (first match wins):
          1. ``single_host`` (on-prem / testing override) — uses app_scheme +
             single_host, appending ``:single_port`` when a port is set
          2. ``base_domain`` (Private Connect) — "https://app.<base_domain>"
          3. ``region`` (e.g., "eu-prod") — "https://app.<region>.arize.com"
          4. Explicit ``app_host`` + ``app_scheme`` fields — default "https://app.arize.com"
        """
        if self.single_host:
            # single_port is part of the single-endpoint override: on-prem
            # deployments serve the app (and thus OAuth) on this host:port.
            # Dropping it here makes the browser flow fall back to the scheme
            # default (80/443) even though the user configured e.g. :4040.
            if self.single_port:
                return (
                    f"{self.app_scheme}://{self.single_host}:{self.single_port}"
                )
            return f"{self.app_scheme}://{self.single_host}"
        if self.base_domain:
            return f"https://app.{self.base_domain}"
        if self.region:
            return f"https://app.{self.region}.arize.com"
        return f"{self.app_scheme}://{self.app_host}"

    # @model_validator(mode="after")
    # def apply_overrides(self) -> "RoutingConfig":
    #     """Apply routing overrides by clearing custom endpoints.
    #
    #     Returns:
    #         Updated RoutingConfig
    #     """
    #     has_region = bool(self.region)
    #     has_single = bool(self.single_host) or bool(self.single_port)
    #     has_base_domain = bool(self.base_domain)
    #
    #     active_count = sum([has_region, has_single, has_base_domain])
    #     if active_count > 0:
    #         self.api_host = ""
    #         self.otlp_host = ""
    #         self.flight_host = ""
    #         self.flight_port = ""
    #
    #     return self


def _validate_int_or_env_var(v: int | str) -> int | str:
    """Validate that a value is an int or an environment variable reference."""
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
        return v
    try:
        return int(v)
    except (ValueError, TypeError) as e:
        raise ValueError(
            f"Expected an integer or an environment variable reference (e.g., ${{MY_VAR}}), got: {v!r}"
        ) from e


class TransportConfig(BaseModel):
    """Transport and performance settings."""

    stream_max_workers: int | str = Field(default=8)
    stream_max_queue_bound: int | str = Field(default=5_000)
    pyarrow_max_chunksize: int | str = Field(default=10_000)
    max_http_payload_size_mb: int | str = Field(default=8)

    @field_validator(
        "stream_max_workers",
        "stream_max_queue_bound",
        "pyarrow_max_chunksize",
        "max_http_payload_size_mb",
        mode="before",
    )
    @classmethod
    def validate_int_fields(cls, v: int | str) -> int | str:
        """Validate that transport int fields are integers or env var references."""
        return _validate_int_or_env_var(v)


class SecurityConfig(BaseModel):
    """Security settings."""

    request_verify: bool | str = Field(default=True)


class OutputConfig(BaseModel):
    """Output formatting (CLI-specific)."""

    format: Literal["table", "json", "csv", "parquet"] = Field(default="table")


class UpdateConfig(BaseModel):
    """Update check configuration."""

    check_interval_hours: float = Field(
        default=6.0,
        gt=0,
        description="Hours between PyPI version checks",
    )
    enabled: bool = Field(
        default=True,
        description="Enable background update checks",
    )


class Config(BaseModel):
    """Root configuration model."""

    profile: ProfileConfig
    auth: AuthConfig
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    transport: TransportConfig = Field(default_factory=TransportConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    update: UpdateConfig = Field(default_factory=UpdateConfig)

    model_config = {"extra": "ignore"}

    @property
    def request_verify(self) -> bool:
        """Return security.request_verify as a bool."""
        return _str_to_bool(self.security.request_verify)

    def to_sdk_config(self, bearer: str | None = None) -> SDKConfiguration:
        """Convert CLI config to SDK config.

        Args:
            bearer: the auth credential to pass to the SDK. If omitted, uses
              self.auth.api_key (api-key profiles). For OAuth profiles, callers MUST
              pass ``bearer=get_active_bearer(self.auth, profile_path=...)``.

        Returns:
            SDKConfig instance

        Raises:
            ValueError: If no bearer can be determined (OAuth profile without bearer override)
        """
        effective = bearer if bearer is not None else self.auth.api_key
        if effective is None:
            raise ValueError(
                "to_sdk_config() on an OAuth profile requires bearer= "
                "(use ax.auth.bearer.get_active_bearer)"
            )
        region = (
            Region(self.routing.region) if self.routing.region else Region.UNSET
        )
        single_port = (
            int(self.routing.single_port) if self.routing.single_port else 0
        )
        flight_port = (
            int(self.routing.flight_port) if self.routing.flight_port else 0
        )

        return SDKConfiguration(
            api_key=effective,
            region=region,
            single_host=self.routing.single_host,
            single_port=single_port,
            base_domain=self.routing.base_domain,
            api_host=self.routing.api_host,
            api_scheme=self.routing.api_scheme,
            otlp_host=self.routing.otlp_host,
            otlp_scheme=self.routing.otlp_scheme,
            flight_host=self.routing.flight_host,
            flight_port=flight_port,
            flight_scheme=self.routing.flight_scheme,
            stream_max_workers=int(self.transport.stream_max_workers),
            stream_max_queue_bound=int(self.transport.stream_max_queue_bound),
            pyarrow_max_chunksize=int(self.transport.pyarrow_max_chunksize),
            max_http_payload_size_mb=int(
                self.transport.max_http_payload_size_mb
            ),
            request_verify=self.request_verify,
            default_headers=cli_default_headers(),
        )
