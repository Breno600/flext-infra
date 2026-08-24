"""Public workspace CLI and facade tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from flext_infra import main as infra_main
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
from flext_infra.workspace.orchestrator import FlextInfraOrchestratorService
from flext_tests import tm
from tests import c, u

_INFRA_SRC = Path(__file__).resolve().parents[3] / "src"


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
    u.Tests.write_standalone_workspace_manifest(project_root, name)
    u.Tests.initialize_git_repo(project_root)


def _write_workspace(workspace_root: Path) -> None:
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / ".gitmodules").write_text(
        '[submodule "demo-a"]\n\tpath = demo-a\n\turl = https://example.invalid/demo-a.git\n',
        encoding="utf-8",
    )
    (workspace_root / "pyproject.toml").write_text(
        (
            "[project]\n"
            'name = "workspace-root"\n'
            'version = "0.1.0"\n'
            "\n"
            "[tool.flext.workspace]\n"
            'members = ["demo-a"]\n'
        ),
        encoding="utf-8",
    )
    config_dir = workspace_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "workspace.yaml").write_text(
        (
            "version: 3\n"
            "name: workspace-root\n"
            "repository:\n"
            "  name: workspace-root\n"
            "  distribution: workspace-root\n"
            "  provider: flext-sh\n"
            "  url: https://github.com/flext-sh/workspace-root.git\n"
            "  path: .\n"
            "  role: workspace-root\n"
            "  state: active\n"
            "  checkout: root\n"
            "  codegen: conform\n"
            "  package: false\n"
            "  editable: false\n"
            "  read_only: false\n"
            "members:\n"
            "  - name: demo-a\n"
            "    distribution: demo-a\n"
            "    provider: flext-sh\n"
            "    url: https://example.invalid/demo-a.git\n"
            "    path: demo-a\n"
            "    role: workspace-member\n"
            "    state: active\n"
            "    checkout: submodule\n"
            "    codegen: conform\n"
            "    package: true\n"
            "    editable: true\n"
            "    read_only: false\n"
            "exclusions: []\n"
        ),
        encoding="utf-8",
    )
    _write_project(workspace_root / "demo-a", "demo-a")


def _write_orchestratable_workspace(
    workspace_root: Path, *, capture_fail_fast: bool = False
) -> Path:
    """Build a workspace whose single member has a trivial ``make check``."""
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / ".gitmodules").write_text(
        '[submodule "demo"]\n\tpath = demo\n\turl = https://example.invalid/demo.git\n',
        encoding="utf-8",
    )
    (workspace_root / "pyproject.toml").write_text(
        (
            "[project]\n"
            'name = "workspace-root"\n'
            'version = "0.1.0"\n'
            "\n"
            "[tool.flext.workspace]\n"
            'members = ["demo"]\n'
        ),
        encoding="utf-8",
    )
    config_dir = workspace_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "workspace.yaml").write_text(
        (
            "version: 3\n"
            "name: workspace-root\n"
            "repository:\n"
            "  name: workspace-root\n"
            "  distribution: workspace-root\n"
            "  provider: flext-sh\n"
            "  url: https://github.com/flext-sh/workspace-root.git\n"
            "  path: .\n"
            "  role: workspace-root\n"
            "  state: active\n"
            "  checkout: root\n"
            "  codegen: conform\n"
            "  package: false\n"
            "  editable: false\n"
            "  read_only: false\n"
            "members:\n"
            "  - name: demo\n"
            "    distribution: demo\n"
            "    provider: flext-sh\n"
            "    url: https://example.invalid/demo.git\n"
            "    path: demo\n"
            "    role: workspace-member\n"
            "    state: active\n"
            "    checkout: submodule\n"
            "    codegen: conform\n"
            "    package: true\n"
            "    editable: true\n"
            "    read_only: false\n"
            "exclusions: []\n"
        ),
        encoding="utf-8",
    )
    member_root = workspace_root / "demo"
    _write_project(member_root, "demo")
    check_recipe = (
        '\t@echo "FAIL_FAST=$(FAIL_FAST)" > "$(CAPTURE_PATH)"\n'
        if capture_fail_fast
        else "\t@true\n"
    )
    (member_root / "base.mk").write_text(f"check:\n{check_recipe}", encoding="utf-8")
    (member_root / "Makefile").write_text("include base.mk\n", encoding="utf-8")

    # Commit the member so the detector sees a real HEAD/gitlink pair.
    u.Tests.commit_git_changes(member_root, "fixture: base.mk and Makefile")

    # Stub a managed Python so the generated Makefile can invoke flext_infra.
    # It must delegate to the interpreter running these tests: flext_infra reads
    # its own distribution metadata at import time, so a bare `python3` that only
    # sees the source tree on PYTHONPATH raises PackageNotFoundError.
    venv_python = member_root / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    venv_python.write_text(
        f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8"
    )
    venv_python.chmod(0o755)

    # Capture the propagated FAIL_FAST value after the generated check runs.
    # The path is supplied as a make variable so the file lives outside the
    # workspace and does not trip the "workspace changed during check" guard.
    if capture_fail_fast:
        (member_root / "custom.mk").write_text(
            'post-check:\n\t@echo "FAIL_FAST=$(FAIL_FAST)" > $(CAPTURE_PATH)\n',
            encoding="utf-8",
        )

    return member_root


def workspace_main(argv: list[str] | None = None) -> int:
    args = ["workspace"]
    if argv is not None:
        args.extend(argv)
    return infra_main(args)


class TestsFlextInfraWorkspaceMain:
    """Behavior contract for test_main."""

    def test_unattached_child_does_not_infer_workspace_from_ancestor(
        self, tmp_path: Path
    ) -> None:
        workspace_root = tmp_path / "workspace"
        _write_workspace(workspace_root)
        member_root = workspace_root / "demo-a"

        result = FlextInfraWorkspaceDetector(
            workspace_root=member_root, apply_changes=False
        ).execute()

        tm.ok(result)
        tm.that(result.value, eq=c.Infra.WorkspaceMode.STANDALONE)

    def test_orchestrate_workspace_rejects_unknown_verb(self) -> None:
        result = FlextInfraOrchestratorService(
            verb="legacy-check", selected_projects=["p-a"]
        ).execute()

        tm.fail(result)
        tm.that((result.error or ""), has="unsupported orchestrate verb")

    def test_orchestrate_runs_make_verb_across_members(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Orchestrate resolves members and runs the make verb to success."""
        workspace_root = tmp_path / "workspace"
        _write_orchestratable_workspace(workspace_root)
        monkeypatch.chdir(workspace_root)

        result = FlextInfraOrchestratorService(
            verb="check",
            selected_projects=["demo"],
            workspace_root=workspace_root,
            make_arg=[f"PROJECT_INFRA_PYTHONPATH={_INFRA_SRC}"],
        ).execute()

        tm.ok(result)
        tm.that(result.value, eq=True)
        log_path = workspace_root / ".reports" / "workspace" / "check" / "demo.log"
        tm.that(log_path.is_file(), eq=True)

    def test_orchestrate_forwards_fail_fast_to_project_make(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fail-fast intent reaches each project's make invocation."""
        workspace_root = tmp_path / "workspace"
        capture_path = tmp_path / "captured.txt"
        _write_orchestratable_workspace(workspace_root, capture_fail_fast=True)
        monkeypatch.chdir(workspace_root)

        result = FlextInfraOrchestratorService(
            verb="check",
            selected_projects=["demo"],
            workspace_root=workspace_root,
            fail_fast=True,
            make_arg=[
                f"PROJECT_INFRA_PYTHONPATH={_INFRA_SRC}",
                f"CAPTURE_PATH={capture_path}",
            ],
        ).execute()

        tm.ok(result)
        captured = capture_path.read_text(encoding="utf-8")
        tm.that(captured, has="FAIL_FAST=1")

    def test_workspace_main_detect_accepts_explicit_workspace_root(
        self, tmp_path: Path
    ) -> None:
        workspace_root = tmp_path / "workspace"
        _write_workspace(workspace_root)
        member_root = workspace_root / "demo-a"

        tm.that(workspace_main(["detect", "--workspace", str(member_root)]), eq=0)

    def test_workspace_main_detect_runs_public_command(self, tmp_path: Path) -> None:
        """``workspace detect`` runs as a public CLI command."""
        project_root = tmp_path / "project"
        _write_project(project_root, "demo-project")

        exit_code = workspace_main(["detect", "--workspace", str(project_root)])

        tm.that(exit_code, eq=0)

    def test_workspace_main_orchestrate_returns_failure_for_unknown_verb(self) -> None:
        tm.that(
            (
                workspace_main([
                    "orchestrate",
                    "--verb",
                    "legacy-check",
                    "--projects",
                    "p-a",
                ])
                == 1
            ),
            eq=True,
        )

    def test_workspace_main_without_command_returns_failure(self) -> None:
        tm.that(workspace_main([]), eq=1)
