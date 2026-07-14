"""Single entry point for command authors to load a profile and build an authenticated SDK client."""

from dataclasses import asdict, replace

from arize import ArizeClient

from ax.auth.bearer import get_active_bearer
from ax.config.manager import ConfigManager
from ax.config.schema import Config
from ax.core.network import NetworkSettings


def make_client() -> tuple[ArizeClient, Config]:
    """Load the active profile and build an authenticated SDK client.

    For OAuth profiles, the bearer token is resolved (and refreshed if needed)
    transparently — command authors don't deal with bearer plumbing.

    Returns:
        ``(client, config)`` — both are typically needed: ``client`` for API
        calls and ``config`` for things like output format defaults.

    Raises:
        ConfigError: if no active profile is set.
    """
    # Resolve the profile name once so load() and profile_path() agree even
    # if the active-profile file changes underfoot. ConfigManager.load()
    # raises ConfigError with a "Run 'ax profiles create'" hint.
    config = ConfigManager.load(expand_env_vars=True)
    network = NetworkSettings.from_config(
        config.network, request_verify=config.request_verify
    )
    network.configure_grpc_environment()
    profile_path = ConfigManager.profile_path(config.profile.name)
    bearer = get_active_bearer(
        config.auth,
        profile_path=profile_path,
        base_url=config.routing.resolve_app_url(),
        network=network,
    )
    sdk_config = config.to_sdk_config(bearer=bearer)
    sdk_config = replace(
        sdk_config,
        proxy_url=network.proxy_for(sdk_config.api_url),
        ssl_ca_cert=network.ca_bundle,
    )
    client = ArizeClient(**asdict(sdk_config))
    return client, config
