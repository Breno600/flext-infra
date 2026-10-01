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
    from .. import p


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
        """Generate __version__.py for each discovered project."""
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

        generated = 0
        skipped = 0

        for project_info in self._filtered_projects(discovered.value):
            metadata_result = u.Infra.read_project_metadata_result(project_info.path)
            if metadata_result.failure:
                return r[bool].from_failure(metadata_result)
            meta = metadata_result.value
            class_name = f"{meta.class_stem}Version"

            if class_name == FlextVersion.__name__:
                skipped += 1
                continue

            src_pkg = project_info.path / "src" / meta.package_name
            if not src_pkg.is_dir():
                continue

            target = src_pkg / "__version__.py"
            rendered = u.Cli.template_render(template_path, meta)
            if rendered.failure:
                return r[bool].from_failure(rendered)
            content = rendered.value

            if target.is_file():
                current = u.Cli.files_read_text(target)
                if current.failure:
                    return r[bool].from_failure(current)
                if current.value == content:
                    continue

            if self.check_only or self.dry_run:
                u.Cli.info(f"  stale: {target.relative_to(self.repository_root)}")
                generated += 1
                continue

            before = u.Cli.atomic_read_binary_file_state(target, required=False)
            if before.failure:
                return r[bool].from_failure(before)
            planned = m.Infra.CodegenFilePlan(
                project=project_info.path,
                path=target,
                before=before.value,
                desired_content=content.encode(c.Cli.ENCODING_DEFAULT),
                desired_mode=0o644,
                owner="codegen",
                policy="full",
            )
            write_result = FlextInfraMisePublication.publish_file_plan(
                planned,
                phase="version-file",
            )
            if write_result.failure:
                return r[bool].from_failure(write_result)
            generated += 1
            u.Cli.info(f"  generated: {target.relative_to(self.repository_root)}")

        verb = "would generate" if (self.check_only or self.dry_run) else "generated"
        u.Cli.info(f"version-file: {verb} {generated}, skipped {skipped}")
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraCodegenVersionFile"]
