"""Tests for configuration setup module."""

import os
from unittest.mock import patch

import pytest

from ax.config.schema import (
    AuthConfig,
    Config,
    RoutingConfig,
    SecurityConfig,
    TransportConfig,
)
from ax.config.setup import (
    ENV_VAR_MAPPING,
    create_config_from_env_vars,
    detect_env_vars,
)


class TestDetectEnvVars:
    """Tests for detect_env_vars function."""

    def test_detect_no_env_vars(self) -> None:
        """Test detect_env_vars when no ARIZE env vars are set."""
        # Ensure no ARIZE env vars are set
        for env_var in ENV_VAR_MAPPING.values():
            os.environ.pop(env_var, None)

        result = detect_env_vars()
        assert result == {}

    def test_detect_single_env_var(self) -> None:
        """Test detect_env_vars finds single env var."""
        os.environ["ARIZE_API_KEY"] = "ak-test123"

        result = detect_env_vars()
        assert result == {"api_key": "ARIZE_API_KEY"}

        # Cleanup
        del os.environ["ARIZE_API_KEY"]

    def test_detect_multiple_env_vars(self) -> None:
        """Test detect_env_vars finds multiple env vars."""
        os.environ["ARIZE_API_KEY"] = "ak-test123"
        os.environ["ARIZE_REGION"] = "US"
        os.environ["ARIZE_STREAM_MAX_WORKERS"] = "16"

        result = detect_env_vars()
        assert result == {
            "api_key": "ARIZE_API_KEY",
            "region": "ARIZE_REGION",
            "stream_max_workers": "ARIZE_STREAM_MAX_WORKERS",
        }

        # Cleanup
        del os.environ["ARIZE_API_KEY"]
        del os.environ["ARIZE_REGION"]
        del os.environ["ARIZE_STREAM_MAX_WORKERS"]

    def test_detect_all_env_vars(self) -> None:
        """Test detect_env_vars finds all supported env vars."""
        # Set all env vars
        test_values = {
            env_var: f"value_{env_var}" for env_var in ENV_VAR_MAPPING.values()
        }
        os.environ.update(test_values)

        result = detect_env_vars()
        assert len(result) == len(ENV_VAR_MAPPING)

        # Cleanup
        for env_var in ENV_VAR_MAPPING.values():
            del os.environ[env_var]


class TestCreateConfigFromEnvVars:
    """Tests for create_config_from_env_vars function."""

    @patch("ax.config.setup.read_output_format")
    def test_create_config_minimal(self, mock_read_format: object) -> None:
        """Test create_config_from_env_vars with minimal env vars."""
        # Mock the interactive output format prompt
        mock_read_format.return_value = "table"  # type: ignore[attr-defined]

        env_vars = {"api_key": "ARIZE_API_KEY"}
        config = create_config_from_env_vars("default", env_vars)

        assert isinstance(config, Config)
        assert config.profile.name == "default"
        assert config.auth.api_key == "${ARIZE_API_KEY}"

    @patch("ax.config.setup.read_output_format")
    def test_create_config_with_routing(self, mock_read_format: object) -> None:
        """Test create_config_from_env_vars with routing env vars."""
        mock_read_format.return_value = "json"  # type: ignore[attr-defined]

        env_vars = {
            "api_key": "ARIZE_API_KEY",
            "region": "ARIZE_REGION",
        }
        config = create_config_from_env_vars("production", env_vars)

        assert config.profile.name == "production"
        assert config.auth.api_key == "${ARIZE_API_KEY}"
        assert config.routing.region == "${ARIZE_REGION}"

    @patch("ax.config.setup.read_output_format")
    def test_create_config_with_transport(
        self, mock_read_format: object
    ) -> None:
        """Test create_config_from_env_vars with transport env vars."""
        mock_read_format.return_value = "table"  # type: ignore[attr-defined]

        env_vars = {
            "api_key": "ARIZE_API_KEY",
            "stream_max_workers": "ARIZE_STREAM_MAX_WORKERS",
            "pyarrow_max_chunksize": "ARIZE_MAX_CHUNKSIZE",
        }
        config = create_config_from_env_vars("default", env_vars)

        assert (
            config.transport.stream_max_workers == "${ARIZE_STREAM_MAX_WORKERS}"
        )
        assert (
            config.transport.pyarrow_max_chunksize == "${ARIZE_MAX_CHUNKSIZE}"
        )

    @patch("ax.config.setup.read_output_format")
    def test_create_config_with_security(
        self, mock_read_format: object
    ) -> None:
        """Test create_config_from_env_vars with security env vars."""
        mock_read_format.return_value = "table"  # type: ignore[attr-defined]

        env_vars = {
            "api_key": "ARIZE_API_KEY",
            "request_verify": "ARIZE_REQUEST_VERIFY",
        }
        config = create_config_from_env_vars("default", env_vars)

        assert config.security.request_verify == "${ARIZE_REQUEST_VERIFY}"

    @patch("ax.config.setup.read_output_format")
    def test_create_config_with_custom_endpoints(
        self, mock_read_format: object
    ) -> None:
        """Test create_config_from_env_vars with custom endpoint env vars."""
        mock_read_format.return_value = "table"  # type: ignore[attr-defined]

        # Use only custom endpoint fields (not mutually exclusive options)
        env_vars = {
            "api_key": "ARIZE_API_KEY",
            "api_host": "ARIZE_API_HOST",
            "api_scheme": "ARIZE_API_SCHEME",
            "otlp_host": "ARIZE_OTLP_HOST",
            "otlp_scheme": "ARIZE_OTLP_SCHEME",
            "flight_host": "ARIZE_FLIGHT_HOST",
            "flight_port": "ARIZE_FLIGHT_PORT",
            "flight_scheme": "ARIZE_FLIGHT_SCHEME",
        }
        config = create_config_from_env_vars("default", env_vars)

        assert isinstance(config.routing, RoutingConfig)
        assert config.routing.api_host == "${ARIZE_API_HOST}"
        assert config.routing.api_scheme == "${ARIZE_API_SCHEME}"
        assert config.routing.otlp_host == "${ARIZE_OTLP_HOST}"
        assert config.routing.flight_port == "${ARIZE_FLIGHT_PORT}"

    @patch("ax.config.setup.read_output_format")
    def test_create_config_raises_without_api_key(
        self, mock_read_format: object
    ) -> None:
        """Test create_config_from_env_vars raises error without api_key."""
        mock_read_format.return_value = "table"  # type: ignore[attr-defined]

        env_vars = {"region": "ARIZE_REGION"}  # Missing api_key

        with pytest.raises(ValueError, match="api_key must be present"):
            create_config_from_env_vars("default", env_vars)

    @patch("ax.config.setup.read_output_format")
    def test_create_config_with_all_transport_and_security(
        self, mock_read_format: object
    ) -> None:
        """Test create_config_from_env_vars with transport and security env vars."""
        mock_read_format.return_value = "csv"  # type: ignore[attr-defined]

        # Use non-mutually-exclusive fields
        env_vars = {
            "api_key": "ARIZE_API_KEY",
            "region": "ARIZE_REGION",
            "stream_max_workers": "ARIZE_STREAM_MAX_WORKERS",
            "stream_max_queue_bound": "ARIZE_STREAM_MAX_QUEUE_BOUND",
            "pyarrow_max_chunksize": "ARIZE_MAX_CHUNKSIZE",
            "max_http_payload_size_mb": "ARIZE_MAX_HTTP_PAYLOAD_SIZE_MB",
            "request_verify": "ARIZE_REQUEST_VERIFY",
        }

        config = create_config_from_env_vars("production", env_vars)

        assert isinstance(config, Config)
        assert config.profile.name == "production"
        assert isinstance(config.auth, AuthConfig)
        assert isinstance(config.routing, RoutingConfig)
        assert isinstance(config.transport, TransportConfig)
        assert isinstance(config.security, SecurityConfig)

        # Verify all values are env var references
        assert config.auth.api_key == "${ARIZE_API_KEY}"
        assert config.routing.region == "${ARIZE_REGION}"
        assert (
            config.transport.stream_max_workers == "${ARIZE_STREAM_MAX_WORKERS}"
        )
        assert (
            config.transport.stream_max_queue_bound
            == "${ARIZE_STREAM_MAX_QUEUE_BOUND}"
        )
        assert config.security.request_verify == "${ARIZE_REQUEST_VERIFY}"


class TestEnvVarMapping:
    """Tests for ENV_VAR_MAPPING constant."""

    def test_env_var_mapping_completeness(self) -> None:
        """Test that ENV_VAR_MAPPING contains expected keys."""
        expected_keys = {
            "api_key",
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
            "stream_max_workers",
            "stream_max_queue_bound",
            "pyarrow_max_chunksize",
            "max_http_payload_size_mb",
            "request_verify",
        }
        assert set(ENV_VAR_MAPPING.keys()) == expected_keys

    def test_env_var_mapping_values(self) -> None:
        """Test that ENV_VAR_MAPPING values follow ARIZE_ prefix convention."""
        for field, env_var in ENV_VAR_MAPPING.items():
            assert env_var.startswith("ARIZE_"), (
                f"Expected {field} env var to start with ARIZE_, got {env_var}"
            )
