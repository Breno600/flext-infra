"""Conformance planning for existing repositories and governed artifacts.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import time
from collections.abc import MutableMapping
from pathlib import Path
from typing import Literal

from flext_infra import c, config, m, p, r, t, u
from flext_infra.codegen._conform.artifact_render import (
    FlextInfraCodegenConformArtifactRender,
)
from flext_infra.deps import FlextInfraPyprojectModernizer
from flext_infra.services import FlextInfraCodegenVscodeMixin
from flext_infra.workspace import FlextInfraWorkspaceEnvironmentContracts


class FlextInfraCodegenConformExistingPlan(FlextInfraCodegenConformArtifactRender):
    """Conformance planning for existing repositories and governed artifacts."""

    def _plan_existing_repository(
        self,
        *,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        contract: m.Infra.CodegenConformSurfaceContract,
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Conform every declared managed surface in an existing repository.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]``.

        """
        root = target.root
        repository = target.repository
        surface_plans = self._plan_existing_contract_surface(
            target,
            workspace,
            codegen,
            contract,
        )
        if surface_plans is not None:
            return surface_plans
        u.Cli.info(f"  stage=pyproject repository={repository.name}")
        pyproject = root / c.PYPROJECT_FILENAME
        if not pyproject.is_file():
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                f"existing repository has no pyproject.toml: {root}; "
                "scaffold templates are available only through codegen new",
            )
        identity = self._validated_existing_identity(target, workspace, codegen)
        if identity.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(identity)
        docs_config = (Path(c.Infra.DIR_DOCS) / c.Infra.DOCS_CONFIG_FILENAME).as_posix()
        if contract.destinations == frozenset({docs_config}):
            return self._plan_existing_docs_config(
                target,
                workspace,
                codegen,
                docs_config,
            )
        return self._plan_existing_managed(
            target,
            workspace,
            codegen,
            contract,
            identity.value,
        )

    def _validated_existing_identity(
        self,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
    ) -> p.Result[t.Pair[m.Infra.ProjectSpec, p.ProjectMetadata]]:
        """Resolve the project identity and prove it matches the live PEP 621.

        Existing checkouts declare no scaffold metadata: the tooling identity
        derives from live PEP 621 metadata (same rule as the render pass)
        instead of referencing an undefined name.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.ProjectSpec,
                p.ProjectMetadata]]``.

        """
        result_type = r[t.Pair[m.Infra.ProjectSpec, p.ProjectMetadata]]
        root = target.root
        repository = target.repository
        u.Cli.info(f"  stage=pyproject repository={repository.name}")
        metadata = u.Infra.read_project_metadata_result(root)
        if metadata.failure:
            return result_type.from_failure(metadata)
        project = workspace.project
        if project is None:
            derived = self._project_spec_from_existing(repository, root, codegen)
            if derived.failure:
                return result_type.from_failure(derived)
            project = derived.value
        dist = metadata.value.project.name
        if dist != repository.distribution:
            return result_type.fail(
                "PEP 621 project name does not match catalog distribution: "
                f"{dist} != {repository.distribution}",
            )
        return result_type.ok((project, metadata.value))

    def _plan_existing_contract_surface(
        self,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        contract: m.Infra.CodegenConformSurfaceContract,
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]] | None:
        """Plan recovery surfaces before consumers parse existing projections.

        Returns:
            The resulting plans for a single-artifact surface, or None when
            the contract does not select one.

        """
        if contract.destinations == frozenset({c.Infra.MISE_TOML_FILENAME}):
            context = m.Infra.ToolchainSpec(**{
                name: value
                for name, value in codegen.toolchain.model_dump().items()
                if name in m.Infra.ToolchainSpec.model_fields
            })
            planned = self._bootstrap_destination_plan(
                target,
                codegen,
                context,
                c.Infra.MISE_TOML_FILENAME,
            )
            if planned.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(planned)
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok((planned.value,))
        if contract.destinations == c.Infra.MAKEFILE_BOOTSTRAP_DESTINATIONS:
            return self._plan_existing_bootstrap(target, workspace, codegen)
        if contract.destinations == frozenset({c.PYPROJECT_FILENAME}):
            return self._plan_existing_pyproject_bootstrap(target.root)
        return None

    def _plan_existing_managed(
        self,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        contract: m.Infra.CodegenConformSurfaceContract,
        identity: t.Pair[m.Infra.ProjectSpec, p.ProjectMetadata],
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Plan the managed templates (and custom content) for an existing tree.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]``.

        """
        result_type = r[t.SequenceOf[m.Infra.CodegenFilePlan]]
        root = target.root
        repository = target.repository
        project, metadata = identity
        managed_started = time.monotonic()
        u.Cli.info(f"  stage=managed-artifacts repository={repository.name}")
        managed_artifacts = u.Infra.snapshot_committed_project_managed_artifacts(root)
        if managed_artifacts.failure:
            return result_type.from_failure(managed_artifacts)
        u.Cli.info(
            f"  stage=managed-artifacts repository={repository.name} "
            f"elapsed={time.monotonic() - managed_started:.2f}s",
        )
        tooling_started = time.monotonic()
        tooling_context = self._existing_tooling_context(
            target,
            project,
            metadata,
            codegen,
            managed_artifacts.value.resolution,
        )
        if tooling_context.failure:
            return result_type.from_failure(tooling_context)
        u.Cli.info(
            f"  stage=tooling-context repository={repository.name} "
            f"elapsed={time.monotonic() - tooling_started:.2f}s",
        )
        render_inputs = self.resolve_render_inputs(
            target=target,
            workspace=workspace,
            codegen=codegen,
            tooling_runtime=tooling_context.value,
            managed_artifacts=managed_artifacts.value,
        )
        managed_result = self._plan_existing_templates(
            render_inputs=render_inputs,
            contract=contract,
        )
        if managed_result.failure:
            return result_type.from_failure(managed_result)
        planned = list(managed_result.value)
        if contract.custom:
            custom_result = self._plan_existing_custom(
                root,
                codegen,
                profile=target.make_profile.value,
            )
            if custom_result.failure:
                return result_type.from_failure(custom_result)
            planned.extend(custom_result.value)
        return result_type.ok(tuple(planned))

    def _existing_tooling_context(
        self,
        target: m.Infra.RepositoryConformTarget,
        project: m.Infra.ProjectSpec,
        metadata: p.ProjectMetadata,
        codegen: m.Infra.CodegenConfigSpec,
        managed_resolution: m.Infra.ProjectManagedArtifactsResolution,
    ) -> p.Result[m.Infra.ToolingRuntimeContext]:
        """Resolve the modernizer tooling context for one existing repository.

        Returns:
            The resulting ``p.Result[m.Infra.ToolingRuntimeContext]``.

        """
        root = target.root
        repository = target.repository
        modernizer = FlextInfraPyprojectModernizer(
            repository_root=root,
            skip_check=True,
            managed_artifacts=managed_resolution,
        )
        return modernizer.resolve_tooling_context(
            m.Infra.ToolingContextRequest(
                project_name=repository.distribution,
                package_name=metadata.package_name,
                path=root / c.PYPROJECT_FILENAME,
                scaffold_project=codegen.scaffold.project,
                upstream=project.upstream,
                runtime_dependency_overlay=project.runtime_dependency_overlay,
                declared_project_dependencies=metadata.project.dependencies,
                topology=m.Infra.PyprojectDeclaredTopology(
                    root_modules=(
                        target.project.root_modules
                        if target.project is not None
                        else ()
                    ),
                    root_packages=(
                        target.project.root_packages
                        if target.project is not None
                        else ()
                    ),
                    repository_namespace_packages=(
                        target.project.repository_namespace_packages
                        if target.project is not None
                        else ()
                    ),
                    packaged_data_paths=(
                        target.project.packaged_data_paths
                        if target.project is not None
                        else ()
                    ),
                    packaged_data_excludes=(
                        target.project.packaged_data_excludes
                        if target.project is not None
                        else ()
                    ),
                    declared_python_dirs=tuple(
                        self._scaffold_python_dirs(
                            codegen.templates.entries,
                            target.make_profile,
                            package=repository.package,
                        ),
                    ),
                    analysis_exclusions=tuple(
                        path.as_posix() for path in target.external_dependency_paths
                    ),
                ),
            ),
        )

    def _plan_existing_pyproject_bootstrap(
        self,
        root: Path,
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Project owned policy before consumers require a valid physical TOML file.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]``.
        """
        result_type = r[t.SequenceOf[m.Infra.CodegenFilePlan]]
        live = u.Infra.live_pyproject_text(
            root / c.PYPROJECT_FILENAME,
            regenerate_managed_tools=True,
        )
        if live.failure:
            return result_type.from_failure(live)
        spec = u.Infra.pyproject_managed_file()
        if spec.failure:
            return result_type.from_failure(spec)
        modernizer = FlextInfraPyprojectModernizer(
            repository_root=root,
            skip_check=True,
        )
        conformed = modernizer.conform_source(
            live.value,
            path=root / c.PYPROJECT_FILENAME,
            format_source=False,
            topology=m.Infra.PyprojectDeclaredTopology(),
        )
        if conformed.failure:
            return result_type.from_failure(conformed)
        planned = self.file_plan(
            root,
            c.PYPROJECT_FILENAME,
            conformed.value,
            mode=spec.value.mode,
        )
        if planned.failure:
            return result_type.from_failure(planned)
        return result_type.ok((planned.value,))

    def _plan_existing_bootstrap(
        self,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Render the bootstrap Make surface before sibling checkouts exist.

        Every destination of the surface renders from the one Makefile spec:
        the lock publisher the bootstrap runs reads only its Mise contract.

        Returns:
            One file plan per bootstrap destination, in destination order.

        """
        context = self._makefile_render_spec(target, workspace, codegen)
        if context.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(context)
        plans: list[m.Infra.CodegenFilePlan] = []
        for destination in sorted(c.Infra.MAKEFILE_BOOTSTRAP_DESTINATIONS):
            planned = self._bootstrap_destination_plan(
                target,
                codegen,
                context.value,
                destination,
            )
            if planned.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(planned)
            plans.append(planned.value)
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(plans))

    def _bootstrap_destination_plan(
        self,
        target: m.Infra.RepositoryConformTarget,
        codegen: m.Infra.CodegenConfigSpec,
        context: p.Model,
        destination: str,
    ) -> p.Result[m.Infra.CodegenFilePlan]:
        """Render and plan exactly one bootstrap destination.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenFilePlan]``.

        """
        result_type = r[m.Infra.CodegenFilePlan]
        entries = tuple(
            entry
            for entry in codegen.templates.entries
            if entry.destination == destination
            and entry.delegate == c.Infra.TemplateDelegate.RENDER
            and target.make_profile in entry.profiles
        )
        if len(entries) != 1 or entries[0].source is None:
            return result_type.fail(
                f"{destination} requires exactly one render template for its profile",
            )
        managed = tuple(
            item for item in codegen.managed_files if item.path == Path(destination)
        )
        if len(managed) != 1:
            return result_type.fail(
                f"{destination} requires exactly one managed-file declaration",
            )
        template = u.Infra.codegen_templates_root(codegen) / entries[0].source
        sources: t.VariadicTuple[m.Cli.AtomicFileState] = ()
        if destination == c.Infra.MISE_TOML_FILENAME:
            owner_sources = u.Infra.snapshot_config_sources(
                config.ssot_config_dir().parent
            )
            if owner_sources.failure:
                return result_type.from_failure(owner_sources)
            authenticated = u.Cli.template_render_authenticated(template, context)
            rendered = authenticated.map(lambda value: value.rendered)
            if authenticated.success:
                sources = (*owner_sources.value, *authenticated.value.source_states)
        else:
            rendered = u.Cli.template_render(template, context)
        if rendered.failure:
            return result_type.from_failure(rendered)
        conflict_marker = u.Infra.first_merge_conflict_marker(rendered.value)
        if conflict_marker is not None:
            return result_type.fail(
                f"rendered {destination} contains a merge conflict marker: "
                f"{conflict_marker}",
            )
        if destination == c.Infra.MISE_TOML_FILENAME:
            composed = self._composed_mise_overlay(target.root, rendered.value, None)
            rendered = composed.map(lambda value: value.rendered)
            if composed.success:
                sources = (*sources, *composed.value.source_states)
        return (
            result_type.from_failure(rendered)
            if rendered.failure
            else self.file_plan(
                target.root,
                destination,
                rendered.value,
                mode=managed[0].mode,
                source_states=sources,
            )
        )

    def _plan_existing_docs_config(
        self,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        destination: str,
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Render the declared docs policy before consumers parse its projection.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]``.

        """
        entries = tuple(
            entry
            for entry in codegen.templates.entries
            if entry.destination == destination
            and entry.delegate == c.Infra.TemplateDelegate.RENDER
            and target.make_profile in entry.profiles
        )
        managed = tuple(
            item for item in codegen.managed_files if item.path == Path(destination)
        )
        if len(entries) != 1 or entries[0].source is None or len(managed) != 1:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                f"docs config requires one declared render template "
                f"and owner: {destination}",
            )
        template = u.Infra.codegen_templates_root(codegen) / entries[0].source
        source = u.Cli.atomic_read_binary_file_state(template, required=True)
        if source.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(source)
        rendered = u.Cli.template_render(template, workspace)
        if rendered.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(rendered)
        parsed = u.Cli.json_loads(rendered.value)
        if parsed.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(parsed)
        plan = self.file_plan(
            target.root,
            destination,
            rendered.value,
            mode=managed[0].mode,
            source_states=(source.value,),
        )
        if plan.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(plan)
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok((plan.value,))

    def _plan_existing_templates(
        self,
        *,
        render_inputs: m.Infra.CodegenRenderInputs,
        contract: m.Infra.CodegenConformSurfaceContract,
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Render the managed-file templates for an existing tree.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]``.

        """
        target = render_inputs.target
        workspace = render_inputs.workspace
        codegen = render_inputs.codegen
        root = target.root
        u.Cli.info(f"  stage=templates repository={target.repository.name}")
        profile = target.make_profile
        planned: list[m.Infra.CodegenFilePlan] = []
        # The pyproject plans first: renders that derive from its requirements
        # (the dependabot cooldown exclusion) read the planned bytes.
        for managed in sorted(
            codegen.managed_files,
            key=lambda item: item.path != Path(c.PYPROJECT_FILENAME),
        ):
            if self._managed_file_skipped(
                target,
                workspace,
                contract,
                profile,
                managed,
            ):
                continue
            resolved = self._managed_render_entry(codegen, workspace, root, managed)
            if resolved.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(resolved)
            (entry, path), present = resolved.value
            if not present or entry is None or path is None:
                continue
            if profile not in entry.profiles or (
                entry.requires_release_protocol and not target.publishes_release
            ):
                # Profile- and capability-excluded workflows must not keep firing.
                # Conform, rather than a user, retires the generated orphan.
                orphan = self._retired_workflow_orphan(render_inputs, managed, path)
                if orphan.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                        orphan,
                    )
                orphan_plan = orphan.value[0]
                if orphan.value[1] and orphan_plan is not None:
                    planned.append(
                        orphan_plan.model_copy(
                            update={"owner": managed.owner, "policy": managed.policy},
                        ),
                    )
                continue
            rendered = self._rendered_managed_plan(render_inputs, managed, entry, path)
            if rendered.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(rendered)
            render_inputs, planned_file = rendered.value
            planned.append(planned_file)
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(planned))

    @staticmethod
    def _managed_file_skipped(
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        contract: m.Infra.CodegenConformSurfaceContract,
        profile: c.Infra.MakeProfile,
        managed: m.Infra.ManagedFileSpec,
    ) -> bool:
        """Whether this managed file is out of scope for the current surface.

        Returns:
            True when the file is skipped before any template resolution.

        """
        if target.beads is None and managed.path.parts[:1] == (".beads",):
            return True
        if not target.ci_enabled and managed.path.parts[:2] == (
            ".github",
            "workflows",
        ):
            return True
        if (
            contract.destinations is not None
            and managed.path.as_posix() not in contract.destinations
        ):
            return True
        return managed.path == Path(c.PYPROJECT_FILENAME) and (
            not contract.pyproject
            or (workspace.project is None and profile is c.Infra.MakeProfile.WORKSPACE)
        )

    @staticmethod
    def _managed_render_entry(
        codegen: m.Infra.CodegenConfigSpec,
        workspace: m.Infra.WorkspaceSpec,
        root: Path,
        managed: m.Infra.ManagedFileSpec,
    ) -> p.Result[t.Pair[t.Pair[m.Infra.TemplateEntrySpec | None, Path | None], bool]]:
        """Resolve the single render template entry and its physical target path.

        Returns:
            The resulting ``p.Result[t.Pair[t.Pair[m.Infra.TemplateEntrySpec |
            None, Path | None], bool]]`` where the boolean marks entry
            presence (False: the managed file declares no render entry for
            this topology).

        """
        result_type = r[
            t.Pair[t.Pair[m.Infra.TemplateEntrySpec | None, Path | None], bool]
        ]
        entries = tuple(
            entry
            for entry in codegen.templates.entries
            if entry.destination == managed.path.as_posix()
            and entry.delegate == c.Infra.TemplateDelegate.RENDER
        )
        if not entries:
            return result_type.ok(((None, None), False))
        if len(entries) != 1:
            return result_type.fail(
                f"managed file requires exactly one render template: {managed.path}",
            )
        entry = entries[0]
        if entry.source is None:
            return result_type.fail(
                f"managed render entry has no template source: {managed.path}",
            )
        if entry.requires_beads and workspace.beads is None:
            return result_type.ok(((None, None), False))
        path = FlextInfraCodegenConformExistingPlan._managed_entry_path(root, entry)
        if path.failure:
            return result_type.from_failure(path)
        return result_type.ok(((entry, path.value), True))

    @staticmethod
    def _managed_entry_path(
        root: Path,
        entry: m.Infra.TemplateEntrySpec,
    ) -> p.Result[Path]:
        """Resolve and confine one managed destination inside the repository root.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        relative = Path(entry.destination)
        if relative.is_absolute() or ".." in relative.parts:
            return r[Path].fail(
                f"managed destination escapes repository root: {entry.destination}",
            )
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()):
            return r[Path].fail(
                f"managed destination escapes repository root: {entry.destination}",
            )
        return r[Path].ok(path)

    def _retired_workflow_orphan(
        self,
        render_inputs: m.Infra.CodegenRenderInputs,
        managed: m.Infra.ManagedFileSpec,
        path: Path,
    ) -> p.Result[t.Pair[m.Infra.CodegenFilePlan | None, bool]]:
        """Plan retirement of a profile-excluded generated workflow orphan.

        A managed destination does not establish authorship of its current
        bytes. Retire generated projections only; repository-owned workflows
        survive profile changes.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenFilePlan | None,
            bool]]`` where the boolean marks orphan presence (False: a
            repository-owned workflow survives).

        """
        result_type = r[t.Pair[m.Infra.CodegenFilePlan | None, bool]]
        if not (managed.path.parts[:2] == (".github", "workflows") and path.is_file()):
            return result_type.ok((None, False))
        # Keep the typed read result distinct from its string payload.
        orphan_read = u.Cli.files_read_text(path)
        if orphan_read.failure:
            return result_type.from_failure(orphan_read)
        if not any(
            marker in orphan_read.value for marker in c.Infra.TEMPLATE_GENERATED_MARKERS
        ):
            return result_type.ok((None, False))
        orphan = self._absent_file_plan(render_inputs.target.root, path)
        if orphan.failure:
            return result_type.from_failure(orphan)
        return result_type.ok((orphan.value, True))

    def _rendered_managed_plan(
        self,
        render_inputs: m.Infra.CodegenRenderInputs,
        managed: m.Infra.ManagedFileSpec,
        entry: m.Infra.TemplateEntrySpec,
        path: Path,
    ) -> p.Result[t.Pair[m.Infra.CodegenRenderInputs, m.Infra.CodegenFilePlan]]:
        """Render, compose, record, and plan one managed artifact.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenRenderInputs,
                m.Infra.CodegenFilePlan]]`` where the inputs carry the planned
            pyproject when this artifact is the pyproject itself.

        """
        result_type = r[t.Pair[m.Infra.CodegenRenderInputs, m.Infra.CodegenFilePlan]]
        root = render_inputs.target.root
        rendered = (
            r[str].fail(
                f"managed render entry has no template source: {entry.destination}",
            )
            if entry.source is None
            else self._rendered_artifact_source(
                render_inputs,
                template_relpath=entry.source,
                destination=entry.destination,
                failure_prefix="",
                project_context=None,
            )
        )
        if rendered.failure:
            return result_type.from_failure(rendered)
        composed = self.compose_project_artifact(
            root,
            entry.destination,
            rendered.value,
            render_inputs=render_inputs,
        )
        if composed.failure:
            return result_type.from_failure(composed)
        rendered_content = composed.value.rendered
        if entry.destination == c.PYPROJECT_FILENAME:
            recorded = self.with_planned_pyproject(render_inputs, rendered_content)
            if recorded.failure:
                return result_type.from_failure(recorded)
            render_inputs = recorded.value
        conflict_marker = u.Infra.first_merge_conflict_marker(rendered_content)
        if conflict_marker is not None:
            return result_type.fail(
                "rendered template contains a merge conflict marker: "
                f"source={entry.source}; target={path}; root={root}; "
                f"marker={conflict_marker}",
            )
        planned = self.file_plan(
            root,
            entry.destination,
            rendered_content,
            mode=managed.mode,
            source_states=composed.value.source_states,
        )
        if planned.failure:
            return result_type.from_failure(planned)
        return result_type.ok((render_inputs, planned.value))

    def _plan_existing_custom(
        self,
        root: Path,
        config: m.Infra.CodegenConfigSpec,
        *,
        profile: str | None = None,
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Validate custom Make content and plan utility, protocol and model facades.

        Existing handwritten Make content is validated against the selected
        profile policy. A discovered package layout also contributes ``u``,
        ``p`` and ``m`` facade plans from consumer-driven owner projection.
        This method returns file plans; it does not publish their contents.

        Returns:
            The custom Make and facade plans, or a typed validation failure.

        """
        policy = config.make.custom_handler_policies.get(
            profile or "",
            config.make.custom_handler_policy,
        )
        plans: list[m.Infra.CodegenFilePlan] = []
        make_plan = self._validated_custom_make_plan(root, policy)
        if make_plan.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(make_plan)
        make_plan_value, make_plan_present = make_plan.value
        if make_plan_present and make_plan_value is not None:
            plans.append(make_plan_value)
        layout = u.Infra.layout(root)
        if layout is not None and layout.class_stem:
            families: t.VariadicTuple[Literal["u", "p", "m"]] = ("u", "p", "m")
            for family in families:
                facade_plan = self._utility_facade_plan(root, layout, family)
                if facade_plan.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                        facade_plan,
                    )
                facade_plan_value, facade_plan_present = facade_plan.value
                if facade_plan_present and facade_plan_value is not None:
                    plans.append(facade_plan_value)
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(plans))

    def _validated_custom_make_plan(
        self,
        root: Path,
        policy: m.Infra.CustomHandlerPolicy,
    ) -> p.Result[t.Pair[m.Infra.CodegenFilePlan | None, bool]]:
        """Validate and plan the existing custom Make content under its policy.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenFilePlan | None,
            bool]]`` where the boolean marks plan presence (False: an absent
            custom Make file).

        """
        result_type = r[t.Pair[m.Infra.CodegenFilePlan | None, bool]]
        path = root / policy.filename
        if path.exists() and not path.is_file():
            return result_type.fail(
                f"custom Make destination is not a regular file: {path}",
            )
        if not path.is_file():
            return result_type.ok((None, False))
        read = u.Cli.files_read_text(path)
        if read.failure:
            return result_type.from_failure(read)
        validation = self.validate_custom_make(read.value, policy)
        if validation.failure:
            return result_type.from_failure(validation)
        planned = self.file_plan(root, policy.filename, read.value)
        if planned.failure:
            return result_type.from_failure(planned)
        return result_type.ok((planned.value, True))

    def _utility_facade_plan(
        self,
        root: Path,
        layout: m.Infra.RopeProjectLayout,
        family: Literal["u", "p", "m"],
    ) -> p.Result[t.Pair[m.Infra.CodegenFilePlan | None, bool]]:
        """Plan one projected facade for the discovered package layout.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenFilePlan | None,
            bool]]`` where the boolean marks plan presence (False: a family
            with no rendered facade).

        Raises:
            ValueError: If a rendered facade has no declaring package module.

        """
        result_type = r[t.Pair[m.Infra.CodegenFilePlan | None, bool]]
        rendered = u.Infra.render_utility_facade(
            layout.package_dir,
            family=family,
        )
        if rendered is None:
            return result_type.ok((None, False))
        facade_path = u.Infra.facade_module_path(layout.package_dir, family)
        if facade_path is None:
            msg = f"rendered {family} facade has no declaring module"
            raise ValueError(msg)
        relative = facade_path.relative_to(root)
        utility_plan = self.file_plan(root, relative.as_posix(), rendered)
        if utility_plan.failure:
            return result_type.from_failure(utility_plan)
        return result_type.ok((utility_plan.value, True))

    @classmethod
    def _complete_governed_plans(
        cls,
        target: m.Infra.RepositoryConformTarget,
        planned: t.SequenceOf[m.Infra.CodegenFilePlan],
        codegen: m.Infra.CodegenConfigSpec,
        contract: m.Infra.CodegenConformSurfaceContract,
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Attach ownership metadata and represent every governed root artifact.

        Only the ``ALL`` surface completes the full governed set; the
        pyproject-scoped surfaces (``DEPENDENCIES``/``PYPROJECT``) keep the plan
        restricted to what their own planners already produced.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]``.

        """
        root = target.root
        governed_by_path = {
            item.path: item
            for item in codegen.managed_files
            if target.beads is not None or item.path.parts[:1] != (".beads",)
        }
        bound = cls._bind_governed_ownership(root, planned, governed_by_path)
        if bound.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(bound)
        completed, represented = bound.value
        if not contract.complete_governed:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(completed))
        represented_set = cls._represent_ungoverned_artifacts(
            target,
            codegen,
            governed_by_path,
            represented,
            completed,
        )
        if represented_set.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                represented_set,
            )
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(completed))

    @staticmethod
    def _bind_governed_ownership(
        root: Path,
        planned: t.SequenceOf[m.Infra.CodegenFilePlan],
        governed_by_path: t.MappingKV[Path, m.Infra.ManagedFileSpec],
    ) -> p.Result[t.Pair[list[m.Infra.CodegenFilePlan], set[Path]]]:
        """Stamp governed ownership onto the planned files, first plan wins.

        Returns:
            The resulting ``p.Result[t.Pair[list[m.Infra.CodegenFilePlan],
                set[Path]]]`` with the bound plans and the represented paths.

        """
        completed: list[m.Infra.CodegenFilePlan] = []
        represented: set[Path] = set()
        represented_indexes: MutableMapping[Path, int] = {}
        for file in planned:
            relative = file.path.relative_to(root)
            governed = governed_by_path.get(relative)
            if governed is None:
                completed.append(file)
                continue
            represented.add(relative)
            governed_file = file.model_copy(
                update={
                    "owner": governed.owner,
                    "policy": governed.policy,
                    "desired_mode": (
                        governed.mode if file.desired_content is not None else None
                    ),
                },
            )
            if relative in represented_indexes:
                completed[represented_indexes[relative]] = governed_file
            else:
                represented_indexes[relative] = len(completed)
                completed.append(governed_file)
        return r[t.Pair[list[m.Infra.CodegenFilePlan], set[Path]]].ok(
            (completed, represented),
        )

    @classmethod
    def _represent_ungoverned_artifacts(
        cls,
        target: m.Infra.RepositoryConformTarget,
        codegen: m.Infra.CodegenConfigSpec,
        governed_by_path: t.MappingKV[Path, m.Infra.ManagedFileSpec],
        represented: set[Path],
        completed: list[m.Infra.CodegenFilePlan],
    ) -> p.Result[bool]:
        """Append a plan for every governed artifact no planner represented.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        root = target.root
        profile = target.make_profile
        for relative, governed in governed_by_path.items():
            if relative in represented:
                continue
            path = root / relative
            if path.exists() and not path.is_file():
                return r[bool].fail(
                    f"governed artifact is not a regular file: {path}",
                )
            if not cls._governed_entry_reachable(codegen, profile, relative):
                continue
            if not path.exists():
                continue
            current = cls._governed_current_text(path)
            if current.failure:
                return r[bool].from_failure(current)
            decided = cls._decide_governed_plan(
                root,
                path,
                relative,
                governed,
                current.value,
            )
            if decided.failure:
                return r[bool].from_failure(decided)
            decided_value, decided_present = decided.value
            if decided_present and decided_value is not None:
                completed.append(decided_value)
        return r[bool].ok(value=True)

    @classmethod
    def _governed_entry_reachable(
        cls,
        codegen: m.Infra.CodegenConfigSpec,
        profile: c.Infra.MakeProfile,
        relative: Path,
    ) -> bool:
        """Whether any template entry for this destination admits the profile.

        Returns:
            True when no entry restricts the destination or the profile is
            among the admitted ones.

        """
        entry_profiles = tuple(
            entry.profiles
            for entry in codegen.templates.entries
            if entry.destination == relative.as_posix()
        )
        if not entry_profiles:
            return True
        allowed = {item for profiles in entry_profiles for item in profiles}
        return profile in allowed

    @staticmethod
    def _governed_current_text(path: Path) -> p.Result[str]:
        """Read the current bytes of an existing governed artifact.

        Returns:
            The resulting ``p.Result[str]``, empty for a non-file path.

        """
        if not path.is_file():
            return r[str].ok("")
        read = u.Cli.files_read_text(path)
        if read.failure:
            return r[str].from_failure(read)
        return r[str].ok(read.value)

    @classmethod
    def _decide_governed_plan(
        cls,
        root: Path,
        path: Path,
        relative: Path,
        governed: m.Infra.ManagedFileSpec,
        current: str,
    ) -> p.Result[t.Pair[m.Infra.CodegenFilePlan | None, bool]]:
        """Decide the representing plan: owner merge first, plain content next.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenFilePlan | None,
            bool]]`` with its presence flag.

        """
        special = cls._special_governed_plan(root, path, relative, governed, current)
        if special.failure:
            return special
        if special.value[1]:
            return special
        result_type = r[t.Pair[m.Infra.CodegenFilePlan | None, bool]]
        current_plan = cls.file_plan(
            root,
            relative.as_posix(),
            current,
            mode=governed.mode,
        )
        if current_plan.failure:
            return result_type.from_failure(current_plan)
        return r[t.Pair[m.Infra.CodegenFilePlan, bool]].ok(
            (
                current_plan.value.model_copy(
                    update={"owner": governed.owner, "policy": governed.policy},
                ),
                True,
            ),
        )

    @classmethod
    def _special_governed_plan(
        cls,
        root: Path,
        path: Path,
        relative: Path,
        governed: m.Infra.ManagedFileSpec,
        current: str,
    ) -> p.Result[t.Pair[m.Infra.CodegenFilePlan | None, bool]]:
        """Plan owner-specific merge behavior for special governed artifacts.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenFilePlan | None,
            bool]]`` where the boolean marks plan presence (False falls
            through to the plain current-content plan).

        """
        vscode_merge = governed.policy == "merge" and (
            governed.owner == c.Infra.CODEGEN_OWNER_VSCODE
        )
        if vscode_merge:
            # Owner-merge dispatch: owners with a canonical document merge
            # (vscode settings today) produce their rendered content here.
            return cls._vscode_merged_plan(root, relative, governed, current)
        if governed.policy == "merge" and relative.as_posix() == (
            c.Infra.ENVRC_LOCAL_RELPATH
        ):
            # Local overrides never carry generated content: the merge strips
            # stale generated sections and deletes the file when nothing
            # custom remains, so `.envrc` stays the single beads owner.
            return cls._envrc_local_plan(root, path, relative, governed, current)
        return r[t.Pair[m.Infra.CodegenFilePlan, bool]].ok((None, False))

    @classmethod
    def _vscode_merged_plan(
        cls,
        root: Path,
        relative: Path,
        governed: m.Infra.ManagedFileSpec,
        current: str,
    ) -> p.Result[t.Pair[m.Infra.CodegenFilePlan | None, bool]]:
        """Render the canonical vscode settings merge when it diverges.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenFilePlan | None,
            bool]]`` with its presence flag.

        """
        result_type = r[t.Pair[m.Infra.CodegenFilePlan | None, bool]]
        merged = FlextInfraCodegenVscodeMixin.render_vscode_settings(root)
        if merged.failure:
            return result_type.from_failure(merged)
        if merged.value == current:
            return result_type.ok((None, False))
        merged_plan = cls.file_plan(
            root,
            relative.as_posix(),
            merged.value,
            mode=governed.mode,
        )
        if merged_plan.failure:
            return result_type.from_failure(merged_plan)
        return result_type.ok(
            (
                merged_plan.value.model_copy(
                    update={"owner": governed.owner, "policy": governed.policy},
                ),
                True,
            ),
        )

    @classmethod
    def _envrc_local_plan(
        cls,
        root: Path,
        path: Path,
        relative: Path,
        governed: m.Infra.ManagedFileSpec,
        current: str,
    ) -> p.Result[t.Pair[m.Infra.CodegenFilePlan | None, bool]]:
        """Normalize the local envrc overrides or plan the file's deletion.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenFilePlan | None,
            bool]]`` with its presence flag.

        """
        result_type = r[t.Pair[m.Infra.CodegenFilePlan | None, bool]]
        normalized = FlextInfraWorkspaceEnvironmentContracts.envrc_local_normalized(
            current,
        )
        if normalized == current:
            current_plan = cls.file_plan(
                root,
                relative.as_posix(),
                current,
                mode=governed.mode,
            )
            if current_plan.failure:
                return result_type.from_failure(current_plan)
            return result_type.ok(
                (
                    current_plan.value.model_copy(
                        update={"owner": governed.owner, "policy": governed.policy},
                    ),
                    True,
                ),
            )
        if not normalized:
            before = u.Cli.atomic_read_binary_file_state(path, required=False)
            if before.failure:
                return result_type.from_failure(before)
            return result_type.ok(
                (
                    m.Infra.CodegenFilePlan(
                        project=root,
                        path=path,
                        before=before.value,
                        desired_content=None,
                        desired_mode=None,
                        owner=governed.owner,
                        policy=governed.policy,
                    ),
                    True,
                ),
            )
        merged_plan = cls.file_plan(
            root,
            relative.as_posix(),
            normalized,
            mode=governed.mode,
        )
        if merged_plan.failure:
            return result_type.from_failure(merged_plan)
        return result_type.ok(
            (
                merged_plan.value.model_copy(
                    update={"owner": governed.owner, "policy": governed.policy},
                ),
                True,
            ),
        )


__all__: list[str] = ["FlextInfraCodegenConformExistingPlan"]
