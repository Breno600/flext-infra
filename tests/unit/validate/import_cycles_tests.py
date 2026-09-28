"""Tests for FlextInfraValidateImportCycles.

Guard 1: ROPE-backed AST cycle detector. Builds a module import graph
via rope's import resolution and runs Tarjan's SCC; any SCC of size >= 2
is a cycle violation. TYPE_CHECKING imports are excluded by rope's
semantic parser because they live in conditional blocks.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tf, tm

from flext_infra.validate.import_cycles import FlextInfraValidateImportCycles
from tests import m, t, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraImportCycles:
    """Import-cycle detection, summary content, and per-project scoping."""

    @pytest.fixture
    def v(self) -> FlextInfraValidateImportCycles:
        """Shared validator instance."""
        return FlextInfraValidateImportCycles()

    @staticmethod
    def _seed_project(
        workspace: Path, name: str, files: t.MappingKV[str, str], *, pkg: str = "tests"
    ) -> Path:
        project = workspace / name
        pkg_dir = project / "src" / pkg
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
        (project / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "0.0.1"\n', encoding="utf-8"
        )
        for filename, content in files.items():
            (pkg_dir / filename).write_text(content, encoding="utf-8")
        return project

    def test_empty_workspace_passes(
        self, tmp_path: Path, v: FlextInfraValidateImportCycles
    ) -> None:
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report, is_=m.Infra.ValidationReport)
        tm.that(report.passed, eq=True)

    def test_acyclic_graph_passes(
        self, tmp_path: Path, v: FlextInfraValidateImportCycles
    ) -> None:
        pkg = u.Tests.write_package_init(tmp_path / "src" / "pkg", "").parent
        tf(base_dir=pkg).create("X = 1\n", "a.py")
        tf(base_dir=pkg).create("from pkg.a import X\n", "b.py")
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.passed, eq=True)

    def test_two_module_cycle_fails(
        self, tmp_path: Path, v: FlextInfraValidateImportCycles
    ) -> None:
        pkg = u.Tests.write_package_init(tmp_path / "src" / "pkg", "").parent
        tf(base_dir=pkg).create("from pkg import b\n", "a.py")
        tf(base_dir=pkg).create("from pkg import a\n", "b.py")
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.passed, eq=False)
        joined = " | ".join(report.violations)
        tm.that(joined, has="pkg.a")
        tm.that(joined, has="pkg.b")

    def test_three_module_cycle_fails(
        self, tmp_path: Path, v: FlextInfraValidateImportCycles
    ) -> None:
        pkg = u.Tests.write_package_init(tmp_path / "src" / "pkg", "").parent
        tf(base_dir=pkg).create("from pkg import b\n", "a.py")
        tf(base_dir=pkg).create("from pkg import c\n", "b.py")
        tf(base_dir=pkg).create("from pkg import a\n", "c.py")
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.passed, eq=False)
        joined = " | ".join(report.violations)
        tm.that(joined, has="pkg.a")
        tm.that(joined, has="pkg.b")
        tm.that(joined, has="pkg.c")

    def test_type_checking_import_is_not_runtime_cycle(
        self, tmp_path: Path, v: FlextInfraValidateImportCycles
    ) -> None:
        pkg = u.Tests.write_package_init(tmp_path / "src" / "pkg", "").parent
        tf(base_dir=pkg).create(
            (
                "from __future__ import annotations\n"
                "from typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n"
                "    from pkg import b\n"
            ),
            "a.py",
        )
        tf(base_dir=pkg).create("from pkg import a\n", "b.py")
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.passed, eq=True)

    def test_summary_reports_cycle_count(
        self, tmp_path: Path, v: FlextInfraValidateImportCycles
    ) -> None:
        pkg = u.Tests.write_package_init(tmp_path / "src" / "pkg", "").parent
        tf(base_dir=pkg).create("from pkg import b\n", "a.py")
        tf(base_dir=pkg).create("from pkg import a\n", "b.py")
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.summary, has="1")
        tm.that(report.summary, has="cycle")

    def test_passing_summary_is_human_readable(
        self, tmp_path: Path, v: FlextInfraValidateImportCycles
    ) -> None:
        u.Tests.write_package_init(tmp_path / "src" / "pkg", "")
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.summary, has="cycle")

    def test_same_named_packages_across_projects_do_not_form_cycle(
        self, tmp_path: Path, v: FlextInfraValidateImportCycles
    ) -> None:
        """Opposite one-way edges in two projects must not merge into a cycle."""
        self._seed_project(
            tmp_path,
            "alpha",
            {"a.py": "from examples.b import Y\n", "b.py": "Y = 1\n"},
            pkg="examples",
        )
        self._seed_project(
            tmp_path,
            "beta",
            {"b.py": "from examples.a import X\n", "a.py": "X = 1\n"},
            pkg="examples",
        )
        u.Tests.declare_workspace_projects(tmp_path, ("alpha", "beta"))
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.passed, eq=True)
        tm.that(report.summary, has="scanned 6 modules")

    def test_cycle_is_attributed_to_owning_project_only(
        self, tmp_path: Path, v: FlextInfraValidateImportCycles
    ) -> None:
        """A real cycle inside one project is reported with that project's label."""
        self._seed_project(
            tmp_path,
            "alpha",
            {"a.py": "from tests import b\n", "b.py": "from tests import a\n"},
        )
        self._seed_project(
            tmp_path, "beta", {"a.py": "X = 1\n", "b.py": "from tests.a import X\n"}
        )
        u.Tests.declare_workspace_projects(tmp_path, ("alpha", "beta"))
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.passed, eq=False)
        joined = " | ".join(report.violations)
        tm.that(joined, has="[alpha]")
        tm.that(joined, has="tests.a")
        tm.that(joined, has="tests.b")
        tm.that(joined, lacks="[beta]")
