"""Tests for input_readers module."""

from unittest.mock import patch

import pytest

from ax.config.input_readers import (
    INSERT_VALUE,
    NO_VALUE,
    USE_ENV_VAR,
    AdvancedRoutingOpts,
    read_region,
    read_routing,
    read_security,
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
            mock_q.select.return_value.ask.return_value = "EU (Europe)"
            assert read_region() == "eu-west-1a"

    @pytest.mark.unit
    def test_us_choice_returns_canonical_region(self) -> None:
        with patch("ax.config.input_readers.questionary") as mock_q:
            mock_q.select.return_value.ask.return_value = (
                "US (United States, default)"
            )
            assert read_region() == "us-central-1a"

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

    @pytest.mark.unit
    def test_public_region_choices(self) -> None:
        with patch("ax.config.input_readers.questionary") as mock_q:
            mock_q.select.return_value.ask.return_value = (
                "US (United States, default)"
            )
            assert read_region() == "us-central-1a"
            mock_q.select.assert_called_once_with(
                "Region:",
                choices=[
                    "US (United States, default)",
                    "EU (Europe)",
                    "CA (Canada)",
                    USE_ENV_VAR,
                ],
                default="US (United States, default)",
            )


@pytest.mark.parametrize(
    ("label", "value"),
    [
        ("US (United States, default)", "us-central-1a"),
        ("EU (Europe)", "eu-west-1a"),
        ("CA (Canada)", "ca-central-1a"),
    ],
)
def test_region_label_maps_to_canonical_value(label: str, value: str) -> None:
    with patch("ax.config.input_readers.questionary") as questionary:
        questionary.select.return_value.ask.return_value = label
        assert read_region() == value


class TestReadSecurity:
    """Tests for read_security() prompts.

    questionary.select side_effect sequence:
      1. TLS certificate verification
      2. custom CA bundle
      3. client certificate
    """

    @pytest.mark.unit
    def test_defaults_leave_tls_fields_empty(self) -> None:
        with (
            patch("ax.config.input_readers.questionary.select") as mock_select,
            patch("ax.config.input_readers.prompt") as mock_prompt,
        ):
            mock_select.return_value.ask.side_effect = [
                "Enabled",
                NO_VALUE,
                NO_VALUE,
            ]
            result = read_security()

        mock_prompt.assert_not_called()
        assert result.request_verify is True
        assert result.ssl_ca_cert == ""
        assert result.client_cert == ""
        assert result.client_key == ""

    @pytest.mark.unit
    def test_inserted_paths_are_saved(self) -> None:
        with (
            patch("ax.config.input_readers.questionary.select") as mock_select,
            patch("ax.config.input_readers.prompt") as mock_prompt,
        ):
            mock_select.return_value.ask.side_effect = [
                "Enabled",
                INSERT_VALUE,
                INSERT_VALUE,
            ]
            mock_prompt.side_effect = ["/ca.pem", "/c.crt", "/c.key"]
            result = read_security()

        assert result.ssl_ca_cert == "/ca.pem"
        assert result.client_cert == "/c.crt"
        assert result.client_key == "/c.key"

    @pytest.mark.unit
    def test_env_var_choice_saves_references(self) -> None:
        with (
            patch("ax.config.input_readers.questionary.select") as mock_select,
            patch("ax.config.input_readers.prompt") as mock_prompt,
        ):
            mock_select.return_value.ask.side_effect = [
                "Enabled",
                USE_ENV_VAR,
                USE_ENV_VAR,
            ]
            mock_prompt.side_effect = [
                "ARIZE_SSL_CA_CERT",
                "ARIZE_CLIENT_CERT",
                "ARIZE_CLIENT_KEY",
            ]
            result = read_security()

        assert result.ssl_ca_cert == "${ARIZE_SSL_CA_CERT}"
        assert result.client_cert == "${ARIZE_CLIENT_CERT}"
        assert result.client_key == "${ARIZE_CLIENT_KEY}"
        defaults = [c.kwargs["default"] for c in mock_prompt.call_args_list]
        assert defaults == [
            "ARIZE_SSL_CA_CERT",
            "ARIZE_CLIENT_CERT",
            "ARIZE_CLIENT_KEY",
        ]
