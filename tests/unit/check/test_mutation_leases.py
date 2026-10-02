"""Real formatter effects share Git capture and physical file-scope leases.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, m, u
from flext_infra.codegen import FlextInfraCodegenFileLeases
from flext_infra.gates import FlextInfraRuffFormatGate
from tests import u as test_u


class TestsFlextInfraMutationLeases:
    """Public formatter behavior respects exact shared writer ownership."""

    @staticmethod
    @pytest.mark.parametrize("git_owned", [False, True])
    def test_format_waits_for_scope_writer_and_does_not_apply_lint(
        tmp_path: Path,
        *,
        git_owned: bool,
    ) -> None:
        """Test format waits for scope writer and does not apply lint."""
        root = (
            test_u.Tests.git_repository(tmp_path) if git_owned else tmp_path / "files"
        )
        root.mkdir(exist_ok=True)
        (root / "pyproject.toml").write_text("[tool.ruff]\n", encoding="utf-8")
        source = root / "src"
        source.mkdir()
        target = source / "sample.py"
        before = "import os\n\nvalue=[1,2,3]\n"
        target.write_text(before, encoding="utf-8")
        gate = FlextInfraRuffFormatGate(root)
        context = m.Infra.GateContext(
            repository_root=root,
            reports_dir=root / "reports",
            apply_fixes=True,
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            with FlextInfraCodegenFileLeases.mutation_lease(root):
                applied = pool.submit(gate.fix, root, context)
                with pytest.raises(TimeoutError):
                    applied.result(timeout=0.2)
                tm.that(target.read_text(encoding="utf-8"), eq=before)
            tm.that(applied.result().result.passed, eq=True)
        tm.that(target.read_text(encoding="utf-8"), ne=before)
        tm.that(target.read_text(encoding="utf-8"), has="import os")
        tm.that(gate.check(root, context).result.passed, eq=True)

    @staticmethod
    def test_malformed_git_marker_is_not_a_file_scope(tmp_path: Path) -> None:
        """Test malformed git marker is not a file scope."""
        marker = tmp_path / c.Infra.GIT_DIR
        marker.mkdir()
        request = m.Infra.GitRepoRequest(repo_root=tmp_path)

        tm.that(u.Infra.git_mutation_scope(request).failure, eq=True)
        tm.that((tmp_path / c.Infra.TRANSACTION_STATE_DIRNAME).exists(), eq=False)

    @staticmethod
    def test_nested_git_scope_uses_original_worktree_journal(
        tmp_path: Path,
    ) -> None:
        """Test nested git scope uses original worktree journal."""
        root = test_u.Tests.git_repository(tmp_path)
        nested = root / "nested"
        nested.mkdir()
        scope = tm.ok(
            u.Infra.git_mutation_scope(m.Infra.GitRepoRequest(repo_root=nested)),
        )
        identity = tm.ok(u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=root)))

        tm.that(scope.git_dir, eq=identity.git_dir)
        tm.that(scope.root, eq=nested.resolve())
