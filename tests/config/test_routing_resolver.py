from ax.config.schema import RoutingConfig


class TestResolveAppUrl:
    def test_default_is_app_arize_com(self):
        assert RoutingConfig().resolve_app_url() == "https://app.arize.com"

    def test_single_host_wins_over_everything(self):
        r = RoutingConfig(
            single_host="arize.my-company.internal",
            single_port="8443",
            api_scheme="https",
        )
        assert r.resolve_app_url() == "https://arize.my-company.internal"

    def test_base_domain_produces_app_subdomain(self):
        r = RoutingConfig(base_domain="example-arize.com")
        assert r.resolve_app_url() == "https://app.example-arize.com"

    def test_region_produces_app_subdomain(self):
        r = RoutingConfig(region="eu-west-1a")
        assert r.resolve_app_url() == "https://app.eu-west-1a.arize.com"

    def test_explicit_app_host_override(self):
        r = RoutingConfig(app_host="app.staging.arize.com", app_scheme="https")
        assert r.resolve_app_url() == "https://app.staging.arize.com"

    def test_non_default_app_scheme(self):
        r = RoutingConfig(app_host="app.local", app_scheme="http")
        assert r.resolve_app_url() == "http://app.local"

    def test_single_host_with_custom_scheme(self):
        r = RoutingConfig(
            single_host="onprem.local", single_port="9000", api_scheme="http"
        )
        assert r.resolve_app_url() == "http://onprem.local"

    def test_custom_api_and_app_hosts_together(self):
        r = RoutingConfig(
            api_host="api-dev.arize.com",
            app_host="app-dev.arize.com",
        )
        assert r.resolve_app_url() == "https://app-dev.arize.com"
