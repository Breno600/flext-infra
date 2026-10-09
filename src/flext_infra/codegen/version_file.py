"""Auto-generate ``__version__.py`` files from the project-metadata SSOT.

Each generated file inherits ``FlextVersion`` from flext-core, with the
project name baked in from ``u.Infra.read_project_metadata_result()`` at generation
time.  No fallback, no hardcoded defaults — ``PackageNotFoundError``
propagates if the package is not installed.

Uses the canonical Jinja2 template ``templates/version_file.py.j2``
and workspace project discovery via ``u.Infra.discover_projects``.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from flext_core import r
from flext_core.__version__ import FlextVersion
from flext_infra import c, m, u
from flext_infra.codegen._execution import FlextInfraCodegenExecutionBase
from flext_infra.codegen._mise_artifacts_publication import FlextInfraMisePublication

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraCodegenVersionFile(FlextInfraCodegenExecutionBase[bool]):
    """Generate ``__version__.py`` for every workspace project.

    Projects whose derived version class name equals ``FlextVersion``
    (the base class defined in flext-core) are skipped — that file is
    the SSOT base and is never generated.  Detection is 100% SSOT-derived
    via ``u.derive_class_stem`` from installed generated lazy exports.

    Project discovery uses ``u.Infra.discover_projects`` — the canonical
    workspace project list. No manual directory iteration.
    """

    @override
    def execute(self) -> p.Result[bool]:
        """Generate __version__.py for each discovered project.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        # The exact
        # source metadata model crosses the sole CLI rendering boundary.
        template_path = (
            Path(__file__).resolve().parent.parent
            / "templates"
            / c.Infra.TEMPLATE_VERSION_FILE
        )
        discovered = u.Infra.discover_projects(self.repository_root)
        if not discovered.success:
            return r[bool].fail("version-file: project discovery failed")

        outcomes: t.MutableIntMapping = {"generated": 0, "skipped": 0}
        for project_info in self._filtered_projects(discovered.value):
            outcome = self._sync_project(project_info.path, template_path)
            if outcome.failure:
                return r[bool].from_failure(outcome)
            outcomes[outcome.value] = outcomes.get(outcome.value, 0) + 1

        verb = "would generate" if (self.check_only or self.dry_run) else "generated"
        u.Cli.info(
            f"version-file: {verb} {outcomes['generated']}, "
            f"skipped {outcomes['skipped']}",
        )
        return r[bool].ok(value=True)

    def _sync_project(self, project: Path, template_path: Path) -> p.Result[str]:
        """Render one project's ``__version__.py`` and name the outcome.

        Returns:
            The resulting ``p.Result[str]``.
        """
        metadata_result = u.Infra.read_project_metadata_result(project)
        if metadata_result.failure:
            return r[str].from_failure(metadata_result)
        meta = metadata_result.value
        if f"{meta.class_stem}Version" == FlextVersion.__name__:
            return r[str].ok("skipped")
        src_pkg = project / "src" / meta.package_name
        if not src_pkg.is_dir():
            return r[str].ok("absent")
        rendered = u.Cli.template_render(template_path, meta)
        if rendered.failure:
            return r[str].from_failure(rendered)
        return self._publish_version(
            project,
            src_pkg / "__version__.py",
            rendered.value,
        )

    def _publish_version(
        self,
        project: Path,
        target: Path,
        content: str,
    ) -> p.Result[str]:
        """Publish ``content`` to ``target`` unless it is already current.

        Returns:
            The resulting ``p.Result[str]``.
        """
        if target.is_file():
            current = u.Cli.files_read_text(target)
            if current.failure:
                return r[str].from_failure(current)
            if current.value == content:
                return r[str].ok("current")
        relative = target.relative_to(self.repository_root)
        if self.check_only or self.dry_run:
            u.Cli.info(f"  stale: {relative}")
            return r[str].ok("generated")
        before = u.Cli.atomic_read_binary_file_state(target, required=False)
        if before.failure:
            return r[str].from_failure(before)
        planned = m.Infra.CodegenFilePlan(
            project=project,
            path=target,
            before=before.value,
            desired_content=content.encode(c.Cli.ENCODING_DEFAULT),
            desired_mode=0o644,
            owner="codegen",
            policy="full",
        )
        published = FlextInfraMisePublication.publish_file_plan(
            planned,
            phase="version-file",
        )
        if published.failure:
            return r[str].from_failure(published)
        u.Cli.info(f"  generated: {relative}")
        return r[str].ok("generated")


__all__: list[str] = ["FlextInfraCodegenVersionFile"]
