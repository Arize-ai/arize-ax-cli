"""Tests for configuration schema module."""

from pathlib import Path

import pytest
from arize import Region, SDKConfiguration
from pydantic import ValidationError

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


class TestProfileConfig:
    """Tests for ProfileConfig model."""

    def test_default_profile_name(self) -> None:
        """Test that default profile name is 'default'."""
        profile = ProfileConfig()
        assert profile.name == "default"

    def test_custom_profile_name(self) -> None:
        """Test creating profile with custom name."""
        profile = ProfileConfig(name="production")
        assert profile.name == "production"


class TestAuthConfig:
    """Tests for AuthConfig model."""

    def test_valid_api_key(self) -> None:
        """Test creating auth config with valid API key."""
        auth = AuthConfig(api_key="ak-test123")
        assert auth.api_key == "ak-test123"

    def test_api_key_stripped(self) -> None:
        """Test that API key is stripped of whitespace."""
        auth = AuthConfig(api_key="  ak-test123  ")
        assert auth.api_key == "ak-test123"

    def test_empty_api_key_raises_error(self) -> None:
        """Test that empty API key raises ValidationError."""
        with pytest.raises(ValidationError, match="api_key cannot be empty"):
            AuthConfig(api_key="")

    def test_whitespace_only_api_key_raises_error(self) -> None:
        """Test that whitespace-only API key raises ValidationError."""
        with pytest.raises(ValidationError, match="api_key cannot be empty"):
            AuthConfig(api_key="   ")


class TestRoutingConfig:
    """Tests for RoutingConfig model."""

    def test_default_routing_config(self) -> None:
        """Test default routing config values."""
        routing = RoutingConfig()
        assert routing.region == ""
        assert routing.single_host == ""
        assert routing.single_port == ""
        assert routing.base_domain == ""
        assert routing.api_host == "api.arize.com"
        assert routing.api_scheme == "https"
        assert routing.otlp_host == "otlp.arize.com"
        assert routing.otlp_scheme == "https"
        assert routing.flight_host == "flight.arize.com"
        assert routing.flight_port == "443"
        assert routing.flight_scheme == "grpc+tls"

    def test_valid_region(self) -> None:
        """Test creating routing config with valid region."""
        routing = RoutingConfig(region="us-east-1b")
        assert routing.region == "us-east-1b"

    def test_empty_region_allowed(self) -> None:
        """Test that empty region is allowed."""
        routing = RoutingConfig(region="")
        assert routing.region == ""

    def test_invalid_region_raises_error(self) -> None:
        """Test that invalid region raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid region"):
            RoutingConfig(region="INVALID")

    def test_env_var_region_allowed(self) -> None:
        """Test that environment variable reference is allowed for region."""
        routing = RoutingConfig(region="${ARIZE_REGION}")
        assert routing.region == "${ARIZE_REGION}"

    def test_mutual_exclusivity_region_and_single_host(self) -> None:
        """Test that region and single_host cannot both be set."""
        with pytest.raises(
            ValidationError,
            match="Only one routing option allowed",
        ):
            RoutingConfig(region="us-east-1b", single_host="example.com")

    def test_mutual_exclusivity_region_and_base_domain(self) -> None:
        """Test that region and base_domain cannot both be set."""
        with pytest.raises(
            ValidationError,
            match="Only one routing option allowed",
        ):
            RoutingConfig(region="us-east-1b", base_domain="example.com")

    def test_mutual_exclusivity_single_host_and_base_domain(self) -> None:
        """Test that single_host and base_domain cannot both be set."""
        with pytest.raises(
            ValidationError,
            match="Only one routing option allowed",
        ):
            RoutingConfig(
                single_host="api.example.com", base_domain="example.com"
            )

    def test_single_host_and_port_together(self) -> None:
        """Test that single_host and single_port can be set together."""
        routing = RoutingConfig(
            single_host="api.example.com", single_port="8443"
        )
        assert routing.single_host == "api.example.com"
        assert routing.single_port == "8443"


class TestTransportConfig:
    """Tests for TransportConfig model."""

    def test_default_transport_config(self) -> None:
        """Test default transport config values."""
        transport = TransportConfig()
        assert transport.stream_max_workers == 8
        assert transport.stream_max_queue_bound == 5_000
        assert transport.pyarrow_max_chunksize == 10_000
        assert transport.max_http_payload_size_mb == 8

    def test_custom_transport_values(self) -> None:
        """Test creating transport config with custom values."""
        transport = TransportConfig(
            stream_max_workers=16,
            stream_max_queue_bound=10_000,
            pyarrow_max_chunksize=20_000,
            max_http_payload_size_mb=16,
        )
        assert transport.stream_max_workers == 16
        assert transport.stream_max_queue_bound == 10_000
        assert transport.pyarrow_max_chunksize == 20_000
        assert transport.max_http_payload_size_mb == 16

    def test_string_values_allowed(self) -> None:
        """Test that string values are allowed for transport fields."""
        transport = TransportConfig(
            stream_max_workers="16",
            stream_max_queue_bound="10000",
            pyarrow_max_chunksize="20000",
            max_http_payload_size_mb="16",
        )
        assert transport.stream_max_workers == "16"
        assert transport.stream_max_queue_bound == "10000"


class TestSecurityConfig:
    """Tests for SecurityConfig model."""

    def test_default_security_config(self) -> None:
        """Test default security config values."""
        security = SecurityConfig()
        assert security.request_verify is True

    def test_disable_verification(self) -> None:
        """Test disabling request verification."""
        security = SecurityConfig(request_verify=False)
        assert security.request_verify is False

    def test_string_value_allowed(self) -> None:
        """Test that string value is allowed for request_verify."""
        security = SecurityConfig(request_verify="${ARIZE_REQUEST_VERIFY}")
        assert security.request_verify == "${ARIZE_REQUEST_VERIFY}"


class TestStorageConfig:
    """Tests for StorageConfig model."""

    def test_default_storage_config(self) -> None:
        """Test default storage config values."""
        storage = StorageConfig()
        assert storage.directory == "~/.arize"
        assert storage.cache_enabled is True

    def test_expanded_directory(self) -> None:
        """Test that expanded_directory returns expanded path."""
        storage = StorageConfig(directory="~/.arize")
        expanded = storage.expanded_directory
        assert isinstance(expanded, Path)
        assert "~" not in str(expanded)
        assert str(expanded).endswith(".arize")

    def test_cache_dir_property(self) -> None:
        """Test that cache_dir returns correct path."""
        storage = StorageConfig(directory="~/.arize")
        cache_dir = storage.cache_dir
        assert isinstance(cache_dir, Path)
        assert str(cache_dir).endswith("cache")

    def test_custom_directory(self) -> None:
        """Test creating storage config with custom directory."""
        storage = StorageConfig(directory="/custom/path")
        assert storage.directory == "/custom/path"
        assert storage.expanded_directory == Path("/custom/path")

    def test_cache_disabled(self) -> None:
        """Test disabling cache."""
        storage = StorageConfig(cache_enabled=False)
        assert storage.cache_enabled is False


class TestOutputConfig:
    """Tests for OutputConfig model."""

    def test_default_output_format(self) -> None:
        """Test default output format is table."""
        output = OutputConfig()
        assert output.format == "table"

    def test_json_output_format(self) -> None:
        """Test setting output format to json."""
        output = OutputConfig(format="json")
        assert output.format == "json"

    def test_csv_output_format(self) -> None:
        """Test setting output format to csv."""
        output = OutputConfig(format="csv")
        assert output.format == "csv"

    def test_parquet_output_format(self) -> None:
        """Test setting output format to parquet."""
        output = OutputConfig(format="parquet")
        assert output.format == "parquet"


class TestConfig:
    """Tests for root Config model."""

    def test_minimal_config(self) -> None:
        """Test creating minimal valid config."""
        config = Config(auth=AuthConfig(api_key="ak-test123"))
        assert config.auth.api_key == "ak-test123"
        assert config.profile.name == "default"
        assert config.routing.region == ""
        assert config.output.format == "table"

    def test_full_config(self) -> None:
        """Test creating config with all fields."""
        config = Config(
            profile=ProfileConfig(name="production"),
            auth=AuthConfig(api_key="ak-prod123"),
            routing=RoutingConfig(region="us-east-1b"),
            transport=TransportConfig(stream_max_workers=16),
            security=SecurityConfig(request_verify=False),
            storage=StorageConfig(directory="/custom/path"),
            output=OutputConfig(format="json"),
        )
        assert config.profile.name == "production"
        assert config.auth.api_key == "ak-prod123"
        assert config.routing.region == "us-east-1b"
        assert config.transport.stream_max_workers == 16
        assert config.security.request_verify is False
        assert config.storage.directory == "/custom/path"
        assert config.output.format == "json"

    def test_extra_fields_forbidden(self) -> None:
        """Test that extra fields are forbidden in config."""
        with pytest.raises(ValidationError):
            Config(
                auth=AuthConfig(api_key="ak-test123"),
                extra_field="not_allowed",  # type: ignore[call-arg]
            )

    def test_to_sdk_config(self) -> None:
        """Test converting Config to SDKConfiguration."""
        config = Config(
            auth=AuthConfig(api_key="ak-test123"),
            routing=RoutingConfig(region="us-east-1b"),
            transport=TransportConfig(stream_max_workers=16),
        )
        sdk_config = config.to_sdk_config()

        assert isinstance(sdk_config, SDKConfiguration)
        assert sdk_config.api_key == "ak-test123"
        assert sdk_config.region == Region("us-east-1b")
        assert sdk_config.stream_max_workers == 16

    def test_to_sdk_config_with_single_endpoint(self) -> None:
        """Test converting Config with single endpoint to SDKConfiguration."""
        config = Config(
            auth=AuthConfig(api_key="ak-test123"),
            routing=RoutingConfig(
                single_host="api.example.com", single_port="8443"
            ),
        )
        sdk_config = config.to_sdk_config()

        assert sdk_config.single_host == "api.example.com"
        assert sdk_config.single_port == 8443

    def test_to_sdk_config_with_custom_endpoints(self) -> None:
        """Test converting Config with custom endpoints to SDKConfiguration."""
        config = Config(
            auth=AuthConfig(api_key="ak-test123"),
            routing=RoutingConfig(
                api_host="custom-api.example.com",
                api_scheme="http",
                flight_host="custom-flight.example.com",
                flight_port="9999",
            ),
        )
        sdk_config = config.to_sdk_config()

        assert sdk_config.api_host == "custom-api.example.com"
        assert sdk_config.api_scheme == "http"
        assert sdk_config.flight_host == "custom-flight.example.com"
        assert sdk_config.flight_port == 9999

    def test_to_sdk_config_unset_region(self) -> None:
        """Test converting Config with unset region to SDKConfiguration."""
        config = Config(
            auth=AuthConfig(api_key="ak-test123"),
            routing=RoutingConfig(region=""),
        )
        sdk_config = config.to_sdk_config()

        assert sdk_config.region == Region.UNSET
