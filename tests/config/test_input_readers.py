"""Tests for input_readers module."""

from unittest.mock import patch

import pytest

from ax.config.input_readers import (
    INSERT_VALUE,
    USE_ENV_VAR,
    AdvancedRoutingOpts,
    read_region,
    read_routing,
)


class TestReadRoutingSingleEndpoint:
    """Tests for the SINGLE_ENDPOINT branch in read_routing().

    Mocking strategy:
    - patch questionary.select: controls the routing-type selection and
      the "Insert value vs env var" choices for host, port, and scheme.
    - patch ax.config.input_readers.prompt: supplies host, port, and scheme values.

    questionary.select side_effect sequence:
      1. routing type → SINGLE_ENDPOINT
      2. host input method → INSERT_VALUE or USE_ENV_VAR
      3. port input method → INSERT_VALUE or USE_ENV_VAR
      4. scheme input method → INSERT_VALUE or USE_ENV_VAR

    prompt side_effect sequence (when INSERT_VALUE is chosen for all):
      1. host value
      2. port value
      3. scheme value
    """

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "scheme_value,expected_http_scheme,expected_flight_scheme",
        [
            ("http", "http", "grpc"),
            ("https", "https", "grpc+tls"),
        ],
    )
    def test_scheme_sets_all_schemes(
        self,
        scheme_value: str,
        expected_http_scheme: str,
        expected_flight_scheme: str,
    ) -> None:
        with (
            patch("ax.config.input_readers.questionary") as mock_q,
            patch(
                "ax.config.input_readers.prompt",
                side_effect=["myhost.example.com", "443", scheme_value],
            ),
        ):
            mock_q.select.return_value.ask.side_effect = [
                AdvancedRoutingOpts.SINGLE_ENDPOINT.value,
                INSERT_VALUE,
                INSERT_VALUE,
                INSERT_VALUE,
            ]
            result = read_routing()

        assert result.single_host == "myhost.example.com"
        assert result.single_port == "443"
        assert result.api_scheme == expected_http_scheme
        assert result.app_scheme == expected_http_scheme
        assert result.otlp_scheme == expected_http_scheme
        assert result.flight_scheme == expected_flight_scheme

    @pytest.mark.unit
    def test_env_var_scheme_propagates_reference(self) -> None:
        with (
            patch("ax.config.input_readers.questionary") as mock_q,
            patch(
                "ax.config.input_readers.prompt",
                side_effect=["host.example.com", "8080", "ARIZE_API_SCHEME"],
            ),
        ):
            mock_q.select.return_value.ask.side_effect = [
                AdvancedRoutingOpts.SINGLE_ENDPOINT.value,
                INSERT_VALUE,
                INSERT_VALUE,
                USE_ENV_VAR,
            ]
            result = read_routing()

        assert result.api_scheme == "${ARIZE_API_SCHEME}"
        assert result.app_scheme == "${ARIZE_API_SCHEME}"
        assert result.otlp_scheme == "${ARIZE_API_SCHEME}"
        # flight_scheme falls back to default when scheme is an env var reference
        assert result.flight_scheme == "grpc+tls"


class TestReadRegion:
    """Tests for read_region(): labeled choices resolve back to zone IDs."""

    @pytest.mark.unit
    def test_labeled_choice_resolves_to_zone_id(self) -> None:
        with patch("ax.config.input_readers.questionary") as mock_q:
            mock_q.select.return_value.ask.return_value = (
                "us-east-1b  (US East)"
            )
            assert read_region() == "us-east-1b"

    @pytest.mark.unit
    def test_unset_choice_returns_empty_string(self) -> None:
        with patch("ax.config.input_readers.questionary") as mock_q:
            mock_q.select.return_value.ask.return_value = (
                "(default - no region needed for US)"
            )
            assert read_region() == ""

    @pytest.mark.unit
    def test_env_var_choice_returns_reference(self) -> None:
        with (
            patch("ax.config.input_readers.questionary") as mock_q,
            patch(
                "ax.config.input_readers.prompt",
                return_value="ARIZE_REGION",
            ),
        ):
            mock_q.select.return_value.ask.return_value = USE_ENV_VAR
            assert read_region() == "${ARIZE_REGION}"
