"""Public workspace CLI and facade tests.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import main
from flext_infra.workspace import FlextInfraWorkspaceDetector
from tests import c, t, u


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
            project_root,
            origin_url=u.Tests.repository_ref(name).url,
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
        return main(args)

    def test_unattached_child_does_not_infer_workspace_from_ancestor(
        self,
        tmp_path: Path,
    ) -> None:
        """Test unattached child does not infer workspace from ancestor."""
        repository_root = tmp_path / "workspace"
        self._write_workspace(repository_root)
        member_root = repository_root / "demo-a"

        result = FlextInfraWorkspaceDetector(
            repository_root=member_root,
            apply_changes=False,
        ).execute()

        tm.ok(result)
        tm.that(result.value, eq=c.Infra.MakeProfile.STANDALONE)

    def test_workspace_main_detect_accepts_explicit_repository_root(
        self,
        tmp_path: Path,
    ) -> None:
        """Test workspace main detect accepts explicit repository root."""
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

    def test_workspace_main_without_command_returns_failure(self) -> None:
        """Test workspace main without command returns failure."""
        tm.that(self._workspace_main([]), eq=1)
