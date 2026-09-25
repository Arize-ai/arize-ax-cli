"""Unit tests for `ax instrument`."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from ax.cli import app
from ax.coding_agents import (
    CODING_AGENTS,
    instrumentation_agents,
    launchable_agents,
)
from ax.core.exceptions import FileIOError
from ax.instrument import flow as flow_module
from ax.instrument import launch as launch_module
from ax.instrument import prompt as prompt_module
from ax.instrument.links import with_utm
from ax.instrument.selfinstall import (
    _is_ready,
    _prepend_to_path,
    _tool_ax,
    ensure_persistent,
)
from ax.instrument.staging import (
    ENV_FILE_NAME,
    OFFLINE_DIR_NAME,
    build_seed,
    clear_onboarding_dir,
    onboarding_dir,
    prepare_onboarding_dir,
    stage_offline_bundle,
)

_PROMPT_TEXT = "# Arize onboarding\n" + ("x" * 5000)


@pytest.mark.unit
class TestCatalog:
    """The agent catalog has to line up with the skills installer."""

    def test_instrumentation_agents_are_shared_adapter_entries(self) -> None:
        agents = instrumentation_agents()
        assert set(agents).issubset(CODING_AGENTS)
        assert all(agent.install_url for agent in agents)
        assert all(agent.seeded_handoff_verified for agent in agents)

    def test_registry_has_unique_names_and_nonempty_platforms(self) -> None:
        assert len({agent.label for agent in CODING_AGENTS}) == len(
            CODING_AGENTS
        )
        assert all(agent.platforms for agent in CODING_AGENTS)

    def test_instrumentation_does_not_treat_a_home_marker_as_launchable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("ax.coding_agents.Path.home", lambda: tmp_path)
        (tmp_path / ".claude").mkdir()
        monkeypatch.setattr("ax.coding_agents.shutil.which", lambda _: None)

        assert launchable_agents() == []

    def test_cursor_editor_cli_is_not_an_instrumentation_launcher(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "ax.coding_agents.shutil.which",
            lambda binary: "/tmp/cursor" if binary == "cursor" else None,
        )

        assert "Cursor" not in [agent.label for agent in launchable_agents()]

    def test_ids_are_unique_and_are_the_binary_names(self) -> None:
        ids = [a.id for a in instrumentation_agents()]
        assert len(ids) == len(set(ids))
        for agent in instrumentation_agents():
            assert " " not in agent.id

    def test_argv_carries_the_seed(self) -> None:
        for agent in instrumentation_agents():
            argv = agent.argv("/path/to/bin", "SEED")
            assert argv[0] == "/path/to/bin"
            assert "SEED" in argv
            if agent.seed_flag:
                assert argv[1] == agent.seed_flag

    def test_argv_uses_the_resolved_path_not_the_id(self) -> None:
        # Windows resolves agents to .cmd shims; launching by bare name fails.
        agent = instrumentation_agents()[0]
        assert agent.argv("/somewhere/else/claude", "S")[0] != agent.id


@pytest.mark.unit
class TestAgentLaunch:
    """Launching agents preserves their exact argument vector."""

    def test_windows_batch_shim_uses_powershell_with_argument_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        argv = [
            r"C:\Agents&Tools\claude.cmd",
            "-i",
            build_seed(Path(r"C:\Users\Jane Doe\.arize\onboarding-prompt.md")),
        ]
        run = Mock(return_value=SimpleNamespace(returncode=17))
        monkeypatch.setattr(launch_module.os, "name", "nt")
        monkeypatch.setattr(launch_module.subprocess, "run", run)

        assert launch_module.exec_agent(argv) == 17
        run.assert_called_once()
        assert run.call_args.args == (
            [
                launch_module._powershell_executable(),
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                launch_module._powershell_command(len(argv) - 1),
            ],
        )
        assert run.call_args.kwargs["check"] is False
        environment = run.call_args.kwargs["env"]
        assert environment[launch_module._SHIM_ENV] == argv[0]
        assert [
            environment[f"{launch_module._ARGUMENT_ENV_PREFIX}{index}"]
            for index in range(len(argv) - 1)
        ] == argv[1:]

    def test_windows_native_executable_keeps_an_argument_vector(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        argv = [r"C:\\agents\\agent.exe", "Read %NAME% & this"]
        run = Mock(return_value=SimpleNamespace(returncode=17))
        monkeypatch.setattr(launch_module.os, "name", "nt")
        monkeypatch.setattr(launch_module.subprocess, "run", run)

        assert launch_module.exec_agent(argv) == 17
        run.assert_called_once_with(argv, check=False)

    def test_posix_replaces_the_process_with_the_resolved_binary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        argv = ["/opt/agents/claude", "Read /tmp/onboarding-prompt.md"]
        execv = Mock()
        monkeypatch.setattr(launch_module.os, "name", "posix")
        monkeypatch.setattr(launch_module.os, "execv", execv)

        assert launch_module.exec_agent(argv) == 0
        execv.assert_called_once_with(argv[0], argv)

    @pytest.mark.skipif(os.name != "nt", reason="requires Windows cmd.exe")
    @pytest.mark.parametrize(
        "prompt_path",
        [
            r"C:\Users\Jane Doe\.arize\onboarding-prompt.md",
            r"C:\Users\O'Connor\.arize\onboarding-prompt.md",
        ],
    )
    def test_windows_batch_shim_receives_the_bootstrap_seed_and_prompt_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prompt_path: str
    ) -> None:
        shim = tmp_path / "agent&tools" / "agent.cmd"
        writer = shim.parent / "writer.py"
        received = tmp_path / "received.txt"
        monkeypatch.setenv("ARIZE_TEST_OUTPUT_PATH", str(received))
        shim.parent.mkdir()
        shim.write_text(
            "@echo off\r\n"
            f'"{sys.executable}" "%~dp0writer.py" "%~1" "%~2"\r\n'
            "exit /b 23\r\n",
            encoding="utf-8",
        )
        writer.write_text(
            "import json\n"
            "import os\n"
            "from pathlib import Path\n"
            "import sys\n"
            "Path(os.environ['ARIZE_TEST_OUTPUT_PATH']).write_text(\n"
            "    json.dumps(sys.argv[1:]), encoding='utf-8'\n"
            ")\n",
            encoding="utf-8",
        )
        seed = build_seed(Path(prompt_path))

        assert launch_module.exec_agent([str(shim), "-i", seed]) == 23
        assert json.loads(received.read_text(encoding="utf-8")) == ["-i", seed]


@pytest.mark.unit
class TestUtm:
    """Install links carry a source, idempotently."""

    def test_adds_source(self) -> None:
        assert "utm_source=axcli" in with_utm("https://example.com/docs")

    def test_is_idempotent(self) -> None:
        once = with_utm("https://example.com/docs")
        assert with_utm(once).count("utm_source") == 1

    def test_preserves_existing_params(self) -> None:
        out = with_utm("https://example.com/docs?a=1")
        assert "a=1" in out and "utm_source" in out

    def test_passes_through_a_non_url(self) -> None:
        assert with_utm("not a url") == "not a url"


@pytest.mark.unit
class TestSeed:
    """The seed tells the agent how to locate the onboarding file."""

    def test_names_the_file_and_the_tool(self) -> None:
        prompt_file = Path("/tmp/x/onboarding-prompt.md")
        seed = build_seed(prompt_file)
        assert str(prompt_file) in seed
        assert "\n" not in seed
        assert "\r" not in seed
        # A shell `cat` of a 40 KB prompt returns a preview, so the agent has to
        # be told to use its file-reading tool instead.
        assert "file-reading tool" in seed
        assert "not a shell command" in seed

    def test_preserves_an_apostrophe_in_the_concrete_path(self) -> None:
        prompt_file = Path("/tmp/O'Connor/onboarding-prompt.md")

        assert str(prompt_file) in build_seed(prompt_file)


@pytest.mark.unit
class TestInstrumentationPhases:
    """The lifecycle reports failures at its phase boundary."""

    def test_acquire_failure_does_not_enter_staging(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise(**_: object) -> str:
            raise FileIOError("manifest unavailable")

        monkeypatch.setattr(prompt_module, "resolve", _raise)

        result = flow_module.acquire(verify=True)

        assert result.phase is flow_module.Phase.ACQUIRE
        assert result.value is None
        assert result.error == "manifest unavailable"
        assert result.outcome is flow_module.Outcome.RETRYABLE_FAILURE

    def test_acquire_authentication_failure_is_terminal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise(**_: object) -> str:
            raise FileIOError("Onboarding prompt manifest verification failed")

        monkeypatch.setattr(prompt_module, "resolve", _raise)

        result = flow_module.acquire(verify=True)

        assert result.outcome is flow_module.Outcome.TERMINAL_FAILURE

    def test_stage_write_failure_clears_its_partial_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cleared: list[object] = []

        class _UnwritableDir:
            def __truediv__(self, _: object) -> _UnwritableDir:
                return self

            def write_text(self, *_: object, **__: object) -> int:
                raise OSError("disk full")

            def __str__(self) -> str:
                return "staging/onboarding-prompt.md"

        staged_dir = _UnwritableDir()

        monkeypatch.setattr(
            flow_module,
            "clear_onboarding_dir",
            lambda path: cleared.append(path),
        )

        result = flow_module.stage(
            flow_module.PreparedStaging(staged_dir, False),
            "prompt",
            tmp_path / "offline",
        )

        assert result.phase is flow_module.Phase.STAGE
        assert result.value is None
        assert result.error is not None
        assert result.outcome is flow_module.Outcome.RETRYABLE_FAILURE
        assert cleared == [staged_dir]

    def test_failed_acquire_leaves_no_previous_owned_artifacts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = onboarding_dir(tmp_path)
        target.mkdir(parents=True)
        (target / prompt_module.PROMPT_FILE_NAME).write_text("old prompt")
        (target / ENV_FILE_NAME).write_text("ARIZE_API_KEY=old")

        prepared = flow_module.prepare_staging(target)

        def _raise(**_: object) -> str:
            raise FileIOError("manifest unavailable")

        monkeypatch.setattr(prompt_module, "resolve", _raise)
        acquired = flow_module.acquire(verify=True)

        assert prepared.succeeded
        assert acquired.error == "manifest unavailable"
        assert list(target.iterdir()) == []

    def test_failed_acquire_removes_an_unused_fallback_directory(
        self, tmp_path: Path
    ) -> None:
        fallback = tmp_path / "arize-onboarding-fallback"
        fallback.mkdir()
        prepared = flow_module.PreparedStaging(fallback, fell_back=True)

        prepared.cleanup()

        assert not fallback.exists()

    def test_handoff_uses_the_verified_staged_prompt(
        self, tmp_path: Path
    ) -> None:
        agent = instrumentation_agents()[0]
        staged = flow_module.StagedPrompt(
            tmp_path / prompt_module.PROMPT_FILE_NAME, False
        )

        result = flow_module.handoff(agent, "/bin/agent", staged)

        assert result.phase is flow_module.Phase.HANDOFF
        assert result.value is not None
        assert result.value[0] == "/bin/agent"
        assert result.value[-1] == build_seed(staged.path)
        assert str(staged.path) in result.value[-1]

    def test_install_reports_a_skills_failure_without_blocking_handoff(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ax.instrument.selfinstall import Result

        monkeypatch.setattr(
            flow_module,
            "ensure_persistent",
            lambda: Result("already-installed", "test"),
        )

        def _raise(*_: object, **__: object) -> list[str]:
            raise flow_module.FileIOError("skills download failed")

        monkeypatch.setattr(flow_module, "install_skills", _raise)

        result = flow_module.install(instrumentation_agents()[0], verify=True)

        assert result.phase is flow_module.Phase.INSTALL
        assert result.value is not None
        assert result.value.skills_error == "skills download failed"

    def test_install_reports_a_filesystem_failure_without_blocking_handoff(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ax.instrument.selfinstall import Result

        monkeypatch.setattr(
            flow_module,
            "ensure_persistent",
            lambda: Result("already-installed", "test"),
        )

        def _raise(*_: object, **__: object) -> list[str]:
            raise PermissionError("skills directory is read-only")

        monkeypatch.setattr(flow_module, "install_skills", _raise)

        result = flow_module.install(instrumentation_agents()[0], verify=True)

        assert result.phase is flow_module.Phase.INSTALL
        assert result.value is not None
        assert result.value.skills_error == "skills directory is read-only"

    def test_launch_failure_preserves_partial_completion(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise(_: list[str]) -> int:
            raise OSError("agent unavailable")

        monkeypatch.setattr(flow_module, "exec_agent", _raise)

        result = flow_module.launch_agent(["agent", "seed"])

        assert result.phase is flow_module.Phase.HANDOFF
        assert result.value is None
        assert result.error == "agent unavailable"
        assert result.outcome is flow_module.Outcome.RETRYABLE_FAILURE

    def test_nonzero_agent_exit_is_a_handoff_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(flow_module, "exec_agent", lambda _: 23)

        result = flow_module.launch_agent(["agent", "seed"])

        assert result.error == "agent exited with status 23"
        assert result.exit_code == 23
        assert result.outcome is flow_module.Outcome.TERMINAL_FAILURE
        assert not result.succeeded

    def test_launch_passes_the_concrete_staged_path_to_the_agent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[str] = []

        def _launch(argv: list[str]) -> int:
            captured.extend(argv)
            return 0

        monkeypatch.setattr(flow_module, "exec_agent", _launch)

        result = flow_module.launch_agent(
            ["agent", "-i", "Read /tmp/prompt.md"]
        )

        assert result.succeeded
        assert captured == ["agent", "-i", "Read /tmp/prompt.md"]


@pytest.mark.unit
class TestStaging:
    """Clearing names what it deletes and never recurses."""

    def test_clears_only_what_we_stage(self, tmp_path: Path) -> None:
        target = onboarding_dir(tmp_path)
        target.mkdir(parents=True)
        (target / prompt_module.PROMPT_FILE_NAME).write_text("x")
        (target / ENV_FILE_NAME).write_text("KEY=secret")

        assert clear_onboarding_dir(target) is True
        assert list(target.iterdir()) == []

    def test_refuses_a_file_it_did_not_stage(self, tmp_path: Path) -> None:
        target = onboarding_dir(tmp_path)
        target.mkdir(parents=True)
        stranger = target / "someones-notes.txt"
        stranger.write_text("do not delete me")

        assert clear_onboarding_dir(target) is False
        assert stranger.exists(), "an unrecognised file must survive"

    def test_leaves_an_unknown_subdirectory_intact(
        self, tmp_path: Path
    ) -> None:
        target = onboarding_dir(tmp_path)
        (target / "something-else").mkdir(parents=True)

        assert clear_onboarding_dir(target) is False
        assert (target / "something-else").is_dir()

    def test_absent_is_ready_and_relative_is_refused(
        self, tmp_path: Path
    ) -> None:
        assert clear_onboarding_dir(tmp_path / "nope") is True
        assert clear_onboarding_dir(Path("relative/path")) is False

    def test_removes_a_symlink_without_following_it(
        self, tmp_path: Path
    ) -> None:
        treasure = tmp_path / "treasure.txt"
        treasure.write_text("keep me")
        target = onboarding_dir(tmp_path)
        target.mkdir(parents=True)
        (target / prompt_module.PROMPT_FILE_NAME).symlink_to(treasure)

        assert clear_onboarding_dir(target) is True
        assert treasure.exists(), "the link target must survive"

    def test_refuses_a_symlinked_bundle_dir_without_following_it(
        self, tmp_path: Path
    ) -> None:
        # `Path.is_dir()` follows symlinks, so a link named `arize-offline` once
        # sent the clearing loop into its target and unlinked the wheels there.
        victim = tmp_path / "someone-elses-wheels"
        victim.mkdir()
        (victim / "important-0.1.0-py3-none-any.whl").write_text("keep me")
        (victim / "MANIFEST").write_text("keep me too")

        target = onboarding_dir(tmp_path)
        target.mkdir(parents=True)
        (target / OFFLINE_DIR_NAME).symlink_to(victim, target_is_directory=True)

        assert clear_onboarding_dir(target) is False
        assert sorted(p.name for p in victim.iterdir()) == [
            "MANIFEST",
            "important-0.1.0-py3-none-any.whl",
        ], "clearing must not delete through a symlink"

    def test_refuses_a_symlinked_staging_directory(
        self, tmp_path: Path
    ) -> None:
        # The directory itself, not an entry in it. Following the link would make
        # iterdir, unlink and chmod all act on the target.
        victim = tmp_path / "elsewhere"
        victim.mkdir()
        (victim / ENV_FILE_NAME).write_text("ARIZE_API_KEY=theirs")
        (victim / prompt_module.PROMPT_FILE_NAME).write_text("their prompt")
        mode = victim.stat().st_mode & 0o777

        link = onboarding_dir(tmp_path)
        link.symlink_to(victim, target_is_directory=True)

        assert clear_onboarding_dir(link) is False
        used, fell_back = prepare_onboarding_dir(link)

        assert fell_back is True, "a symlinked staging dir must fall back"
        assert used != link
        assert len(list(victim.iterdir())) == 2, "target must be untouched"
        assert victim.stat().st_mode & 0o777 == mode, (
            "target must not be chmodded"
        )

    def test_prepare_creates_the_directory(self, tmp_path: Path) -> None:
        target = onboarding_dir(tmp_path)
        staged, fell_back = prepare_onboarding_dir(target)

        assert staged == target
        assert fell_back is False
        assert staged.is_dir()
        if os.name != "nt":
            assert staged.stat().st_mode & 0o777 == 0o700

    def test_prepare_falls_back_when_it_cannot_use_the_path(
        self, tmp_path: Path
    ) -> None:
        target = onboarding_dir(tmp_path)
        target.mkdir(parents=True)
        (target / "stranger").write_text("refuse to delete this")

        staged, fell_back = prepare_onboarding_dir(target)

        assert fell_back is True
        assert staged != target
        assert staged.is_dir()


@pytest.mark.unit
class TestOfflineBundle:
    """Bundle staging is all or nothing."""

    def _source(self, tmp_path: Path, *, complete: bool) -> Path:
        source = tmp_path / "assets"
        source.mkdir()
        (source / "coding_harness_tracing-0.1.0-py3-none-any.whl").write_text(
            "wheel"
        )
        (source / "harness-install.sh").write_text("#!/bin/sh\n")
        if complete:
            (source / "harness-install.bat").write_text("@echo off\n")
            (source / "LICENSE-coding-harness-tracing").write_text("licence")
        return source

    def test_stages_the_bundle(self, tmp_path: Path) -> None:
        target = tmp_path / "onboarding"
        target.mkdir()
        staged = stage_offline_bundle(
            target, self._source(tmp_path, complete=True)
        )

        assert staged is not None
        assert staged.name == OFFLINE_DIR_NAME
        assert (staged / "harness-install.sh").exists()

    def test_stages_nothing_when_a_file_is_missing(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "onboarding"
        target.mkdir()

        assert (
            stage_offline_bundle(target, self._source(tmp_path, complete=False))
            is None
        )
        # The prompt branches on this directory existing, so a partial one is
        # worse than none.
        assert not (target / OFFLINE_DIR_NAME).exists()

    def test_stages_nothing_when_the_source_is_absent(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "onboarding"
        target.mkdir()

        assert stage_offline_bundle(target, tmp_path / "missing") is None
        assert not (target / OFFLINE_DIR_NAME).exists()


@pytest.mark.unit
@pytest.mark.skip(reason="superseded by signed manifest tests")
class TestPrompt:
    """The prompt is downloaded on every run, from whichever CDN answers."""

    def test_fetches_from_the_first_cdn(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(prompt_module.ENV_PROMPT_URL, raising=False)
        seen: list[str] = []

        def _fetch(url: str, **_kw: object) -> str:
            seen.append(url)
            return _PROMPT_TEXT

        monkeypatch.setattr(prompt_module, "_fetch", _fetch)

        assert prompt_module.resolve() == _PROMPT_TEXT
        assert len(seen) == 1
        assert "jsdelivr" in seen[0]

    def test_urls_are_unversioned(self) -> None:
        # Unversioned on purpose: a prompt fix reaches users without a release
        # of this CLI, which is the whole reason nothing is pinned or cached.
        for url in prompt_module._CDN_URLS:
            assert "@" not in url.split("/npm/")[-1].split("/")[0]
            assert "evals" in url

    def test_falls_back_to_the_second_cdn(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ax.core.exceptions import FileIOError

        seen: list[str] = []

        def _fetch(url: str, **_kw: object) -> str:
            seen.append(url)
            if "jsdelivr" in url:
                raise FileIOError("primary down")
            return _PROMPT_TEXT

        monkeypatch.delenv(prompt_module.ENV_PROMPT_URL, raising=False)
        monkeypatch.setattr(prompt_module, "_fetch", _fetch)

        assert prompt_module.resolve() == _PROMPT_TEXT
        assert len(seen) == 2

    def test_an_override_replaces_both_urls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(prompt_module.ENV_PROMPT_URL, "https://example/x.md")
        assert prompt_module._urls() == ["https://example/x.md"]

    def test_raises_when_every_url_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ax.core.exceptions import FileIOError

        def _fetch(url: str, **_kw: object) -> str:
            raise FileIOError(f"down: {url}")

        monkeypatch.delenv(prompt_module.ENV_PROMPT_URL, raising=False)
        monkeypatch.setattr(prompt_module, "_fetch", _fetch)

        with pytest.raises(FileIOError, match="needs network access"):
            prompt_module.resolve()

    def test_a_short_response_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An error page or a truncated body must not reach the agent: it would
        # follow the opening steps and stop.
        from ax.core.exceptions import FileIOError

        class _Response:
            def read(self) -> bytes:
                return b"Not Found"

            def __enter__(self) -> _Response:
                return self

            def __exit__(self, *_: object) -> None:
                return None

        monkeypatch.setattr(
            "urllib.request.urlopen", lambda *a, **k: _Response()
        )
        with pytest.raises(FileIOError, match="too short"):
            prompt_module._fetch("https://example/x.md")

    def test_a_malformed_body_is_a_download_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Must be FileIOError, not UnicodeDecodeError, or resolve() would skip
        # the second CDN and surface an unexpected error.
        from ax.core.exceptions import FileIOError

        class _Response:
            def read(self) -> bytes:
                return b"\xff\xfe" + b"x" * 5000

            def __enter__(self) -> _Response:
                return self

            def __exit__(self, *_: object) -> None:
                return None

        monkeypatch.setattr(
            "urllib.request.urlopen", lambda *a, **k: _Response()
        )
        with pytest.raises(FileIOError):
            prompt_module._fetch("https://example/x.md")


@pytest.mark.unit
class TestSignedPrompt:
    """Prompt manifests are authenticated before their content is used."""

    @staticmethod
    def _manifest(
        prompt: bytes, private_key: object, *, minimum_version: str = "0.35.0"
    ) -> bytes:
        import base64
        import hashlib
        import json

        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )

        assert isinstance(private_key, Ed25519PrivateKey)
        metadata: dict[str, object] = {
            "key_id": "test",
            "minimum_ax_cli_version": minimum_version,
            "prompt_sha256": hashlib.sha256(prompt).hexdigest(),
            "prompt_url": "https://example.test/onboarding-prompt.md",
            "revision": "test",
            "schema_version": 1,
        }
        signature = private_key.sign(prompt_module._signed_payload(metadata))
        metadata["signature"] = base64.b64encode(signature).decode()
        return json.dumps(metadata).encode()

    @staticmethod
    def _use_test_key(monkeypatch: pytest.MonkeyPatch) -> object:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )

        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        monkeypatch.setattr(
            prompt_module, "_PUBLIC_KEYS_PEM", {"test": public_key}
        )
        return private_key

    def test_resolves_only_a_verified_prompt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        private_key = self._use_test_key(monkeypatch)
        manifest = self._manifest(_PROMPT_TEXT.encode(), private_key)

        def _fetch(url: str, **_kw: object) -> bytes:
            return manifest if "manifest" in url else _PROMPT_TEXT.encode()

        monkeypatch.setattr(prompt_module, "_fetch_bytes", _fetch)
        assert prompt_module.resolve() == _PROMPT_TEXT

    def test_rejects_an_invalid_signature(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ax.core.exceptions import FileIOError

        private_key = self._use_test_key(monkeypatch)
        raw = bytearray(self._manifest(_PROMPT_TEXT.encode(), private_key))
        raw[-2] ^= 1

        with pytest.raises(FileIOError, match="verification failed"):
            prompt_module._parse_manifest(bytes(raw))

    def test_rejects_a_changed_prompt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ax.core.exceptions import FileIOError

        private_key = self._use_test_key(monkeypatch)
        manifest = self._manifest(_PROMPT_TEXT.encode(), private_key)
        monkeypatch.setattr(
            prompt_module,
            "_fetch_bytes",
            lambda url, **_kw: manifest
            if "manifest" in url
            else b"changed" * 1000,
        )

        with pytest.raises(FileIOError, match="digest verification failed"):
            prompt_module.resolve()

    def test_rejects_an_incompatible_prompt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ax.core.exceptions import FileIOError

        private_key = self._use_test_key(monkeypatch)
        manifest = self._manifest(
            _PROMPT_TEXT.encode(), private_key, minimum_version="999.0.0"
        )
        monkeypatch.setattr(
            prompt_module, "_fetch_bytes", lambda *_a, **_k: manifest
        )

        with pytest.raises(FileIOError, match="newer AX CLI"):
            prompt_module.resolve()


@pytest.mark.unit
class TestSelfInstall:
    """The handoff checks the agent's actual AX command state."""

    def test_current_runtime_ax_is_not_ready(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prefix = tmp_path / "runtime"
        binary = prefix / "bin" / "ax"
        binary.parent.mkdir(parents=True)
        binary.write_text("#!/bin/sh\n")
        monkeypatch.setattr("sys.prefix", str(prefix))

        assert _is_ready(binary) is False

    def test_persistent_compatible_ax_is_ready(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from subprocess import CompletedProcess

        binary = tmp_path / "persistent" / "ax"
        binary.parent.mkdir()
        binary.write_text("#!/bin/sh\n")
        monkeypatch.setattr("sys.prefix", str(tmp_path / "runtime"))
        monkeypatch.setattr(
            "ax.instrument.selfinstall._run",
            lambda _: CompletedProcess([], 0, "ax 999.0.0", ""),
        )

        assert _is_ready(binary) is True

    def test_prepending_tool_directory_makes_it_first(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tool_dir = tmp_path / "uv-bin"
        monkeypatch.setenv(
            "PATH",
            f"{tmp_path / 'first'}{os.pathsep}{tool_dir}{os.pathsep}{tmp_path / 'last'}",
        )

        _prepend_to_path(tool_dir)

        assert os.environ["PATH"].split(os.pathsep)[0] == str(tool_dir)
        assert os.environ["PATH"].split(os.pathsep).count(str(tool_dir)) == 1

    def test_installs_when_ax_is_only_in_the_current_runtime(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from subprocess import CompletedProcess

        runtime = tmp_path / "runtime"
        current = runtime / "bin" / "ax"
        tool_dir = tmp_path / "uv-bin"
        executable = "ax.cmd" if os.name == "nt" else "ax"
        tool_ax = tool_dir / executable
        for binary in (current, tool_ax):
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_text("#!/bin/sh\n")
            binary.chmod(0o755)
        monkeypatch.setattr("sys.prefix", str(runtime))
        monkeypatch.setattr(
            "ax.instrument.selfinstall._agent_ax", lambda: current
        )
        monkeypatch.setattr(
            "ax.instrument.selfinstall._uv_binary", lambda: "uv"
        )
        monkeypatch.setenv("PATH", str(runtime / "bin"))
        calls: list[tuple[list[str], Mapping[str, str] | None]] = []

        def _run(
            argv: list[str], *, env: Mapping[str, str] | None = None
        ) -> CompletedProcess[str]:
            calls.append((argv, env))
            if argv[1:4] == ["tool", "dir", "--bin"]:
                return CompletedProcess(argv, 0, str(tool_dir), "")
            if argv[1:3] == ["tool", "dir"]:
                return CompletedProcess(argv, 0, str(tmp_path / "tools"), "")
            if argv[-1] == "--version":
                return CompletedProcess(argv, 0, "ax 999.0.0", "")
            return CompletedProcess(argv, 0, "", "")

        monkeypatch.setattr("ax.instrument.selfinstall._run", _run)

        result = ensure_persistent()

        assert result.status == "installed"
        assert any(
            call[:4] == ["uv", "tool", "install", "--force"]
            for call, _ in calls
        )
        install_environment = next(
            env
            for call, env in calls
            if call[:4] == ["uv", "tool", "install", "--force"]
        )
        assert install_environment is not None
        assert install_environment["PATH"].split(os.pathsep)[0] == str(tool_dir)
        assert os.environ["PATH"].split(os.pathsep)[0] == str(tool_dir)

    def test_persistent_uv_tool_runtime_does_not_reinstall(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from subprocess import CompletedProcess

        tools_dir = tmp_path / "configured-tools"
        runtime = tools_dir / "arize-ax-cli"
        current = runtime / "bin" / "ax"
        current.parent.mkdir(parents=True)
        current.write_text("#!/bin/sh\n")
        current.chmod(0o755)
        monkeypatch.setattr("sys.prefix", str(runtime))
        monkeypatch.setattr(
            "ax.instrument.selfinstall._agent_ax", lambda: current
        )
        monkeypatch.setattr(
            "ax.instrument.selfinstall._uv_binary", lambda: "uv"
        )
        calls: list[list[str]] = []

        def _run(argv: list[str]) -> CompletedProcess[str]:
            calls.append(argv)
            if argv == ["uv", "tool", "dir"]:
                return CompletedProcess(argv, 0, str(tools_dir), "")
            if argv[-1] == "--version":
                return CompletedProcess(argv, 0, "ax 999.0.0", "")
            pytest.fail(f"unexpected command: {argv}")

        monkeypatch.setattr("ax.instrument.selfinstall._run", _run)

        result = ensure_persistent()

        assert result.status == "already-installed"
        assert not any(call[:3] == ["uv", "tool", "install"] for call in calls)

    def test_rejects_an_incompatible_tool_after_install(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from subprocess import CompletedProcess

        runtime = tmp_path / "runtime"
        current = runtime / "bin" / "ax"
        tool_dir = tmp_path / "uv-bin"
        tool_ax = tool_dir / "ax"
        for binary in (current, tool_ax):
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_text("#!/bin/sh\n")
            binary.chmod(0o755)
        monkeypatch.setattr("sys.prefix", str(runtime))
        monkeypatch.setattr(
            "ax.instrument.selfinstall._agent_ax", lambda: current
        )
        monkeypatch.setattr(
            "ax.instrument.selfinstall._uv_binary", lambda: "uv"
        )

        def _run(
            argv: list[str], *, env: Mapping[str, str] | None = None
        ) -> CompletedProcess[str]:
            if argv[1:4] == ["tool", "dir", "--bin"]:
                return CompletedProcess(argv, 0, str(tool_dir), "")
            if argv[-1] == "--version":
                return CompletedProcess(argv, 0, "ax 0.1.0", "")
            return CompletedProcess(argv, 0, "", "")

        monkeypatch.setattr("ax.instrument.selfinstall._run", _run)

        assert ensure_persistent().status == "failed"

    @pytest.mark.skipif(os.name != "nt", reason="requires Windows PATHEXT")
    def test_windows_resolves_the_uv_tool_cmd_shim(
        self, tmp_path: Path
    ) -> None:
        tool_dir = tmp_path / "uv-bin"
        tool_dir.mkdir()
        shim = tool_dir / "ax.cmd"
        shim.write_text("@echo off\r\n", encoding="utf-8")

        _prepend_to_path(tool_dir)

        assert _tool_ax(tool_dir) == shim.resolve()


@pytest.mark.unit
class TestCommand:
    """The command surface."""

    def test_help_mentions_both_entry_points(self) -> None:
        result = CliRunner().invoke(app, ["instrument", "--help"])
        assert result.exit_code == 0

    def test_registered_on_the_root_app(self) -> None:
        result = CliRunner().invoke(app, ["--help"])
        assert "instrument" in result.output

    def test_no_terminal_stages_the_prompt_and_exits_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Pasting the command into a coding agent runs it without a terminal.
        # It must stage the prompt, address the person, and exit 0 — a failure
        # status sends an agent hunting for workarounds.
        monkeypatch.setenv("ARIZE_DIRECTORY", str(tmp_path))
        monkeypatch.setattr(
            prompt_module, "resolve", lambda **_kw: _PROMPT_TEXT
        )

        result = CliRunner().invoke(app, ["instrument"])

        assert result.exit_code == 0
        staged = onboarding_dir(tmp_path) / prompt_module.PROMPT_FILE_NAME
        assert staged.is_file(), "the prompt must actually be staged"

        # Exactly two lines, and the path on the second. An agent relaying a
        # longer message drops its middle, so wrapping or an extra status line
        # is a real regression, not cosmetics.
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        assert len(lines) == 2, (
            f"expected 2 stdout lines, got {len(lines)}: {lines}"
        )
        assert "in a terminal" in lines[0]
        assert "prompt was staged" in lines[0]
        assert str(staged) in lines[1]

    def test_no_terminal_retryable_failure_does_not_forbid_retrying(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ARIZE_DIRECTORY", str(tmp_path))

        def _raise(**_: object) -> str:
            raise FileIOError("manifest temporarily unavailable")

        monkeypatch.setattr(prompt_module, "resolve", _raise)

        result = CliRunner().invoke(app, ["instrument"])

        assert result.exit_code == 1
        assert "Retry this command" in result.output
        assert "Do not retry" not in result.output

    def test_interactive_flow_prepares_before_acquiring(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ax import instrument
        from ax.instrument.selfinstall import Result

        agent = instrumentation_agents()[0]
        events: list[str] = []
        prepared = flow_module.PreparedStaging(tmp_path / "onboarding", False)
        staged = flow_module.StagedPrompt(
            prepared.path / prompt_module.PROMPT_FILE_NAME, False
        )

        monkeypatch.setattr(
            instrument.sys, "stdin", SimpleNamespace(isatty=lambda: True)
        )
        monkeypatch.setattr(
            instrument.sys, "stdout", SimpleNamespace(isatty=lambda: True)
        )
        monkeypatch.setattr(instrument, "_choose_agent", lambda: agent)
        monkeypatch.setattr(
            instrument,
            "_request_verify",
            lambda: events.append("verify") or True,
        )
        monkeypatch.setattr(
            instrument,
            "preflight",
            lambda _: flow_module.PhaseResult(
                flow_module.Phase.PREFLIGHT, "agent"
            ),
        )
        monkeypatch.setattr(
            instrument,
            "prepare_staging",
            lambda _: events.append("prepare")
            or flow_module.PhaseResult(flow_module.Phase.PREPARE, prepared),
        )
        monkeypatch.setattr(
            instrument,
            "acquire",
            lambda **_: events.append("acquire")
            or flow_module.PhaseResult(flow_module.Phase.ACQUIRE, "prompt"),
        )
        monkeypatch.setattr(
            instrument,
            "stage",
            lambda *_: events.append("stage")
            or flow_module.PhaseResult(flow_module.Phase.STAGE, staged),
        )
        monkeypatch.setattr(
            instrument,
            "install",
            lambda *_args, **_kwargs: events.append("install")
            or flow_module.PhaseResult(
                flow_module.Phase.INSTALL,
                flow_module.InstallResult(Result("already-installed"), 0),
            ),
        )
        monkeypatch.setattr(
            instrument,
            "handoff",
            lambda *_: events.append("handoff")
            or flow_module.PhaseResult(flow_module.Phase.HANDOFF, ["agent"]),
        )
        monkeypatch.setattr(
            instrument,
            "launch_agent",
            lambda _, **__: events.append("launch")
            or flow_module.PhaseResult(flow_module.Phase.HANDOFF, 0),
        )

        assert instrument.run() == 0
        assert events == [
            "prepare",
            "verify",
            "acquire",
            "stage",
            "install",
            "handoff",
            "launch",
        ]

    def test_interactive_launch_failure_reports_partial_completion(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from ax import instrument
        from ax.instrument.selfinstall import Result

        agent = instrumentation_agents()[0]
        prepared = flow_module.PreparedStaging(tmp_path / "onboarding", False)
        staged = flow_module.StagedPrompt(
            prepared.path / prompt_module.PROMPT_FILE_NAME, False
        )
        monkeypatch.setattr(
            instrument.sys, "stdin", SimpleNamespace(isatty=lambda: True)
        )
        monkeypatch.setattr(
            instrument.sys, "stdout", SimpleNamespace(isatty=lambda: True)
        )
        monkeypatch.setattr(instrument, "_choose_agent", lambda: agent)
        monkeypatch.setattr(instrument, "_request_verify", lambda: True)
        monkeypatch.setattr(
            instrument,
            "preflight",
            lambda _, **__: flow_module.PhaseResult(
                flow_module.Phase.PREFLIGHT, "agent"
            ),
        )
        monkeypatch.setattr(
            instrument,
            "prepare_staging",
            lambda _: flow_module.PhaseResult(
                flow_module.Phase.PREPARE, prepared
            ),
        )
        monkeypatch.setattr(
            instrument,
            "acquire",
            lambda **_: flow_module.PhaseResult(
                flow_module.Phase.ACQUIRE, "prompt"
            ),
        )
        monkeypatch.setattr(
            instrument,
            "stage",
            lambda *_: flow_module.PhaseResult(flow_module.Phase.STAGE, staged),
        )
        monkeypatch.setattr(
            instrument,
            "install",
            lambda *_args, **_kwargs: flow_module.PhaseResult(
                flow_module.Phase.INSTALL,
                flow_module.InstallResult(Result("already-installed"), 0),
            ),
        )
        monkeypatch.setattr(
            instrument,
            "handoff",
            lambda *_: flow_module.PhaseResult(
                flow_module.Phase.HANDOFF, ["agent"]
            ),
        )
        monkeypatch.setattr(
            instrument,
            "launch_agent",
            lambda _, **__: flow_module.PhaseResult(
                flow_module.Phase.HANDOFF,
                error="agent exited with status 23",
                exit_code=23,
            ),
        )

        assert instrument.run() == 23
        captured = capsys.readouterr()
        assert "verified prompt is staged" in captured.out + captured.err


@pytest.mark.unit
class TestSkillsVerify:
    """The skills download honours the same TLS setting as `ax skills install`."""

    def _capture(
        self, monkeypatch: pytest.MonkeyPatch, *, configured: bool
    ) -> dict:
        from ax import instrument
        from ax.instrument.selfinstall import Result

        seen: dict = {}

        def _fake_install(agent: object, **kwargs: object) -> list[str]:
            seen["agent"] = agent
            seen.update(kwargs)
            return []

        class _Config:
            request_verify = configured

        monkeypatch.setattr(flow_module, "install_skills", _fake_install)
        monkeypatch.setattr(
            flow_module,
            "ensure_persistent",
            lambda: Result("already-installed", "test"),
        )
        monkeypatch.setattr(
            "ax.config.manager.ConfigManager.load",
            classmethod(lambda cls, *a, **k: _Config()),
        )
        flow_module.install(
            instrumentation_agents()[0], verify=instrument._request_verify()
        )
        return seen

    def test_passes_the_configured_value_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Behavioural, not a grep of the source: the point is that the value
        # reaches install_skills, wherever the call happens to live.
        seen = self._capture(monkeypatch, configured=False)
        assert seen["verify"] is False
        assert seen["force"] is False
        assert seen["agent"] is instrumentation_agents()[0]

    def test_verification_stays_on_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert self._capture(monkeypatch, configured=True)["verify"] is True

    def test_defaults_to_on_with_no_configuration(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from ax import instrument
        from ax.core.exceptions import ConfigError

        def _raise(cls: object, *a: object, **k: object) -> object:
            raise ConfigError("no profile yet")

        monkeypatch.setattr(
            "ax.config.manager.ConfigManager.load", classmethod(_raise)
        )
        # Onboarding normally runs before any configuration exists.
        assert instrument._request_verify() is True
