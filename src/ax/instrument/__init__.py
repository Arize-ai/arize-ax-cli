"""The onboarding flow behind ``ax instrument``.

Picks a coding agent, makes this CLI and the Arize skills available to it, stages
the onboarding prompt, and hands over the terminal.
"""

from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path

import questionary
from rich.console import Console

from ax.coding_agents import (
    CodingAgentAdapter,
    instrumentation_agents,
    launchable_agents,
)
from ax.instrument.flow import (
    InstallResult,
    Outcome,
    acquire,
    handoff,
    install,
    launch_agent,
    preflight,
    prepare_staging,
    stage,
)
from ax.instrument.links import with_utm
from ax.instrument.staging import onboarding_dir
from ax.utils.console import (
    emphasis,
    error,
    info,
    new_line,
    spinner,
    success,
    text,
    text_dimmed,
    warning,
)

# Bundled beside this package when a release includes it. Absent in a plain
# checkout, in which case the prompt uses its network install path.
_OFFLINE_SOURCE = Path(__file__).parent / "assets" / "offline"


def _arize_dir() -> Path:
    """Return the Arize directory, honouring the SDK's environment variable.

    Read from the SDK's constants rather than by constructing an
    ``SDKConfiguration``: that validates credentials and raises
    ``MissingAPIKeyError`` when no key is set, and onboarding by definition runs
    before the user has one.
    """
    from arize.constants.config import (
        DEFAULT_ARIZE_DIRECTORY,
        ENV_ARIZE_DIRECTORY,
    )

    raw = os.environ.get(ENV_ARIZE_DIRECTORY) or DEFAULT_ARIZE_DIRECTORY
    return Path(raw).expanduser()


def _request_verify() -> bool:
    """Return the configured TLS verification setting, defaulting to on.

    ``ax skills install`` honours ``request_verify``, so this has to as well —
    otherwise the same download succeeds there and fails here behind a
    TLS-inspecting proxy. No configuration yet is the normal case for onboarding,
    and means the default.
    """
    from ax.config.manager import ConfigManager
    from ax.core.exceptions import ConfigError

    try:
        return bool(ConfigManager.load().request_verify)
    except ConfigError:
        return True


def _choose_agent() -> CodingAgentAdapter | str | None:
    """Ask which agent to use.

    Returns:
        The chosen agent, an install URL when none are installed, or None if the
        user cancelled.
    """
    found = launchable_agents()

    if found:
        text("Which coding agent should set up tracing?")
        new_line()
        return questionary.select(
            "Agent:",
            choices=[
                questionary.Choice(title=agent.label, value=agent)
                for agent in found
            ],
        ).ask()

    warning("No supported coding agent found on your PATH.")
    info("Pick one to open its install instructions, then run this again.")
    new_line()
    return questionary.select(
        "Install:",
        choices=[
            questionary.Choice(
                title=agent.label, value=agent.instrumentation_url
            )
            for agent in instrumentation_agents()
        ],
    ).ask()


def _report_self_install(result: InstallResult) -> None:
    """Print one line for the self-install step."""
    self_install = result.self_install
    if self_install.status == "already-installed":
        message = f"  Already installed ({self_install.detail})."
    elif self_install.status == "installed":
        message = f"  Installed {self_install.detail}."
    elif self_install.status == "failed":
        message = "  Skipped — the setup will install it instead."
    else:
        message = (
            f"  Skipped — {self_install.detail}."
            if self_install.detail
            else "  Skipped."
        )

    text_dimmed(message)


def _report_install(agent: CodingAgentAdapter, result: InstallResult) -> None:
    """Report the non-fatal installation phase."""
    _report_self_install(result)
    text(f"Installing the Arize skills for {agent.label}...")
    if result.skills_error:
        text_dimmed(f"  Skipped ({result.skills_error}).")
        text_dimmed("  The setup will follow the Arize docs instead.")
    elif result.installed_skills:
        text_dimmed(f"  {result.installed_skills} installed.")
    else:
        text_dimmed("  Already present.")


# No-terminal output is a two-line instruction intended for agent relay.
_stdout = Console(stderr=False, soft_wrap=True, highlight=False)


def _unwrapped(message: str) -> None:
    """Print *message* to stdout as exactly one line, whatever the width."""
    _stdout.print(message)


def _report_phase_failure(result: object, fallback: str) -> None:
    """Report a failed phase and whether retrying is useful."""
    phase_result = result
    message = getattr(phase_result, "error", None) or fallback
    error(message)
    if getattr(phase_result, "outcome", None) is Outcome.RETRYABLE_FAILURE:
        info("Retry this command after fixing the temporary problem.")


def _handoff_without_terminal() -> int:
    """Stage the prompt and address the person, when there is no terminal.

    Without a terminal, stage the verified prompt and tell the user where it is.
    """
    prepared = prepare_staging(onboarding_dir(_arize_dir()))
    if prepared.error is not None or prepared.value is None:
        _report_phase_failure(prepared, "Could not prepare onboarding staging.")
        return 1

    acquired = acquire(verify=_request_verify())
    if acquired.error is not None or acquired.value is None:
        prepared.value.cleanup()
        # A prompt that cannot be authenticated cannot safely be handed to the
        # agent, so stop rather than suggesting an unverified workaround.
        _report_phase_failure(
            acquired, "Could not acquire the onboarding prompt."
        )
        if acquired.outcome is Outcome.TERMINAL_FAILURE:
            new_line()
            text(
                "Do not retry and do not work around this. A sandbox this "
                "restricted blocks network access as well, so the setup could "
                "not finish. Tell the user to allow writes to their home "
                "directory and network access, or to run 'uvx arize-ax-cli "
                "instrument' in a terminal."
            )
        return 1

    staged = stage(prepared.value, acquired.value, _OFFLINE_SOURCE)
    if staged.error is not None or staged.value is None:
        _report_phase_failure(staged, "Could not stage the onboarding prompt.")
        return 1
    prompt_file = staged.value.path

    _unwrapped(
        "Run 'uvx arize-ax-cli instrument' in a terminal to install AX and "
        "skills and launch your coding agent — the prompt was staged here."
    )
    _unwrapped(
        f"The prompt is at {prompt_file} if you'd rather have your agent "
        "follow it."
    )
    return 0


def run() -> int:
    """Run the onboarding flow.

    Returns:
        A process exit code. On POSIX a successful launch replaces this process
        and never returns.
    """
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return _handoff_without_terminal()

    new_line()
    emphasis("Set up Arize AX tracing")
    text_dimmed(
        "Chooses a coding agent, gives it the Arize skills, and hands it a "
        "guided setup."
    )
    new_line()

    chosen = _choose_agent()
    if chosen is None:
        info("Nothing selected. Exiting.")
        return 0

    if isinstance(chosen, str):
        url = with_utm(chosen)
        info(f"Opening {url}")
        webbrowser.open(url)
        return 0

    checked = preflight(chosen)
    if checked.error is not None or checked.value is None:
        error(checked.error or "The selected agent is unavailable.")
        return 1

    new_line()
    text("Preparing onboarding staging...")
    prepared = prepare_staging(onboarding_dir(_arize_dir()))
    if prepared.error is not None or prepared.value is None:
        _report_phase_failure(prepared, "Could not prepare onboarding staging.")
        return 1

    verify = _request_verify()

    new_line()
    text("Verifying the onboarding prompt...")
    acquired = acquire(verify=verify)
    if acquired.error is not None or acquired.value is None:
        prepared.value.cleanup()
        _report_phase_failure(
            acquired, "Could not acquire the onboarding prompt."
        )
        return 1

    new_line()
    text("Staging the onboarding prompt...")
    staged = stage(prepared.value, acquired.value, _OFFLINE_SOURCE)
    if staged.error is not None or staged.value is None:
        _report_phase_failure(staged, "Could not stage the onboarding prompt.")
        return 1

    new_line()
    text("Making the AX CLI available to the agent...")
    with spinner("Making AX available and downloading skills"):
        installed = install(chosen, verify=verify)
    if installed.value is None:
        _report_phase_failure(installed, "Could not install AX prerequisites.")
        staged.value.cleanup()
        return 1
    _report_install(chosen, installed.value)

    if staged.value.fell_back:
        new_line()
        warning(
            f"Staged in {staged.value.path.parent} instead of the Arize directory."
        )
        text_dimmed(
            "Instrumenting an app still works. Tracing the coding agent itself "
            "needs a writable home directory."
        )

    new_line()
    success(f"Launching {chosen.label}...")
    new_line()

    launch = handoff(chosen, checked.value, staged.value)
    if launch.value is None:
        _report_phase_failure(launch, "Could not prepare the agent handoff.")
        return 1

    launched = launch_agent(launch.value)
    if launched.error is not None or launched.value is None:
        _report_phase_failure(
            launched, f"Could not launch {chosen.id}: {launched.error}"
        )
        info(
            "The verified prompt is staged and AX preparation completed. "
            "Fix the agent installation, then run 'ax instrument' to retry."
        )
        return launched.exit_code or 1
    return launched.value
