"""Verify ci.yml grants packages: read only to declared registry consumers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from flext_tests import tm

from flext_infra import c
from tests import t, u


class TestsFlextInfraCiPackageRegistryRead:
    """A GitHub Packages consumer reads its registry; nobody else can."""

    ci_template = (
        Path(__file__).resolve().parents[3]
        / "src/flext_infra/templates/project/base/.github/workflows/ci.yml.j2"
    )

    @classmethod
    def _job_permissions(cls, *, packages_read: bool) -> Mapping[str, t.JsonValue]:
        spec = u.CodegenTestSupport.Ci.workflow_spec(
            dist="fixture-registry-consumer",
            make_profile=c.Infra.MakeProfile.STANDALONE,
            repository_branch="develop",
            ci_trigger_branches=("develop", "main"),
            overrides=u.CodegenTestSupport.Ci.WorkflowRenderOverrides(
                packages_read=packages_read,
            ),
        )
        rendered = tm.ok(u.Cli.template_render(cls.ci_template, spec))
        jobs = tm.ok(u.Cli.yaml_parse(rendered))["jobs"]
        assert isinstance(jobs, Mapping)
        permissions: t.MutableJsonMapping = {}
        for name, job in jobs.items():
            assert isinstance(job, Mapping)
            permissions[name] = job["permissions"]
        return permissions

    def test_declared_consumer_ci_job_reads_packages(self) -> None:
        """Test declared consumer ci job reads packages."""
        permissions = self._job_permissions(packages_read=True)

        tm.that(permissions["ci"], eq={"contents": "read", "packages": "read"})
        tm.that(permissions["release-plan"], eq={"contents": "read"})
        tm.that(permissions["merge-guard"], eq={"contents": "read"})

    def test_undeclared_consumer_stays_contents_only(self) -> None:
        """Test undeclared consumer stays contents only."""
        permissions = self._job_permissions(packages_read=False)

        for job_permissions in permissions.values():
            tm.that(job_permissions, eq={"contents": "read"})
