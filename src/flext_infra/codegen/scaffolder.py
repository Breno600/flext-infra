"""Module scaffolder for base module generation.

Generates missing base modules (constants, typings, protocols, models, utilities)
in both src/ and tests/ directories for workspace projects.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_infra import c, m, r, u
from flext_infra.codegen._execution import FlextInfraCodegenExecutionBase
from flext_infra.codegen._mise_artifacts_publication import FlextInfraMisePublication

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraCodegenScaffolder(FlextInfraCodegenExecutionBase[str]):
    """Generates missing base modules in src/ and tests/ directories."""

    @override
    def execute(self) -> p.Result[str]:
        """Execute scaffolding directly from the validated CLI model.

        Returns:
            The resulting ``p.Result[str]``.

        """
        dry_run = self.dry_run or not self.apply_changes
        results = self.run(dry_run=dry_run)
        total_created = sum(len(result.files_created) for result in results)
        total_skipped = sum(len(result.files_skipped) for result in results)
        lines: t.MutableSequenceOf[str] = []
        if dry_run:
            lines.append("Dry-run mode: no files will be created")
        lines.extend(
            f"  {result.project}: created {len(result.files_created)} files"
            for result in results
            if result.files_created
        )
        lines.append(
            f"Scaffold: {total_created} created, {total_skipped} skipped"
            f" across {len(results)} projects",
        )
        return r[str].ok("\n".join(lines))

    def run(
        self,
        *,
        dry_run: bool = False,
        projects: t.SequenceOf[p.Infra.ProjectInfo] | None = None,
    ) -> t.SequenceOf[m.Infra.ScaffoldResult]:
        """Scaffold missing base modules for all projects in workspace.

        Args:
            dry_run: If True, only report changes without writing.
            projects: Pre-discovered projects to skip redundant discovery.

        Returns:
            List of ScaffoldResult models, one per project.

        """
        if projects is not None:
            selected_projects = tuple(projects)
        else:
            projects_result = u.Infra.projects(self.repository_root)
            selected_projects = (
                tuple(projects_result.unwrap()) if projects_result.success else ()
            )
        return [
            self._scaffold_project(project, dry_run=dry_run)
            for project in selected_projects
        ]

    def _scaffold_project(
        self,
        project: p.Infra.ProjectInfo,
        *,
        dry_run: bool = False,
    ) -> m.Infra.ScaffoldResult:
        """Scaffold missing base modules for a single project.

        Args:
            project: Project descriptor or project root path.
            dry_run: If True, only report changes without writing.

        Returns:
            ScaffoldResult with lists of created and skipped files.

        """
        project_path = project.path
        if not (project_path / c.Infra.DEFAULT_SRC_DIR).is_dir():
            return m.Infra.ScaffoldResult(
                project=project_path.name,
                files_created=[],
                files_skipped=[],
            )
        project_layout = u.Infra.layout(project_path)
        if project_layout is None or not project_layout.class_stem:
            return m.Infra.ScaffoldResult(
                project=project_path.name,
                files_created=[],
                files_skipped=[],
            )
        files_created: t.MutableSequenceOf[str] = []
        files_skipped: t.MutableSequenceOf[str] = []
        if project_layout.init_path.is_file():
            created, skipped = self._scaffold_dir(
                m.Infra.ScaffoldDirRequest(
                    target_dir=project_layout.package_dir,
                    prefix=project_layout.class_stem,
                    modules=c.Infra.SRC_MODULES,
                    test_prefix="",
                    base_module=c.Infra.PKG_CORE_UNDERSCORE,
                    project_module=project_layout.package_name,
                    test_module=False,
                    dry_run=dry_run,
                    files_created=[],
                    files_skipped=[],
                ),
            )
            files_created.extend(created)
            files_skipped.extend(skipped)
        tests_dir = project_path / c.Infra.DIR_TESTS
        if tests_dir.is_dir():
            created, skipped = self._scaffold_dir(
                m.Infra.ScaffoldDirRequest(
                    target_dir=tests_dir,
                    prefix=project_layout.class_stem,
                    modules=c.Infra.TESTS_MODULES,
                    test_prefix="Tests",
                    base_module=c.Infra.PKG_TESTS_UNDERSCORE,
                    project_module=project_layout.package_name,
                    test_module=True,
                    dry_run=dry_run,
                    files_created=[],
                    files_skipped=[],
                ),
            )
            files_created.extend(created)
            files_skipped.extend(skipped)
        examples_dir = project_path / c.Infra.DIR_EXAMPLES
        if examples_dir.is_dir():
            created, skipped = self._scaffold_dir(
                m.Infra.ScaffoldDirRequest(
                    target_dir=examples_dir,
                    prefix=project_layout.class_stem,
                    modules=c.Infra.SRC_MODULES,
                    test_prefix="Examples",
                    base_module=project_layout.package_name,
                    project_module=project_layout.package_name,
                    test_module=False,
                    dry_run=dry_run,
                    files_created=[],
                    files_skipped=[],
                ),
            )
            files_created.extend(created)
            files_skipped.extend(skipped)
        scripts_dir = project_path / c.Infra.DIR_SCRIPTS
        if scripts_dir.is_dir():
            created, skipped = self._scaffold_dir(
                m.Infra.ScaffoldDirRequest(
                    target_dir=scripts_dir,
                    prefix=project_layout.class_stem,
                    modules=c.Infra.SRC_MODULES,
                    test_prefix="Scripts",
                    base_module=project_layout.package_name,
                    project_module=project_layout.package_name,
                    test_module=False,
                    dry_run=dry_run,
                    files_created=[],
                    files_skipped=[],
                ),
            )
            files_created.extend(created)
            files_skipped.extend(skipped)
        return m.Infra.ScaffoldResult(
            project=project_path.name,
            files_created=files_created,
            files_skipped=files_skipped,
        )

    @staticmethod
    def _scaffold_dir(
        request: m.Infra.ScaffoldDirRequest,
    ) -> t.Pair[t.MutableSequenceOf[str], t.MutableSequenceOf[str]]:
        """Generate missing modules in a directory and return file lists.

        Returns:
            The resulting ``t.Pair[t.MutableSequenceOf[str],
                t.MutableSequenceOf[str]]``.

        Raises:
            OSError: If writing scaffold.

        """
        files_created: t.MutableSequenceOf[str] = []
        files_skipped: t.MutableSequenceOf[str] = []
        for filename, suffix, base_class, doc_suffix in request.modules:
            filepath = request.target_dir / filename
            if filepath.exists():
                files_skipped.append(str(filepath))
                continue
            class_name = f"{request.test_prefix}{request.prefix}{suffix}"
            docstring = f"{doc_suffix} for {request.prefix.lower()}."
            if request.test_module:
                alias = u.Infra.facade_family_declared_by(filename).letter
                content = u.Infra.generate_test_module_skeleton(
                    context=m.Infra.TestModuleSkeletonRenderContext(
                        class_name=class_name,
                        base_class=base_class,
                        project_module=request.project_module,
                        alias=alias,
                        namespace=f"{request.test_prefix}{request.prefix}",
                        project_namespace=request.prefix.removeprefix(
                            c.Infra.PKG_PREFIX_UNDERSCORE.rstrip("_").capitalize(),
                        ),
                        docstring=docstring,
                    ),
                )
            else:
                content = u.Infra.generate_module_skeleton(
                    class_name=class_name,
                    base_class=base_class,
                    base_module=request.base_module,
                    docstring=docstring,
                )
            if request.dry_run:
                files_created.append(str(filepath))
                continue
            before = u.Cli.atomic_read_binary_file_state(filepath, required=False)
            if before.failure:
                message = f"writing scaffold {filepath}: {before.error}"
                raise OSError(message)
            planned = m.Infra.CodegenFilePlan(
                project=request.target_dir,
                path=filepath,
                before=before.value,
                desired_content=content.encode(c.Cli.ENCODING_DEFAULT),
                desired_mode=0o644,
                owner="codegen",
            )
            written = FlextInfraMisePublication.publish_file_plan(
                planned,
                phase="scaffold",
            )
            if written.failure:
                message = f"writing scaffold {filepath}: {written.error}"
                raise OSError(message)
            files_created.append(str(filepath))
        return files_created, files_skipped


__all__: list[str] = ["FlextInfraCodegenScaffolder"]
