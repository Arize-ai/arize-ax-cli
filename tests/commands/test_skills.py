"""Tests for skills CLI commands."""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ax.cli import app
from ax.commands.skills import AGENT_SLUGS, AGENTS

# Canonical --agent flags for all three agents (used in e2e tests)
_ALL_AGENT_FLAGS = [flag for slug in AGENT_SLUGS for flag in ("--agent", slug)]


@pytest.mark.e2e
class TestSkillsInstallAndClearE2E:
    """End-to-end tests that download real skills from GitHub."""

    def test_install_and_clear_local(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Install skills to a temp project dir, verify files, then clear them."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        # Install non-interactively for all agents in the tmp project dir
        result = runner.invoke(
            app,
            ["skills", "install", "--yes", "--force", *_ALL_AGENT_FLAGS],
        )
        assert result.exit_code == 0, f"install failed:\n{result.output}"

        # Every agent must have at least one skill installed, each with a SKILL.md
        for agent_name, (_, _, subdir) in AGENTS.items():
            skills_dir = tmp_path / subdir
            assert skills_dir.exists(), f"skills dir missing for {agent_name}"
            installed = [d for d in skills_dir.iterdir() if d.is_dir()]
            assert installed, f"No skills installed for {agent_name}"
            for skill_dir in installed:
                assert (skill_dir / "SKILL.md").exists(), (
                    f"Missing SKILL.md for '{skill_dir.name}' ({agent_name})"
                )

        # .arize-tmp-traces should NOT be created by skill install
        assert not (tmp_path / ".arize-tmp-traces").exists()

        # --- clear ---
        result = runner.invoke(
            app,
            ["skills", "clear", "--yes", *_ALL_AGENT_FLAGS],
        )
        assert result.exit_code == 0, f"clear failed:\n{result.output}"

        # All arize-* skill dirs should be gone
        for _, _, subdir in AGENTS.values():
            skills_dir = tmp_path / subdir
            remaining = (
                [
                    d
                    for d in skills_dir.iterdir()
                    if d.is_dir() and d.name.startswith("arize-")
                ]
                if skills_dir.exists()
                else []
            )
            assert not remaining, (
                f"Arize skills should have been removed but still exist: {remaining}"
            )

    def test_install_project_dir_flag(self, tmp_path: Path) -> None:
        """--project-dir flag targets a specific directory instead of cwd."""
        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "skills",
                "install",
                "--yes",
                "--force",
                "--project-dir",
                str(tmp_path),
                *_ALL_AGENT_FLAGS,
            ],
        )
        assert result.exit_code == 0, f"install failed:\n{result.output}"

        # All agents should have skills in tmp_path
        for _, _, subdir in AGENTS.values():
            assert (tmp_path / subdir).exists()

    def test_clear_no_skills_exits_cleanly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Clear on a directory with no skills exits cleanly."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        result = runner.invoke(
            app,
            ["skills", "clear", "--yes", *_ALL_AGENT_FLAGS],
        )
        assert result.exit_code == 0
        assert "No Arize skills found" in result.output

    def test_install_single_agent(self, tmp_path: Path) -> None:
        """--agent scopes installation to one agent only."""
        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "skills",
                "install",
                "--yes",
                "--agent",
                "claude-code",
                "--project-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, f"install failed:\n{result.output}"

        # Claude Code skills should be present (at least one)
        claude_skills_dir = tmp_path / ".claude/skills"
        assert claude_skills_dir.exists()
        assert any(claude_skills_dir.iterdir()), (
            "Expected at least one skill installed"
        )

        # Cursor, Codex, and Windsurf should NOT have been touched
        assert not (tmp_path / ".cursor/skills").exists()
        assert not (tmp_path / ".codex/skills").exists()
        assert not (tmp_path / ".windsurf/skills").exists()


class TestSkillsCommandRegistered:
    """Verify the skills subcommands are registered."""

    def test_install_registered(self) -> None:
        """Skills install subcommand is available."""
        from ax.commands.skills import app as skills_app

        names = [cmd.name for cmd in skills_app.registered_commands]
        assert "install" in names

    def test_clear_registered(self) -> None:
        """Skills clear subcommand is available."""
        from ax.commands.skills import app as skills_app

        names = [cmd.name for cmd in skills_app.registered_commands]
        assert "clear" in names

    def test_skills_registered_in_main_app(self) -> None:
        """Skills command group is registered in the main ax app."""
        runner = CliRunner()
        result = runner.invoke(app, ["skills", "--help"])
        assert result.exit_code == 0
        assert "install" in result.output
        assert "clear" in result.output


class TestResolveAgents:
    """Unit tests for _resolve_agents validation."""

    def test_yes_without_agent_raises_usage_error(self) -> None:
        """--yes without --agent should exit with a usage error."""
        runner = CliRunner()
        result = runner.invoke(app, ["skills", "install", "--yes"])
        assert result.exit_code != 0
        assert "--agent" in result.output

    def test_unknown_agent_slug_raises_usage_error(self) -> None:
        """An unrecognised --agent value should exit with a helpful error."""
        runner = CliRunner()
        result = runner.invoke(
            app, ["skills", "install", "--agent", "vscode", "--yes"]
        )
        assert result.exit_code != 0
        assert "vscode" in result.output

    def test_valid_slugs_are_accepted(self) -> None:
        """All documented agent slugs are accepted without error at validation stage."""
        from ax.commands.skills import AGENT_SLUGS, _resolve_agents

        # No detected agents, just validate slug resolution
        for slug, display_name in AGENT_SLUGS.items():
            result = _resolve_agents([slug], yes=False, detected=[])
            assert result == [display_name]

    def test_multiple_agents(self) -> None:
        """Multiple --agent values are all resolved."""
        from ax.commands.skills import _resolve_agents

        result = _resolve_agents(
            ["claude-code", "cursor"], yes=False, detected=[]
        )
        assert result == ["Claude Code", "Cursor"]


class TestDetectAgents:
    """Unit tests for _detect_agents."""

    def test_detects_via_home_dir(self, tmp_path: Path) -> None:
        """Agent is detected when its home config directory exists."""
        from ax.commands.skills import _detect_agents

        fake_claude = tmp_path / ".claude"
        fake_claude.mkdir()

        with (
            patch("ax.commands.skills.Path.home", return_value=tmp_path),
            patch("ax.commands.skills.shutil.which", return_value=None),
        ):
            detected = _detect_agents()

        assert "Claude Code" in detected

    def test_detects_via_binary(self, tmp_path: Path) -> None:
        """Agent is detected when its binary is found in PATH."""
        from ax.commands.skills import _detect_agents

        def fake_which(name: str) -> str | None:
            return "/usr/bin/cursor" if name == "cursor" else None

        with (
            patch("ax.commands.skills.Path.home", return_value=tmp_path),
            patch("ax.commands.skills.shutil.which", side_effect=fake_which),
        ):
            detected = _detect_agents()

        assert "Cursor" in detected
        assert "Claude Code" not in detected
        assert "Codex" not in detected
        assert "Windsurf" not in detected

    def test_no_agents_detected(self, tmp_path: Path) -> None:
        """Returns empty list when no agents are found."""
        from ax.commands.skills import _detect_agents

        with (
            patch("ax.commands.skills.Path.home", return_value=tmp_path),
            patch("ax.commands.skills.shutil.which", return_value=None),
        ):
            result = _detect_agents()

        assert result == []
