"""Hand the terminal to a coding agent.

Platform-split on purpose. On POSIX the process is replaced, so there is no
parent left to supervise — which is only safe because the staging directory is
cleared at the next launch rather than on exit.

``os.exec*`` cannot be used on Windows: it does not replace the process there but
starts a new one and ends this one, so the shell prompt returns while the agent
is still starting and the two contend for the console. Windows therefore runs the
agent as a child and waits, which is what the existing shell and Node launchers
do on that platform.

Never pass flags that skip an agent's approval prompts. The user's approval model
and the onboarding prompt's own approval gate both have to stay intact.
"""

from __future__ import annotations

import os
import subprocess

_ARGUMENT_ENV_PREFIX = "ARIZE_AX_INSTRUMENT_ARG_"
_SHIM_ENV = "ARIZE_AX_INSTRUMENT_SHIM"


def _is_batch_shim(binary: str) -> bool:
    """Return whether Windows must launch this executable through PowerShell."""
    return os.path.splitext(binary)[1].lower() in {".bat", ".cmd"}


def _powershell_executable() -> str:
    """Return the inbox Windows PowerShell executable."""
    system_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
    return os.path.join(
        system_root,
        "System32",
        "WindowsPowerShell",
        "v1.0",
        "powershell.exe",
    )


def _powershell_command(argument_count: int) -> str:
    """Build a fixed script that invokes the shim stored in its environment."""
    arguments = ", ".join(
        f"$env:{_ARGUMENT_ENV_PREFIX}{index}" for index in range(argument_count)
    )
    return f"& $env:{_SHIM_ENV} @({arguments}); exit $LASTEXITCODE"


def _powershell_environment(argv: list[str]) -> dict[str, str]:
    """Return a child environment containing the exact batch shim invocation."""
    child_environment = os.environ.copy()
    child_environment[_SHIM_ENV] = argv[0]
    child_environment.update(
        {
            f"{_ARGUMENT_ENV_PREFIX}{index}": argument
            for index, argument in enumerate(argv[1:])
        }
    )
    return child_environment


def exec_agent(argv: list[str]) -> int:
    """Run *argv*, replacing this process where the platform allows it.

    Args:
        argv: The full command, starting with the resolved executable path.

    Returns:
        The agent's exit code on Windows. On POSIX this does not return.

    Raises:
        OSError: If the agent could not be started.
    """
    if os.name == "nt":
        if _is_batch_shim(argv[0]):
            completed = subprocess.run(  # noqa: S603 - inbox PowerShell binary
                [
                    _powershell_executable(),
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    _powershell_command(len(argv) - 1),
                ],
                check=False,
                env=_powershell_environment(argv),
            )
            return completed.returncode

        completed = subprocess.run(  # noqa: S603 - resolved agent binary
            argv,
            check=False,
        )
        return completed.returncode

    os.execv(argv[0], argv)  # noqa: S606 - binary resolved via shutil.which
    return 0  # unreachable: os.execv replaces this process
