"""Skills management commands for AI coding agents."""

import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Annotated

import questionary
import typer
from rich.console import Console
from rich.table import Table

from ax.config.manager import ConfigManager
from ax.core.decorators import handle_errors
from ax.core.exceptions import ConfigError, FileIOError, UsageError
from ax.core.network import NetworkSettings
from ax.utils.console import (
    emphasis,
    info,
    new_line,
    spinner,
    success,
    text_dimmed,
    warning,
)
from ax.utils.http import download_url

# NOTE: Downloads from `main` by default. This is intentional for now — the repo
# is internal and skills are just Markdown files. A future improvement would pin
# to a tagged release and verify a checksum before extracting.
# TODO: consider pinning to a tagged release + checksum verification once
# arize-skills adopts a release cadence.
SKILLS_REPO_ZIP = (
    "https://github.com/Arize-ai/arize-skills/archive/refs/heads/main.zip"
)
_SKILLS_ZIP_INNER_DIR = "arize-skills-main"

# agent display name -> (home config dir, binary name, skills subdir)
AGENTS: dict[str, tuple[str, str, str]] = {
    "Claude Code": (".claude", "claude", ".claude/skills"),
    "Cursor": (".cursor", "cursor", ".cursor/skills"),
    "Codex": (".codex", "codex", ".codex/skills"),
    "Windsurf": (".windsurf", "windsurf", ".windsurf/skills"),
}

# CLI slug -> display name (used for --agent option values)
AGENT_SLUGS: dict[str, str] = {
    "claude-code": "Claude Code",
    "cursor": "Cursor",
    "codex": "Codex",
    "windsurf": "Windsurf",
}

_INSTALL_AGENT_OPTION_HELP = (
    "Agent to install for (can be repeated). "
    f"Valid: {', '.join(AGENT_SLUGS)}. "
    "Required when using --yes."
)
_CLEAR_AGENT_OPTION_HELP = (
    "Agent to clear skills for (can be repeated). "
    f"Valid: {', '.join(AGENT_SLUGS)}."
)

app = typer.Typer(
    name="skills",
    help="Manage Arize AI agent skills",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)

_console = Console(stderr=True)


def _detect_agents() -> list[str]:
    """Return agent display names that appear to be installed on this machine."""
    detected = []
    for name, (home_dir, binary, _) in AGENTS.items():
        if (Path.home() / home_dir).exists() or shutil.which(
            binary
        ) is not None:
            detected.append(name)
    return detected


def _resolve_agents(
    agent_slugs: list[str] | None, yes: bool, detected: list[str]
) -> list[str]:
    """Return the list of agent display names to target.

    If --agent is given, validates the slugs and returns the matching display names.
    If --yes is given without --agent, raises UsageError (unsafe to default to all agents).
    Otherwise, shows an interactive checkbox with detected agents pre-checked.
    """
    if agent_slugs is not None:
        for slug in agent_slugs:
            if slug not in AGENT_SLUGS:
                valid = ", ".join(AGENT_SLUGS)
                raise UsageError(
                    f"Unknown agent '{slug}'. Valid values: {valid}"
                )
        return [AGENT_SLUGS[slug] for slug in agent_slugs]

    if yes:
        raise UsageError(
            "Specify at least one --agent when using --yes "
            f"(e.g. --agent claude-code). Valid values: {', '.join(AGENT_SLUGS)}"
        )

    # Interactive checkbox — pre-check detected agents
    if not detected:
        warning("No AI coding agents detected on this machine.")
        info("You can still select agents to install for.")
        new_line()

    all_agent_names = list(AGENTS.keys())
    try:
        result: list[str] | None = questionary.checkbox(
            "Which agents to install skills for?",
            choices=[
                questionary.Choice(
                    title=f"{name}  (detected)" if name in detected else name,
                    value=name,
                    checked=(name in detected),
                )
                for name in all_agent_names
            ],
        ).ask()
    except Exception:
        raise UsageError(
            "Interactive selection requires a TTY. "
            f"Specify agents non-interactively: --agent claude-code --yes  "
            f"(valid agents: {', '.join(AGENT_SLUGS)})"
        ) from None
    if result is None:
        raise typer.Abort()
    return result


def _select_skills(yes: bool, available: list[str]) -> list[str]:
    """Prompt the user to select which skills to install."""
    if yes:
        return list(available)

    try:
        result: list[str] | None = questionary.checkbox(
            "Which skills to install?",
            choices=[
                questionary.Choice(title=s, value=s, checked=True)
                for s in available
            ],
        ).ask()
    except Exception:
        raise UsageError(
            "Interactive selection requires a TTY. "
            "Use --yes to install all available skills non-interactively."
        ) from None
    if result is None:
        raise typer.Abort()
    return result


def _download_zip(
    tmp_dir: Path,
    *,
    verify: bool = True,
    network: NetworkSettings | None = None,
) -> Path:
    """Download the arize-skills zipball to tmp_dir and return the path."""
    dest = tmp_dir / "arize-skills.zip"
    download_url(
        SKILLS_REPO_ZIP,
        dest,
        timeout=30,
        verify=verify,
        network=network,
    )
    return dest


def _extract_zip(zip_path: Path, tmp_dir: Path) -> Path:
    """Extract the zipball and return the path to the skills/ subdirectory."""
    extract_dir = tmp_dir / "extracted"
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
    except Exception as e:
        raise FileIOError(f"Failed to extract skills archive: {e}") from e

    skills_root = extract_dir / _SKILLS_ZIP_INNER_DIR / "skills"
    if not skills_root.exists():
        raise FileIOError(
            f"Unexpected archive structure: skills/ not found inside {_SKILLS_ZIP_INNER_DIR}"
        )
    return skills_root


def _copy_skill(
    skill: str, source_root: Path, target_dir: Path, *, force: bool
) -> bool:
    """Copy a skill directory from source_root into target_dir.

    Returns True if the skill was copied, False if skipped (dest exists and force=False).
    """
    src = source_root / skill
    dest = target_dir / skill
    if not src.exists():
        return False
    if dest.exists() and not force:
        return False
    target_dir.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return True


def _resolve_target_root(
    global_install: bool, project_dir: Path | None
) -> tuple[bool, Path]:
    """Return (is_global, target_root) based on flags."""
    if global_install:
        return True, Path.home()
    root = project_dir.resolve() if project_dir else Path.cwd()
    if project_dir and not root.exists():
        raise UsageError(f"Directory does not exist: {root}")
    return False, root


@app.command("install")
@handle_errors
def install(
    agent: Annotated[
        list[str] | None,
        typer.Option("--agent", "-a", help=_INSTALL_AGENT_OPTION_HELP),
    ] = None,
    global_install: Annotated[
        bool,
        typer.Option(
            "--global",
            "-g",
            help="Install globally (~/.claude/skills/, ~/.cursor/skills/, etc.)",
        ),
    ] = False,
    project_dir: Annotated[
        Path | None,
        typer.Option(
            "--project-dir", "-d", help="Project directory (default: cwd)"
        ),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes", "-y", help="Skip confirmations. Requires --agent."
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Overwrite existing skills without prompting"
        ),
    ] = False,
) -> None:
    """Install Arize skills for AI coding agents (Claude Code, Cursor, Codex, Windsurf).

    Downloads skills from https://github.com/Arize-ai/arize-skills and installs
    them into each agent's skills directory. Defaults to the current project directory;
    use --global to install to ~/.claude/skills/ (and equivalent) instead.

    Examples:
      ax skills install                          # interactive

      ax skills install --agent claude-code      # interactive, Claude only

      ax skills install --agent claude-code --agent cursor --yes  # non-interactive
    """
    is_global, target_root = _resolve_target_root(global_install, project_dir)

    new_line()
    emphasis("Install Arize Skills")
    text_dimmed(
        "Installs context skills for AI coding agents so they understand Arize APIs."
    )
    if is_global:
        text_dimmed(
            "Scope: global (~/.claude/skills/, ~/.cursor/skills/, ~/.codex/skills/, ~/.windsurf/skills/)"
        )
    else:
        text_dimmed(f"Scope: project ({target_root})")
    new_line()

    detected = _detect_agents()
    selected_agents = _resolve_agents(agent, yes, detected)
    if not selected_agents:
        info("No agents selected. Exiting.")
        raise typer.Exit()

    new_line()

    try:
        config = ConfigManager.load()
    except ConfigError:
        verify = True
        network = NetworkSettings.from_environment()
    else:
        verify = config.request_verify
        network = NetworkSettings.from_config(
            config.network, request_verify=verify
        )

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_dir = Path(tmp_str)

        with spinner("Downloading skills from GitHub"):
            zip_path = _download_zip(tmp_dir, verify=verify, network=network)

        with spinner("Extracting skills"):
            source_root = _extract_zip(zip_path, tmp_dir)

        available_skills = sorted(
            d.name for d in source_root.iterdir() if d.is_dir()
        )
        selected_skills = _select_skills(yes, available_skills)
        if not selected_skills:
            info("No skills selected. Exiting.")
            raise typer.Exit()

        new_line()

        # Install skills for each selected agent
        results: dict[str, list[str]] = {a: [] for a in selected_agents}

        for current_agent in selected_agents:
            _, _, subdir = AGENTS[current_agent]
            target_dir = (
                Path.home() / subdir if is_global else target_root / subdir
            )
            info(f"Installing skills for {current_agent}...")

            for skill in selected_skills:
                dest = target_dir / skill
                should_copy = True

                if dest.exists() and not force:
                    if not yes:
                        overwrite = questionary.confirm(
                            f"Skill '{skill}' already exists for {current_agent}. Overwrite?",
                            default=False,
                        ).ask()
                        if overwrite is None:
                            raise typer.Abort()
                        should_copy = overwrite
                    else:
                        # --yes without --force: skip existing skills
                        should_copy = False

                # Pass force=True: the outer logic already decided to proceed
                if should_copy and _copy_skill(
                    skill, source_root, target_dir, force=True
                ):
                    results[current_agent].append(skill)

    # Summary table
    new_line()
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Agent")
    table.add_column("Installed Skills")

    any_installed = False
    for current_agent in selected_agents:
        installed = results[current_agent]
        if installed:
            any_installed = True
        table.add_row(
            current_agent,
            ", ".join(installed) if installed else "[dim]none[/dim]",
        )

    _console.print(table)
    new_line()

    if any_installed:
        success("Skills installation complete!")
        text_dimmed("Restart your agent to pick up the new skills.")
    else:
        info(
            "No new skills were installed. "
            "Skills already exist — use --force to overwrite."
        )


@app.command("clear")
@handle_errors
def clear(
    agent: Annotated[
        list[str] | None,
        typer.Option("--agent", "-a", help=_CLEAR_AGENT_OPTION_HELP),
    ] = None,
    global_install: Annotated[
        bool,
        typer.Option(
            "--global",
            "-g",
            help="Clear from global install (~/.claude/skills/, ~/.cursor/skills/, etc.)",
        ),
    ] = False,
    project_dir: Annotated[
        Path | None,
        typer.Option(
            "--project-dir", "-d", help="Project directory (default: cwd)"
        ),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation prompt."),
    ] = False,
) -> None:
    """Remove Arize skills installed by 'ax skills install'.

    Only removes skill directories whose names start with 'arize-'.
    User-created skills are not affected.
    """
    is_global, target_root = _resolve_target_root(global_install, project_dir)

    # If --agent is given, validate and use those; otherwise scan all known agents.
    if agent is not None:
        for slug in agent:
            if slug not in AGENT_SLUGS:
                valid = ", ".join(AGENT_SLUGS)
                raise UsageError(
                    f"Unknown agent '{slug}'. Valid values: {valid}"
                )
        selected_agents = [AGENT_SLUGS[slug] for slug in agent]
    else:
        selected_agents = list(AGENTS.keys())

    # Find which skills exist for the selected agents
    to_remove: dict[str, list[str]] = {}
    for current_agent in selected_agents:
        _, _, subdir = AGENTS[current_agent]
        skills_dir = Path.home() / subdir if is_global else target_root / subdir

        found = (
            sorted(
                d.name
                for d in skills_dir.iterdir()
                if d.is_dir() and d.name.startswith("arize-")
            )
            if skills_dir.exists()
            else []
        )
        if found:
            to_remove[current_agent] = found

    if not to_remove:
        info("No Arize skills found to remove.")
        raise typer.Exit()

    # Show what will be removed (skill names only — agent context is the group header)
    new_line()
    emphasis("The following skills will be removed:")
    for current_agent, skill_names in to_remove.items():
        _console.print(f"  [bold]{current_agent}[/bold]")
        for skill_name in skill_names:
            _console.print(f"    [dim]{skill_name}[/dim]")
    new_line()

    if not yes:
        confirmed = questionary.confirm(
            "Proceed with removal?", default=False
        ).ask()
        if confirmed is None:
            raise typer.Abort()
        if not confirmed:
            info("Aborted. No skills removed.")
            raise typer.Exit()

    removed: dict[str, list[str]] = {}
    for current_agent, skill_names in to_remove.items():
        _, _, subdir = AGENTS[current_agent]
        skills_dir = Path.home() / subdir if is_global else target_root / subdir
        removed[current_agent] = []
        for skill_name in skill_names:
            shutil.rmtree(skills_dir / skill_name)
            removed[current_agent].append(skill_name)

    # Summary
    new_line()
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Agent")
    table.add_column("Removed Skills")

    for current_agent, skills in removed.items():
        table.add_row(
            current_agent,
            ", ".join(skills) if skills else "[dim]none[/dim]",
        )

    _console.print(table)
    new_line()
    success("Skills removed.")
