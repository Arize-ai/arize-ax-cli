"""Shared Arize skills download and installation operations."""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from ax.core.exceptions import FileIOError
from ax.utils.http import download_url

if TYPE_CHECKING:
    from ax.coding_agents import CodingAgentAdapter

SKILLS_REPO_ZIP = (
    "https://github.com/Arize-ai/arize-skills/archive/refs/heads/main.zip"
)
_SKILLS_ZIP_INNER_DIR = "arize-skills-main"


def download_skills(tmp_dir: Path, *, verify: bool = True) -> Path:
    """Download the skills archive to *tmp_dir*."""
    destination = tmp_dir / "arize-skills.zip"
    download_url(SKILLS_REPO_ZIP, destination, timeout=30, verify=verify)
    return destination


def extract_skills(zip_path: Path, tmp_dir: Path) -> Path:
    """Extract a skills archive and return its skills directory."""
    extract_dir = tmp_dir / "extracted"
    try:
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_dir)
    except Exception as exc:
        raise FileIOError(f"Failed to extract skills archive: {exc}") from exc

    skills_root = extract_dir / _SKILLS_ZIP_INNER_DIR / "skills"
    if not skills_root.exists():
        raise FileIOError(
            "Unexpected archive structure: skills/ not found inside "
            f"{_SKILLS_ZIP_INNER_DIR}"
        )
    return skills_root


def available_skills(source_root: Path) -> list[str]:
    """Return available skill directory names in deterministic order."""
    return sorted(
        entry.name for entry in source_root.iterdir() if entry.is_dir()
    )


def install_skills(
    agent: CodingAgentAdapter,
    *,
    is_global: bool = True,
    target_root: Path | None = None,
    force: bool = False,
    verify: bool = True,
    source_root: Path | None = None,
    skills: list[str] | None = None,
) -> list[str]:
    """Install selected Arize skills for an agent without prompting.

    When *source_root* is provided, callers can share one download across
    agents. Otherwise this function downloads and extracts the skills archive.
    """
    if source_root is None:
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_dir = Path(tmp_str)
            downloaded = download_skills(tmp_dir, verify=verify)
            extracted = extract_skills(downloaded, tmp_dir)
            return install_skills(
                agent,
                is_global=is_global,
                target_root=target_root,
                force=force,
                source_root=extracted,
                skills=skills,
            )

    target_dir = agent.skills_dir(
        is_global=is_global,
        target_root=target_root,
    )
    requested = skills if skills is not None else available_skills(source_root)
    installed: list[str] = []
    for skill in requested:
        source = source_root / skill
        destination = target_dir / skill
        if not source.exists() or (destination.exists() and not force):
            continue
        target_dir.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)
        installed.append(skill)
    return installed
