"""Public runner tests for ``FlextInfraWorkspaceChecker``.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.check.workspace_check import FlextInfraWorkspaceChecker

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraExtendedProjectRunners:
    """Exercise runner behavior through the public checker API only."""

    # Why (suite budget): full-suite xdist can stall durable atomic report writes
    # beyond the default case timeout while the nested checker publishes reports.
    @pytest.mark.slow
    def test_run_projects_records_requested_gates(
        self, real_python_package: Path
    ) -> None:
        checker = FlextInfraWorkspaceChecker(repository_root=real_python_package.parent)
        result = checker.run_projects(
            [real_python_package.name],
            ["lint", "pyrefly"],
            reports_dir=real_python_package.parent / "reports",
        )

        tm.ok(result)
        # 'format' is not a check gate: 73887691 gave each tool one owner and
        # moved ruff format to the 'fmt' verb, so the check registry carries
        # lint/pyrefly and never reports a format gate here.
        tm.that({"lint", "pyrefly"} <= set(result.value[0].gates), eq=True)
        tm.that("format" in set(result.value[0].gates), eq=False)

    @pytest.mark.parametrize("gate_method", ["lint", "format"])
    def test_public_method_returns_gate_result(
        self, gate_method: str, real_python_package: Path
    ) -> None:
        checker = FlextInfraWorkspaceChecker(repository_root=real_python_package.parent)
        result = (
            checker.lint(real_python_package)
            if gate_method == "lint"
            else checker.format(real_python_package)
        )

        tm.ok(result)
        tm.that(result.value.gate, eq=gate_method)
