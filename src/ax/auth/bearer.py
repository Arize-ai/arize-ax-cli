"""Transparent access-token refresh with file-level locking for concurrent CLI safety."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import tomli_w
import tomllib
from filelock import FileLock

from ax.auth import OAUTH_CLIENT_ID
from ax.auth.oauth_client import OAuthClient
from ax.config.schema import AuthConfig, OAuthCredentials
from ax.core.exceptions import ConfigError
from ax.core.network import NetworkSettings

# Refresh if the access token expires within this many seconds.
_REFRESH_WINDOW = timedelta(seconds=60)


def get_active_bearer(
    auth: AuthConfig,
    *,
    profile_path: Path,
    base_url: str,
    network: NetworkSettings | None = None,
) -> str:
    """Return the bearer credential to pass to the Arize SDK.

    - For API-key profiles, returns the key directly.
    - For OAuth profiles, returns the current access token — refreshing it
      via the /oauth2/token endpoint if it expires within 60 seconds.
    """
    if auth.api_key is not None:
        return auth.api_key
    if auth.oauth is None:
        raise ConfigError(
            "Profile is logged out. Run 'ax auth login' to sign in, or "
            "'ax profiles create --auth-method api-key' to use an API key."
        )

    now = datetime.now(timezone.utc)
    if auth.oauth.expires_at - now > _REFRESH_WINDOW:
        return auth.oauth.access_token

    return _refresh_and_persist(auth.oauth, profile_path, base_url, network)


def _refresh_and_persist(
    current: OAuthCredentials,
    profile_path: Path,
    base_url: str,
    network: NetworkSettings | None = None,
) -> str:
    """Refresh the OAuth token pair and persist it.

    Holds a file lock on the profile so concurrent ``ax`` invocations don't
    double-refresh.
    """
    lock_path = profile_path.with_suffix(profile_path.suffix + ".lock")
    with FileLock(str(lock_path), timeout=30):
        # Re-read inside the lock — a concurrent process may have just refreshed.
        if profile_path.exists():
            on_disk = _read_oauth(profile_path)
            if (
                on_disk is not None
                and on_disk.expires_at - datetime.now(timezone.utc)
                > _REFRESH_WINDOW
            ):
                return on_disk.access_token
            if on_disk is not None:
                current = on_disk

        client = OAuthClient(
            base_url=base_url,
            client_id=OAUTH_CLIENT_ID,
            network=network,
        )
        resp = client.refresh(refresh_token=current.refresh_token)
        new_expires = datetime.now(timezone.utc) + timedelta(
            seconds=resp.expires_in
        )
        new_oauth = OAuthCredentials(
            access_token=resp.access_token,
            refresh_token=resp.refresh_token,
            expires_at=new_expires,
            user_email=current.user_email,
        )
        _write_oauth(profile_path, new_oauth)
        return new_oauth.access_token


def _read_oauth(p: Path) -> OAuthCredentials | None:
    with p.open("rb") as f:
        data = tomllib.load(f)
    oauth = data.get("auth", {}).get("oauth")
    if not oauth:
        return None
    return OAuthCredentials(**oauth)


def _write_oauth(p: Path, oauth: OAuthCredentials) -> None:
    """Rewrite the profile TOML, preserving non-auth sections."""
    if p.exists():
        with p.open("rb") as f:
            data = tomllib.load(f)
    else:
        data = {}
    data.setdefault("auth", {})["oauth"] = {
        "access_token": oauth.access_token,
        "refresh_token": oauth.refresh_token,
        "expires_at": oauth.expires_at,
        "user_email": oauth.user_email,
    }
    with p.open("wb") as f:
        tomli_w.dump(data, f)
