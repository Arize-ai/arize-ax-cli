"""Configuration schema using Pydantic models."""

from pathlib import Path
from typing import Literal

from arize import Region, SDKConfiguration
from pydantic import BaseModel, Field, field_validator, model_validator


class ProfileConfig(BaseModel):
    """Profile metadata."""

    name: str = Field(default="default", description="Profile name")


class AuthConfig(BaseModel):
    """Authentication credentials."""

    api_key: str = Field(description="Arize API key")

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate API key is not empty.

        Args:
            v: API key value

        Returns:
            Validated API key

        Raises:
            ValueError: If API key is empty
        """
        if not v or not v.strip():
            raise ValueError("api_key cannot be empty")
        return v.strip()


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

        # Validate as a literal region
        valid_regions = Region.list_regions()
        if v not in valid_regions:
            raise ValueError(
                f"Invalid region: {v}. Must be empty string or one of: "
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


class TransportConfig(BaseModel):
    """Transport and performance settings."""

    stream_max_workers: int | str = Field(default=8)
    stream_max_queue_bound: int | str = Field(default=5_000)
    pyarrow_max_chunksize: int | str = Field(default=10_000)
    max_http_payload_size_mb: int | str = Field(default=8)


class SecurityConfig(BaseModel):
    """Security settings."""

    request_verify: bool | str = Field(default=True)


class StorageConfig(BaseModel):
    """Storage and caching configuration."""

    directory: str = Field(default="~/.arize")
    cache_enabled: bool = Field(default=True)

    @property
    def expanded_directory(self) -> Path:
        """Get expanded directory path.

        Returns:
            Expanded directory path
        """
        return Path(self.directory).expanduser()

    @property
    def cache_dir(self) -> Path:
        """Get computed cache directory path.

        Returns:
            Cache directory path
        """
        return self.expanded_directory / "cache"


class OutputConfig(BaseModel):
    """Output formatting (CLI-specific)."""

    format: Literal["table", "json", "csv", "parquet"] = Field(default="table")


class Config(BaseModel):
    """Root configuration model."""

    profile: ProfileConfig = Field(default_factory=ProfileConfig)
    auth: AuthConfig
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    transport: TransportConfig = Field(default_factory=TransportConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    model_config = {"extra": "forbid"}

    def to_sdk_config(self) -> SDKConfiguration:
        """Convert CLI config to SDK config.

        Returns:
            SDKConfig instance
        """
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
            api_key=self.auth.api_key,
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
            request_verify=bool(self.security.request_verify),
        )
