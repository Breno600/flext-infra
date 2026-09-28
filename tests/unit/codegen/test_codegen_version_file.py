"""Tests for FlextInfraCodegenVersionFile.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.codegen.version_file import FlextInfraCodegenVersionFile
from tests import c, t, u

if TYPE_CHECKING:
    from pathlib import Path

_WORKSPACE_PYPROJECT = """\
[project]
name = "{workspace_name}"
version = "{project_version}"

[tool.uv.workspace]
members = [{members}]
"""

_PROJECT_PYPROJECT = """\
[project]
name = "{project_name}"
version = "{project_version}"
"""


class TestsFlextInfraCodegenVersionFile:
    def _create_workspace(
        self, tmp_path: Path, project_name: str
    ) -> t.Triple[Path, Path, Path]:
        """Create minimal workspace/project/package structure."""
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "pyproject.toml").write_text(
            _WORKSPACE_PYPROJECT.format(
                workspace_name=c.Tests.WORKSPACE_PROJECT_NAME,
                project_version=c.Tests.RELEASE_VERSION_BASE,
                members=f'"{project_name}"',
            ),
            encoding="utf-8",
        )
        proj = ws / project_name
        proj.mkdir()
        (proj / "pyproject.toml").write_text(
            _PROJECT_PYPROJECT.format(
                project_name=project_name, project_version=c.Tests.RELEASE_VERSION_BASE
            ),
            encoding="utf-8",
        )
        pkg_name = project_name.replace("-", "_")
        pkg = proj / "src" / pkg_name
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        u.Tests.declare_workspace_projects(ws, (project_name,))
        return ws, proj, pkg

    def test_generates_version_file_for_project(self, tmp_path: Path) -> None:
        ws, _proj, pkg = self._create_workspace(tmp_path, c.Tests.DEMO_PROJECT_NAME)
        svc = FlextInfraCodegenVersionFile.model_validate({"repository_root": ws})

        result = svc.execute()

        tm.ok(result)
        version_file = pkg / "__version__.py"
        tm.that(version_file.exists(), eq=True)

    def test_generated_file_contains_class_name(self, tmp_path: Path) -> None:
        ws, _proj, pkg = self._create_workspace(tmp_path, c.Tests.DEMO_PROJECT_NAME)
        svc = FlextInfraCodegenVersionFile.model_validate({"repository_root": ws})

        svc.execute()

        version_file = pkg / "__version__.py"
        content = version_file.read_text(encoding="utf-8")
        tm.that(content, has="DemoProjectVersion")

    def test_generated_file_inherits_flext_version(self, tmp_path: Path) -> None:
        ws, _proj, pkg = self._create_workspace(tmp_path, c.Tests.DEMO_PROJECT_NAME)
        svc = FlextInfraCodegenVersionFile.model_validate({"repository_root": ws})

        svc.execute()

        content = (pkg / "__version__.py").read_text(encoding="utf-8")
        tm.that(content, has="FlextVersion")

    def test_check_only_does_not_write_file(self, tmp_path: Path) -> None:
        ws, _proj, pkg = self._create_workspace(tmp_path, c.Tests.DEMO_PROJECT_NAME)
        svc = FlextInfraCodegenVersionFile.model_validate({
            "repository_root": ws,
            "check_only": True,
        })

        svc.execute()

        tm.that(not (pkg / "__version__.py").exists(), eq=True)

    def test_dry_run_does_not_write_file(self, tmp_path: Path) -> None:
        ws, _proj, pkg = self._create_workspace(tmp_path, c.Tests.DEMO_PROJECT_NAME)
        svc = FlextInfraCodegenVersionFile.model_validate({
            "repository_root": ws,
            "dry_run": True,
        })

        svc.execute()

        tm.that(not (pkg / "__version__.py").exists(), eq=True)

    def test_idempotent_when_file_already_correct(self, tmp_path: Path) -> None:
        ws, _proj, pkg = self._create_workspace(tmp_path, c.Tests.DEMO_PROJECT_NAME)
        svc = FlextInfraCodegenVersionFile.model_validate({"repository_root": ws})

        svc.execute()
        first_content = (pkg / "__version__.py").read_text(encoding="utf-8")
        svc.execute()
        second_content = (pkg / "__version__.py").read_text(encoding="utf-8")

        tm.that(first_content, eq=second_content)

    def test_project_filter_only_generates_for_matching_project(
        self, tmp_path: Path
    ) -> None:
        # Create workspace with two projects
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "pyproject.toml").write_text(
            _WORKSPACE_PYPROJECT.format(
                workspace_name=c.Tests.WORKSPACE_PROJECT_NAME,
                project_version=c.Tests.RELEASE_VERSION_BASE,
                members=", ".join(
                    f'"{project_name}"'
                    for project_name in c.Tests.PROJECT_MEMBERS_BY_SCENARIO["filtered"]
                ),
            ),
            encoding="utf-8",
        )
        for name in c.Tests.PROJECT_MEMBERS_BY_SCENARIO["filtered"]:
            proj = ws / name
            proj.mkdir()
            (proj / "pyproject.toml").write_text(
                _PROJECT_PYPROJECT.format(
                    project_name=name, project_version=c.Tests.RELEASE_VERSION_BASE
                ),
                encoding="utf-8",
            )
            pkg = proj / "src" / name.replace("-", "_")
            pkg.mkdir(parents=True)
            (pkg / "__init__.py").write_text("", encoding="utf-8")
        u.Tests.declare_workspace_projects(
            ws, c.Tests.PROJECT_MEMBERS_BY_SCENARIO["filtered"]
        )
        svc = FlextInfraCodegenVersionFile.model_validate({
            "repository_root": ws,
            "project_filter": c.Tests.PROJECT_A_NAME,
        })

        svc.execute()

        tm.that(
            (
                ws
                / c.Tests.PROJECT_A_NAME
                / "src"
                / c.Tests.PROJECT_A_NAME.replace("-", "_")
                / "__version__.py"
            ).exists(),
            eq=True,
        )
        tm.that(
            not (
                ws
                / c.Tests.PROJECT_B_NAME
                / "src"
                / c.Tests.PROJECT_B_NAME.replace("-", "_")
                / "__version__.py"
            ).exists(),
            eq=True,
        )

    def test_skips_project_without_src_pkg_dir(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "pyproject.toml").write_text(
            _WORKSPACE_PYPROJECT.format(
                workspace_name=c.Tests.WORKSPACE_PROJECT_NAME,
                project_version=c.Tests.RELEASE_VERSION_BASE,
                members=", ".join(
                    f'"{project_name}"'
                    for project_name in c.Tests.PROJECT_MEMBERS_BY_SCENARIO[
                        "missing_src"
                    ]
                ),
            ),
            encoding="utf-8",
        )
        no_src = ws / c.Tests.PROJECT_NO_SRC_NAME
        no_src.mkdir()
        (no_src / "pyproject.toml").write_text(
            _PROJECT_PYPROJECT.format(
                project_name=c.Tests.PROJECT_NO_SRC_NAME,
                project_version=c.Tests.RELEASE_VERSION_BASE,
            ),
            encoding="utf-8",
        )
        svc = FlextInfraCodegenVersionFile.model_validate({"repository_root": ws})

        result = svc.execute()

        tm.ok(result)
