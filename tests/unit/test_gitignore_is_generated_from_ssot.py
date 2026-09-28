"""Tests that this repository's ``.gitignore`` is reproducible from config.

The generator filters the shared policy by the repository profile. Workspace
roots receive the ordered whitelist while standalone projects receive only
universal ignore sections. This test follows that same typed topology instead
of freezing the workspace projection into every repository.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

import flext_infra
from flext_infra import c, config
from flext_infra.codegen.conform import FlextInfraCodegenConform
from tests import u as test_u


class TestsFlextInfraGitignoreIsGeneratedFromSsot:
    def _repository_root(self) -> Path:
        """Return the workspace root that owns this checkout."""
        return Path(flext_infra.__file__).resolve().parents[2]

    def _is_allowed_by_policy(self, rendered: str, relative_path: str) -> bool:
        """Return whether one policy snapshot keeps *relative_path* trackable."""
        return test_u.Tests.is_tracked_under(rendered, relative_path)

    def test_every_managed_file_survives_the_ignore_policy(self) -> None:
        """No committed managed artifact is ignored by the shipped policy.

        ``codegen conform`` creates every entry of ``managed_files`` and then
        verifies the tree through git. A whitelist that blocks one of those
        paths makes the artifact untrackable, so conform re-reports it as a new
        file on every run and the whole transaction never converges.
        """
        committed = config.Infra.codegen.managed_files
        rendered = (
            "\n".join(test_u.Tests.ignore_patterns_for(self._repository_root())) + "\n"
        )
        blocked = tuple(
            item.path.as_posix()
            for item in committed
            if not self._is_allowed_by_policy(rendered, item.path.as_posix())
        )

        tm.that(blocked, eq=())

    def test_vendored_package_directory_is_trackable(self) -> None:
        """A vendored tree inside the package stays tracked and therefore packaged.

        Why (flext-f6gqq): hatchling honours .gitignore, so an unanchored
        ``vendor/`` rule silently dropped ``src/<pkg>/vendor`` from the wheel
        while still ignoring the root-level vendor tree it was meant for.
        """
        rendered = tm.ok(
            FlextInfraCodegenConform.render_project_gitignore(
                config.Infra.codegen,
                profile=c.Infra.MakeProfile.STANDALONE,
                project_name="probe-project",
            )
        )

        tm.that(
            test_u.Tests.is_tracked_under(
                rendered, "src/probe_project/vendor/docx/document.py"
            ),
            eq=True,
        )
        tm.that(test_u.Tests.is_tracked_under(rendered, "vendor/module.go"), eq=False)

    def test_declared_projects_are_trackable_under_the_rendered_policy(self) -> None:
        """A project declared in the manifest is trackable in the rendered body.

        The workspace policy denies every top-level directory (``/*`` and
        ``/*/``), so a governed project only becomes trackable when the whitelist
        is derived from the live topology. Arbitrary project paths are used —
        including a nested one, whose every ancestor must be unignored — so the
        contract holds for any manifest instead of freezing today's projects.
        """
        projects = ("probe-project", "nested/probe-project")
        workspace = test_u.Tests.workspace_spec(
            test_u.Tests.repository_ref("probe-root"),
            subprojects=tuple(
                test_u.Tests.repository_ref(
                    Path(item).name,
                    path=Path(item),
                    role=c.Infra.MakeProfile.STANDALONE,
                )
                for item in projects
            ),
        )

        rendered = tm.ok(
            FlextInfraCodegenConform.render_project_gitignore(
                config.Infra.codegen,
                profile=c.Infra.MakeProfile.WORKSPACE,
                project_name="probe-root",
                workspace=workspace,
            )
        )

        blocked = tuple(
            project
            for project in projects
            if not test_u.Tests.is_tracked_under(rendered, f"{project}/pyproject.toml")
        )

        tm.that(blocked, eq=())
