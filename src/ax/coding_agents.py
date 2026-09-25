"""Shared definitions for supported AI coding agents."""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

_ALL_PLATFORMS = frozenset({"darwin", "linux", "win32"})


@dataclass(frozen=True)
class CodingAgentAdapter:
    """Describe one coding agent's skills and launch integration.

    Attributes:
        id: Stable identifier and primary executable name.
        slug: Value accepted by ``ax skills --agent``.
        label: Human-readable agent name.
        home_marker: Relative home path that indicates the agent is configured.
        detection_binaries: Executable names that identify an installed agent.
        launch_binaries: Executable names verified for seeded instrumentation.
        global_skills_subdir: Skills path relative to the user's home directory.
        project_skills_subdir: Skills path relative to a project directory.
        platforms: Platform identifiers where the agent integration is supported.
        seeded_handoff_verified: Whether its seeded interactive launch is verified.
        install_url: Installation documentation for launchable agents.
        seed_flag: Flag used to pass a seeded prompt at launch time.
    """

    id: str
    slug: str
    label: str
    home_marker: str
    detection_binaries: tuple[str, ...]
    launch_binaries: tuple[str, ...]
    global_skills_subdir: str
    project_skills_subdir: str
    platforms: frozenset[str]
    seeded_handoff_verified: bool = False
    install_url: str | None = None
    seed_flag: str | None = None

    @property
    def supports_instrumentation(self) -> bool:
        """Whether AX can launch this agent with an onboarding prompt."""
        return (
            self.seeded_handoff_verified
            and self.install_url is not None
            and sys.platform in self.platforms
        )

    @property
    def instrumentation_url(self) -> str:
        """Return the installation URL for an instrumentation-capable agent."""
        if not self.supports_instrumentation or self.install_url is None:
            raise ValueError(f"{self.label} does not support instrumentation")
        return self.install_url

    def skills_dir(
        self, *, is_global: bool, target_root: Path | None = None
    ) -> Path:
        """Return the directory where this agent reads Arize skills."""
        if is_global:
            return Path.home() / self.global_skills_subdir
        root = target_root if target_root is not None else Path.cwd()
        return root / self.project_skills_subdir

    def _resolve(self, binaries: tuple[str, ...]) -> str | None:
        """Return the first executable from *binaries* found on PATH."""
        for binary in binaries:
            if path := shutil.which(binary):
                return path
        return None

    def resolve_detection_binary(self) -> str | None:
        """Return an executable path that establishes the agent is installed."""
        return self._resolve(self.detection_binaries)

    def resolve_launch_binary(self) -> str | None:
        """Return a verified executable path for seeded instrumentation."""
        return self._resolve(self.launch_binaries)

    def is_detected(self) -> bool:
        """Return whether the agent has a home marker or executable on PATH."""
        return (
            Path.home() / self.home_marker
        ).exists() or self.resolve_detection_binary() is not None

    def is_launchable(self) -> bool:
        """Return whether this agent can be launched for instrumentation now."""
        return (
            self.supports_instrumentation
            and self.resolve_launch_binary() is not None
        )

    def argv(self, binary: str, seed: str) -> list[str]:
        """Return the argv that launches this agent with *seed*."""
        if self.seed_flag:
            return [binary, self.seed_flag, seed]
        return [binary, seed]


CODING_AGENTS: tuple[CodingAgentAdapter, ...] = (
    CodingAgentAdapter(
        "claude",
        "claude-code",
        "Claude Code",
        ".claude",
        ("claude",),
        ("claude",),
        ".claude/skills",
        ".claude/skills",
        _ALL_PLATFORMS,
        True,
        "https://docs.claude.com/en/docs/claude-code",
    ),
    CodingAgentAdapter(
        "codex",
        "codex",
        "Codex",
        ".codex",
        ("codex",),
        ("codex",),
        ".codex/skills",
        ".codex/skills",
        _ALL_PLATFORMS,
        True,
        "https://developers.openai.com/codex/cli",
    ),
    CodingAgentAdapter(
        "cursor-agent",
        "cursor",
        "Cursor",
        ".cursor",
        ("cursor-agent", "cursor"),
        ("cursor-agent",),
        ".cursor/skills",
        ".cursor/skills",
        _ALL_PLATFORMS,
        True,
        "https://docs.cursor.com/en/cli/overview",
    ),
    CodingAgentAdapter(
        "windsurf",
        "windsurf",
        "Windsurf",
        ".windsurf",
        ("windsurf",),
        ("windsurf",),
        ".windsurf/skills",
        ".windsurf/skills",
        _ALL_PLATFORMS,
    ),
    CodingAgentAdapter(
        "copilot",
        "github-copilot",
        "GitHub Copilot",
        ".copilot",
        ("copilot",),
        ("copilot",),
        ".agents/skills",
        ".agents/skills",
        _ALL_PLATFORMS,
        True,
        "https://github.com/features/copilot/cli",
        seed_flag="-i",
    ),
    CodingAgentAdapter(
        "agy",
        "antigravity-cli",
        "Antigravity CLI",
        ".gemini/antigravity-cli",
        ("agy",),
        ("agy",),
        ".gemini/antigravity-cli/skills",
        ".agents/skills",
        _ALL_PLATFORMS,
        True,
        "https://antigravity.google/docs/cli/getting-started",
        seed_flag="-i",
    ),
)


def agent_slugs() -> tuple[str, ...]:
    """Return the stable command-line slugs in registry order."""
    return tuple(agent.slug for agent in CODING_AGENTS)


def agent_labels() -> tuple[str, ...]:
    """Return human-readable agent names in registry order."""
    return tuple(agent.label for agent in CODING_AGENTS)


def agent_for_slug(slug: str) -> CodingAgentAdapter | None:
    """Return the adapter identified by *slug*, if supported."""
    return next((agent for agent in CODING_AGENTS if agent.slug == slug), None)


def agent_for_label(label: str) -> CodingAgentAdapter | None:
    """Return the adapter identified by *label*, if supported."""
    return next(
        (agent for agent in CODING_AGENTS if agent.label == label), None
    )


def instrumentation_agents() -> tuple[CodingAgentAdapter, ...]:
    """Return adapters with a verified seeded instrumentation handoff."""
    return tuple(
        agent for agent in CODING_AGENTS if agent.supports_instrumentation
    )


def detected_agents(
    agents: tuple[CodingAgentAdapter, ...] = CODING_AGENTS,
) -> list[CodingAgentAdapter]:
    """Return installed agents, preserving registry order."""
    return [agent for agent in agents if agent.is_detected()]


def launchable_agents(
    agents: tuple[CodingAgentAdapter, ...] | None = None,
) -> list[CodingAgentAdapter]:
    """Return agents that can receive an interactive instrumentation handoff."""
    if agents is None:
        agents = instrumentation_agents()
    return [agent for agent in agents if agent.is_launchable()]
