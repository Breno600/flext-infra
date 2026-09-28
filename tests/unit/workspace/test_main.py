"""Public workspace CLI and facade tests."""

from __future__ import annotations

import os
from pathlib import Path

from flext_tests import tm

from flext_infra import c, main as infra_main
from flext_infra.workspace import (
    FlextInfraOrchestratorService,
    FlextInfraWorkspaceDetector,
)
from tests import t, u


class TestsFlextInfraWorkspaceMain:
    """Behavior contract for test_main."""

    @staticmethod
    def _write_project(project_root: Path, name: str) -> None:
        project_root.mkdir(parents=True, exist_ok=True)
        (project_root / "pyproject.toml").write_text(
            (
                "[project]\n"
                f'name = "{name}"\n'
                'version = "0.1.0"\n'
                'description = "Demo project"\n'
                'requires-python = ">=3.13"\n'
            ),
            encoding="utf-8",
        )
        u.Tests.write_project_beads_config(project_root, name)
        u.Tests.write_workspace_manifest(project_root, name)
        u.Tests.initialize_git_repo(
            project_root, origin_url=u.Tests.repository_ref(name).url
        )

    def _write_workspace(self, repository_root: Path) -> None:
        self._write_project(repository_root, "workspace")
        self._write_project(repository_root / "demo-a", "demo-a")
        u.Tests.WorktreeFixture.write_gitmodules(repository_root, ("demo-a",))

    @staticmethod
    def _workspace_main(argv: t.SequenceOf[str] | None = None) -> int:
        args = ["workspace"]
        if argv is not None:
            args.extend(argv)
        return infra_main(args)

    def test_unattached_child_does_not_infer_workspace_from_ancestor(
        self, tmp_path: Path
    ) -> None:
        repository_root = tmp_path / "workspace"
        self._write_workspace(repository_root)
        member_root = repository_root / "demo-a"

        result = FlextInfraWorkspaceDetector(
            repository_root=member_root, apply_changes=False
        ).execute()

        tm.ok(result)
        tm.that(result.value, eq=c.Infra.MakeProfile.STANDALONE)

    def test_workspace_main_detect_accepts_explicit_repository_root(
        self, tmp_path: Path
    ) -> None:
        repository_root = tmp_path / "workspace"
        self._write_workspace(repository_root)
        member_root = repository_root / "demo-a"

        tm.that(
            self._workspace_main(["detect", "--repository-root", str(member_root)]),
            eq=0,
        )

    def test_workspace_main_detect_runs_public_command(self, tmp_path: Path) -> None:
        """``workspace detect`` runs as a public CLI command."""
        project_root = tmp_path / "project"
        self._write_project(project_root, "demo-project")

        exit_code = self._workspace_main([
            "detect",
            "--repository-root",
            str(project_root),
        ])

        tm.that(exit_code, eq=0)

    def test_workspace_main_orchestrate_returns_failure_for_unknown_verb(self) -> None:
        """The public command rejects an undeclared operation."""
        tm.that(self._workspace_main(["orchestrate", "--verb", "legacy-check"]), eq=1)

    def test_workspace_orchestrate_passes_repository_root_to_member(
        self, tmp_path: Path
    ) -> None:
        """Attached members receive the workspace root as REPOSITORY_ROOT."""
        member_root = tmp_path / "demo-a"
        member_root.mkdir()
        sentinel = member_root / "observed-repository-root.txt"
        (member_root / c.Infra.MAKEFILE_FILENAME).write_text(
            "check:\n"
            "\t@printf '%s\\n' '$(REPOSITORY_ROOT)'"
            " > observed-repository-root.txt\n",
            encoding=c.Infra.ENCODING_DEFAULT,
        )
        service = FlextInfraOrchestratorService(
            repository_root=tmp_path, verb=c.Infra.VERB_CHECK, projects=("demo-a",)
        )
        previous = Path.cwd()
        os.chdir(tmp_path)
        try:
            result = service.orchestrate(("demo-a",), c.Infra.VERB_CHECK)
        finally:
            os.chdir(previous)

        tm.ok(result)
        tm.that(
            sentinel.read_text(encoding=c.Infra.ENCODING_DEFAULT).strip(),
            eq=str(tmp_path.resolve()),
        )

    def test_workspace_orchestrator_declares_enforcement_fix(self) -> None:
        """The generated workspace Make handler has a matching public allowlist."""
        tm.that(c.Infra.ORCHESTRATED_VERBS, has="fix-enforcement")

    def test_workspace_main_without_command_returns_failure(self) -> None:
        tm.that(self._workspace_main([]), eq=1)
