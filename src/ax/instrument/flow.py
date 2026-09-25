"""Typed operations for the ``ax instrument`` onboarding lifecycle."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Generic, TypeVar

from ax.core.exceptions import FileIOError
from ax.instrument import prompt as prompt_module
from ax.instrument.launch import exec_agent
from ax.instrument.selfinstall import Result as SelfInstallResult
from ax.instrument.selfinstall import ensure_persistent
from ax.instrument.staging import (
    build_seed,
    clear_onboarding_dir,
    prepare_onboarding_dir,
    stage_offline_bundle,
)
from ax.skills_installer import install_skills

if TYPE_CHECKING:
    from pathlib import Path

    from ax.coding_agents import CodingAgentAdapter


class Phase(StrEnum):
    """An ordered operation in interactive instrumentation."""

    PREFLIGHT = "preflight"
    PREPARE = "prepare"
    ACQUIRE = "acquire"
    STAGE = "stage"
    INSTALL = "install"
    HANDOFF = "handoff"


class Outcome(StrEnum):
    """Whether a phase completed, can be retried, or must stop the flow."""

    SUCCESS = "success"
    RETRYABLE_FAILURE = "retryable-failure"
    TERMINAL_FAILURE = "terminal-failure"


T = TypeVar("T")

_TERMINAL_PROMPT_FAILURES = (
    "manifest verification failed",
    "requires a newer AX CLI",
    "digest verification failed",
    "prompt is too short",
    "prompt is not valid UTF-8",
)


@dataclass(frozen=True)
class PhaseResult(Generic[T]):
    """The successful value or user-facing failure from one lifecycle phase."""

    phase: Phase
    value: T | None = None
    error: str | None = None
    exit_code: int | None = None
    outcome: Outcome = Outcome.SUCCESS

    @property
    def succeeded(self) -> bool:
        """Whether the phase produced a value."""
        return self.outcome is Outcome.SUCCESS and self.value is not None

    @classmethod
    def retryable_failure(cls, phase: Phase, error: str) -> PhaseResult[T]:
        """Create a phase result whose operation can safely be retried."""
        return cls(phase, error=error, outcome=Outcome.RETRYABLE_FAILURE)

    @classmethod
    def terminal_failure(
        cls, phase: Phase, error: str, *, exit_code: int | None = None
    ) -> PhaseResult[T]:
        """Create a phase result that cannot progress without a change."""
        return cls(
            phase,
            error=error,
            exit_code=exit_code,
            outcome=Outcome.TERMINAL_FAILURE,
        )


@dataclass(frozen=True)
class PreparedStaging:
    """An AX-owned directory cleared before an onboarding attempt."""

    path: Path
    fell_back: bool

    def cleanup(self) -> None:
        """Remove only AX-owned staging artifacts after an unsuccessful flow."""
        if clear_onboarding_dir(self.path) and self.fell_back:
            with suppress(OSError):
                self.path.rmdir()


@dataclass(frozen=True)
class StagedPrompt:
    """A verified prompt written to a directory owned by instrumentation."""

    path: Path
    fell_back: bool

    def cleanup(self) -> None:
        """Remove only AX-owned staging artifacts after an unsuccessful flow."""
        clear_onboarding_dir(self.path.parent)


@dataclass(frozen=True)
class InstallResult:
    """Non-fatal outcomes from making AX and its skills available to an agent."""

    self_install: SelfInstallResult
    installed_skills: int | None
    skills_error: str | None = None


def preflight(agent: CodingAgentAdapter) -> PhaseResult[str]:
    """Resolve the selected agent immediately before changing local state."""
    binary = agent.resolve_launch_binary()
    if binary is None:
        return PhaseResult.terminal_failure(
            Phase.PREFLIGHT, f"'{agent.id}' is no longer on your PATH."
        )
    return PhaseResult(Phase.PREFLIGHT, value=binary)


def acquire(*, verify: bool) -> PhaseResult[str]:
    """Download and authenticate the onboarding prompt without writing files."""
    try:
        return PhaseResult(
            Phase.ACQUIRE, value=prompt_module.resolve(verify=verify)
        )
    except FileIOError as exc:
        if any(marker in str(exc) for marker in _TERMINAL_PROMPT_FAILURES):
            return PhaseResult.terminal_failure(Phase.ACQUIRE, str(exc))
        return PhaseResult.retryable_failure(Phase.ACQUIRE, str(exc))


def prepare_staging(target_dir: Path) -> PhaseResult[PreparedStaging]:
    """Clear AX-owned artifacts before a network operation can fail."""
    try:
        staged_dir, fell_back = prepare_onboarding_dir(target_dir)
    except OSError as exc:
        return PhaseResult.retryable_failure(
            Phase.PREPARE,
            f"No writable directory to stage the onboarding prompt in: {exc}",
        )
    return PhaseResult(
        Phase.PREPARE, value=PreparedStaging(staged_dir, fell_back)
    )


def stage(
    prepared: PreparedStaging,
    prompt_text: str,
    offline_source: Path,
) -> PhaseResult[StagedPrompt]:
    """Write a verified prompt and optional offline bundle to prepared storage."""
    staged_dir = prepared.path

    prompt_file = staged_dir / prompt_module.PROMPT_FILE_NAME
    try:
        prompt_file.write_text(prompt_text, encoding="utf-8")
    except OSError as exc:
        prepared.cleanup()
        return PhaseResult.retryable_failure(
            Phase.STAGE, f"Could not write {prompt_file}: {exc}"
        )

    stage_offline_bundle(staged_dir, offline_source)
    return PhaseResult(
        Phase.STAGE,
        value=StagedPrompt(prompt_file, prepared.fell_back),
    )


def install(
    agent: CodingAgentAdapter, *, verify: bool
) -> PhaseResult[InstallResult]:
    """Persist AX when needed and install skills without blocking handoff."""
    self_install = ensure_persistent()
    try:
        installed = install_skills(agent, verify=verify, force=False)
    except (FileIOError, OSError) as exc:
        return PhaseResult(
            Phase.INSTALL,
            value=InstallResult(
                self_install,
                installed_skills=None,
                skills_error=str(exc),
            ),
        )
    return PhaseResult(
        Phase.INSTALL,
        value=InstallResult(self_install, installed_skills=len(installed)),
    )


def handoff(
    agent: CodingAgentAdapter, binary: str, staged: StagedPrompt
) -> PhaseResult[list[str]]:
    """Build the verified handoff argv after every earlier phase succeeded."""
    return PhaseResult(
        Phase.HANDOFF,
        value=agent.argv(binary, build_seed(staged.path)),
    )


def launch_agent(argv: list[str]) -> PhaseResult[int]:
    """Launch an agent while preserving staged completion on launch failure."""
    try:
        exit_code = exec_agent(argv)
    except OSError as exc:
        return PhaseResult.retryable_failure(Phase.HANDOFF, str(exc))
    if exit_code:
        return PhaseResult.terminal_failure(
            Phase.HANDOFF,
            f"agent exited with status {exit_code}",
            exit_code=exit_code,
        )
    return PhaseResult(Phase.HANDOFF, value=exit_code)
