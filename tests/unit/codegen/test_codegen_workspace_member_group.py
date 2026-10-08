"""A workspace root keeps every attached member in its native uv workspace.

The root environment serves every attached member: setup syncs the root lock
with ``--all-packages``, so a conform that drops a member from
``[tool.uv.workspace]`` (or from its ``workspace = true`` source) makes that
sync uninstall the member and every later member import fails. The retired
git-pinned ``workspace`` dependency group never returns: a member declared
both as a path and as a URL is a uv conflict.

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
    def test_workspace_root_group_survives_conform_at_a_fixed_point(
        tmp_path: Path,
    ) -> None:
        """Real root conform declares every attached member and converges."""
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
        members = first.workspace.subprojects
        tm.that(len(members), eq=1)
        rendered = u.Tests.codegen_file_text(
            next(item for item in first.files if item.path == root_pyproject),
        )
        sources = u.Tests.toml_table_at(rendered, "tool", "uv", "sources")
        for member in members:
            tm.that(sources[member.distribution], eq={"workspace": True})
        tm.that(
            "workspace" in u.Tests.toml_table_at(rendered, c.Infra.DEPENDENCY_GROUPS),
            eq=False,
        )
        root_pyproject.write_text(rendered, encoding="utf-8")
        second = tm.ok(service.plan(request))
        tm.that(
            u.Tests.codegen_file_text(
                next(item for item in second.files if item.path == root_pyproject),
            ),
            eq=rendered,
        )
