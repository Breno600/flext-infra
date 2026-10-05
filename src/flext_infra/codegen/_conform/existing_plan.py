"""Conformance planning for existing repositories and governed artifacts.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import time
from collections.abc import MutableMapping
from pathlib import Path
from typing import Literal

from flext_core import r
from flext_infra import c, m, p, t, u
from flext_infra.codegen._conform.artifact_render import (
    FlextInfraCodegenConformArtifactRender,
)
from flext_infra.codegen._mise_artifacts_cold_start import FlextInfraMiseColdStart
from flext_infra.deps import FlextInfraPyprojectModernizer
from flext_infra.services.codegen import FlextInfraCodegen
from flext_infra.workspace.environment_contracts import (
    FlextInfraWorkspaceEnvironmentContracts,
)


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
        if contract.destinations == frozenset(c.Infra.ARTIFACT_NAMES):
            return FlextInfraMiseColdStart.candidate_plans(root)
        stage_started = time.monotonic()
        u.Cli.info(f"  stage=pyproject repository={repository.name}")
        pyproject = root / c.PYPROJECT_FILENAME
        if not pyproject.is_file():
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                f"existing repository has no pyproject.toml: {root}; "
                "scaffold templates are available only through codegen new",
            )
        metadata = u.Infra.read_project_metadata_result(root)
        if metadata.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(metadata)
        project = workspace.project
        if project is None:
            # Existing checkouts declare no scaffold metadata: derive the
            # tooling identity from live PEP 621 metadata (same rule as the
            # render pass) instead of referencing an undefined name.
            derived = self._project_spec_from_existing(
                repository,
                root,
                codegen,
            )
            if derived.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                    derived,
                )
            project = derived.value
        dist = metadata.value.project.name
        if dist != repository.distribution:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                "PEP 621 project name does not match catalog distribution: "
                f"{dist} != {repository.distribution}",
            )
        if contract.destinations == c.Infra.MAKEFILE_BOOTSTRAP_DESTINATIONS:
            return self._plan_existing_bootstrap(target, workspace, codegen)
        docs_config = (Path(c.Infra.DIR_DOCS) / c.Infra.DOCS_CONFIG_FILENAME).as_posix()
        if contract.destinations == frozenset({docs_config}):
            return self._plan_existing_docs_config(
                target,
                workspace,
                codegen,
                docs_config,
            )
        managed_artifacts = u.Infra.snapshot_committed_project_managed_artifacts(root)
        if managed_artifacts.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                managed_artifacts,
            )
        u.Cli.info(
            f"  stage=managed-artifacts repository={repository.name} "
            f"elapsed={time.monotonic() - stage_started:.2f}s",
        )
        stage_started = time.monotonic()
        modernizer = FlextInfraPyprojectModernizer(
            repository_root=root,
            skip_check=True,
            managed_artifacts=managed_artifacts.value.resolution,
        )
        tooling_context = modernizer.resolve_tooling_context(
            project_name=repository.distribution,
            package_name=metadata.value.package_name,
            path=pyproject,
            scaffold_project=codegen.scaffold.project,
            upstream=project.upstream,
            runtime_dependency_overlay=project.runtime_dependency_overlay,
            declared_project_dependencies=metadata.value.project.dependencies,
            topology=m.Infra.PyprojectDeclaredTopology(
                root_modules=(
                    target.project.root_modules if target.project is not None else ()
                ),
                root_packages=(
                    target.project.root_packages if target.project is not None else ()
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
        )
        if tooling_context.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                tooling_context,
            )
        u.Cli.info(
            f"  stage=tooling-context repository={repository.name} "
            f"elapsed={time.monotonic() - stage_started:.2f}s",
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
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(managed_result)
        planned = list(managed_result.value)
        if contract.custom:
            custom_result = self._plan_existing_custom(
                root,
                codegen,
                profile=target.make_profile.value,
            )
            if custom_result.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                    custom_result,
                )
            planned.extend(custom_result.value)
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(planned))

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
            entries = tuple(
                entry
                for entry in codegen.templates.entries
                if entry.destination == destination
                and entry.delegate == c.Infra.TemplateDelegate.RENDER
                and target.make_profile in entry.profiles
            )
            if len(entries) != 1 or entries[0].source is None:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"{destination} requires exactly one render template "
                    "for its profile",
                )
            managed = tuple(
                item for item in codegen.managed_files if item.path == Path(destination)
            )
            if len(managed) != 1:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"{destination} requires exactly one managed-file declaration",
                )
            rendered = u.Cli.template_render(
                u.Infra.codegen_templates_root(codegen) / entries[0].source,
                context.value,
            )
            if rendered.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                    rendered,
                )
            conflict_marker = u.Infra.first_merge_conflict_marker(rendered.value)
            if conflict_marker is not None:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"rendered {destination} contains a merge conflict marker: "
                    f"{conflict_marker}",
                )
            plan = self.file_plan(
                target.root,
                destination,
                rendered.value,
                mode=managed[0].mode,
            )
            if plan.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(plan)
            plans.append(plan.value)
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(plans))

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
            if target.beads is None and managed.path.parts[:1] == (".beads",):
                continue
            if not target.ci_enabled and managed.path.parts[:2] == (
                ".github",
                "workflows",
            ):
                continue
            if (
                contract.destinations is not None
                and managed.path.as_posix() not in contract.destinations
            ):
                continue
            pyproject_skipped = managed.path == Path(c.PYPROJECT_FILENAME) and (
                not contract.pyproject
                or (
                    workspace.project is None
                    and profile is c.Infra.MakeProfile.WORKSPACE
                )
            )
            if pyproject_skipped:
                continue
            entries = tuple(
                entry
                for entry in codegen.templates.entries
                if entry.destination == managed.path.as_posix()
                and entry.delegate == c.Infra.TemplateDelegate.RENDER
            )
            if not entries:
                continue
            if len(entries) != 1:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"managed file requires exactly one render template: "
                    f"{managed.path}",
                )
            entry = entries[0]
            if entry.source is None:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"managed render entry has no template source: {managed.path}",
                )
            if entry.requires_beads and workspace.beads is None:
                continue
            relative = Path(entry.destination)
            if relative.is_absolute() or ".." in relative.parts:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"managed destination escapes repository root: {entry.destination}",
                )
            path = (root / relative).resolve()
            if not path.is_relative_to(root.resolve()):
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"managed destination escapes repository root: {entry.destination}",
                )
            if profile not in entry.profiles or (
                entry.requires_release_protocol and not target.publishes_release
            ):
                # Profile- and capability-excluded workflows must not keep firing.
                # Conform, rather than a user, retires the generated orphan.
                if (
                    managed.path.parts[:2] == (".github", "workflows")
                    and path.is_file()
                ):
                    # Keep the typed read result distinct from its string payload.
                    orphan_read = u.Cli.files_read_text(path)
                    if orphan_read.failure:
                        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                            orphan_read,
                        )
                    # A managed destination does not establish authorship of
                    # its current bytes. Retire generated projections only;
                    # repository-owned workflows survive profile changes.
                    if not any(
                        marker in orphan_read.value
                        for marker in c.Infra.TEMPLATE_GENERATED_MARKERS
                    ):
                        continue
                    absent_plan = self._absent_file_plan(root, path)
                    if absent_plan.failure:
                        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                            absent_plan,
                        )
                    planned.append(
                        absent_plan.value.model_copy(
                            update={"owner": managed.owner, "policy": managed.policy},
                        ),
                    )
                continue
            rendered = self._rendered_artifact_source(
                render_inputs,
                template_relpath=entry.source,
                destination=entry.destination,
                failure_prefix="",
                project_context=None,
            )
            if rendered.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(rendered)
            composed = self.compose_project_artifact(
                root,
                entry.destination,
                rendered.value,
                render_inputs=render_inputs,
            )
            if composed.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(composed)
            rendered_content = composed.value.rendered
            if entry.destination == c.PYPROJECT_FILENAME:
                recorded = self.with_planned_pyproject(render_inputs, rendered_content)
                if recorded.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                        recorded,
                    )
                render_inputs = recorded.value
            conflict_marker = u.Infra.first_merge_conflict_marker(rendered_content)
            if conflict_marker is not None:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    "rendered template contains a merge conflict marker: "
                    f"source={entry.source}; target={path}; root={root}; "
                    f"marker={conflict_marker}",
                )
            file_plan = self.file_plan(
                root,
                entry.destination,
                rendered_content,
                mode=managed.mode,
                source_states=composed.value.source_states,
            )
            if file_plan.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(file_plan)
            planned.append(file_plan.value)
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(planned))

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

        Raises:
            ValueError: If facade rendering fails or a rendered facade has no
                declaring package module.

        """
        policy = config.make.custom_handler_policies.get(
            profile or "",
            config.make.custom_handler_policy,
        )
        path = root / policy.filename
        if path.exists() and not path.is_file():
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                f"custom Make destination is not a regular file: {path}",
            )
        plans: list[m.Infra.CodegenFilePlan] = []
        if path.is_file():
            read = u.Cli.files_read_text(path)
            if read.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(read)
            validation = self.validate_custom_make(read.value, policy)
            if validation.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(validation)
            planned = self.file_plan(root, policy.filename, read.value)
            if planned.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(planned)
            plans.append(planned.value)
        layout = u.Infra.layout(root)
        if layout is not None and layout.class_stem:
            families: t.VariadicTuple[Literal["u", "p", "m"]] = ("u", "p", "m")
            for family in families:
                rendered = u.Infra.render_utility_facade(
                    layout.package_dir,
                    family=family,
                )
                if rendered is None:
                    continue
                facade_path = u.Infra.facade_module_path(layout.package_dir, family)
                if facade_path is None:
                    msg = f"rendered {family} facade has no declaring module"
                    raise ValueError(msg)
                relative = facade_path.relative_to(root)
                utility_plan = self.file_plan(root, relative.as_posix(), rendered)
                if utility_plan.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                        utility_plan,
                    )
                plans.append(utility_plan.value)
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(plans))

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
        profile = target.make_profile
        governed_by_path = {
            item.path: item
            for item in codegen.managed_files
            if target.beads is not None or item.path.parts[:1] != (".beads",)
        }
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
        if not contract.complete_governed:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(completed))
        for relative, governed in governed_by_path.items():
            if relative in represented:
                continue
            path = root / relative
            if path.exists() and not path.is_file():
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"governed artifact is not a regular file: {path}",
                )
            entry_profiles = tuple(
                entry.profiles
                for entry in codegen.templates.entries
                if entry.destination == relative.as_posix()
            )
            if entry_profiles:
                allowed = {item for profiles in entry_profiles for item in profiles}
                if profile not in allowed:
                    continue
            if not path.exists():
                continue
            current = ""
            if path.is_file():
                read = u.Cli.files_read_text(path)
                if read.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(read)
                current = read.value
            if (
                governed.policy == "merge"
                and governed.owner == c.Infra.CODEGEN_OWNER_VSCODE
            ):
                # Owner-merge dispatch: owners with a canonical document merge
                # (vscode settings today) produce their rendered content here.
                merged = FlextInfraCodegen.render_vscode_settings(root)
                if merged.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(merged)
                if merged.value != current:
                    merged_plan = cls.file_plan(
                        root,
                        relative.as_posix(),
                        merged.value,
                        mode=governed.mode,
                    )
                    if merged_plan.failure:
                        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                            merged_plan,
                        )
                    completed.append(
                        merged_plan.value.model_copy(
                            update={"owner": governed.owner, "policy": governed.policy},
                        ),
                    )
                    continue
            if (
                governed.policy == "merge"
                and relative.as_posix() == c.Infra.ENVRC_LOCAL_RELPATH
            ):
                # Local overrides never carry generated content: the merge
                # strips stale generated sections and deletes the file when
                # nothing custom remains, so `.envrc` stays the single
                # beads activation owner.
                normalized = (
                    FlextInfraWorkspaceEnvironmentContracts.envrc_local_normalized(
                        current,
                    )
                )
                if normalized == current:
                    current_plan = cls.file_plan(
                        root,
                        relative.as_posix(),
                        current,
                        mode=governed.mode,
                    )
                    if current_plan.failure:
                        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                            current_plan,
                        )
                    completed.append(
                        current_plan.value.model_copy(
                            update={"owner": governed.owner, "policy": governed.policy},
                        ),
                    )
                    continue
                if not normalized:
                    before = u.Cli.atomic_read_binary_file_state(path, required=False)
                    if before.failure:
                        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                            before,
                        )
                    completed.append(
                        m.Infra.CodegenFilePlan(
                            project=root,
                            path=path,
                            before=before.value,
                            desired_content=None,
                            desired_mode=None,
                            owner=governed.owner,
                            policy=governed.policy,
                        ),
                    )
                    continue
                merged_plan = cls.file_plan(
                    root,
                    relative.as_posix(),
                    normalized,
                    mode=governed.mode,
                )
                if merged_plan.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                        merged_plan,
                    )
                completed.append(
                    merged_plan.value.model_copy(
                        update={"owner": governed.owner, "policy": governed.policy},
                    ),
                )
                continue
            current_plan = cls.file_plan(
                root,
                relative.as_posix(),
                current,
                mode=governed.mode,
            )
            if current_plan.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                    current_plan,
                )
            completed.append(
                current_plan.value.model_copy(
                    update={"owner": governed.owner, "policy": governed.policy},
                ),
            )
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(completed))


__all__: list[str] = ["FlextInfraCodegenConformExistingPlan"]
