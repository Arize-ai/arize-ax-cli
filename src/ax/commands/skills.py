"""Skills management commands for AI coding agents."""

import shutil
import tempfile
from pathlib import Path
from typing import Annotated

import questionary
import typer
from rich.console import Console
from rich.table import Table

from ax.coding_agents import (
    agent_for_label,
    agent_for_slug,
    agent_labels,
    agent_slugs,
    detected_agents,
)
from ax.config.manager import ConfigManager
from ax.core.decorators import handle_errors
from ax.core.exceptions import ConfigError, UsageError
from ax.skills_installer import (
    available_skills,
    download_skills,
    extract_skills,
    install_skills,
)
from ax.utils.console import (
    emphasis,
    info,
    new_line,
    spinner,
    success,
    text_dimmed,
    warning,
)

_INSTALL_AGENT_OPTION_HELP = (
    "Agent to install for (can be repeated). "
    f"Valid: {', '.join(agent_slugs())}. "
    "Required when using --yes."
)
_CLEAR_AGENT_OPTION_HELP = (
    "Agent to clear skills for (can be repeated). "
    f"Valid: {', '.join(agent_slugs())}."
)

app = typer.Typer(
    name="skills",
    help="Manage Arize AI agent skills",
    no_args_is_help=True,
    context_settings={"help_option_names": ["--help", "-h"]},
)

_console = Console(stderr=True)


def skills_dir_for(
    agent: str, *, is_global: bool, target_root: Path | None = None
) -> Path:
    """Return the skills directory for *agent*.

    Args:
        agent: Agent display name in the shared coding-agent registry.
        is_global: Install into the home directory rather than a project.
        target_root: Project root, required when *is_global* is False.

    Returns:
        The directory skills should be written into.

    Raises:
        UsageError: If *agent* is not a known agent.
    """
    adapter = agent_for_label(agent)
    if adapter is None:
        raise UsageError(f"Unknown agent: {agent}")
    return adapter.skills_dir(is_global=is_global, target_root=target_root)


def _detect_agents() -> list[str]:
    """Return agent display names that appear to be installed on this machine."""
    return [agent.label for agent in detected_agents()]


def _resolve_agents(
    requested_slugs: list[str] | None, yes: bool, detected: list[str]
) -> list[str]:
    """Return the list of agent display names to target.

    If --agent is given, validates the slugs and returns the matching display names.
    If --yes is given without --agent, raises UsageError (unsafe to default to all agents).
    Otherwise, shows an interactive checkbox with detected agents pre-checked.
    """
    if requested_slugs is not None:
        resolved = []
        for slug in requested_slugs:
            adapter = agent_for_slug(slug)
            if adapter is None:
                valid = ", ".join(agent_slugs())
                raise UsageError(
                    f"Unknown agent '{slug}'. Valid values: {valid}"
                )
            resolved.append(adapter.label)
        return resolved

    if yes:
        raise UsageError(
            "Specify at least one --agent when using --yes "
            f"(e.g. --agent claude-code). Valid values: {', '.join(agent_slugs())}"
        )

    # Interactive checkbox — pre-check detected agents
    if not detected:
        warning("No AI coding agents detected on this machine.")
        info("You can still select agents to install for.")
        new_line()

    all_agent_names = agent_labels()
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
            f"(valid agents: {', '.join(agent_slugs())})"
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
        verify = config.request_verify
    except ConfigError:
        verify = True

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_dir = Path(tmp_str)

        with spinner("Downloading skills from GitHub"):
            zip_path = download_skills(tmp_dir, verify=verify)

        with spinner("Extracting skills"):
            source_root = extract_skills(zip_path, tmp_dir)

        selected_skills = _select_skills(yes, available_skills(source_root))
        if not selected_skills:
            info("No skills selected. Exiting.")
            raise typer.Exit()

        new_line()

        # Install skills for each selected agent
        results: dict[str, list[str]] = {a: [] for a in selected_agents}

        for current_agent in selected_agents:
            adapter = agent_for_label(current_agent)
            if adapter is None:
                raise UsageError(f"Unknown agent: {current_agent}")
            target_dir = adapter.skills_dir(
                is_global=is_global, target_root=target_root
            )
            info(f"Installing skills for {current_agent}...")
            to_install: list[str] = []

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

                if should_copy:
                    to_install.append(skill)

            results[current_agent] = install_skills(
                adapter,
                is_global=is_global,
                target_root=target_root,
                force=True,
                source_root=source_root,
                skills=to_install,
            )

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
        selected_agents = _resolve_agents(agent, yes=False, detected=[])
    else:
        selected_agents = list(agent_labels())

    # Find which skills exist for the selected agents
    to_remove: dict[str, list[str]] = {}
    for current_agent in selected_agents:
        skills_dir = skills_dir_for(
            current_agent, is_global=is_global, target_root=target_root
        )

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
        skills_dir = skills_dir_for(
            current_agent, is_global=is_global, target_root=target_root
        )
        removed[current_agent] = []
        for skill_name in skill_names:
            # Several agents read project skills from the same `.agents/skills`
            # directory, so by the time a later agent is processed its skills may
            # already have been removed. Still reported against each agent,
            # because each one has genuinely lost them.
            target = skills_dir / skill_name
            if target.is_dir():
                shutil.rmtree(target)
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
