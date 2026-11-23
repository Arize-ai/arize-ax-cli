import pytest
from arize import Region

from ax.config.manager import resolve_oauth_app_url
from ax.config.schema import (
    AuthConfig,
    AuthMethod,
    Config,
    ProfileConfig,
    RoutingConfig,
)


class TestResolveAppUrl:
    def test_default_is_app_arize_com(self):
        assert resolve_oauth_app_url(RoutingConfig()) == "https://app.arize.com"

    def test_single_host_wins_over_everything(self):
        r = RoutingConfig(
            single_host="arize.my-company.internal",
            single_port="8443",
            api_scheme="https",
        )
        assert (
            resolve_oauth_app_url(r) == "https://arize.my-company.internal:8443"
        )

    def test_single_host_without_port_omits_port(self):
        r = RoutingConfig(single_host="arize.my-company.internal")
        assert resolve_oauth_app_url(r) == "https://arize.my-company.internal"

    def test_base_domain_produces_app_subdomain(self):
        r = RoutingConfig(base_domain="example-arize.com")
        assert resolve_oauth_app_url(r) == "https://app.example-arize.com"

    def test_region_produces_app_subdomain(self):
        r = RoutingConfig(region="eu-west-1a")
        assert resolve_oauth_app_url(r) == "https://app.eu-west-1a.arize.com"

    def test_explicit_app_host_override(self):
        r = RoutingConfig(app_host="app.staging.arize.com", app_scheme="https")
        assert resolve_oauth_app_url(r) == "https://app.staging.arize.com"

    def test_non_default_app_scheme(self):
        r = RoutingConfig(app_host="app.local", app_scheme="http")
        assert resolve_oauth_app_url(r) == "http://app.local"

    def test_single_host_with_custom_scheme(self):
        r = RoutingConfig(
            single_host="onprem.local", single_port="9000", app_scheme="http"
        )
        assert resolve_oauth_app_url(r) == "http://onprem.local:9000"

    def test_custom_api_and_app_hosts_together(self):
        r = RoutingConfig(
            api_host="api-dev.arize.com",
            app_host="app-dev.arize.com",
        )
        assert resolve_oauth_app_url(r) == "https://app-dev.arize.com"


@pytest.mark.parametrize(
    ("region", "app_url", "canonical"),
    [
        ("US", "https://app.arize.com", "us-central-1a"),
        ("us", "https://app.arize.com", "us-central-1a"),
        ("us-central-1a", "https://app.arize.com", "us-central-1a"),
        ("EU", "https://app.eu-west-1a.arize.com", "eu-west-1a"),
        ("eu-west-1a", "https://app.eu-west-1a.arize.com", "eu-west-1a"),
        ("CA", "https://app.ca-central-1a.arize.com", "ca-central-1a"),
        (
            "ca-central-1a",
            "https://app.ca-central-1a.arize.com",
            "ca-central-1a",
        ),
    ],
)
def test_public_oauth_and_api_routing(
    region: str, app_url: str, canonical: str
) -> None:
    config = Config(
        profile=ProfileConfig(name="test"),
        auth=AuthConfig(auth_method=AuthMethod.OAUTH),
        routing=RoutingConfig(region=region),
    )
    assert resolve_oauth_app_url(config.routing) == app_url
    sdk_config = config.to_sdk_config(bearer="test-token")
    assert sdk_config.region == Region(canonical)
    assert sdk_config.api_host == f"api.{canonical}.arize.com"
    assert sdk_config.otlp_host == f"otlp.{canonical}.arize.com"
    assert sdk_config.flight_host == f"flight.{canonical}.arize.com"
