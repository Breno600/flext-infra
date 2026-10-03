"""Fresh-process import proof as a make check gate.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import m
from flext_infra.gates.fresh_import import FlextInfraFreshImportGate
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraFreshImportGate:
    """The proof runs in the checkout's provisioned runtime, inside make check."""

    @staticmethod
    def _project(tmp_path: Path) -> Path:
        """Materialize one standalone package checkout without a runtime.

        Returns:
            The checkout root.

        """
        project = tmp_path / "flext-demo"
        _ = u.Tests.standalone_workspace(project, project.name)
        return project

    @staticmethod
    def _execution(project: Path) -> m.Infra.GateExecution:
        """Run the gate over one checkout.

        Returns:
            The gate execution.

        """
        context = m.Infra.GateContext(
            repository_root=project,
            reports_dir=project / ".reports",
        )
        return FlextInfraFreshImportGate(repository_root=project).check(
            project,
            context,
        )

    def test_a_checkout_without_its_runtime_fails_loud(self, tmp_path: Path) -> None:
        """Check, not generation, reports the missing runtime setup provisions."""
        project = self._project(tmp_path)
        gate = FlextInfraFreshImportGate(repository_root=project)

        tm.that(gate.selected_for(project), eq=True)
        result = self._execution(project).result

        tm.that(result.passed, eq=False)
        tm.that(
            " | ".join(result.errors),
            has="fresh-import target interpreter is missing",
        )

    def test_a_provisioned_checkout_imports_its_package(self, tmp_path: Path) -> None:
        """The package imports in a fresh process of the checkout's runtime."""
        project = self._project(tmp_path)
        _ = u.Tests.provision_runtime_environment(project)

        result = self._execution(project).result

        tm.that(result.passed, eq=True, msg=" | ".join(result.errors))

    def test_a_declared_non_package_repository_is_not_selected(
        self,
        tmp_path: Path,
    ) -> None:
        """A ``package: false`` declaration deselects the gate, whatever the tree."""
        project = self._project(tmp_path)
        manifest = m.Infra.WorkspaceManifestSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name=project.name,
            repository=u.Tests.repository_ref(project.name).model_copy(
                update={"package": False},
            ),
            project=u.Tests.project_spec(project.name),
        )
        tm.ok(
            u.Cli.yaml_dump(
                u.Infra.workspace_manifest_path(project),
                manifest.model_dump(mode="json"),
            ),
        )

        tm.that(
            FlextInfraFreshImportGate(repository_root=project).selected_for(project),
            eq=False,
        )
