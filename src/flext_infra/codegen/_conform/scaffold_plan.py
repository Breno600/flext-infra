"""Complete scaffold planning for ``codegen new``."""

from __future__ import annotations

from pathlib import Path

from flext_core import r

from ... import c, m, p, t, u
from ...deps import FlextInfraPyprojectModernizer
from .existing_plan import FlextInfraCodegenConformExistingPlan


class FlextInfraCodegenConformScaffoldPlan(FlextInfraCodegenConformExistingPlan):
    """Complete scaffold planning for ``codegen new``."""

    def _plan_scaffold_repository(
        self,
        *,
        root: Path,
        repository: m.Infra.RepositoryRef,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        contract: m.Infra.CodegenConformSurfaceContract,
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Render the complete scaffold for ``codegen new`` only."""
        project = workspace.project
        if project is None:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                f"scaffold workspace has no project metadata: {workspace.name}"
            )
        profile = target.make_profile
        pyproject = root / c.PYPROJECT_FILENAME
        managed_artifacts = u.Infra.empty_snapshot()
        # New and existing repositories share the exact same
        # root-scoped modernizer pipeline, so first generation is a fixed point.
        # A declared subproject consumes the workspace root
        # tooling profile even before the atomic scaffold creates files on disk.
        modernizer = FlextInfraPyprojectModernizer(
            repository_root=target.root,
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
        # Why (flext-6itas.4): a scaffold's declared roots are the complete
        # future topology only for a subproject/standalone target; a workspace
        # root aggregates subproject trees it has not declared here.
        tooling_result = modernizer.resolve_tooling_context(
            project_name=repository.distribution,
            package_name=project.package_name,
            path=pyproject,
            root_modules=project.root_modules,
            root_packages=project.root_packages,
            declared_python_dirs=self._scaffold_python_dirs(
                codegen.templates.entries, profile
            ),
            declared_python_dirs_are_complete=(
                profile is not c.Infra.MakeProfile.WORKSPACE
            ),
            analysis_exclusions=analysis_exclusions,
        )
        if tooling_result.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(tooling_result)
        context_result = self._project_render_context(
            repository,
            target,
            workspace,
            codegen,
            tooling_runtime=tooling_result.value,
            repository_root=pyproject.parent,
            managed_artifacts=managed_artifacts.resolution,
            use_committed_artifacts=False,
        )
        if context_result.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(context_result)
        context = context_result.value
        planned: list[m.Infra.CodegenFilePlan] = []
        templates_root = u.Infra.codegen_templates_root(codegen)
        seen_destinations: set[str] = set()
        # One selection and one formatted path govern validation and planning.
        scaffold_entries = tuple(
            (
                entry,
                entry.destination.format(
                    package_name=context.package_name, ns=context.ns
                ),
            )
            for entry in codegen.templates.entries
            if profile in entry.profiles
            and (not entry.requires_release_protocol or target.publishes_release)
            and (
                contract.destinations is None
                or entry.destination in contract.destinations
            )
        )
        for entry, destination in scaffold_entries:
            source = (templates_root / entry.source).resolve()
            if not source.is_relative_to(templates_root) or not source.is_file():
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"template source is missing or escapes its root: {entry.source}"
                )
            relative = Path(destination)
            if relative.is_absolute() or ".." in relative.parts:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"template destination escapes repository root: {destination}"
                )
            if destination in seen_destinations:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"duplicate template destination: {destination}"
                )
            seen_destinations.add(destination)
            path = root / relative
            if path.exists() and not path.is_file():
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"template destination is not a regular file: {path}"
                )
            for parent in path.parents:
                if parent == root:
                    break
                if parent.exists() and not parent.is_dir():
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                        f"template destination parent is not a directory: {parent}"
                    )
        for entry, destination in scaffold_entries:
            if entry.delegate != "render":
                continue
            if destination == c.PYPROJECT_FILENAME and not contract.pyproject:
                continue
            if not contract.delegates and destination != c.PYPROJECT_FILENAME:
                continue
            rendered = self._rendered_artifact_source(
                templates_root=templates_root,
                template_relpath=entry.source,
                failure_prefix=f"stage=templates repository={repository.name} ",
                dist=context.dist,
                repository=repository,
                repository_root=root,
                target=target,
                workspace=workspace,
                codegen=codegen,
                destination=destination,
                tooling_runtime=tooling_result.value,
                project_context=context,
                managed_artifacts=managed_artifacts.resolution,
            )
            if rendered.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(rendered)
            rendered_content = self.compose_project_artifact(
                root,
                destination,
                rendered.value,
                managed_artifacts=managed_artifacts,
                workspace=workspace,
                codegen=codegen,
                repository=repository,
                target=target,
            )
            if rendered_content.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                    rendered_content
                )
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
