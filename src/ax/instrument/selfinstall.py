"""Make AX persistently available before handing over to an agent.

``uvx`` environments are ephemeral, so the launched agent would otherwise need
to install AX again. A failed persistent install is non-fatal: the prompt can
still perform that step.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from packaging.version import InvalidVersion, Version

from ax.version import __version__

if TYPE_CHECKING:
    from collections.abc import Mapping

PACKAGE = "arize-ax-cli"
_TIMEOUT_SECONDS = 300

ENV_SKIP = "ARIZE_SKIP_SELF_INSTALL"


@dataclass(frozen=True)
class Result:
    """Outcome of making the CLI persistent.

    Attributes:
        status: One of ``already-installed``, ``installed``, ``skipped`` or
            ``failed``.
        detail: Extra context for the status, if any.
    """

    status: str
    detail: str = ""


def _resolved(path: Path) -> Path | None:
    """Return *path* fully resolved, or None if the filesystem refuses."""
    try:
        return path.resolve()
    except OSError:
        return None


def _agent_ax() -> Path | None:
    """Return the AX executable the launched agent would resolve."""
    resolved = shutil.which("ax")
    return _resolved(Path(resolved)) if resolved else None


def _is_current_runtime(binary: Path) -> bool:
    """Return whether *binary* belongs to this command's own environment."""
    prefix = _resolved(Path(sys.prefix))
    return prefix is not None and binary.is_relative_to(prefix)


def _tool_dir(uv: str) -> Path | None:
    """Ask uv where it keeps persistent tool environments."""
    result = _run([uv, "tool", "dir"])
    if result is None or result.returncode != 0:
        return None
    output = (result.stdout or "").strip()
    return _resolved(Path(output)) if output else None


def _is_persistent_tool_runtime(binary: Path, uv: str) -> bool:
    """Return whether *binary* runs from AX's persistent uv tool environment."""
    if not _is_current_runtime(binary):
        return False
    tool_dir = _tool_dir(uv)
    prefix = _resolved(Path(sys.prefix))
    if tool_dir is None or prefix is None:
        return False
    return prefix == tool_dir / PACKAGE


def _version(binary: Path) -> Version | None:
    """Read a CLI version without importing code from that CLI's environment."""
    result = _run([str(binary), "--version"])
    if result is None or result.returncode != 0:
        return None
    match = re.search(
        r"\b(\d+(?:\.\d+)+(?:[-+][0-9A-Za-z.-]+)?)\b",
        (result.stdout or "") + (result.stderr or ""),
    )
    if match is None:
        return None
    try:
        return Version(match.group(1))
    except InvalidVersion:
        return None


def _is_ready(binary: Path | None, *, persistent_runtime: bool = False) -> bool:
    """Return whether an agent can use a persistent, compatible AX CLI."""
    if binary is None or (
        _is_current_runtime(binary) and not persistent_runtime
    ):
        return False
    version = _version(binary)
    return version is not None and version >= Version(__version__)


def _uv_binary() -> str | None:
    """Return the path to uv, or None if it cannot be found.

    uv exports ``UV`` when it runs a command, and that is the only way to find it
    in some environments: a ``uvx`` child gets its ephemeral environment on PATH
    but not uv itself, so a PATH lookup alone returns nothing.
    """
    from_env = os.environ.get("UV")
    if from_env and Path(from_env).is_file():
        return from_env
    return shutil.which("uv")


def _run(
    argv: list[str], *, env: Mapping[str, str] | None = None
) -> subprocess.CompletedProcess[str] | None:
    """Run *argv*, capturing output. None if it could not be run at all."""
    try:
        return subprocess.run(  # noqa: S603 - argv is built here, never shell
            argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _tool_bin_dir(uv: str) -> Path | None:
    """Ask uv where it puts tool executables."""
    result = _run([uv, "tool", "dir", "--bin"])
    if result is None or result.returncode != 0:
        return None
    output = (result.stdout or "").strip()
    return Path(output) if output else None


def _tool_ax(bin_dir: Path) -> Path | None:
    """Resolve AX in uv's tool directory, including Windows executable suffixes."""
    resolved = shutil.which("ax", path=str(bin_dir))
    return _resolved(Path(resolved)) if resolved else None


def _path_with_prepend(directory: Path, path: str) -> str:
    """Return *path* with *directory* first, without duplicate entries."""
    target = os.path.normcase(os.path.normpath(str(directory)))
    entries = [entry for entry in path.split(os.pathsep) if entry]
    remaining = [
        entry
        for entry in entries
        if os.path.normcase(os.path.normpath(entry)) != target
    ]
    return os.pathsep.join([str(directory), *remaining])


def _prepend_to_path(directory: Path) -> None:
    """Make *directory* the first executable directory inherited by the agent."""
    os.environ["PATH"] = _path_with_prepend(
        directory, os.environ.get("PATH", "")
    )


def ensure_persistent() -> Result:
    """Make AX available as a persistent, compatible command for an agent.

    Returns:
        What happened, for the caller to report. Never raises.
    """
    if os.environ.get(ENV_SKIP):
        return Result("skipped", "ARIZE_SKIP_SELF_INSTALL is set")

    agent_ax = _agent_ax()
    uv = _uv_binary()
    persistent_runtime = (
        agent_ax is not None
        and uv is not None
        and _is_persistent_tool_runtime(agent_ax, uv)
    )
    if _is_ready(agent_ax, persistent_runtime=persistent_runtime):
        version = _version(agent_ax) if agent_ax is not None else None
        return Result("already-installed", str(version or __version__))

    if uv is None:
        return Result("skipped", "no uv found")

    bin_dir = _tool_bin_dir(uv)
    if bin_dir is None:
        return Result("failed")

    # Pinned to our own version so the agent gets the CLI that launched it
    # rather than whatever happens to be newest. The child sees the destination
    # bin directory first so uv does not mistake this uvx runtime for the AX
    # command it is installing.
    result = _run(
        [uv, "tool", "install", "--force", f"{PACKAGE}=={__version__}"],
        env={
            **os.environ,
            "PATH": _path_with_prepend(bin_dir, os.environ.get("PATH", "")),
        },
    )
    if result is None or result.returncode != 0:
        return Result("failed")

    tool_ax = _tool_ax(bin_dir)
    if tool_ax is None or not _is_ready(tool_ax):
        return Result("failed")
    _prepend_to_path(bin_dir)
    return Result("installed", __version__)
