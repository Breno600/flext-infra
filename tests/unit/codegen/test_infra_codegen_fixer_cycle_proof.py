"""Tests for the fixer pipeline's import-cycle proof and import rebinding.

Validates that the auto-fix pass proves the post-fix tree cycle-free through
the existing codemod project-facts detector, and that the public relocation
cascade preserves the declaring package when rebinding a deep import.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import infra
from flext_infra.codegen.fixer import FlextInfraCodegenFixer
from tests import m, u


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
            files={
                "__init__.py": "u = __name__\n",
                "models.py": "u = __name__\n",
                "consumer.py": (
                    "from bind_pkg.models import u\nassert u == __package__\n"
                ),
            },
        )
        path = project / "src" / "bind_pkg" / "consumer.py"
        original = path.read_text(encoding="utf-8")
        with infra.rope_workspace(project) as rope:
            edits = tm.ok(
                u.Infra.plan_package_root_import(
                    rope,
                    path,
                    source_module="bind_pkg.models",
                    aliases=("u",),
                )
            )
        tm.that(len(edits), eq=1)
        tm.that(path.read_text(encoding="utf-8"), eq=original)
        path.write_text(edits[0].updated_source, encoding="utf-8")
        output = tm.ok(
            u.Cli.run_raw((
                sys.executable,
                "-I",
                "-c",
                "import sys; sys.path.insert(0, sys.argv[1]); import bind_pkg.consumer",
                str(project / "src"),
            ))
        )
        tm.that(u.Cli.process_succeeded(output.outcome), eq=True, msg=output.stderr)

    @staticmethod
    def test_package_root_import_preserves_foreign_package_identity(
        tmp_path: Path,
    ) -> None:
        """A foreign-package finding stays residue instead of being rebound.

        Binding it into the foreign top-level package is exactly the defect
        that rewrote ``from flext_infra import u`` to ``from flext_cli import u``
        in own-package files, so the consumer keeps its exact source binding.

        """
        source = "from flext_cli.utilities import u\n"
        project = u.Tests.create_codegen_project(
            tmp_path=tmp_path,
            name="foreign-proj",
            pkg_name="foreign_pkg",
            files={"consumer.py": source},
        )
        path = project / "src" / "foreign_pkg" / "consumer.py"
        original = path.read_text(encoding="utf-8")
        with infra.rope_workspace(project) as rope:
            edits = tm.ok(
                u.Infra.plan_package_root_import(
                    rope,
                    path,
                    source_module="flext_cli.utilities",
                    aliases=("u",),
                )
            )
        tm.that(edits, empty=True)
        tm.that(path.read_text(encoding="utf-8"), eq=original)
