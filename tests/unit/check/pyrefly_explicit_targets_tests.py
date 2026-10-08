"""Pyrefly explicit targets keep the project's configured excludes.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, config, m
from flext_infra.gates.pyrefly import FlextInfraPyreflyGate

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraPyreflyExplicitTargets:
    """A root module never pulls an excluded generated tree into Pyrefly."""

    @staticmethod
    @pytest.mark.slow
    def test_explicit_targets_keep_configured_excludes(
        real_python_package: Path,
    ) -> None:
        """The real gate excludes a generated tree yet still checks governed code.

        Premise (flext-gknfx): a root-level module switches the gate to
        explicit targets, and Pyrefly ignores the configured project-excludes
        for explicit files, so flext-grpc's generated protos were checked.
        """
        names = config.Infra.codegen.generated_sources
        tm.that(names, empty=False)
        project = real_python_package
        pyproject = project / c.PYPROJECT_FILENAME
        pyproject.write_text(
            pyproject.read_text(encoding="utf-8")
            + '\n[tool.pyrefly]\nproject-includes = ["src/**/*.py*"]\n'
            + f'project-excludes = ["**/{names[0]}/**"]\n',
            encoding="utf-8",
        )
        (project / "conftest.py").write_text('"""Root module."""\n', encoding="utf-8")
        tree = project / "src" / "test_pkg" / names[0]
        tree.mkdir()
        (tree / "wire_pb2.py").write_text('value: int = "wire"\n', encoding="utf-8")
        reports = project / ".reports"
        reports.mkdir()
        context = m.Infra.GateContext(repository_root=project, reports_dir=reports)
        gate = FlextInfraPyreflyGate(project)

        excluded = gate.check(project, context)

        tm.that(excluded.result.passed, eq=True, msg=str(excluded.issues))
        governed_module = project / "src" / "test_pkg" / "contract.py"
        governed_module.write_text('value: int = "governed"\n', encoding="utf-8")
        governed = gate.check(project, context)
        tm.that(governed.result.passed, eq=False)
        tm.that(
            all(issue.file.endswith(governed_module.name) for issue in governed.issues),
            eq=True,
            msg=str(governed.issues),
        )
