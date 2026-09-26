"""Conformance planning for existing repositories and governed artifacts."""

from __future__ import annotations

import time
from collections.abc import MutableMapping
from pathlib import Path
from typing import Literal

from flext_core import r

from ... import c, m, p, t, u
from ...deps import FlextInfraPyprojectModernizer
from ...services.codegen import FlextInfraCodegen
from ...workspace.environment_contracts import FlextInfraWorkspaceEnvironmentContracts
from .artifact_render import FlextInfraCodegenConformArtifactRender


class FlextInfraCodegenConformExistingPlan(FlextInfraCodegenConformArtifactRender):
    """Conformance planning for existing repositories and governed artifacts."""

    def _plan_existing_repository(
        self,
        *,
        root: Path,
        repository_root: Path,
        repository: m.Infra.RepositoryRef,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        contract: m.Infra.CodegenConformSurfaceContract,
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Conform every declared managed surface in an existing repository."""
        stage_started = time.monotonic()
        u.Cli.info(f"  stage=pyproject repository={repository.name}")
        pyproject = root / c.PYPROJECT_FILENAME
        if not pyproject.is_file():
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                f"existing repository has no pyproject.toml: {root}; "
                "scaffold templates are available only through codegen new"
            )
        metadata = u.Infra.read_project_metadata_result(root)
        if metadata.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(metadata)
        dist = metadata.value.project.name
        if dist != repository.distribution:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                "PEP 621 project name does not match catalog distribution: "
                f"{dist} != {repository.distribution}"
            )
        managed_artifacts = u.Infra.snapshot_committed_project_managed_artifacts(root)
        if managed_artifacts.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                managed_artifacts
            )
        u.Cli.info(
            f"  stage=managed-artifacts repository={repository.name} "
            f"elapsed={time.monotonic() - stage_started:.2f}s"
        )
        stage_started = time.monotonic()
        modernizer = FlextInfraPyprojectModernizer(
            repository_root=repository_root,
            skip_check=True,
            managed_artifacts=managed_artifacts.value.resolution,
        )
        tooling_context = modernizer.resolve_tooling_context(
            project_name=repository.distribution,
            package_name=metadata.value.package_name,
            path=pyproject,
            root_modules=(
                target.project.root_modules if target.project is not None else ()
            ),
            root_packages=(
                target.project.root_packages if target.project is not None else ()
            ),
            declared_python_dirs=self._scaffold_python_dirs(
                codegen.templates.entries,
                target.make_profile,
                package=repository.package,
            ),
            analysis_exclusions=tuple(
                path.as_posix() for path in target.external_dependency_paths
            ),
        )
        if tooling_context.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                tooling_context
            )
        u.Cli.info(
            f"  stage=tooling-context repository={repository.name} "
            f"elapsed={time.monotonic() - stage_started:.2f}s"
        )
        managed_result = self._plan_existing_templates(
            root=root,
            repository=repository,
            target=target,
            workspace=workspace,
            codegen=codegen,
            tooling_runtime=tooling_context.value,
            contract=contract,
            managed_artifacts=managed_artifacts.value,
        )
        if managed_result.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(managed_result)
        planned = list(managed_result.value)
        if contract.custom:
            custom_result = self._plan_existing_custom(
                root, codegen, profile=target.make_profile.value
            )
            if custom_result.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                    custom_result
                )
            planned.extend(custom_result.value)
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(planned))

    def _plan_existing_templates(
        self,
        *,
        root: Path,
        repository: m.Infra.RepositoryRef,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        tooling_runtime: m.Infra.ToolingRuntimeContext,
        contract: m.Infra.CodegenConformSurfaceContract,
        managed_artifacts: m.Infra.ProjectManagedArtifactsSnapshot,
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Render configured overwrite-owned templates for an existing tree."""
        u.Cli.info(f"  stage=templates repository={repository.name}")
        profile = target.make_profile
        templates_root = u.Infra.codegen_templates_root(codegen)
        planned: list[m.Infra.CodegenFilePlan] = []
        for managed in codegen.managed_files:
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
            if managed.path == Path(c.Infra.CUSTOM_MAKE_FILENAME) or pyproject_skipped:
                continue
            entries = tuple(
                entry
                for entry in codegen.templates.entries
                if entry.destination == managed.path.as_posix()
                and entry.delegate == "render"
            )
            if not entries:
                continue
            if len(entries) != 1:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"managed file requires exactly one render template: {managed.path}"
                )
            entry = entries[0]
            relative = Path(entry.destination)
            if relative.is_absolute() or ".." in relative.parts:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"managed destination escapes repository root: {entry.destination}"
                )
            path = (root / relative).resolve()
            try:
                path.relative_to(root.resolve())
            except ValueError:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"managed destination escapes repository root: {entry.destination}"
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
                            orphan_read
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
                            absent_plan
                        )
                    planned.append(
                        absent_plan.value.model_copy(
                            update={"owner": managed.owner, "policy": managed.policy}
                        )
                    )
                continue
            rendered = self._rendered_artifact_source(
                templates_root=templates_root,
                template_relpath=entry.source,
                failure_prefix="",
                dist=repository.distribution,
                repository=repository,
                repository_root=root,
                target=target,
                workspace=workspace,
                codegen=codegen,
                destination=entry.destination,
                tooling_runtime=tooling_runtime,
                project_context=None,
                managed_artifacts=managed_artifacts.resolution,
            )
            if rendered.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(rendered)
            rendered_content = rendered.value
            composed = self.compose_project_artifact(
                root,
                entry.destination,
                rendered_content,
                managed_artifacts=managed_artifacts,
                workspace=workspace,
                codegen=codegen,
                repository=repository,
                target=target,
            )
            if composed.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(composed)
            rendered_content = composed.value.rendered
            conflict_marker = u.Infra.first_merge_conflict_marker(rendered_content)
            if conflict_marker is not None:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    "rendered template contains a merge conflict marker: "
                    f"source={entry.source}; target={path}; root={root}; "
                    f"marker={conflict_marker}"
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
        """Validate the handwritten Make surface against its profile contract."""
        policy = config.make.custom_handler_policies.get(
            profile or "", config.make.custom_handler_policy
        )
        path = root / policy.filename
        if path.exists() and not path.is_file():
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                f"custom Make destination is not a regular file: {path}"
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
            families: t.VariadicTuple[Literal["u", "p"]] = ("u", "p")
            for family in families:
                rendered = u.Infra.render_utility_facade(
                    layout.package_dir, family=family
                )
                if rendered is None:
                    continue
                relative = (
                    layout.package_dir
                    / (c.Infra.FAMILY_PUBLIC_MODULES[family] + c.Infra.EXT_PYTHON)
                ).relative_to(root)
                utility_plan = self.file_plan(root, relative.as_posix(), rendered)
                if utility_plan.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                        utility_plan
                    )
                plans.append(utility_plan.value)
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(plans))

    @classmethod
    def _complete_governed_plans(
        cls,
        root: Path,
        planned: t.SequenceOf[m.Infra.CodegenFilePlan],
        codegen: m.Infra.CodegenConfigSpec,
        contract: m.Infra.CodegenConformSurfaceContract,
        *,
        profile: c.Infra.MakeProfile,
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Attach ownership metadata and represent every governed root artifact.

        Only the ``ALL`` surface completes the full governed set; the
        pyproject-scoped surfaces (``DEPENDENCIES``/``PYPROJECT``) keep the plan
        restricted to what their own planners already produced.
        """
        governed_by_path = {item.path: item for item in codegen.managed_files}
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
                }
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
                    f"governed artifact is not a regular file: {path}"
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
                        root, relative.as_posix(), merged.value, mode=governed.mode
                    )
                    if merged_plan.failure:
                        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                            merged_plan
                        )
                    completed.append(
                        merged_plan.value.model_copy(
                            update={"owner": governed.owner, "policy": governed.policy}
                        )
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
                        current
                    )
                )
                if normalized == current:
                    current_plan = cls.file_plan(
                        root, relative.as_posix(), current, mode=governed.mode
                    )
                    if current_plan.failure:
                        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                            current_plan
                        )
                    completed.append(
                        current_plan.value.model_copy(
                            update={"owner": governed.owner, "policy": governed.policy}
                        )
                    )
                    continue
                if not normalized:
                    before = u.Cli.atomic_read_binary_file_state(path, required=False)
                    if before.failure:
                        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                            before
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
                        )
                    )
                    continue
                merged_plan = cls.file_plan(
                    root, relative.as_posix(), normalized, mode=governed.mode
                )
                if merged_plan.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                        merged_plan
                    )
                completed.append(
                    merged_plan.value.model_copy(
                        update={"owner": governed.owner, "policy": governed.policy}
                    )
                )
                continue
            current_plan = cls.file_plan(
                root, relative.as_posix(), current, mode=governed.mode
            )
            if current_plan.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                    current_plan
                )
            completed.append(
                current_plan.value.model_copy(
                    update={"owner": governed.owner, "policy": governed.policy}
                )
            )
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(completed))


__all__: list[str] = ["FlextInfraCodegenConformExistingPlan"]
