"""Tests for TOML-based config creation and flag-to-config helpers."""

from pathlib import Path

import pytest

from ax.config.schema import Config
from ax.config.setup import (
    create_config_from_flags,
    create_config_from_toml,
    merge_config_with_flags,
)
from ax.core.exceptions import ConfigError

# ---------------------------------------------------------------------------
# TestCreateConfigFromToml
# ---------------------------------------------------------------------------


class TestCreateConfigFromToml:
    """Tests for create_config_from_toml."""

    def test_minimal_toml(self, tmp_path: Path) -> None:
        """Minimal TOML with only api_key parses into a valid Config."""
        toml_file = tmp_path / "config.toml"
        toml_file.write_bytes(b'[auth]\napi_key = "test-key-123"\n')

        result = create_config_from_toml(str(toml_file), profile="test")

        assert isinstance(result, Config)
        assert result.auth.api_key == "test-key-123"
        assert result.profile.name == "test"

    def test_full_toml(self, tmp_path: Path) -> None:
        """Full TOML with all sections parses into a valid Config."""
        toml_file = tmp_path / "config.toml"
        toml_file.write_bytes(
            b"[auth]\n"
            b'api_key = "full-key"\n'
            b"\n[routing]\n"
            b'region = "us-east-1b"\n'
            b"\n[transport]\n"
            b"stream_max_workers = 16\n"
            b"\n[security]\n"
            b"request_verify = true\n"
            b"\n[output]\n"
            b'format = "json"\n'
        )

        result = create_config_from_toml(str(toml_file), profile="test")

        assert result.auth.api_key == "full-key"
        assert result.routing.region == "us-east-1b"
        assert result.transport.stream_max_workers == 16
        assert result.security.request_verify is True
        assert result.output.format == "json"

    def test_legacy_storage_section_is_ignored(self, tmp_path: Path) -> None:
        """Legacy cache settings do not prevent a profile from loading."""
        toml_file = tmp_path / "config.toml"
        toml_file.write_bytes(
            b'[auth]\napi_key = "test-key-123"\n'
            b"\n[storage]\n"
            b'directory = "/tmp/arize"\n'
            b"cache_enabled = false\n"
        )

        result = create_config_from_toml(str(toml_file), profile="test")

        assert result.auth.api_key == "test-key-123"
        assert not hasattr(result, "storage")

    def test_env_var_refs_preserved(self, tmp_path: Path) -> None:
        """Env var references like ${ARIZE_API_KEY} are preserved as strings."""
        toml_file = tmp_path / "config.toml"
        toml_file.write_bytes(b'[auth]\napi_key = "${ARIZE_API_KEY}"\n')

        result = create_config_from_toml(str(toml_file), profile="test")

        assert result.auth.api_key == "${ARIZE_API_KEY}"

    def test_empty_toml_raises(self, tmp_path: Path) -> None:
        """An empty TOML file raises ConfigError due to missing required fields."""
        toml_file = tmp_path / "config.toml"
        toml_file.write_bytes(b"")

        with pytest.raises(ConfigError):
            create_config_from_toml(str(toml_file), profile="test")

    def test_file_not_found(self) -> None:
        """Nonexistent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            create_config_from_toml(
                "/nonexistent/path/config.toml", profile="test"
            )

    def test_invalid_toml(self, tmp_path: Path) -> None:
        """Malformed TOML raises ConfigError."""
        toml_file = tmp_path / "config.toml"
        toml_file.write_bytes(b'[auth\napi_key = "unclosed section"\n')

        with pytest.raises(ConfigError, match="Failed to parse"):
            create_config_from_toml(str(toml_file), profile="test")


# ---------------------------------------------------------------------------
# TestCreateConfigWithPrecedence
# ---------------------------------------------------------------------------


class TestCreateConfigFromFlags:
    """Tests for create_config_from_flags."""

    def test_missing_api_key_raises(self) -> None:
        """Empty flat dict raises ConfigError due to missing required api_key."""
        with pytest.raises(ConfigError):
            create_config_from_flags(profile="test", flat={})

    def test_api_key_maps_to_auth_section(self) -> None:
        """api_key in flat dict produces a valid Config with auth.api_key set."""
        config = create_config_from_flags(
            profile="test", flat={"api_key": "my-key"}
        )

        assert config.auth.api_key == "my-key"

    def test_routing_fields_nested_correctly(self) -> None:
        """Routing flat keys are grouped into config.routing."""
        config = create_config_from_flags(
            profile="test", flat={"api_key": "k", "region": "us-east-1b"}
        )

        assert config.routing.region == "us-east-1b"

    def test_transport_fields_nested_correctly(self) -> None:
        """Transport flat keys are grouped into config.transport."""
        config = create_config_from_flags(
            profile="test", flat={"api_key": "k", "stream_max_workers": 16}
        )

        assert config.transport.stream_max_workers == 16

    def test_output_format_mapped_to_format_key(self) -> None:
        """output_format flat key maps to config.output.format."""
        config = create_config_from_flags(
            profile="test", flat={"api_key": "k", "output_format": "json"}
        )

        assert config.output.format == "json"

    def test_security_is_nested_correctly(self) -> None:
        """Security keys are grouped into their section."""
        config = create_config_from_flags(
            profile="test",
            flat={
                "api_key": "k",
                "request_verify": False,
            },
        )

        assert config.security.request_verify is False

    def test_profile_name_embedded(self) -> None:
        """The profile name is correctly embedded in the returned Config."""
        config = create_config_from_flags(
            profile="my-profile", flat={"api_key": "k"}
        )

        assert config.profile.name == "my-profile"

    def test_output_format_defaults_when_omitted(self) -> None:
        """Omitting output_format uses the OutputConfig model default."""
        config = create_config_from_flags(profile="test", flat={"api_key": "k"})

        assert config.output.format == "table"

    def test_returns_config_instance(self) -> None:
        """Returns a Config instance when all required fields are supplied."""
        config = create_config_from_flags(
            profile="test", flat={"api_key": "k", "output_format": "json"}
        )

        assert isinstance(config, Config)


# ---------------------------------------------------------------------------
# TestMergeConfigWithFlags
# ---------------------------------------------------------------------------


class TestMergeConfigWithFlags:
    """Tests for merge_config_with_flags."""

    def test_partial_routing_updates_only_passed_fields(
        self, sample_config_data: dict[str, object]
    ) -> None:
        """Merging a single routing key leaves other sections unchanged."""
        existing = Config.model_validate(sample_config_data)
        merged = merge_config_with_flags(existing, {"region": "eu-west-1a"})

        assert merged.routing.region == "eu-west-1a"
        assert merged.auth.api_key == existing.auth.api_key
        assert merged.transport.stream_max_workers == (
            existing.transport.stream_max_workers
        )

    def test_partial_transport_update(
        self, sample_config_data: dict[str, object]
    ) -> None:
        """Merging one transport field preserves other transport defaults."""
        existing = Config.model_validate(sample_config_data)
        merged = merge_config_with_flags(existing, {"stream_max_workers": 42})

        assert merged.transport.stream_max_workers == 42
        assert merged.transport.stream_max_queue_bound == (
            existing.transport.stream_max_queue_bound
        )

    def test_merge_auth_security_output(
        self, sample_config_data: dict[str, object]
    ) -> None:
        """Auth, security, and output keys merge in one call."""
        existing = Config.model_validate(sample_config_data)
        merged = merge_config_with_flags(
            existing,
            {
                "api_key": "new-key",
                "request_verify": False,
                "output_format": "json",
            },
        )

        assert merged.auth.api_key == "new-key"
        assert merged.security.request_verify is False
        assert merged.output.format == "json"

    def test_invalid_region_raises_config_error(
        self, sample_config_data: dict[str, object]
    ) -> None:
        """Invalid merged routing fails validation as ConfigError."""
        existing = Config.model_validate(sample_config_data)

        with pytest.raises(ConfigError):
            merge_config_with_flags(existing, {"region": "not-a-valid-region"})
