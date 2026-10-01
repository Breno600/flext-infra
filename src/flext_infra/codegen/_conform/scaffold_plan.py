"""Complete scaffold planning for ``codegen new``."""

from __future__ import annotations

from pathlib import Path

from flext_core import r
from flext_infra import c, m, p, t, u
from flext_infra.codegen._conform.existing_plan import (
    FlextInfraCodegenConformExistingPlan,
)
from flext_infra.deps import FlextInfraPyprojectModernizer


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
        """Render the complete scaffold for ``codegen new`` only."""
        project = workspace.project
        if project is None:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                f"scaffold workspace has no project metadata: {workspace.name}",
            )
        root = target.root
        repository = target.repository
        profile = target.make_profile
        pyproject = root / c.PYPROJECT_FILENAME
        managed_artifacts = u.Infra.empty_snapshot()
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
            managed_artifacts=managed_artifacts.resolution,
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
            project_name=repository.distribution,
            package_name=project.package_name,
            path=pyproject,
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
        )
        if tooling_result.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(tooling_result)
        render_inputs = self.resolve_render_inputs(
            target=target,
            workspace=workspace,
            codegen=codegen,
            tooling_runtime=tooling_result.value,
            managed_artifacts=managed_artifacts,
        )
        context_result = self._project_render_context(
            render_inputs,
            planned_data_files=tuple(
                destination for _, destination in scaffold_entries
            ),
        )
        if context_result.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(context_result)
        context = context_result.value
        planned: list[m.Infra.CodegenFilePlan] = []
        templates_root = u.Infra.codegen_templates_root(codegen)
        seen_destinations: set[str] = set()
        # One selection and one formatted path govern validation and planning.
        for entry, destination in scaffold_entries:
            if entry.delegate == c.Infra.TemplateDelegate.RENDER:
                if entry.source is None:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                        f"render entry has no template source: {destination}",
                    )
                source = (templates_root / entry.source).resolve()
                if not source.is_relative_to(templates_root) or not source.is_file():
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                        f"template source is missing or escapes its root: {entry.source}",
                    )
            relative = Path(destination)
            if relative.is_absolute() or ".." in relative.parts:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"template destination escapes repository root: {destination}",
                )
            if destination in seen_destinations:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"duplicate template destination: {destination}",
                )
            seen_destinations.add(destination)
            path = root / relative
            if path.exists() and not path.is_file():
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"template destination is not a regular file: {path}",
                )
            for parent in path.parents:
                if parent == root:
                    break
                if parent.exists() and not parent.is_dir():
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                        f"template destination parent is not a directory: {parent}",
                    )
        # The pyproject plans first: renders that derive from its requirements
        # (the dependabot cooldown exclusion) read the planned bytes.
        for entry, destination in sorted(
            scaffold_entries,
            key=lambda item: item[1] != c.PYPROJECT_FILENAME,
        ):
            if entry.delegate == c.Infra.TemplateDelegate.MANIFEST:
                manifest_path = (
                    Path(c.CONFIG_DIR_NAME) / c.Infra.WORKSPACE_MANIFEST_FILENAME
                )
                if Path(destination) != manifest_path:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
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
                rendered = u.Cli.yaml_roundtrip_dump_text(
                    manifest.model_dump(
                        mode="json",
                        exclude_none=True,
                        exclude_computed_fields=True,
                    ),
                )
            else:
                if entry.source is None:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                        f"render entry has no template source: {destination}",
                    )
                rendered = self._rendered_artifact_source(
                    render_inputs,
                    template_relpath=entry.source,
                    destination=destination,
                    failure_prefix=f"stage=templates repository={repository.name} ",
                    project_context=context,
                )
            if rendered.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(rendered)
            rendered_content = self.compose_project_artifact(
                root,
                destination,
                rendered.value,
                render_inputs=render_inputs,
            )
            if rendered_content.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                    rendered_content,
                )
            if destination == c.PYPROJECT_FILENAME:
                recorded = self.with_planned_pyproject(
                    render_inputs,
                    rendered_content.value.rendered,
                )
                if recorded.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                        recorded,
                    )
                render_inputs = recorded.value
            file_plan = self.file_plan(
                root,
                destination,
                rendered_content.value.rendered,
                source_states=rendered_content.value.source_states,
            )
            if file_plan.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(file_plan)
            planned.append(file_plan.value)
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(planned))


__all__: list[str] = ["FlextInfraCodegenConformScaffoldPlan"]
