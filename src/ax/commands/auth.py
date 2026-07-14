"""ax auth login / logout commands."""

import webbrowser
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests
import typer
from rich import print as rprint

from ax.auth import OAUTH_CLIENT_ID
from ax.auth.oauth_client import OAuthClient
from ax.auth.oauth_flow import LoopbackServer, generate_pkce_pair, random_state
from ax.config.manager import ConfigManager
from ax.config.schema import AuthConfig, AuthMethod, OAuthCredentials
from ax.core.decorators import handle_errors
from ax.core.exceptions import ConfigError
from ax.core.network import NetworkSettings

app = typer.Typer(
    name="auth",
    help="Authenticate to Arize via OAuth (browser-based login).",
    no_args_is_help=True,
)

_LOGIN_TIMEOUT_SECONDS = 300.0  # 5 minutes for user to complete browser login


def perform_oauth_login(
    base_url: str,
    login_timeout_seconds: float = _LOGIN_TIMEOUT_SECONDS,
    network: NetworkSettings | None = None,
) -> OAuthCredentials:
    """Open the browser, complete PKCE flow, return fresh OAuthCredentials.

    Callers: ``ax auth login`` and ``ax profiles create --auth-method oauth``.

    Args:
        base_url: The Arize app URL to authenticate against (e.g. "https://app.arize.com").
        login_timeout_seconds: Seconds to wait for the browser callback before timing out.
        network: Shared proxy and TLS policy for the token exchange.

    Returns:
        Fresh OAuthCredentials with access_token, refresh_token, expires_at, user_email.
    """
    verifier, challenge, method = generate_pkce_pair()
    state = random_state()
    # The loopback handler 302-redirects the browser to the Arize app's
    # branded /auth/cli/callback page once it's captured the code. Build the
    # URL from the same base_url we just authenticated against — the user is
    # demonstrably able to reach it.
    callback_page_base_url = f"{base_url.rstrip('/')}/auth/cli/callback"
    server = LoopbackServer(
        expected_state=state, callback_page_base_url=callback_page_base_url
    )
    server.start()
    redirect_uri = f"http://127.0.0.1:{server.port}/callback"

    query = urlencode(
        {
            "response_type": "code",
            "client_id": OAUTH_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": "openid email",
            "code_challenge": challenge,
            "code_challenge_method": method,
        }
    )
    authorize_url = f"{base_url}/oauth2/authorize?{query}"

    rprint(f"Opening [cyan]{authorize_url}[/cyan] in your browser...")
    webbrowser.open(authorize_url)
    rprint("Waiting for authentication in your browser... (Ctrl+C to cancel)")

    result = server.wait(timeout=login_timeout_seconds)

    client = OAuthClient(
        base_url=base_url,
        client_id=OAUTH_CLIENT_ID,
        network=network,
    )
    try:
        resp = client.exchange_code(
            code=result.code, code_verifier=verifier, redirect_uri=redirect_uri
        )
    except requests.HTTPError as exc:
        body = exc.response.text if exc.response is not None else "(no body)"
        status = exc.response.status_code if exc.response is not None else "?"
        rprint(
            f"[red]error:[/red] token exchange failed — status={status}\n"
            f"[dim]response body:[/dim] {body}"
        )
        raise typer.Exit(code=1) from exc
    except requests.RequestException as exc:
        rprint(f"[red]error:[/red] token exchange network error: {exc}")
        raise typer.Exit(code=1) from exc

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=resp.expires_in)
    return OAuthCredentials(
        access_token=resp.access_token,
        refresh_token=resp.refresh_token,
        expires_at=expires_at,
        user_email=resp.user_email or "(unknown)",
    )


@app.command("login")
@handle_errors
def login_cmd() -> None:
    """Sign in to the active profile via the browser.

    Writes fresh OAuth tokens to the active profile. The profile must already
    exist (use ``ax profiles create --auth-method oauth`` if not) and must be
    an OAuth profile. If the profile is already signed in with non-expired
    tokens, this is a no-op.
    """
    cfg = ConfigManager.load(expand_env_vars=False)
    profile_name = cfg.profile.name

    if not cfg.auth.uses_oauth:
        rprint(
            f"[red]error:[/red] active profile '{profile_name}' is configured "
            f"for API-key authentication. Use [cyan]ax profiles create --auth-method oauth[/cyan] "
            f"to set up an OAuth profile."
        )
        raise typer.Exit(code=1)

    # Skip the browser flow when the profile is already authenticated and the
    # access token hasn't expired. The CLI auto-refreshes near expiry on every
    # command, so an unexpired access token means a usable session — no point
    # spinning up the browser flow. Users who explicitly want to re-auth
    # (e.g., to switch user) should run `ax auth logout` first.
    if cfg.auth.oauth is not None:
        now = datetime.now(timezone.utc)
        if cfg.auth.oauth.expires_at > now:
            rprint(
                f"[green]✓[/green] You are already logged in as "
                f"[bold]{cfg.auth.oauth.user_email}[/bold] (profile: {profile_name}). "
                f"Run [cyan]ax auth logout[/cyan] first to switch users."
            )
            raise typer.Exit(code=0)

    resolved_base_url = cfg.routing.resolve_app_url()
    # Resolve env references only now: doing it earlier would make the
    # friendly early-exit paths above unreachable when the profile holds a
    # ${VAR} the current shell does not define.
    resolved_cfg = ConfigManager.load(expand_env_vars=True)
    network = NetworkSettings.from_config(
        resolved_cfg.network,
        request_verify=resolved_cfg.request_verify,
    )
    oauth_creds = perform_oauth_login(
        base_url=resolved_base_url,
        network=network,
    )
    new_auth = AuthConfig(auth_method=AuthMethod.OAUTH, oauth=oauth_creds)
    new_cfg = cfg.model_copy(update={"auth": new_auth})
    ConfigManager.save(new_cfg, profile_name)
    rprint(
        f"[green]✓[/green] Logged in as [bold]{oauth_creds.user_email}[/bold] "
        f"(profile: {profile_name})"
    )


@app.command("logout")
@handle_errors
def logout_cmd() -> None:
    """Revoke both tokens and clear OAuth credentials on the active profile."""
    cfg = ConfigManager.load(expand_env_vars=False)
    profile_name = cfg.profile.name

    if not cfg.auth.uses_oauth:
        rprint(
            f"[red]error:[/red] active profile '{profile_name}' is configured "
            "for API-key authentication. Logout only applies to OAuth profiles. "
            "Use [cyan]ax profiles create --auth-method oauth[/cyan] to set up "
            "an OAuth profile."
        )
        raise typer.Exit(code=1)

    if cfg.auth.oauth is None:
        rprint(
            f"[yellow]Profile '{profile_name}' is already logged out.[/yellow]"
        )
        raise typer.Exit(code=0)

    resolved_base_url = cfg.routing.resolve_app_url()
    # Revoke BOTH tokens server-side. Revoking only the refresh token would
    # leave the access token usable until its 1h TTL elapses — a stolen copy
    # of the [auth.oauth] block would still pass apiproxy's validator, since
    # only the refresh-token jti would be in oauth_revoked_jtis. Revoke is
    # best-effort: a network failure shouldn't block local clearing of the
    # profile (the user's intent is "end this session locally").
    # Clearing local credentials must never be blocked by an unresolvable
    # ${VAR} reference elsewhere in the profile: fall back to environment
    # settings for the best-effort revoke calls.
    try:
        resolved_cfg = ConfigManager.load(expand_env_vars=True)
        network = NetworkSettings.from_config(
            resolved_cfg.network,
            request_verify=resolved_cfg.request_verify,
        )
    except ConfigError:
        network = NetworkSettings.from_environment()
    client = OAuthClient(
        base_url=resolved_base_url,
        client_id=OAUTH_CLIENT_ID,
        network=network,
    )
    client.revoke(token=cfg.auth.oauth.access_token)
    client.revoke(token=cfg.auth.oauth.refresh_token)

    # Clear OAuth credentials but keep the rest of the profile (routing,
    # output, auth_method) so `ax auth login` can re-authenticate without
    # re-prompting for routing. model_copy preserves auth_method="oauth".
    cleared_auth = cfg.auth.model_copy(update={"oauth": None})
    cleared_cfg = cfg.model_copy(update={"auth": cleared_auth})
    ConfigManager.save(cleared_cfg, profile_name)
    rprint(
        f"[green]✓[/green] Logged out of profile '{profile_name}'. "
        f"Run [cyan]ax auth login[/cyan] to sign in again."
    )
