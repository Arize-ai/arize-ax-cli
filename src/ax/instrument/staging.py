"""Stage the verified onboarding prompt for the coding agent.

Cleanup names only AX-owned artifacts and never recurses or follows symlinks.
When the preferred private directory is unavailable, staging falls back to a
temporary directory.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from ax.instrument.prompt import PROMPT_FILE_NAME

# Written by the prompt when it traces the coding agent itself. It lives inside
# the cleared directory on purpose, so a stray key from a crashed run is removed.
ENV_FILE_NAME = "harness.env"

# The offline tracing bundle, staged beside the prompt.
OFFLINE_DIR_NAME = "arize-offline"
_OFFLINE_FILES = (
    "harness-install.sh",
    "harness-install.bat",
    "LICENSE-coding-harness-tracing",
)
_BUNDLE_EXTRA_FILES = ("MANIFEST",)

_STAGING_PREFIX = ".staging-"


def onboarding_dir(arize_dir: Path) -> Path:
    """Return the staging directory under *arize_dir*."""
    return arize_dir / "onboarding"


def _clear_bundle_dir(path: Path) -> bool:
    """Empty a staged bundle directory by naming everything we could put there.

    Stops without deleting anything further the moment it meets an entry it does
    not recognise. Wheel filenames carry a version that cannot be known ahead of
    time, so ``.whl`` is matched by extension, non-recursively, in this one
    directory.

    Returns:
        True if the directory was removed.
    """
    for entry in path.iterdir():
        known = (
            entry.name.endswith(".whl")
            or entry.name in _OFFLINE_FILES
            or entry.name in _BUNDLE_EXTRA_FILES
        )
        if entry.is_dir() or not known:
            return False
        entry.unlink()
    path.rmdir()
    return True


def clear_onboarding_dir(path: Path) -> bool:
    """Empty the staging directory by deleting exactly the files we create.

    Never a recursive delete. Two things follow: a wrong path can at worst try to
    unlink a handful of names that will not exist, and ``rmdir`` refuses a
    non-empty directory, so anything unexpected stops us instead of being
    destroyed. Unlinking a symlink removes the link, never its target.

    Returns:
        True when the directory is gone or empty and safe to stage into.
    """
    if not path.is_absolute():
        return False
    # A symlink here would make every operation below act on its target:
    # iterdir would list the target, unlink would delete the target's files, and
    # prepare_onboarding_dir would chmod the target to 0700. Refusing sends the
    # caller to a temporary directory instead.
    if path.is_symlink():
        return False
    if not path.exists():
        return True

    try:
        for entry in path.iterdir():
            # Symlinks are handled before the directory test, and never
            # descended into. `Path.is_dir()` follows the link, so a link named
            # `arize-offline` would otherwise send the loop below into whatever
            # it points at and unlink the wheels living there — deleting through
            # a link rather than deleting the link.
            if entry.is_symlink():
                if entry.name not in (PROMPT_FILE_NAME, ENV_FILE_NAME):
                    return False
                entry.unlink()
                continue
            if entry.is_dir():
                ours = entry.name == OFFLINE_DIR_NAME or entry.name.startswith(
                    _STAGING_PREFIX
                )
                if not ours or not _clear_bundle_dir(entry):
                    return False
                continue
            if entry.name not in (PROMPT_FILE_NAME, ENV_FILE_NAME):
                return False
            entry.unlink()
    except OSError:
        return False
    return True


def prepare_onboarding_dir(path: Path) -> tuple[Path, bool]:
    """Clear and create the staging directory.

    Degrades to a temporary directory when the given path cannot be used: a
    read-only home, a directory owned by another user after a past ``sudo`` run,
    a full disk, or an unrecognised file we refuse to delete. The work is
    attempted and allowed to fail rather than probing for writability first — a
    probe lies on NFS and ACL filesystems, races, and cannot see a full disk.

    Mode 0700 because the prompt writes credentials into this directory.

    Args:
        path: Preferred staging directory.

    Returns:
        A tuple of the directory used and whether it fell back to a temporary one.

    Raises:
        OSError: If even a temporary directory cannot be created.
    """
    if clear_onboarding_dir(path):
        try:
            path.mkdir(parents=True, exist_ok=True)
            if os.name != "nt":
                # mkdir's mode is filtered by the umask, so set it outright.
                # Windows has no POSIX mode; there the directory inherits the
                # profile's own access control.
                path.chmod(0o700)
        except OSError:
            pass
        else:
            return path, False

    return Path(tempfile.mkdtemp(prefix="arize-onboarding-")), True


def stage_offline_bundle(target_dir: Path, source_dir: Path) -> Path | None:
    """Copy the offline tracing bundle beside the prompt.

    Staging is all or nothing: the prompt decides which install path to take
    purely on whether this directory exists, so a partial one is worse than none.
    The bundle is built under a temporary name in the same parent and renamed
    into place, so the directory the prompt looks for only ever appears complete.

    Never raises. This is an enhancement, and any failure leaves the prompt to
    use its network path.

    Args:
        target_dir: The staging directory to copy into.
        source_dir: Directory holding the wheels and install scripts.

    Returns:
        The staged bundle directory, or None if nothing was staged.
    """
    if not source_dir.is_dir():
        return None

    staging: Path | None = None
    try:
        wheels = [f.name for f in source_dir.iterdir() if f.suffix == ".whl"]
        if not any(w.startswith("coding_harness_tracing-") for w in wheels):
            return None
        if not all((source_dir / f).exists() for f in _OFFLINE_FILES):
            return None

        staging = Path(tempfile.mkdtemp(prefix=_STAGING_PREFIX, dir=target_dir))
        for name in (*wheels, *_OFFLINE_FILES, *_BUNDLE_EXTRA_FILES):
            source = source_dir / name
            if source.exists():
                shutil.copyfile(source, staging / name)
        if os.name != "nt":
            (staging / "harness-install.sh").chmod(0o755)

        final = target_dir / OFFLINE_DIR_NAME
        staging.rename(final)
    except OSError:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        return None
    return final


def build_seed(prompt_file: Path) -> str:
    """Return the instruction that points an agent at *prompt_file*.

    The agent is told to read the file with its file-reading tool rather than a
    shell command: a shell ``cat`` of a 40 KB prompt returns a short preview and
    persists the rest, and an agent reading through the shell then works from the
    preview alone.
    """
    return (
        "Read this exact file in full with your file-reading tool, not a shell "
        f"command: {prompt_file}. Then follow it to set up Arize AX tracing, "
        "walking me through each step and asking me questions as needed."
    )
