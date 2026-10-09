"""A workspace root's SonarCloud scope excludes its member checkouts.

Each workspace member is a separate repository analysed by its own SonarCloud
project. When the root scope scans the member checkouts too, their code is
counted again as root code and the root quality gate fails on duplication it
does not own. The exclusion is derived from the declared topology, never listed.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import c, config, t
from flext_infra.codegen import FlextInfraCodegenConform
from tests import u


class TestsFlextInfraCodegenSonarcloudWorkspaceScope:
    """Tests for the workspace-derived ``.sonarcloud.properties`` scope."""

    @staticmethod
    def _rendered_scope(
        root: Path,
    ) -> tuple[t.StrSequence, t.StrSequence, t.StrSequence]:
        """Plan conform for one root and return its exclusion and CPD scopes.

        Returns:
            The rendered ``sonar.exclusions`` and ``sonar.cpd.exclusions``, and
            the member patterns derived from the planned workspace topology.

        """
        request = u.Tests.conform_request(
            root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        plan = tm.ok(FlextInfraCodegenConform(repository_root=root).plan(request))
        rendered = tm.not_none(
            u.Tests.planned_text(plan, c.Infra.SONARCLOUD_PROPERTIES_FILENAME),
        )
        properties = {
            key: value
            for key, _, value in (
                line.partition("=")
                for line in rendered.splitlines()
                if line and not line.startswith("#")
            )
        }
        return (
            tuple(properties["sonar.exclusions"].split(",")),
            tuple(
                item
                for item in properties.get("sonar.cpd.exclusions", "").split(",")
                if item
            ),
            tuple(f"{item.path.as_posix()}/**" for item in plan.workspace.subprojects),
        )

    def test_workspace_root_excludes_members_and_standalone_does_not(
        self,
        tmp_path: Path,
    ) -> None:
        """The root render excludes each declared member; a member render does not."""
        root = tmp_path / "workspace"
        member = u.Tests.WorktreeFixture.governed_workspace_with_member(root)
        tm.that((root / c.Infra.GITMODULES).is_file(), eq=True)
        sonarcloud = config.Infra.codegen.sonarcloud
        # Tracked generated-source trees join the declared exclusions from
        # their one codegen artifact key (flext-gknfx).
        generated = config.Infra.codegen.generated_source_globs
        tests_scope = f"{c.Infra.DIR_TESTS}/**"

        exclusions, cpd_exclusions, members = self._rendered_scope(root)
        tm.that(members, eq=(f"{member.relative_to(root).as_posix()}/**",))
        member_pattern = members[0]
        tm.that(
            exclusions,
            eq=(*sonarcloud.exclusions, *generated, tests_scope, member_pattern),
        )
        tm.that(
            cpd_exclusions,
            eq=(*sonarcloud.cpd_exclusions, member_pattern),
        )

        standalone_exclusions, standalone_cpd, standalone_members = (
            self._rendered_scope(member)
        )
        tm.that(standalone_members, empty=True)
        tm.that(
            standalone_exclusions,
            eq=(*sonarcloud.exclusions, *generated, tests_scope),
        )
        tm.that(standalone_cpd, eq=tuple(sonarcloud.cpd_exclusions))
