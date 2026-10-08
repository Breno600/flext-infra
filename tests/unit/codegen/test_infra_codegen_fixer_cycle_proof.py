"""Tests for the fixer pipeline's import-cycle proof and import rebinding.

Validates that the auto-fix pass proves the post-fix tree cycle-free through
the existing codemod project-facts detector, and that the public relocation
cascade preserves the declaring package when rebinding a deep import.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, infra, m
from flext_infra.codegen.fixer import FlextInfraCodegenFixer
from flext_infra.refactor.namespace_relocations import (
    FlextInfraNamespaceRelocationCascade,
)
from tests import u


def _finding(
    file: Path,
    *,
    module: str,
    name: str,
) -> m.Infra.ModScanFinding:
    """Build one minimal package-root-import finding payload.

    Returns:
        The resulting ``m.Infra.ModScanFinding``.
    """
    return m.Infra.ModScanFinding(
        rule_file="namespace-law.yml",
        rule_id="ban-noncanonical-alias-import",
        repository="test",
        file=file,
        range={"start": {"line": 0, "column": 0}, "end": {"line": 0, "column": 1}},
        text=f"from {module} import {name}",
        actionable=False,
        classification=c.Infra.ModScanFindingClass.DETECTION_ONLY,
        payload={
            "metaVariables": {
                "single": {
                    "MODULE": module,
                    "NAME": name,
                },
            },
        },
    )


def _reports_import_cycle(result: m.Infra.AutoFixResult) -> bool:
    """Return whether one auto-fix result reports an IMPORT-CYCLE skip."""
    return any(
        violation.rule == "IMPORT-CYCLE" for violation in result.violations_skipped
    )


class TestsFlextInfraCodegenFixerCycleProof:
    """Behavior contract for the fixer's cycle proof and import rebinding."""

    @staticmethod
    @pytest.mark.slow
    def test_auto_fix_flags_modules_in_a_runtime_cycle(tmp_path: Path) -> None:
        """Two modules importing each other are both flagged as cycle members."""
        project = u.Tests.create_codegen_project(
            tmp_path=tmp_path,
            name="cycle-proj",
            pkg_name="cycle_pkg",
            files={
                "alpha.py": "from cycle_pkg import beta\n",
                "beta.py": "from cycle_pkg import alpha\n",
            },
        )
        u.Tests.declare_workspace_projects(tmp_path, (project.name,))
        u.Tests.provision_checkout(project)
        results = FlextInfraCodegenFixer(repository_root=tmp_path).fix_workspace(
            projects=[
                u.Tests.create_project_info(
                    project,
                    name=project.name,
                    package_name="cycle_pkg",
                ),
            ],
        )
        flagged = {
            violation.module
            for result in results
            for violation in result.violations_skipped
            if violation.rule == "IMPORT-CYCLE"
        }
        tm.that(flagged, has="cycle_pkg.alpha")
        tm.that(flagged, has="cycle_pkg.beta")

    @staticmethod
    @pytest.mark.slow
    def test_auto_fix_passes_an_acyclic_tree(tmp_path: Path) -> None:
        """A tree without cycles records no IMPORT-CYCLE violation."""
        project = u.Tests.create_codegen_project(
            tmp_path=tmp_path,
            name="clean-proj",
            pkg_name="clean_pkg",
            files={
                "alpha.py": "from clean_pkg import beta\n",
                "beta.py": "",
            },
        )
        u.Tests.declare_workspace_projects(tmp_path, (project.name,))
        u.Tests.provision_checkout(project)
        results = FlextInfraCodegenFixer(repository_root=tmp_path).fix_workspace(
            projects=[
                u.Tests.create_project_info(
                    project,
                    name=project.name,
                    package_name="clean_pkg",
                ),
            ],
        )
        tm.that([result for result in results if _reports_import_cycle(result)], eq=[])

    @staticmethod
    def test_package_root_import_binds_own_package_symbol_to_own_package(
        tmp_path: Path,
    ) -> None:
        """A deep own-package import rebinds to the own package root."""
        project = u.Tests.create_codegen_project(
            tmp_path=tmp_path,
            name="bind-proj",
            pkg_name="bind_pkg",
            files={"consumer.py": "from bind_pkg.models import u\n"},
        )
        finding = _finding(
            Path("src/bind_pkg/consumer.py"),
            module="bind_pkg.models",
            name="u",
        )
        consumer = project / finding.file
        with infra.rope_workspace(project) as workspace:
            FlextInfraNamespaceRelocationCascade().run(
                project_root=project,
                rope_project=workspace.rope_project,
                findings=((c.Infra.CodemodRelocation.PACKAGE_ROOT_IMPORT, finding),),
                py_files=(consumer,),
            )
        tm.that(consumer.read_text(encoding="utf-8"), eq="from bind_pkg import u\n")

    @staticmethod
    def test_package_root_import_preserves_foreign_package_identity(
        tmp_path: Path,
    ) -> None:
        """Rebinding a foreign source must not invent a local declaring package."""
        project = u.Tests.create_codegen_project(
            tmp_path=tmp_path,
            name="foreign-proj",
            pkg_name="foreign_pkg",
            files={"consumer.py": "from flext_cli.utilities import u\n"},
        )
        finding = _finding(
            Path("src/foreign_pkg/consumer.py"),
            module="flext_cli.utilities",
            name="u",
        )
        consumer = project / finding.file
        with infra.rope_workspace(project) as workspace:
            FlextInfraNamespaceRelocationCascade().run(
                project_root=project,
                rope_project=workspace.rope_project,
                findings=((c.Infra.CodemodRelocation.PACKAGE_ROOT_IMPORT, finding),),
                py_files=(consumer,),
            )
        tm.that(consumer.read_text(encoding="utf-8"), eq="from flext_cli import u\n")
