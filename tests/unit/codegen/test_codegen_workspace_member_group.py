"""A workspace root keeps its attached members in its own dependency group.

The root environment serves every attached member: setup syncs every group of
the root lock exactly, so a conform that drops the member group makes that
sync uninstall the members and every later member import fails.
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import c
from flext_infra.codegen import FlextInfraCodegenConform
from tests import u


class TestsFlextInfraCodegenWorkspaceMemberGroup:
    def test_workspace_root_group_survives_conform_at_a_fixed_point(
        self, tmp_path: Path,
    ) -> None:
        """Real root conform declares every attached member and converges."""
        root = tmp_path / "workspace"
        root_pyproject = u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            "sample-workspace",
            workspace="sample-workspace",
            database="sample_workspace",
            issue_prefix="sample",
        )
        member = root / "sample-member"
        u.Tests.WorktreeFixture.initialize_governed_project(
            member,
            "sample-member",
            workspace="sample-workspace",
            database="sample_workspace",
            issue_prefix="sample",
        )
        u.Tests.WorktreeFixture.attach_submodule(
            root, member, distribution="sample-member", relative_path="sample-member",
        )
        # A governed workspace root declares its own project, exactly as the
        # real composed root does; conform renders no root pyproject without it.
        u.Tests.write_standalone_workspace_manifest(
            root, "sample-workspace", role=c.Infra.MakeProfile.WORKSPACE,
        )
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
        declared = tuple(
            u.Tests.toml_strings_at(rendered, c.Infra.DEPENDENCY_GROUPS, "workspace"),
        )
        tm.that(
            tuple(u.Infra.dep_name(item) for item in declared),
            eq=tuple(item.distribution for item in first.workspace.subprojects),
        )
        root_pyproject.write_text(rendered, encoding="utf-8")
        second = tm.ok(service.plan(request))
        tm.that(
            u.Tests.codegen_file_text(
                next(item for item in second.files if item.path == root_pyproject),
            ),
            eq=rendered,
        )
