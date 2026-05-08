"""Decorators enforcing credential-type preconditions on CLI commands.

The CLI must not open Arrow Flight connections under OAuth authentication
(Flight is REST-only under OAuth in v1 — see design spec). Today, the
`--all` flag is the only code path that triggers Flight. This decorator
rejects such invocations at argparse time, BEFORE any SDK client is built.
"""

from collections.abc import Callable
from functools import wraps
from typing import Any

import typer
from rich import print as rprint

from ax.config.manager import ConfigManager


def require_api_key_auth(
    flag_label: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Refuse to run the wrapped command under OAuth when ``use_all`` is set.

    Raises ``typer.Exit(code=2)`` if the active profile uses OAuth AND the
    wrapped command's ``use_all`` kwarg is truthy. ``flag_label`` is used
    only in the error message (e.g. ``"--all"``).
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            if not kwargs.get("use_all"):
                return fn(*args, **kwargs)

            try:
                cfg = ConfigManager.load(expand_env_vars=False)
            except Exception:
                # If we can't load the active profile, let the underlying
                # command surface its own error rather than masking it here.
                return fn(*args, **kwargs)

            if cfg.auth.uses_oauth:
                rprint(
                    f"[red]error:[/red] The {flag_label} flag requires an API key profile "
                    "(uses Arrow Flight, which is not supported under OAuth "
                    "authentication in this version).\n\n"
                    "Either:\n"
                    f"  - Run without {flag_label} (uses REST, limited to first page), or\n"
                    "  - Switch to an API key profile: [cyan]ax profiles use <name>[/cyan]"
                )
                raise typer.Exit(code=2)

            return fn(*args, **kwargs)

        return wrapper

    return decorator
