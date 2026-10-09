"""Repository-local topology ownership inside linked worktrees.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, infra, m
from flext_infra.codegen import FlextInfraCodegenConform
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
from tests import u


# Conform materializes a full managed tree; the real Git scenarios therefore use
# the config-owned slow budget instead of weakening the global timeout.
@pytest.mark.slow
class TestsFlextInfraCodegenLinkedWorktreeManifest:
    """Keep topology inputs and writes owned by the repository being conformed."""

    @staticmethod
    def test_linked_lane_reads_its_local_beads_identity_and_only_writes_lane(
        tmp_path: Path,
    ) -> None:
        """Use dirty lane-local policy without reading or mutating the primary."""
        primary = tmp_path / "primary"
        primary_pyproject = u.Tests.WorktreeFixture.initialize_governed_project(
            primary,
            "fixture-project",
            beads=u.Tests.BeadsIdentity(
                workspace="primary-workspace",
                database="primary-database",
                issue_prefix="primary-prefix",
            ),
        )
        lane = tmp_path / "lane"
        tm.ok(
            u.Infra.git_add_lane_worktree(
                m.Infra.GitWorktreeAddRequest(
                    repo_root=primary,
                    lane=lane,
                    branch="bugfix/lane-local-topology",
                    base=c.Infra.GIT_HEAD,
                ),
            ),
        )
        lane_beads = u.Tests.WorktreeFixture.write_beads_project(
            lane,
            workspace="lane-workspace",
            database="lane-database",
            issue_prefix="lane-prefix",
        )
        lane_beads_bytes = lane_beads.read_bytes()
        primary_pyproject.write_text(
            f"{primary_pyproject.read_text(encoding='utf-8')}# human WIP\n",
            encoding="utf-8",
        )
        primary_snapshot = u.Tests.WorktreeFixture.repository_snapshot(primary)

        request = u.Tests.conform_request(
            lane,
            what=c.Infra.CodegenConformSurface.MAKEFILE,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        plan = tm.ok(
            FlextInfraCodegenConform(repository_root=lane, request=request).plan(
                request,
            ),
        )

        planned = {item.path: item for item in plan.files}
        tm.that(
            set(planned),
            eq={lane / item for item in c.Infra.MAKEFILE_BOOTSTRAP_DESTINATIONS},
        )
        makefile_plan = planned[lane / c.Infra.MAKEFILE_FILENAME]
        tm.that(
            u.Tests.codegen_file_text(makefile_plan),
            has="MAKE_PROFILE := standalone",
        )
        beads = tm.not_none(plan.workspace.beads)
        tm.that(beads.workspace, eq="lane-workspace")
        tm.that(beads.database, eq="lane-database")
        tm.that(beads.issue_prefix, eq="lane-prefix")
        tm.that(all(item.path.is_relative_to(lane) for item in plan.files), eq=True)
        tm.that(
            tm.ok(FlextInfraWorkspaceDetector.resolve_repository_root(lane)),
            eq=lane.resolve(),
        )
        tm.that(lane_beads.read_bytes(), eq=lane_beads_bytes)
        tm.that((lane / c.Infra.MAKEFILE_FILENAME).exists(), eq=False)
        tm.that((primary / c.Infra.MAKEFILE_FILENAME).exists(), eq=False)
        tm.that(
            u.Tests.WorktreeFixture.repository_snapshot(primary),
            eq=primary_snapshot,
        )

    @staticmethod
    @pytest.mark.parametrize(
        ("beads_content", "expected_error"),
        [
            pytest.param(
                None,
                "missing required repository-local Beads configuration",
                id="missing",
            ),
            pytest.param(
                "version: [\nworkspace: invalid\n",
                "YAML parse error",
                id="malformed",
            ),
        ],
    )
    def test_invalid_local_beads_identity_fails_before_any_write(
        tmp_path: Path,
        beads_content: str | None,
        expected_error: str,
    ) -> None:
        """Fail planning atomically when the required local input is invalid."""
        root = tmp_path / "project"
        u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            "fixture-project",
            beads=u.Tests.BeadsIdentity(
                workspace="fixture-workspace",
                database="fixture-database",
                issue_prefix="fixture-prefix",
            ),
        )
        beads_path = root / "config" / "beads.yaml"
        if beads_content is None:
            beads_path.unlink()
        else:
            beads_path.write_text(beads_content, encoding="utf-8")
        before = u.Tests.WorktreeFixture.repository_snapshot(root)

        result = infra.codegen_conform(
            u.Tests.conform_request(
                root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            ),
        )

        tm.fail(result, has=expected_error)
        tm.that(u.Tests.WorktreeFixture.repository_snapshot(root), eq=before)

    @staticmethod
    def test_workspace_members_inherit_identity_and_topology_inputs_are_never_rewritten(
        tmp_path: Path,
    ) -> None:
        """Members declare the workspace identity; conform never rewrites inputs."""
        root = tmp_path / "workspace"
        u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            "fixture-workspace",
            beads=u.Tests.BeadsIdentity(
                workspace="root-workspace",
                database="root-database",
                issue_prefix="root-prefix",
            ),
        )
        project_names = ("fixture-alpha", "fixture-beta")
        for project_name in project_names:
            u.Tests.WorktreeFixture.initialize_governed_project(
                root / project_name,
                project_name,
                beads=u.Tests.BeadsIdentity(
                    workspace="root-workspace",
                    database="root-database",
                    issue_prefix="root-prefix",
                ),
            )
        gitmodules = u.Tests.WorktreeFixture.write_gitmodules(root, project_names)
        u.Tests.git_bootstrap(root, ("add", c.Infra.GITMODULES, *project_names))
        u.Tests.git_bootstrap(
            root,
            ("commit", "-m", "fixture: declare workspace subprojects"),
        )
        protected_bytes = {gitmodules: gitmodules.read_bytes()}

        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        tm.that(
            tuple(project.path.as_posix() for project in workspace.subprojects),
            eq=project_names,
        )
        for project_name in project_names:
            beads = tm.ok(
                FlextInfraWorkspaceDetector.load_beads_spec(root / project_name),
            )
            tm.that(beads.workspace, eq="root-workspace")
            tm.that(beads.database, eq="root-database")
            tm.that(beads.issue_prefix, eq="root-prefix")

        applied = tm.ok(
            infra.codegen_conform(
                u.Tests.conform_request(
                    root,
                    scope=c.Infra.CodegenConformScope.DECLARED,
                    mode=c.Infra.CodegenConformMode.APPLY,
                ),
            ),
        )

        tm.that(bool(applied.written_files), eq=True)
        for path, content in protected_bytes.items():
            tm.that(path.read_bytes(), eq=content)
        tm.that(
            tuple(
                path
                for path in applied.written_files
                if path == gitmodules or path.name == "beads.yaml"
            ),
            empty=True,
        )
        # Every member owns a physical ledger route rendered by generation;
        # the retired cross-project symlink is never recreated.
        for project_name in project_names:
            route = root / project_name / ".beads"
            tm.that(route.is_dir(), eq=True)
            tm.that(route.is_symlink(), eq=False)
            tm.that((route / "config.yaml").is_file(), eq=True)

    @staticmethod
    def test_declared_subproject_cannot_escape_through_a_linked_path(
        tmp_path: Path,
    ) -> None:
        """Reject a declared subproject whose path resolves outside its owner."""
        root = tmp_path / "workspace"
        outside = tmp_path / "outside-project"
        u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            "fixture-workspace",
            beads=u.Tests.BeadsIdentity(
                workspace="root-workspace",
                database="root-database",
                issue_prefix="root-prefix",
            ),
        )
        u.Tests.WorktreeFixture.initialize_governed_project(
            outside,
            "linked-project",
            beads=u.Tests.BeadsIdentity(
                workspace="outside-workspace",
                database="outside-database",
                issue_prefix="outside-prefix",
            ),
        )
        (root / "linked-project").symlink_to(outside, target_is_directory=True)
        u.Tests.WorktreeFixture.write_gitmodules(root, ("linked-project",))
        outside_snapshot = u.Tests.WorktreeFixture.repository_snapshot(outside)

        result = infra.codegen_conform(
            u.Tests.conform_request(
                root,
                what=c.Infra.CodegenConformSurface.MAKEFILE,
                scope=c.Infra.CodegenConformScope.DECLARED,
                mode=c.Infra.CodegenConformMode.CHECK,
            ),
        )

        tm.fail(result, has="escapes workspace root")
        tm.that(
            u.Tests.WorktreeFixture.repository_snapshot(outside),
            eq=outside_snapshot,
        )
