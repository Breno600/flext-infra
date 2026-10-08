"""A workspace root redirects its attached members through native uv sources.

The root environment serves every attached member: native uv workspace
membership plus ``uv sync --all-packages`` provisions them, and the root's
``[tool.uv.sources]`` redirects each member to the workspace. The retired
git-pinned ``workspace`` dependency group never comes back: a member declared
both as a workspace path and as a URL is a uv conflict.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import c
from flext_infra.codegen import FlextInfraCodegenConform
from tests import u


class TestsFlextInfraCodegenWorkspaceMemberGroup:
    """Tests for ``FlextInfraCodegenWorkspaceMemberGroup``."""

    @staticmethod
    def test_workspace_root_sources_survive_conform_at_a_fixed_point(
        tmp_path: Path,
    ) -> None:
        """Real root conform redirects every attached member and converges."""
        root = tmp_path / "workspace"
        _ = u.Tests.WorktreeFixture.governed_workspace_with_member(root)
        root_pyproject = root / c.PYPROJECT_FILENAME
        request = u.Tests.conform_request(
            root,
            what=c.Infra.CodegenConformSurface.PYPROJECT,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        service = FlextInfraCodegenConform(repository_root=root, request=request)
        first = tm.ok(service.plan(request))
        tm.that(len(first.workspace.subprojects), eq=1)
        rendered = u.Tests.codegen_file_text(
            next(item for item in first.files if item.path == root_pyproject),
        )
        sources = u.Tests.toml_mapping(
            u.Tests.toml_table_at(rendered, "tool", "uv").get("sources", {}),
        )
        for member in first.workspace.subprojects:
            tm.that(sources.get(member.distribution), eq={"workspace": True})
        groups = u.Tests.toml_table_at(rendered, c.Infra.DEPENDENCY_GROUPS)
        tm.that("workspace" in groups, eq=False)
        root_pyproject.write_text(rendered, encoding="utf-8")
        second = tm.ok(service.plan(request))
        tm.that(
            u.Tests.codegen_file_text(
                next(item for item in second.files if item.path == root_pyproject),
            ),
            eq=rendered,
        )
