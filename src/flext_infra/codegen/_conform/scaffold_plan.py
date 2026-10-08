"""Complete scaffold planning for ``codegen new``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, config, m, p, r, t, u
from flext_infra.codegen._conform.existing_plan import (
    FlextInfraCodegenConformExistingPlan,
)
from flext_infra.deps.modernizer import FlextInfraPyprojectModernizer
from flext_infra.deps.phases.tool_tables import FlextInfraToolTablesPhase


class FlextInfraCodegenConformScaffoldPlan(FlextInfraCodegenConformExistingPlan):
    """Complete scaffold planning for ``codegen new``."""

    def _plan_scaffold_repository(
        self,
        *,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        contract: m.Infra.CodegenConformSurfaceContract,
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Render the complete scaffold for ``codegen new`` only.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]``.

        """
        project = workspace.project
        if project is None:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                f"scaffold workspace has no project metadata: {workspace.name}",
            )
        root = target.root
        profile = target.make_profile
        # New and existing repositories share the exact same
        # root-scoped modernizer pipeline, so first generation is a fixed point.
        # A declared subproject consumes the workspace root
        # tooling profile even before the atomic scaffold creates files on disk.
        scaffold_entries = tuple(
            (
                entry,
                entry.destination.format(
                    package_name=project.package_name,
                    ns=project.namespace,
                ),
            )
            for entry in codegen.templates.entries
            if profile in entry.profiles
            and (entry.destination != c.PYPROJECT_FILENAME or contract.pyproject)
            and (contract.delegates or entry.destination == c.PYPROJECT_FILENAME)
            and (not entry.requires_release_protocol or target.publishes_release)
            and (not entry.requires_beads or workspace.beads is not None)
            and (
                contract.destinations is None
                or entry.destination in contract.destinations
            )
        )
        modernizer = FlextInfraPyprojectModernizer(
            repository_root=root,
            skip_check=True,
            managed_artifacts=u.Infra.empty_snapshot().resolution,
        )
        analysis_exclusions = tuple(
            path.as_posix()
            for path in (
                *target.external_dependency_paths,
                *workspace.external_dependency_paths,
            )
        )
        # Why: a scaffold's declared roots are the complete
        # future topology only for a subproject/standalone target; a workspace
        # root aggregates subproject trees it has not declared here.
        tooling_result = modernizer.resolve_tooling_context(
            m.Infra.ToolingContextRequest(
                project_name=target.repository.distribution,
                package_name=project.package_name,
                path=root / c.PYPROJECT_FILENAME,
                scaffold_project=codegen.scaffold.project,
                upstream=project.upstream,
                runtime_dependency_overlay=project.runtime_dependency_overlay,
                declared_project_dependencies=(),
                topology=m.Infra.PyprojectDeclaredTopology(
                    root_modules=project.root_modules,
                    root_packages=project.root_packages,
                    repository_namespace_packages=project.repository_namespace_packages,
                    packaged_data_paths=project.packaged_data_paths,
                    planned_data_files=tuple(
                        destination for _, destination in scaffold_entries
                    ),
                    declared_python_dirs=tuple(
                        self._scaffold_python_dirs(codegen.templates.entries, profile),
                    ),
                    declared_python_dirs_are_complete=(
                        profile is not c.Infra.MakeProfile.WORKSPACE
                    ),
                    analysis_exclusions=analysis_exclusions,
                ),
            ),
        )
        if tooling_result.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(tooling_result)
        prepared = self._scaffold_render_setup(
            target,
            workspace,
            codegen,
            scaffold_entries,
            tooling_result.value,
        )
        if prepared.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(prepared)
        render_inputs, context = prepared.value
        targets = self._validated_scaffold_targets(codegen, root, scaffold_entries)
        if targets.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(targets)
        planned: list[m.Infra.CodegenFilePlan] = []
        # The pyproject plans first: renders that derive from its requirements
        # (the dependabot cooldown exclusion) read the planned bytes.
        for entry, destination in sorted(
            scaffold_entries,
            key=lambda item: item[1] != c.PYPROJECT_FILENAME,
        ):
            entry_plan = self._scaffold_entry_plan(
                entry=entry,
                destination=destination,
                workspace=workspace,
                render_inputs=render_inputs,
                context=context,
            )
            if entry_plan.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                    entry_plan,
                )
            file_plan, render_inputs = entry_plan.value
            planned.append(file_plan)
        return self._with_planned_facade_rebinds(
            planned=tuple(planned),
            scaffold_entries=scaffold_entries,
            workspace=workspace,
            render_inputs=render_inputs,
        )

    def _scaffold_render_setup(
        self,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        scaffold_entries: t.VariadicTuple[t.Pair[m.Infra.TemplateEntrySpec, str]],
        tooling_runtime: m.Infra.ToolingRuntimeContext,
    ) -> p.Result[t.Pair[m.Infra.CodegenRenderInputs, m.Infra.ProjectRenderContext]]:
        """Resolve render inputs and the project render context for a scaffold.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenRenderInputs,
                m.Infra.ProjectRenderContext]]``.

        """
        result_type = r[
            t.Pair[m.Infra.CodegenRenderInputs, m.Infra.ProjectRenderContext]
        ]
        render_inputs = self.resolve_render_inputs(
            target=target,
            workspace=workspace,
            codegen=codegen,
            tooling_runtime=tooling_runtime,
            managed_artifacts=u.Infra.empty_snapshot(),
        )
        context_result = self._project_render_context(
            render_inputs,
            planned_data_files=tuple(
                destination for _, destination in scaffold_entries
            ),
        )
        if context_result.failure:
            return result_type.from_failure(context_result)
        return result_type.ok((render_inputs, context_result.value))

    def _validated_scaffold_targets(
        self,
        codegen: m.Infra.CodegenConfigSpec,
        root: Path,
        scaffold_entries: t.VariadicTuple[t.Pair[m.Infra.TemplateEntrySpec, str]],
    ) -> p.Result[bool]:
        """Validate every scaffold template source and destination path.

        One selection and one formatted path govern validation and planning.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        result_type = r[bool]
        templates_root = u.Infra.codegen_templates_root(codegen)
        seen_destinations: set[str] = set()
        for entry, destination in scaffold_entries:
            if entry.delegate == c.Infra.TemplateDelegate.RENDER:
                source = self._validated_template_source(
                    templates_root,
                    entry,
                    destination,
                )
                if source.failure:
                    return result_type.from_failure(source)
            destination_check = self._validated_destination(
                root,
                destination,
                seen_destinations,
            )
            if destination_check.failure:
                return result_type.from_failure(destination_check)
            seen_destinations.add(destination)
        return result_type.ok(value=True)

    @staticmethod
    def _validated_template_source(
        templates_root: Path,
        entry: m.Infra.TemplateEntrySpec,
        destination: str,
    ) -> p.Result[bool]:
        """Prove a render entry's template source exists inside its root.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        result_type = r[bool]
        if entry.source is None:
            return result_type.fail(
                f"render entry has no template source: {destination}",
            )
        source = (templates_root / entry.source).resolve()
        if not source.is_relative_to(templates_root) or not source.is_file():
            return result_type.fail(
                f"template source is missing or escapes its root: {entry.source}",
            )
        return result_type.ok(value=True)

    @staticmethod
    def _validated_destination(
        root: Path,
        destination: str,
        seen_destinations: set[str],
    ) -> p.Result[bool]:
        """Confine one template destination inside the root, without duplicates.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        result_type = r[bool]
        relative = Path(destination)
        if relative.is_absolute() or ".." in relative.parts:
            return result_type.fail(
                f"template destination escapes repository root: {destination}",
            )
        if destination in seen_destinations:
            return result_type.fail(
                f"duplicate template destination: {destination}",
            )
        path = root / relative
        if path.exists() and not path.is_file():
            return result_type.fail(
                f"template destination is not a regular file: {path}",
            )
        for parent in path.parents:
            if parent == root:
                break
            if parent.exists() and not parent.is_dir():
                return result_type.fail(
                    f"template destination parent is not a directory: {parent}",
                )
        return result_type.ok(value=True)

    def _with_planned_facade_rebinds(
        self,
        *,
        planned: t.VariadicTuple[m.Infra.CodegenFilePlan],
        scaffold_entries: t.VariadicTuple[t.Pair[m.Infra.TemplateEntrySpec, str]],
        workspace: m.Infra.WorkspaceSpec,
        render_inputs: m.Infra.CodegenRenderInputs,
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Render the final pyproject over the sources the scaffold plans.

        The pyproject renders before the sources, but its facade-rebind Mypy
        scope and its first-party namespaces are facts of those sources:
        derived from the tree before publication it omits every facade the
        scaffold creates, and the next
        generation adds them. Once every source is planned, the scope is
        derived from the planned bytes and the pyproject is rendered once more
        with it; nothing rendered earlier reads that scope.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]``.

        """
        result_type = r[t.SequenceOf[m.Infra.CodegenFilePlan]]
        root = render_inputs.target.root
        pyproject_entry = next(
            (
                entry
                for entry, destination in scaffold_entries
                if destination == c.PYPROJECT_FILENAME
            ),
            None,
        )
        if pyproject_entry is None:
            return result_type.ok(planned)
        planned_sources = {
            plan.path: plan.desired_content.decode(c.Cli.ENCODING_DEFAULT)
            for plan in planned
            if plan.path.suffix == c.Infra.EXT_PYTHON
            and plan.desired_content is not None
        }
        tooling = render_inputs.tooling_runtime
        rebinds = u.Infra.facade_rebind_modules(root, planned_sources)
        type_checking = config.Infra.tooling.tools.ruff.lint.flake8_type_checking
        runtime_bases = u.Infra.runtime_evaluated_base_classes(
            root,
            planned_sources,
            type_checking.runtime_evaluated_roots,
        )
        first_party = tuple(
            FlextInfraToolTablesPhase.first_party_namespaces(
                path=root,
                planned_sources=tuple(planned_sources),
            ),
        )
        if (
            rebinds == tuple(tooling.mypy_facade_rebind_modules)
            and first_party == tuple(tooling.first_party)
            and runtime_bases == tuple(tooling.ruff_runtime_evaluated_base_classes)
        ):
            return result_type.ok(planned)
        final_inputs = render_inputs.model_copy(
            update={
                "tooling_runtime": tooling.model_copy(
                    update={
                        "mypy_facade_rebind_modules": rebinds,
                        "ruff_runtime_evaluated_base_classes": runtime_bases,
                        "first_party": first_party,
                    },
                ),
            },
        )
        context = self._project_render_context(
            final_inputs,
            planned_data_files=tuple(
                destination for _, destination in scaffold_entries
            ),
        )
        if context.failure:
            return result_type.from_failure(context)
        final = self._scaffold_entry_plan(
            entry=pyproject_entry,
            destination=c.PYPROJECT_FILENAME,
            workspace=workspace,
            render_inputs=final_inputs,
            context=context.value,
        )
        if final.failure:
            return result_type.from_failure(final)
        pyproject_plan, _ = final.value
        return result_type.ok(
            tuple(
                pyproject_plan if plan.path == pyproject_plan.path else plan
                for plan in planned
            ),
        )

    def _scaffold_entry_plan(
        self,
        *,
        entry: m.Infra.TemplateEntrySpec,
        destination: str,
        workspace: m.Infra.WorkspaceSpec,
        render_inputs: m.Infra.CodegenRenderInputs,
        context: m.Infra.ProjectRenderContext,
    ) -> p.Result[t.Pair[m.Infra.CodegenFilePlan, m.Infra.CodegenRenderInputs]]:
        """Render one scaffold entry into its file plan.

        A rendered pyproject is recorded on the returned render inputs, which
        later renders read.

        Returns:
            The entry's file plan and the render inputs later renders read.

        """
        result_type = r[t.Pair[m.Infra.CodegenFilePlan, m.Infra.CodegenRenderInputs]]
        root = render_inputs.target.root
        rendered = self._scaffold_rendered_source(
            entry,
            destination,
            workspace,
            render_inputs,
            context,
        )
        if rendered.failure:
            return result_type.from_failure(rendered)
        rendered_content = self.compose_project_artifact(
            root,
            destination,
            rendered.value,
            render_inputs=render_inputs,
        )
        if rendered_content.failure:
            return result_type.from_failure(rendered_content)
        if destination == c.PYPROJECT_FILENAME:
            recorded = self.with_planned_pyproject(
                render_inputs,
                rendered_content.value.rendered,
            )
            if recorded.failure:
                return result_type.from_failure(recorded)
            render_inputs = recorded.value
        file_plan = self.file_plan(
            root,
            destination,
            rendered_content.value.rendered,
            source_states=rendered_content.value.source_states,
        )
        if file_plan.failure:
            return result_type.from_failure(file_plan)
        return result_type.ok((file_plan.value, render_inputs))

    def _scaffold_rendered_source(
        self,
        entry: m.Infra.TemplateEntrySpec,
        destination: str,
        workspace: m.Infra.WorkspaceSpec,
        render_inputs: m.Infra.CodegenRenderInputs,
        context: m.Infra.ProjectRenderContext,
    ) -> p.Result[str]:
        """Render one scaffold entry's source bytes.

        Returns:
            The resulting ``p.Result[str]``.

        """
        project = workspace.project
        if project is None:
            return r[str].fail(
                f"scaffold workspace has no project metadata: {workspace.name}",
            )
        if entry.delegate != c.Infra.TemplateDelegate.MANIFEST:
            if entry.source is None:
                return r[str].fail(
                    f"render entry has no template source: {destination}",
                )
            return self._rendered_artifact_source(
                render_inputs,
                template_relpath=entry.source,
                destination=destination,
                failure_prefix=(
                    f"stage=templates "
                    f"repository={render_inputs.target.repository.name} "
                ),
                project_context=context,
            )
        manifest_path = Path(c.CONFIG_DIR_NAME) / c.Infra.WORKSPACE_MANIFEST_FILENAME
        if Path(destination) != manifest_path:
            return r[str].fail(
                f"manifest delegate has an invalid destination: {destination}",
            )
        manifest = m.Infra.WorkspaceManifestSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name=workspace.name,
            namespace_scan_dirs=workspace.namespace_scan_dirs,
            repository=workspace.repository,
            project=project,
            members=workspace.subprojects,
            external_dependency_paths=workspace.external_dependency_paths,
            integration=workspace.integration,
        )
        return u.Cli.yaml_roundtrip_dump_text(
            u.Cli.yaml_deep_to_commented(
                manifest.model_dump(
                    mode="json",
                    exclude_none=True,
                    exclude_computed_fields=True,
                ),
            ),
        )


__all__: list[str] = ["FlextInfraCodegenConformScaffoldPlan"]
