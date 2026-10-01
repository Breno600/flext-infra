"""Unified, fail-closed conformance for new and existing repositories.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_core import r, s
from flext_infra import c, m, p, u
from flext_infra.codegen._conform import FlextInfraCodegenConformExecute

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraCodegenConform(s[m.Infra.CodegenResult]):
    """Plan every selected output, then atomically write only a clean plan."""

    @staticmethod
    def _mise_bootstrap_environment() -> m.Infra.MiseBootstrapEnvironmentSpec:
        """Project the single generated Mise isolation contract into templates."""
        return u.Infra.mise_bootstrap_environment()

    @staticmethod
    def _link_mode(
        repository: m.Infra.RepositoryRef, toolchain: m.Infra.ToolchainSpec
    ) -> str:
        """Resolve the repository override through one codegen authority."""
        link_mode = repository.uv_link_mode or toolchain.uv_link_mode
        if not isinstance(link_mode, str):
            msg = "resolved uv link mode must be a string"
            raise TypeError(msg)
        return link_mode

    @staticmethod
    def _dependency_cooldown_policy(
        repository: m.Infra.RepositoryRef, toolchain: m.Infra.ToolchainSpec
    ) -> tuple[tuple[str, ...], dict[str, str]]:
        """Compose fleet defaults with the repository's narrower policy."""
        exclusions = dict.fromkeys(toolchain.dependency_cooldown_exclusions)
        overrides = dict(toolchain.dependency_cooldown_overrides)
        for package in repository.dependency_cooldown_exclusions:
            overrides.pop(package, None)
            exclusions[package] = None
        for package, cutoff in repository.dependency_cooldown_overrides.items():
            exclusions.pop(package, None)
            overrides[package] = cutoff
        return tuple(exclusions), overrides

    @staticmethod
    def _discover_script_verbs(
        repository_root: Path,
    ) -> tuple[m.Infra.MakeVerbSpec, ...]:
        """Discover script verbs from scripts/<verb>/all.sh in the repository root.

        The filesystem is the SSOT: a verb is emitted only when its all.sh
        entrypoint exists. No manual list is required.
        """
        scripts_dir = repository_root / "scripts"
        if not scripts_dir.is_dir():
            return ()
        discovered: list[m.Infra.MakeVerbSpec] = []
        for entry in sorted(scripts_dir.iterdir()):
            if entry.is_dir() and (entry / "all.sh").is_file():
                discovered.append(
                    m.Infra.MakeVerbSpec(
                        name=entry.name,
                        description=f"Script command: {entry.name}",
                        requires_apply=True,
                    )
                )
        return tuple(discovered)

    @classmethod
    def _surface_contract(
        cls, surface: c.Infra.CodegenConformSurface
    ) -> m.Infra.CodegenConformSurfaceContract:
        match surface:
            case c.Infra.CodegenConformSurface.ALL:
                return m.Infra.CodegenConformSurfaceContract(complete_governed=True)
            case c.Infra.CodegenConformSurface.DEPENDENCIES:
                return m.Infra.CodegenConformSurfaceContract(
                    destinations=frozenset({c.Infra.PYPROJECT_FILENAME}),
                    delegates=False,
                    custom=False,
                )
            case c.Infra.CodegenConformSurface.PYPROJECT:
                return m.Infra.CodegenConformSurfaceContract(
                    destinations=frozenset({c.Infra.PYPROJECT_FILENAME}),
                    delegates=False,
                    custom=False,
                )
            case c.Infra.CodegenConformSurface.MAKEFILE:
                return m.Infra.CodegenConformSurfaceContract(
                    destinations=frozenset({c.Infra.MAKEFILE_FILENAME}),
                    pyproject=False,
                    custom=False,
                )
            case _:
                msg = f"Unsupported codegen conform surface: {surface}"
                raise ValueError(msg)

class FlextInfraCodegenConform(FlextInfraCodegenConformExecute):
    """Plan every selected output, then atomically write only a clean plan."""

    @classmethod
    def settle_repository(cls, root: Path) -> p.Result[bool]:
        """Conform every projection of ``root``, then lock it without upgrading.

        Conform settles ``pyproject.toml`` and every rendered projection first,
        so the lock resolves against them; it upgrades nothing (only ``upg``
        resolves the newest releases). Identical inputs regenerate identical
        bytes, so a rerun changes nothing.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        conformed = cls.execute_request(
            m.Infra.CodegenConformRequest(
                root=root,
                make_profile=current_repository.role,
                beads=workspace.beads,
                project=workspace.project,
                canonical_project_name=current_repository.distribution,
                baseline_branch=baseline_result.value,
                baseline_reference=(
                    f"refs/heads/{baseline_result.value}"
                    if self.scaffolded_repository
                    else f"refs/remotes/origin/{baseline_result.value}"
                ),
                ci_enabled=True,
                gascity_enabled=workspace.gascity_enabled,
                external_dependency_paths=workspace.external_dependency_paths,
                technical_branch_patterns=(
                    config_spec.branch_policy.technical_branch_patterns
                ),
                governed_branch_patterns=(
                    config_spec.branch_policy.governed_branch_patterns
                ),
            )
        )
        selected_result = self._select_repositories(
            request, workspace, current_repository
        )
        if selected_result.failure:
            return r[m.Infra.CodegenPlan].from_failure(selected_result)
        selected = selected_result.value
        contract = self._surface_contract(c.Infra.CodegenConformSurface(request.what))
        files: list[m.Infra.CodegenFilePlan] = []
        environments: list[m.Infra.UvEnvironmentPlan] = []
        ancestry_plans: list[m.Infra.BranchAncestryPlan] = []
        total_repositories = len(selected)
        u.Cli.info(f"stage=plan repositories={total_repositories}")
        for repository_index, repository in enumerate(selected, start=1):
            repository_started = time.monotonic()
            u.Cli.progress(
                repository_index, total_repositories, repository.name, "conform"
            )
            u.Cli.info(
                f"  stage=topology repository={repository.name} "
                f"role={repository.role.value} kind={repository.kind.value}"
            )
            if repository.kind is not c.Infra.ProjectKind.INTERNAL_FLEXT:
                u.Cli.info(
                    f"  stage=skip repository={repository.name} "
                    f"kind={repository.kind.value} is not rewritten by generation"
                )
                continue
            is_current_repository = repository.name == current_target.repository.name
            if is_current_repository:
                repository_root = current_target.root
                if repository_root != root:
                    return r[m.Infra.CodegenPlan].fail(
                        "current conformance target differs from the requested root: "
                        f"{repository_root} != {root}"
                    )
            else:
                # The governing root is the requested checkout, never the
                # previous iteration's member: resolving the second declared
                # repository against the first produced <root>/alpha/beta.
                repository_root_result = self._repository_root(
                    root, workspace, repository
                )
                if repository_root_result.failure:
                    return r[m.Infra.CodegenPlan].from_failure(repository_root_result)
                repository_root = repository_root_result.value
            if repository_root.exists() and not repository_root.is_dir():
                return r[m.Infra.CodegenPlan].fail(
                    f"declared repository path is not a directory: {repository_root}"
                )
            if not repository_root.is_dir() and self.initial_workspace is None:
                return r[m.Infra.CodegenPlan].fail(
                    f"declared repository checkout is missing: {repository_root}"
                )
            if is_current_repository:
                target = current_target
                local_workspace = workspace
            else:
                if repository.path != Path():
                    declared_member = FlextInfraWorkspaceDetector.load_workspace_spec(
                        repository_root
                    )
                    if declared_member.failure:
                        return r[m.Infra.CodegenPlan].from_failure(declared_member)
                    local_repository = repository.model_copy(update={"path": Path()})
                    # The parent owns topology and selection; the member owns its
                    # project metadata, including the runtime dependency profile.
                    local_workspace = m.Infra.WorkspaceSpec(
                        name=repository.name,
                        beads=workspace.beads,
                        repository=local_repository,
                        project=declared_member.value.project,
                    )
                else:
                    local_workspace_result = (
                        FlextInfraWorkspaceDetector.load_workspace_spec(repository_root)
                    )
                    if local_workspace_result.failure:
                        return r[m.Infra.CodegenPlan].from_failure(
                            local_workspace_result
                        )
                    local_workspace = local_workspace_result.value
                target_result = FlextInfraWorkspaceDetector.conform_target(
                    repository_root, local_workspace
                )
                if target_result.failure:
                    return r[m.Infra.CodegenPlan].from_failure(target_result)
                target = target_result.value
                if repository.path != Path():
                    target = target.model_copy(update={"repository": repository})
            if (
                self.initial_workspace is not None
                and repository.name == workspace.repository.name
            ):
                repository_plan = self._plan_scaffold_repository(
                    root=repository_root,
                    repository=target.repository,
                    target=target,
                    workspace=local_workspace,
                    codegen=config_spec,
                    contract=contract,
                )
            else:
                repository_plan = self._plan_existing_repository(
                    root=repository_root,
                    repository_root=repository_root,
                    repository=target.repository,
                    target=target,
                    workspace=local_workspace,
                    codegen=config_spec,
                    contract=contract,
                )
            if repository_plan.failure:
                return r[m.Infra.CodegenPlan].from_failure(repository_plan)
            governed = self._complete_governed_plans(
                repository_root,
                repository_plan.value,
                config_spec,
                contract,
                profile=target.make_profile,
                workspace=local_workspace,
            )
            if governed.failure:
                return r[m.Infra.CodegenPlan].from_failure(governed)
            files.extend(governed.value)
            if contract.complete_governed:
                retired = self.retired_projection_plans(
                    repository_root, target.make_profile
                )
                if retired.failure:
                    return r[m.Infra.CodegenPlan].from_failure(retired)
                governed_paths = {item.path for item in governed.value}
                files.extend(
                    item for item in retired.value if item.path not in governed_paths
                )
            environments.append(
                self._uv_environment_plan(
                    root=repository_root,
                    repository_root=repository_root,
                    target=target,
                    workspace=local_workspace,
                    config=config_spec,
                )
            )
            if self.initial_workspace is None or (repository_root / ".git").exists():
                ancestry_result = self._branch_ancestry_plan(target)
                if ancestry_result.failure:
                    return r[m.Infra.CodegenPlan].from_failure(ancestry_result)
                ancestry_plans.append(ancestry_result.value)
            u.Cli.status(
                "conform",
                repository.name,
                result=True,
                elapsed=time.monotonic() - repository_started,
            )
        return r[m.Infra.CodegenPlan].ok(
            m.Infra.CodegenPlan(
                request=request,
                repositories=selected,
                workspace=workspace,
                make_spec=config_spec.make,
                uv_environments=tuple(environments),
                branch_ancestry=tuple(ancestry_plans),
                files=tuple(files),
            )
        )

    @staticmethod
    def _complete_governed_plans(
        root: Path,
        planned: t.SequenceOf[m.Infra.CodegenFilePlan],
        codegen: m.Infra.CodegenConfigSpec,
        contract: m.Infra.CodegenConformSurfaceContract,
        *,
        profile: c.Infra.MakeProfile,
        workspace: m.Infra.WorkspaceSpec | None = None,
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Attach ownership metadata and represent every governed root artifact.

        Only the ``ALL`` surface completes the full governed set; the
        pyproject-scoped surfaces (``DEPENDENCIES``/``PYPROJECT``) keep the plan
        restricted to what their own planners already produced.
        """
        governed_by_path = {item.path: item for item in codegen.managed_files}
        completed: list[m.Infra.CodegenFilePlan] = []
        represented: set[Path] = set()
        represented_indexes: dict[Path, int] = {}
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
                    merged_plan = FlextInfraCodegenConform._file_plan(
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
            if governed.policy == "merge" and relative.as_posix() == c.Infra.GITIGNORE:
                # The canonical .gitignore body is rendered
                # from the same base/gitignore.j2 + computed
                # CodegenConfigSpec.gitignore_sections used by `codegen new` —
                # ONE render mechanism derived from the artifact SSOT.
                # Per-project exception fields land in their typed owner.
                rendered_gitignore = FlextInfraCodegenConform._render_gitignore(
                    codegen,
                    profile=profile,
                    project_name=root.name,
                    workspace=workspace,
                    project_dir=root,
                )
                if rendered_gitignore.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                        rendered_gitignore
                    )
                if rendered_gitignore.value != current:
                    gitignore_plan = FlextInfraCodegenConform._file_plan(
                        root,
                        relative.as_posix(),
                        rendered_gitignore.value,
                        mode=governed.mode,
                    )
                    if gitignore_plan.failure:
                        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                            gitignore_plan
                        )
                    completed.append(
                        gitignore_plan.value.model_copy(
                            update={"owner": governed.owner, "policy": governed.policy}
                        )
                    )
                    continue
            current_plan = FlextInfraCodegenConform._file_plan(
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

    @staticmethod
    def _package_root() -> Path:
        """Return the installed flext-infra package root."""
        return Path(__file__).resolve().parent.parent

    @staticmethod
    def render_project_gitignore(
        codegen: m.Infra.CodegenConfigSpec,
        *,
        profile: c.Infra.MakeProfile,
        project_name: str,
        workspace: m.Infra.WorkspaceSpec | None = None,
        project_dir: Path | None = None,
    ) -> p.Result[str]:
        """Render the canonical ``.gitignore`` for one named project.

        Public seam consumed by the layout engine: per-project
        layout ``gitignore_additions`` from the layout SSOT and the
        repository-owned ``ManagedArtifacts.Gitignore.patterns`` read from
        ``project_dir`` are appended as trailing derived sections so conform
        and layout never diverge.
        """
        return FlextInfraCodegenConform._render_gitignore(
            codegen,
            profile=profile,
            project_name=project_name,
            workspace=workspace,
            project_dir=project_dir,
        )

    @staticmethod
    def _render_gitignore(
        codegen: m.Infra.CodegenConfigSpec,
        *,
        profile: c.Infra.MakeProfile,
        project_name: str | None = None,
        workspace: m.Infra.WorkspaceSpec | None = None,
        project_dir: Path | None = None,
    ) -> p.Result[str]:
        """Render the canonical ``.gitignore`` body via the single template.

        ``codegen new`` renders ``base/gitignore.j2`` with
        the full project context; conform renders the same template with the
        codegen config — both consume the same computed ``gitignore_sections``
        projection, so the body is byte-identical.
        """
        entry = next(
            (
                item
                for item in codegen.templates.entries
                if item.destination == c.Infra.GITIGNORE
            ),
            None,
        )
        if entry is None:
            return r[str].fail(
                "gitignore template is missing from codegen configuration"
            )
        templates_root = (
            FlextInfraCodegenConform._package_root()
            / "templates"
            / codegen.templates.root
        ).resolve()
        sections = [
            section
            for section in codegen.gitignore_sections
            if not section.profiles or profile in section.profiles
        ]
        # The deny-all root policy (`/*` + `/*/`) would swallow every governed
        # subproject directory, so their whitelist is DERIVED from the live workspace
        # topology instead of a hardcoded name glob: declaring a subproject in
        # local .gitmodules is the single source that makes it trackable.
        # Nested paths need every ancestor unignored, otherwise git never
        # descends far enough to reach the subproject itself.
        member_patterns: list[str] = []
        if workspace is not None:
            for declared_repository in workspace.subprojects:
                parts = declared_repository.path.as_posix().strip("/").split("/")
                # Every ancestor is unignored so git can descend into the
                # subproject, then its contents are unignored with the `/**` form.
                prefixes = [
                    "/".join(parts[:depth]) for depth in range(1, len(parts) + 1)
                ]
                candidates = [f"!/{prefix}/" for prefix in prefixes]
                candidates.append(f"!/{prefixes[-1]}/**")
                for pattern in candidates:
                    if pattern not in member_patterns:
                        member_patterns.append(pattern)
        if member_patterns:
            sections.append(
                m.Infra.ScaffoldGitignoreSectionSpec(
                    name="WHITELIST: governed workspace subprojects (derived)",
                    patterns=tuple(member_patterns),
                )
            )
        if project_name is not None:
            override = codegen.layout.project_overrides.get(project_name)
            if override is not None and override.gitignore_additions:
                sections.append(
                    m.Infra.ScaffoldGitignoreSectionSpec(
                        name=c.Infra.GITIGNORE_LAYOUT_SECTION_NAME,
                        patterns=override.gitignore_additions,
                    )
                )
        if project_dir is not None:
            # The repository owns the ignore patterns the fleet scaffold cannot
            # know (local caches, generated runtime state); they are declared in
            # its own config/*.yaml and appended as one derived section.
            resolved = u.Infra.load_project_managed_artifacts(project_dir)
            if resolved.failure:
                return r[str].from_failure(resolved)
            project_patterns = resolved.value.artifacts.Gitignore.patterns
            if project_patterns:
                sections.append(
                    m.Infra.ScaffoldGitignoreSectionSpec(
                        name=c.Infra.GITIGNORE_PROJECT_SECTION_NAME,
                        patterns=project_patterns,
                    )
                )
        context = m.Infra.GitignoreRenderSpec(gitignore_sections=tuple(sections))
        return u.Cli.template_render(templates_root / entry.source, context)

    @staticmethod
    def _select_repositories(
        request: m.Infra.CodegenConformRequest,
        workspace: m.Infra.WorkspaceSpec,
        current_repository: m.Infra.RepositoryRef,
    ) -> p.Result[t.VariadicTuple[m.Infra.RepositoryRef]]:
        """Resolve self/subprojects/all from the local read-only topology."""
        scope = c.Infra.CodegenConformScope(request.scope)
        if scope is c.Infra.CodegenConformScope.SELF:
            selected = (current_repository,)
        elif scope is c.Infra.CodegenConformScope.DECLARED:
            if not workspace.subprojects:
                return r[tuple[m.Infra.RepositoryRef, ...]].fail(
                    "subprojects scope requires local .gitmodules entries"
                )
            selected = tuple(workspace.subprojects)
        else:
            selected = (workspace.repository, *workspace.subprojects)
        mutable = tuple(
            repository
            for repository in selected
            if repository.codegen is not c.Infra.CodegenKind.NONE
            and not repository.read_only
        )
        if not mutable:
            return r[tuple[m.Infra.RepositoryRef, ...]].fail(
                "selected repositories do not permit code generation"
            )
        return r[tuple[m.Infra.RepositoryRef, ...]].ok(mutable)

    @staticmethod
    def _repository_root(
        root: Path, workspace: p.Infra.WorkspaceSpec, repository: p.Infra.RepositoryRef
    ) -> p.Result[Path]:
        """Resolve one declared checkout without escaping its workspace owner."""
        if repository.name == workspace.repository.name:
            return r[Path].ok(root)
        resolved_root = root.resolve()
        resolved: Path = (resolved_root / repository.path).resolve()
        if not resolved.is_relative_to(resolved_root):
            return r[Path].fail(
                "declared repository path escapes workspace root: "
                f"{repository.path.as_posix()}"
            )
        return r[Path].ok(resolved)

    @staticmethod
    def _scaffold_python_dirs(
        entries: t.SequenceOf[p.Infra.TemplateEntrySpec], profile: c.Infra.MakeProfile
    ) -> t.StrSequence:
        """Return Python roots the selected scaffold manifest actually creates."""
        # Derive future roots from both
        # declarative owners so scaffold and existing-tree discovery converge.
        generated_roots = {
            Path(entry.destination).parts[0]
            for entry in entries
            if profile in entry.profiles
            and entry.delegate == "render"
            and Path(entry.destination).parts
        }
        return tuple(
            directory
            for directory in config.Infra.tooling.tools.pyright.path_rules.env_dirs
            if directory in generated_roots
        )

    @staticmethod
    def _conformed_pyproject_source(
        source: str,
        *,
        repository: m.Infra.RepositoryRef,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        workspace_mode: c.Infra.MakeProfile,
        uv_exclude_dependencies: t.VariadicTuple[
            m.Infra.UvScopedDependencyExclusionSpec
        ],
    ) -> p.Result[str]:
        """Conform one pyproject source under this repository's cooldown policy."""
        cooldown_exclusions, cooldown_overrides = (
            FlextInfraCodegenConform._dependency_cooldown_policy(
                repository, codegen.toolchain
            )
        )
        return u.Infra.pyproject_conform(
            source,
            providers=codegen.providers,
            workspace=workspace,
            workspace_mode=workspace_mode,
            toolchain=codegen.toolchain,
            required_dev_dependencies=codegen.scaffold.project.dev,
            uv_link_mode=FlextInfraCodegenConform._link_mode(
                repository, codegen.toolchain
            ),
            dependency_cooldown_exclusions=cooldown_exclusions,
            dependency_cooldown_overrides=cooldown_overrides,
            uv_exclude_dependencies=uv_exclude_dependencies,
        )

    @staticmethod
    def _routed_uv_exclude_dependencies(
        *,
        repository: m.Infra.RepositoryRef,
        target: m.Infra.RepositoryConformTarget,
        codegen: m.Infra.CodegenConfigSpec,
    ) -> t.VariadicTuple[m.Infra.UvScopedDependencyExclusionSpec]:
        """Return the uv dependency exclusions routed to one repository.

        Workspace root owns resolution for attached subprojects (uv reads
        exclude-dependencies only from the workspace root). Subprojects still
        receive their own routed excludes for standalone CI clones.
        """
        if target.make_profile is c.Infra.MakeProfile.WORKSPACE:
            return tuple(codegen.uv_exclude_dependencies)
        return tuple(
            item
            for item in codegen.uv_exclude_dependencies
            if item.project == repository.distribution
        )

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
        pyproject = root / c.Infra.PYPROJECT_FILENAME
        managed_artifacts = u.Infra.empty_snapshot()
        # New and existing repositories share the exact same
        # root-scoped modernizer pipeline, so first generation is a fixed point.
        # A declared subproject consumes the workspace root
        # tooling profile even before the atomic scaffold creates files on disk.
        tooling_root = target.root
        modernizer = FlextInfraPyprojectModernizer(
            repository_root=tooling_root,
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
        declared_python_dirs = self._scaffold_python_dirs(
            codegen.templates.entries, profile
        )
        # Why (flext-6itas.4): a scaffold's declared roots are the complete
        # future topology only for a subproject/standalone target; a workspace
        # root aggregates subproject trees it has not declared here.
        declared_python_dirs_are_complete = profile is not c.Infra.MakeProfile.WORKSPACE
        tooling_result = modernizer.resolve_tooling_context(
            project_name=repository.distribution,
            package_name=project.package_name,
            path=pyproject,
            root_modules=project.root_modules,
            root_packages=project.root_packages,
            declared_python_dirs=declared_python_dirs,
            declared_python_dirs_are_complete=declared_python_dirs_are_complete,
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
        )
        if context_result.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(context_result)
        context = context_result.value
        planned: list[m.Infra.CodegenFilePlan] = []
        templates_root = (
            self._package_root() / "templates" / codegen.templates.root
        ).resolve()
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
            if destination == c.Infra.PYPROJECT_FILENAME and not contract.pyproject:
                continue
            if not contract.delegates and destination != c.Infra.PYPROJECT_FILENAME:
                continue
            if (
                destination == c.Infra.BEADS_METADATA_RELPATH
                and not (root / destination).is_file()
            ):
                # Why (flext-l2296 family): the ledger metadata is minted by
                # Beads at first use, so a fresh clone legitimately lacks it.
                # Planning the absent runtime artifact failed the gen check
                # gate on every clean checkout. When present, the render below
                # stays identity-preserving.
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
            rendered_content = self._compose_project_artifact(
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
            file_plan = self._file_plan(
                root,
                destination,
                rendered_content.value.rendered,
                source_states=rendered_content.value.source_states,
            )
            if file_plan.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(file_plan)
            planned.append(file_plan.value)
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(planned))

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
        pyproject = root / c.Infra.PYPROJECT_FILENAME
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
        managed_artifacts = u.Infra.snapshot_project_managed_artifacts(root)
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
                codegen.templates.entries, target.make_profile
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
        templates_root = (
            self._package_root() / "templates" / codegen.templates.root
        ).resolve()
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
            pyproject_skipped = managed.path == Path(c.Infra.PYPROJECT_FILENAME) and (
                not contract.pyproject
                or (
                    workspace.project is None
                    and profile is c.Infra.MakeProfile.WORKSPACE
                )
            )
            if (
                managed.policy in {"delegated", "manual"}
                or managed.path == Path(c.Infra.CUSTOM_MAKE_FILENAME)
                or pyproject_skipped
            ):
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
            if (
                entry.destination == c.Infra.BEADS_METADATA_RELPATH
                and not path.is_file()
            ):
                # Why (flext-l2296 family): the ledger metadata is minted by
                # Beads at first use, so a fresh clone legitimately lacks it.
                # Planning an absent runtime artifact made the gen check gate
                # fail on every clean checkout. When the file exists, the
                # identity-preserving refresh below still applies.
                continue
            try:
                path.relative_to(root.resolve())
            except ValueError:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"managed destination escapes repository root: {entry.destination}"
                )
            if profile not in entry.profiles:
                # Why: profile-excluded managed workflows must not keep firing
                # (ci-matrix on standalone). Prune the orphan projection.
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
            if managed.policy == "create-only" and path.is_file():
                current = u.Cli.files_read_text(path)
                if current.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                        current
                    )
                file_plan = self._file_plan(
                    root, entry.destination, current.value, mode=managed.mode
                )
                if file_plan.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                        file_plan
                    )
                planned.append(file_plan.value)
                continue
            if managed.policy == "create-only" and path.exists():
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"create-only destination is not a regular file: {path}"
                )
            if managed.policy == "create-only":
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
            composed = self._compose_project_artifact(
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
            conflict_marker = next(
                (
                    line
                    for line in rendered_content.splitlines()
                    if line.startswith(("<<<<<<< ", "||||||| ", ">>>>>>> "))
                ),
                None,
            )
            if conflict_marker is not None:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    "rendered template contains a merge conflict marker: "
                    f"source={entry.source}; target={path}; root={root}; "
                    f"marker={conflict_marker}"
                )
            file_plan = self._file_plan(
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

    @staticmethod
    def _compose_project_artifact(
        repository_root: Path,
        destination: str,
        rendered: str,
        *,
        managed_artifacts: m.Infra.ProjectManagedArtifactsSnapshot | None = None,
        workspace: m.Infra.WorkspaceSpec | None = None,
        codegen: m.Infra.CodegenConfigSpec | None = None,
        repository: m.Infra.RepositoryRef | None = None,
        target: m.Infra.RepositoryConformTarget | None = None,
    ) -> p.Result[m.Infra.CodegenArtifactComposition]:
        """Apply typed project overlays after canonical template rendering."""
        if destination == c.Infra.PYPROJECT_FILENAME:
            live_path = repository_root / c.Infra.PYPROJECT_FILENAME
            live = (
                live_path.read_text(encoding="utf-8") if live_path.is_file() else None
            )
            overlaid = u.Infra.overlay_preserved(rendered, live)
            if overlaid.failure:
                return r[m.Infra.CodegenArtifactComposition].from_failure(overlaid)
            rendered = overlaid.value
            if workspace is not None and codegen is not None and repository is not None:
                profile = (
                    target.make_profile
                    if target is not None
                    else c.Infra.MakeProfile.STANDALONE
                )
                excludes = (
                    FlextInfraCodegenConform._routed_uv_exclude_dependencies(
                        repository=repository, target=target, codegen=codegen
                    )
                    if target is not None
                    else ()
                )
                conformed = FlextInfraCodegenConform._conformed_pyproject_source(
                    rendered,
                    repository=repository,
                    workspace=workspace,
                    codegen=codegen,
                    workspace_mode=profile,
                    uv_exclude_dependencies=excludes,
                )
                if conformed.failure:
                    return r[m.Infra.CodegenArtifactComposition].from_failure(conformed)
                rendered = conformed.value
            formatted = u.Infra.format_toml_source(
                rendered,
                path=live_path,
                toolchain_root=repository_root,
                taplo_version=config.Infra.codegen.toolchain.taplo_version,
            )
            rendered = formatted.value if formatted.success else rendered
        if destination != c.Infra.MISE_TOML_FILENAME:
            return r[m.Infra.CodegenArtifactComposition].ok(
                m.Infra.CodegenArtifactComposition(rendered=rendered)
            )
        resolved_artifacts = managed_artifacts
        if resolved_artifacts is None:
            snapshot = u.Infra.snapshot_project_managed_artifacts(repository_root)
            if snapshot.failure:
                return r[m.Infra.CodegenArtifactComposition].from_failure(snapshot)
            resolved_artifacts = snapshot.value
        composed = u.Infra.compose_mise_toml_from_snapshot(
            resolved_artifacts.sources, rendered
        )
        if composed.failure:
            return r[m.Infra.CodegenArtifactComposition].from_failure(composed)
        return r[m.Infra.CodegenArtifactComposition].ok(
            m.Infra.CodegenArtifactComposition(
                rendered=composed.value, source_states=resolved_artifacts.sources
            )
        )

    @staticmethod
    def _custom_ci_steps(repository_root: Path) -> str:
        """Read the project-owned workflow steps, if the project declares any.

        This is the CI counterpart of ``custom.mk``: the generator injects the
        block verbatim and never interprets it, so a project extends its own
        pipeline without the generator learning that project's concerns.
        """
        source: Path = repository_root / c.Infra.CUSTOM_CI_STEPS_FILENAME
        if not source.is_file():
            return ""
        return source.read_text(encoding=c.DEFAULT_ENCODING).rstrip("\n")

    @staticmethod
    def _repository_root_rel(workspace: m.Infra.WorkspaceSpec) -> str:
        """Return the environment root owned by the inferred target."""
        if workspace.project is not None:
            project_root_rel: str = workspace.project.repository_root_rel
            return project_root_rel
        return "."

    @staticmethod
    def _repository_provider(
        repository: m.Infra.RepositoryRef, codegen: m.Infra.CodegenConfigSpec
    ) -> p.Result[m.Infra.ProviderSpec]:
        """Resolve one repository to exactly one provider-owned policy."""
        resolved: p.Result[m.Infra.ProviderSpec] = u.Infra.repository_provider(
            repository, codegen.providers
        )
        return resolved

    @classmethod
    def _managed_gitlinks(
        cls, workspace: m.Infra.WorkspaceSpec, codegen: m.Infra.CodegenConfigSpec
    ) -> p.Result[t.VariadicTuple[m.Infra.ManagedGitlinkSpec]]:
        """Resolve provider baselines only for mutable governed subprojects."""
        resolved: list[m.Infra.ManagedGitlinkSpec] = []
        for repository in workspace.subprojects:
            provider = cls._repository_provider(repository, codegen)
            if provider.failure:
                return r[tuple[m.Infra.ManagedGitlinkSpec, ...]].from_failure(provider)
            resolved.append(
                m.Infra.ManagedGitlinkSpec(
                    repository=repository,
                    branch=u.Infra.resolve_integration_branch(
                        workspace, provider.value
                    ),
                )
            )
        return r[tuple[m.Infra.ManagedGitlinkSpec, ...]].ok(tuple(resolved))

    @staticmethod
    def _beads_project_id(repository_root: Path) -> str | None:
        """Return the checkout's own ledger identity, or None if unminted.

        `.beads/identity.toml` is the canonical owner (`[project] id`); the
        generated marker is its projection. An absent file is not a failure —
        it means Beads has not minted an identity for this checkout yet.
        """
        identity = repository_root / ".beads" / "identity.toml"
        if not identity.is_file():
            return None
        source = u.Cli.files_read_text(identity)
        if source.failure:
            msg = f"failed to read beads identity at {identity}: {source.error}"
            raise RuntimeError(msg)
        payload = u.Cli.toml_mapping_from_text(source.value)
        if payload is None:
            msg = f"beads identity at {identity} is not valid TOML"
            raise ValueError(msg)
        project = payload.get("project")
        if not isinstance(project, Mapping):
            return None
        value = project.get("id")
        return value.strip() if isinstance(value, str) and value.strip() else None

    def _rendered_artifact_source(
        self,
        *,
        templates_root: Path,
        template_relpath: Path,
        failure_prefix: str,
        dist: str,
        repository: m.Infra.RepositoryRef,
        repository_root: Path,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        destination: str,
        tooling_runtime: m.Infra.ToolingRuntimeContext,
        project_context: m.Infra.ProjectRenderContext | None,
        managed_artifacts: m.Infra.ProjectManagedArtifactsResolution | None = None,
    ) -> p.Result[str]:
        """Resolve one artifact render context and render its template source.

        ``failure_prefix`` carries the only difference between the scaffold and
        existing-repository planners: the stage banner the scaffold planner
        prepends to a render failure.
        """
        artifact_context = self._artifact_render_context(
            dist=dist,
            repository=repository,
            repository_root=repository_root,
            target=target,
            workspace=workspace,
            codegen=codegen,
            destination=destination,
            tooling_runtime=tooling_runtime,
            project_context=project_context,
            managed_artifacts=managed_artifacts,
        )
        if artifact_context.failure:
            return r[str].from_failure(artifact_context)
        rendered = u.Cli.template_render(
            templates_root / template_relpath, artifact_context.value
        )
        if rendered.failure:
            return r[str].fail(
                f"{failure_prefix}"
                f"template={template_relpath}: "
                f"{rendered.error or 'template render failed'}"
            )
        return rendered

    def _artifact_render_context(
        self,
        *,
        dist: str,
        repository: m.Infra.RepositoryRef,
        repository_root: Path,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        destination: str,
        tooling_runtime: m.Infra.ToolingRuntimeContext,
        project_context: m.Infra.ProjectRenderContext | None,
        managed_artifacts: m.Infra.ProjectManagedArtifactsResolution | None = None,
    ) -> p.Result[p.Model]:
        """Resolve one governed artifact to its canonical typed render input."""
        if destination == c.Infra.GITIGNORE:
            profile = target.make_profile
            sections = [
                section
                for section in codegen.gitignore_sections
                if not section.profiles or profile in section.profiles
            ]
            if managed_artifacts is not None:
                project_patterns = managed_artifacts.artifacts.Gitignore.patterns
                if project_patterns:
                    sections.append(
                        m.Infra.ScaffoldGitignoreSectionSpec(
                            name=c.Infra.GITIGNORE_PROJECT_SECTION_NAME,
                            patterns=project_patterns,
                        )
                    )
            return r[p.Model].ok(
                m.Infra.GitignoreRenderSpec(gitignore_sections=tuple(sections))
            )
        if destination == ".pre-commit-config.yaml":
            return r[p.Model].ok(
                m.Infra.MakeWorkflowRenderSpec(dist=dist, make=codegen.make)
            )
        if destination in {
            ".markdownlint.json",
            ".markdownlintignore",
            ".qlty/qlty.toml",
        }:
            return r[p.Model].ok(
                m.Infra.MarkdownLintRenderSpec(tooling=config.Infra.tooling)
            )
        if destination == ".envrc":
            return r[p.Model].ok(
                m.Infra.EnvrcRenderSpec(
                    state_directory_name=codegen.toolchain.state_directory_name,
                    scratch_namespace=codegen.toolchain.scratch_namespace,
                    pycache_namespace=codegen.toolchain.pycache_namespace,
                    environment_path_prepends=(
                        codegen.toolchain.environment_path_prepends
                    ),
                    mise_bootstrap=(
                        FlextInfraCodegenConform._mise_bootstrap_environment()
                    ),
                    gascity=(
                        m.Infra.BeadsWorkspaceEnvironmentSpec()
                        if target.gascity_enabled
                        else None
                    ),
                )
            )
        if destination in {".mise.toml", ".python-version"}:
            # Computed toolchain fields are projections, not inputs: filter the
            # dump to the render spec's declared fields before construction.
            toolchain_data = {
                field_name: value
                for field_name, value in codegen.toolchain.model_dump().items()
                if field_name in m.Infra.MiseTomlRenderSpec.model_fields
            }
            toolchain_data["gascity_enabled"] = target.gascity_enabled
            return r[p.Model].ok(m.Infra.MiseTomlRenderSpec(**toolchain_data))

        if destination == c.Infra.BEADS_CONFIG_RELPATH:
            project_types = target.beads.custom_issue_types
            required_types = codegen.toolchain.beads.required_custom_types
            beads = codegen.toolchain.beads
            return r[p.Model].ok(
                m.Infra.BeadsConfigRenderSpec(
                    issue_prefix=target.beads.issue_prefix,
                    endpoint_origin=beads.endpoint_origin,
                    endpoint_status=beads.endpoint_status,
                    gascity_enabled=target.gascity_enabled,
                    custom_issue_types=tuple(
                        dict.fromkeys((*project_types, *required_types))
                    ),
                    dolt_mode=beads.dolt_mode,
                    export_auto=beads.export_auto,
                    backup_enabled=beads.backup_enabled,
                    dolt_disable_event_flush=beads.dolt_disable_event_flush,
                )
            )
        if destination == c.Infra.BEADS_METADATA_RELPATH:
            # Why: this marker is regenerated on every `make gen`, but the
            # ledger identity inside it is owned by the checkout, not by the
            # fleet SSOT. Rendering without it stripped the key, and Beads then
            # minted a NEW identity on next access — rig gmn lost
            # 2b1a0582-… that way (commit 3e7ba1e). Read it back so a
            # regeneration is identity-preserving.
            return r[p.Model].ok(
                m.Infra.BeadsMetadataRenderSpec(
                    database=target.beads.database,
                    project_id=self._beads_project_id(repository_root),
                )
            )
        if destination.startswith(".github/"):
            provider = self._repository_provider(repository, codegen)
            if provider.failure:
                return r[p.Model].from_failure(provider)
            workspace_repositories = (
                tuple(workspace.subprojects)
                if target.make_profile is c.Infra.MakeProfile.WORKSPACE
                else ()
            )
            # Why: ci.yml.j2 iterates this to build its push/pull_request branch
            # filters, so an unsupplied value fails the render outright. The
            # repository's own integration branch is the only branch this layer
            # can name from resolved data; a fleet-wide list hardcoded here would
            # make every repository trigger on branches it does not have.
            branch = u.Infra.resolve_integration_branch(workspace, provider.value)
            return r[p.Model].ok(
                m.Infra.GithubWorkflowRenderSpec(
                    dist=dist,
                    make_profile=target.make_profile,
                    gascity_enabled=target.gascity_enabled,
                    repository_branch=branch,
                    ci_trigger_branches=tuple(
                        dict.fromkeys((
                            *codegen.branch_policy.ci_trigger_branches,
                            branch,
                        ))
                    ),
                    python_version=codegen.toolchain.python_version,
                    state_directory_name=codegen.toolchain.state_directory_name,
                    dependency_cooldown_days=(
                        codegen.toolchain.dependency_cooldown_days
                    ),
                    github_actions=codegen.github_actions,
                    make=codegen.make,
                    workspace_repositories=workspace_repositories,
                    # Why: dependabot.yml.j2 branches on this and the model
                    # declares it, but the .github/ spec never supplied it, so
                    # every render died with "'has_devcontainer' is undefined".
                    # Dependabot rejects its ENTIRE config when an ecosystem
                    # names a directory that is absent, so this is read from the
                    # checkout rather than declared: a stale flag would silently
                    # disable Dependabot for the repository.
                    has_devcontainer=(repository_root / ".devcontainer").is_dir(),
                    checkout_submodules=codegen.checkout_submodules_overrides.get(
                        dist, codegen.checkout_submodules
                    ),
                    custom_steps=FlextInfraCodegenConform._custom_ci_steps(
                        repository_root
                    ),
                    private_submodules=codegen.ci_private_submodules.get(dist),
                    private_dependency_auth=codegen.ci_private_dependency_auth.get(
                        dist
                    ),
                    system_packages=tuple(codegen.ci_system_packages.get(dist, ())),
                )
            )
        destination_path = Path(destination)
        if (
            destination_path.parent.as_posix() == "tests/fixtures/ci/docker"
            and destination_path.suffix == ".Dockerfile"
        ):
            return r[p.Model].ok(
                m.Infra.DistroDockerRenderSpec(
                    package_name=dist.replace("-", "_"),
                    python_version=codegen.toolchain.python_version,
                    make=codegen.make,
                    mise_bootstrap=self._mise_bootstrap_environment(),
                )
            )
        if destination in {
            c.Infra.RELEASE_BUILD_CONSTRAINTS_PATH,
            c.Infra.RELEASE_GITLEAKS_CONFIG_PATH,
        }:
            # Why (flext-to3n7): the release build phase snapshots these two
            # policies from the repository; they are fleet policy owned by
            # config/infra.yaml, never scaffold-only project metadata.
            return r[p.Model].ok(
                m.Infra.ReleasePolicyRenderSpec(
                    build_constraints=config.Infra.release.build_constraints
                )
            )
        if destination == c.Infra.MAKEFILE_FILENAME:
            profile = target.make_profile
            subprojects = (
                tuple(workspace.subprojects)
                if profile is c.Infra.MakeProfile.WORKSPACE
                else ()
            )
            gitlinks = self._managed_gitlinks(workspace, codegen)
            if gitlinks.failure:
                return r[p.Model].from_failure(gitlinks)
            cooldown_exclusions, cooldown_overrides = self._dependency_cooldown_policy(
                repository, codegen.toolchain
            )
            return r[p.Model].ok(
                m.Infra.MakefileRenderSpec(
                    pytest=config.Infra.tooling.tools.pytest,
                    mise_bootstrap=self._mise_bootstrap_environment(),
                    dist=dist,
                    state_directory_name=codegen.toolchain.state_directory_name,
                    scratch_namespace=codegen.toolchain.scratch_namespace,
                    infra_cli=config.Infra.name,
                    make_profile=profile,
                    makefile_custom_include=c.Infra.MAKEFILE_CUSTOM_INCLUDE,
                    repository_root_rel=FlextInfraCodegenConform._repository_root_rel(
                        workspace
                    ),
                    workspace_subprojects=tuple(
                        item.path.as_posix() for item in workspace.subprojects
                    ),
                    workspace_repositories=subprojects,
                    workspace_gitlinks=gitlinks.value,
                    uv_link_mode=FlextInfraCodegenConform._link_mode(
                        repository, codegen.toolchain
                    ),
                    uv_version=codegen.toolchain.uv_version,
                    uv_exclude_newer=codegen.toolchain.uv_exclude_newer,
                    dependency_cooldown_exclusions=cooldown_exclusions,
                    dependency_cooldown_overrides=cooldown_overrides,
                    make=codegen.make,
                    extra_verbs=(
                        repository.extra_verbs
                        if repository.script_dispatch is None
                        else tuple(
                            dict.fromkeys((
                                *repository.extra_verbs,
                                *FlextInfraCodegenConform._discover_script_verbs(
                                    repository_root
                                ),
                            ))
                        )
                    ),
                    script_dispatch=repository.script_dispatch,
                    workspace_cli_group=c.Infra.CLI_GROUP_WORKSPACE,
                    mypy_memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
                    mypy_timeout_seconds=c.Infra.MYPY_TIMEOUT_SECONDS_DEFAULT,
                    mypy_timeout_exit_code=c.Infra.PROCESS_TIMEOUT_EXIT_CODE,
                    mypy_signal_exit_offset=c.Infra.PROCESS_SIGNAL_EXIT_OFFSET,
                    prlimit_command=c.Infra.PRLIMIT_COMMAND,
                    prlimit_address_space_option=(c.Infra.PRLIMIT_ADDRESS_SPACE_OPTION),
                    timeout_command=c.Infra.TIMEOUT_COMMAND,
                    timeout_kill_after_seconds=c.Infra.TIMEOUT_KILL_AFTER_SECONDS,
                    pytest_process_timeout_seconds=(
                        config.Infra.tooling.tools.pytest.process_timeout_seconds
                    ),
                )
            )
        if destination == c.Infra.CUSTOM_MAKE_FILENAME:
            # Existing repositories project custom routes from the same typed
            # Make contract as Makefile; they do not require scaffold-only
            # project metadata.
            make_context = FlextInfraCodegenConform.make_render_context(
                repository,
                target,
                workspace,
                codegen,
                tooling_runtime=tooling_runtime,
                repository_root=repository_root,
            )
            if make_context.failure:
                return r[p.Model].from_failure(make_context)
            return r[p.Model].ok(make_context.value)
        if destination in {
            c.Infra.MARKDOWNLINT_CONFIG_FILENAME,
            c.Infra.MARKDOWNLINT_IGNORE_FILENAME,
        }:
            return r[p.Model].ok(
                m.Infra.ToolingRenderSpec(tooling=config.Infra.tooling)
            )
        if project_context is not None:
            return r[p.Model].ok(project_context)
        context_result = self._project_render_context(
            repository,
            target,
            workspace,
            codegen,
            tooling_runtime=tooling_runtime,
            repository_root=repository_root,
            managed_artifacts=managed_artifacts,
        )
        if context_result.failure:
            return r[p.Model].from_failure(context_result)
        return r[p.Model].ok(context_result.value)

    @staticmethod
    def make_render_context(
        repository: m.Infra.RepositoryRef,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        *,
        tooling_runtime: m.Infra.ToolingRuntimeContext,
        repository_root: Path,
    ) -> p.Result[m.Infra.MakeRenderContext]:
        """Build the typed context consumed by the generated Makefile."""
        profile = target.make_profile
        subprojects = (
            tuple(workspace.subprojects)
            if profile is c.Infra.MakeProfile.WORKSPACE
            else ()
        )
        gitlinks = FlextInfraCodegenConform._managed_gitlinks(workspace, codegen)
        if gitlinks.failure:
            return r[m.Infra.MakeRenderContext].from_failure(gitlinks)
        cooldown_exclusions, cooldown_overrides = (
            FlextInfraCodegenConform._dependency_cooldown_policy(
                repository, codegen.toolchain
            )
        )
        extra_verbs = repository.extra_verbs
        if repository.script_dispatch is not None:
            discovered = FlextInfraCodegenConform._discover_script_verbs(
                repository_root
            )
            existing_names = {verb.name for verb in extra_verbs}
            extra_verbs = tuple(
                dict.fromkeys((*extra_verbs, *discovered))
            )
        return r[m.Infra.MakeRenderContext].ok(
            m.Infra.MakeRenderContext(
                pytest=config.Infra.tooling.tools.pytest,
                mise_bootstrap=(FlextInfraCodegenConform._mise_bootstrap_environment()),
                make=codegen.make,
                mypy_memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
                mypy_timeout_seconds=c.Infra.MYPY_TIMEOUT_SECONDS_DEFAULT,
                mypy_timeout_exit_code=c.Infra.PROCESS_TIMEOUT_EXIT_CODE,
                mypy_signal_exit_offset=c.Infra.PROCESS_SIGNAL_EXIT_OFFSET,
                prlimit_command=c.Infra.PRLIMIT_COMMAND,
                prlimit_address_space_option=c.Infra.PRLIMIT_ADDRESS_SPACE_OPTION,
                timeout_command=c.Infra.TIMEOUT_COMMAND,
                timeout_kill_after_seconds=c.Infra.TIMEOUT_KILL_AFTER_SECONDS,
                tooling_runtime=tooling_runtime,
                dist=repository.distribution,
                infra_cli=config.Infra.name,
                python_version=codegen.toolchain.python_version,
                uv_link_mode=FlextInfraCodegenConform._link_mode(
                    repository, codegen.toolchain
                ),
                uv_exclude_newer=codegen.toolchain.uv_exclude_newer,
                dependency_cooldown_exclusions=cooldown_exclusions,
                dependency_cooldown_overrides=cooldown_overrides,
                # ProjectRenderContext replaces this with the composed map.
                # Pass the neutral value explicitly so Pydantic never deep-copies
                # the MappingProxyType model default while building the base.
                ruff_per_file_ignores={},
                make_profile=profile,
                workspace_cli_group=c.Infra.CLI_GROUP_WORKSPACE,
                repository_root_rel=FlextInfraCodegenConform._repository_root_rel(
                    workspace
                ),
                makefile_custom_include=c.Infra.MAKEFILE_CUSTOM_INCLUDE,
                workspace_subprojects=tuple(
                    item.path.as_posix() for item in workspace.subprojects
                ),
                workspace_repositories=subprojects,
                workspace_gitlinks=gitlinks.value,
                extra_verbs=extra_verbs,
                script_dispatch=repository.script_dispatch,
            )
        )

    @staticmethod
    def _project_spec_from_existing(
        repository: m.Infra.RepositoryRef,
        repository_root: Path,
        codegen: m.Infra.CodegenConfigSpec,
    ) -> p.Result[m.Infra.ProjectSpec]:
        """Derive scaffold ProjectSpec from live PEP 621 metadata for existing trees."""
        metadata = u.Infra.read_project_metadata_result(repository_root)
        if metadata.failure:
            return r[m.Infra.ProjectSpec].from_failure(metadata)
        pep621 = metadata.value.project
        package_name = metadata.value.package_name
        class_stem = metadata.value.class_stem
        alias = u.Infra.package_alias(package_name=package_name)
        namespace = class_stem.removeprefix("Flext") or class_stem
        author = pep621.authors[0] if pep621.authors else None
        author_name = author.name if author is not None and author.name else ""
        author_email = author.email if author is not None and author.email else ""
        if not author_name or not author_email:
            return r[m.Infra.ProjectSpec].fail(
                f"existing pyproject is missing author name/email: {repository_root}"
            )
        homepage = pep621.urls.homepage or repository.url.removesuffix(".git")
        documentation = pep621.urls.documentation or homepage
        runtime_names = {
            name for item in pep621.dependencies if (name := u.Infra.dep_name(item))
        }
        profiles = codegen.scaffold.project.dependency_profiles
        upstream = next(
            (
                item.upstream
                for item in profiles
                if item.project is None
                and item.upstream.replace("_", "-") in runtime_names
            ),
            None,
        )
        if upstream is None:
            return r[m.Infra.ProjectSpec].fail(
                "no scaffold.project.dependency_profiles.upstream matches live "
                f"dependencies at {repository_root}"
            )
        licenses = codegen.scaffold.project.supported_licenses
        return r[m.Infra.ProjectSpec].ok(
            m.Infra.ProjectSpec(
                package_name=package_name,
                class_stem=class_stem,
                namespace=namespace,
                constant_name=repository.distribution,
                namespace_attribute=alias,
                alias=alias,
                environment_prefix=f"{package_name.upper()}_",
                description=pep621.description or repository.distribution,
                license=licenses[0],
                author_name=author_name,
                author_email=author_email,
                upstream=upstream,
                homepage=homepage,
                documentation=documentation,
                repository_root_rel=".",
                year=codegen.scaffold.project.copyright_year,
            )
        )

    @staticmethod
    def _project_render_context(
        repository: m.Infra.RepositoryRef,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        *,
        tooling_runtime: m.Infra.ToolingRuntimeContext,
        repository_root: Path,
        managed_artifacts: m.Infra.ProjectManagedArtifactsResolution | None = None,
    ) -> p.Result[m.Infra.ProjectRenderContext]:
        """Build the complete typed context consumed by project templates."""
        if workspace.project is None:
            # Existing checkouts declare no scaffold metadata: derive the render
            # identity from the live project metadata instead of failing, so
            # conforming a governed repository never depends on scaffold-only
            # declarations.
            metadata = u.Infra.read_project_metadata_result(repository_root)
            if metadata.failure:
                return r[m.Infra.ProjectRenderContext].from_failure(metadata)
            repository_provider = FlextInfraCodegenConform._repository_provider(
                repository, codegen
            )
            if repository_provider.failure:
                return r[m.Infra.ProjectRenderContext].from_failure(repository_provider)
            live_name = metadata.value.package_name
            class_stem = u.derive_class_stem(live_name)
            project = m.Infra.ProjectSpec(
                package_name=live_name,
                class_stem=class_stem,
                namespace=class_stem.removeprefix("Flext") or class_stem,
                constant_name=live_name,
                namespace_attribute=live_name,
                alias=u.Infra.package_alias(package_name=live_name),
                environment_prefix=f"{live_name.upper()}_",
                license=config.Infra.codegen.scaffold.project.supported_licenses[0],
                author_name="FLEXT Team",
                author_email="team@flext.dev",
                upstream=(
                    config.Infra.codegen.scaffold.project.dependency_profiles[
                        0
                    ].upstream
                ),
                homepage=f"{repository_provider.value.base_url.rstrip('/')}/",
                documentation=f"{repository_provider.value.base_url.rstrip('/')}/",
                repository_root_rel=".",
                year=time.localtime().tm_year,
                description=metadata.value.project.description,
            )
        else:
            project = workspace.project
        dependency_profile = next(
            (
                item
                for item in codegen.scaffold.project.dependency_profiles
                if item.project is None and item.upstream == project.upstream
            ),
            None,
        )
        if dependency_profile is None:
            return r[m.Infra.ProjectRenderContext].fail(
                f"unsupported scaffold upstream: {project.upstream}"
            )
        additions = tuple(
            item
            for item in codegen.scaffold.project.dependency_profiles
            if item.project == repository.distribution
        )
        if additions:
            dependency_profile = m.Infra.ScaffoldDependencyProfileSpec.model_validate({
                **dependency_profile.model_dump(),
                "runtime": tuple(
                    dict.fromkeys((
                        *dependency_profile.runtime,
                        *(
                            requirement
                            for item in additions
                            for requirement in item.runtime
                        ),
                    ))
                ),
                "codegen": tuple(
                    dict.fromkeys((
                        *dependency_profile.codegen,
                        *(
                            requirement
                            for item in additions
                            for requirement in item.codegen
                        ),
                    ))
                ),
            })
        if project.license not in codegen.scaffold.project.supported_licenses:
            supported = ", ".join(codegen.scaffold.project.supported_licenses)
            return r[m.Infra.ProjectRenderContext].fail(
                f"unsupported scaffold license: {project.license}; "
                f"supported licenses: {supported}"
            )
        profile = target.make_profile
        make_context = FlextInfraCodegenConform.make_render_context(
            repository,
            target,
            workspace,
            codegen,
            tooling_runtime=tooling_runtime,
            repository_root=repository_root,
        )
        if make_context.failure:
            return r[m.Infra.ProjectRenderContext].from_failure(make_context)
        repository_provider = FlextInfraCodegenConform._repository_provider(
            repository, codegen
        )
        if repository_provider.failure:
            return r[m.Infra.ProjectRenderContext].from_failure(repository_provider)
        flext_provider = repository_provider.value
        packaged_data_dirs = (
            tuple(
                data_dir
                for data_dir in config.Infra.tooling.tools.hatch.packaged_data_dirs
                if any(
                    profile in entry.profiles
                    and Path(entry.destination).parts
                    and Path(entry.destination).parts[0] == data_dir
                    for entry in codegen.templates.entries
                )
            )
            if profile is not c.Infra.MakeProfile.WORKSPACE
            else ()
        )
        # Emit only the .gitignore sections that apply to this profile: a
        # section with no declared profiles is universal; a workspace-only
        # section (subproject-directory allowlist and submodule/Beads
        # Beads coordination) never reaches a subproject or standalone .gitignore.
        profile_gitignore_sections = [
            section
            for section in codegen.gitignore_sections
            if not section.profiles or profile in section.profiles
        ]
        if managed_artifacts is not None:
            project_patterns = managed_artifacts.artifacts.Gitignore.patterns
            if project_patterns:
                profile_gitignore_sections.append(
                    m.Infra.ScaffoldGitignoreSectionSpec(
                        name=c.Infra.GITIGNORE_PROJECT_SECTION_NAME,
                        patterns=project_patterns,
                    )
                )
        # The repository's own pyproject.toml is the version SSOT; the release
        # protocol is its only writer, so conform reads it and never syncs it.
        # A tree that has no pyproject yet is being created: it starts at the
        # typed initial version and the protocol owns every change after that.
        version_result = (
            u.Infra.current_workspace_version(repository_root)
            if (repository_root / c.Infra.PYPROJECT_FILENAME).is_file()
            else r[str].ok(config.Infra.initial_project_version)
        )
        if version_result.failure:
            return r[m.Infra.ProjectRenderContext].from_failure(version_result)
        return r[m.Infra.ProjectRenderContext].ok(
            m.Infra.ProjectRenderContext(
                **make_context.value.model_dump(
                    by_alias=True,
                    exclude={"mise_bootstrap", "ruff_per_file_ignores"},
                    exclude_computed_fields=True,
                ),
                mise_bootstrap=FlextInfraCodegenConform._mise_bootstrap_environment(),
                scaffold=codegen.scaffold,
                gitignore_sections=tuple(profile_gitignore_sections),
                dependency_profile=dependency_profile,
                tooling=config.Infra.tooling,
                # Why: the fleet policy alone is not the effective Ruff contract.
                # A repository may carry an operator-authorized exemption in its
                # own config/*.yaml ManagedArtifacts block, and ensure_ruff
                # composes the two when it edits a pyproject in place. The
                # template rendered only the fleet map, so a full render silently
                # dropped the local overlay -- flext-infra's own _rope exemption
                # disappeared on every conform and returned 12 SLF001 findings
                # the operator had already ruled on. Compose here so both paths
                # produce the same effective map.
                ruff_per_file_ignores=(
                    FlextInfraEnsureRuffConfigPhase.compose_per_file_ignores(
                        repository_root, managed_artifacts=managed_artifacts
                    )
                ),
                environment_path_prepends=(codegen.toolchain.environment_path_prepends),
                beads_tool_selector=codegen.toolchain.beads.selector,
                beads_tool_version=codegen.toolchain.beads.version,
                # prerelease is load-bearing: every fork release of bd carries a
                # suffixed tag (-fdN) and mise refuses to resolve one unless
                # told the release is a prerelease. Omitting it silently pinned
                # every rig to upstream, which lacks the bd list cycle guard.
                beads_tool_prerelease=codegen.toolchain.beads.prerelease,
                beads=workspace.beads,
                canonical_project_name=target.canonical_project_name,
                const_name=project.constant_name,
                package_name=project.package_name,
                packaged_data_dirs=packaged_data_dirs,
                class_stem=project.class_stem,
                ns=project.namespace,
                ns_attr=project.namespace_attribute,
                alias=project.alias,
                env_prefix=project.environment_prefix,
                upstream=project.upstream,
                inherited_facets=project.inherited_facets,
                root_packages=project.root_packages,
                root_modules=project.root_modules,
                runtime_dependency_overlay=project.runtime_dependency_overlay,
                description=project.description,
                version=version_result.value,
                license=project.license,
                python_required_version=codegen.toolchain.python_required_version,
                kubectl_version=codegen.toolchain.kubectl_version,
                helm_version=codegen.toolchain.helm_version,
                kind_version=codegen.toolchain.kind_version,
                direnv_version=codegen.toolchain.direnv_version,
                uv_version=codegen.toolchain.uv_version,
                qlty_version=codegen.toolchain.qlty_version,
                node_version=codegen.toolchain.node_version,
                jscpd_version=codegen.toolchain.jscpd_version,
                waza_version=codegen.toolchain.waza_version,
                taplo_version=codegen.toolchain.taplo_version,
                ast_grep_version=codegen.toolchain.ast_grep_version,
                gitleaks_version=codegen.toolchain.gitleaks_version,
                scc_version=codegen.toolchain.scc_version,
                kubeconform_version=codegen.toolchain.kubeconform_version,
                go_version=codegen.toolchain.go_version,
                author_name=project.author_name,
                author_email=project.author_email,
                repository=project.homepage,
                homepage=project.homepage,
                documentation=project.documentation,
                flext_git_base_url=flext_provider.base_url,
                flext_git_branch=flext_provider.branch,
                repository_provider=repository.provider,
                repository_git_url=repository.url,
                repository_branch=u.Infra.resolve_integration_branch(
                    workspace, repository_provider.value
                ),
                year=project.year,
            )
        )

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
            planned = self._file_plan(root, policy.filename, read.value)
            if planned.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(planned)
            plans.append(planned.value)
        layout = u.Infra.layout(root)
        if layout is not None and layout.class_stem:
            rendered = u.Infra.render_utility_facade(layout.package_dir)
            if rendered is not None:
                relative = (layout.package_dir / c.Infra.UTILITIES_PY).relative_to(root)
                utility_plan = self._file_plan(root, relative.as_posix(), rendered)
                if utility_plan.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                        utility_plan
                    )
                plans.append(utility_plan.value)
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(plans))

    @staticmethod
    def validate_custom_make(
        content: str, policy: m.Infra.CustomHandlerPolicy
    ) -> p.Result[bool]:
        """Reject public targets, aliases, includes, and toolchain declarations."""
        target_re = re.compile(policy.target_pattern)
        in_define = False
        # Collapse backslash continuation lines before validating so that
        # directives like `.PHONY` can span multiple physical lines. Only
        # collapse non-recipe lines (recipe lines start with whitespace and are
        # skipped below); the reported line number is the first physical line.
        logical_lines: list[tuple[int, str]] = []
        pending_line: str | None = None
        pending_number: int = 0
        for line_number, raw_line in enumerate(content.splitlines(), start=1):
            if (
                raw_line
                and not raw_line[0].isspace()
                and raw_line.rstrip().endswith("\\")
            ):
                trimmed = raw_line.rstrip()[:-1].rstrip()
                if pending_line is None:
                    pending_line = trimmed
                    pending_number = line_number
                else:
                    pending_line += " " + trimmed
                continue
            # A continuation collapses several physical lines into one logical
            # line, which is reported at the line the continuation STARTED on,
            # not the line it ended on. Assigning back onto the loop variables
            # made the two indistinguishable and left the next iteration reading
            # a value the iterator never produced.
            logical_line = raw_line
            logical_number = line_number
            if pending_line is not None:
                joined = pending_line + " " + raw_line.strip()
                if joined.rstrip().endswith("\\"):
                    pending_line = joined.rstrip()[:-1].rstrip()
                    continue
                logical_line = joined
                logical_number = pending_number
                pending_line = None
            logical_lines.append((logical_number, logical_line))
        if pending_line is not None:
            if pending_line.startswith(".PHONY:"):
                return r[bool].fail(
                    f"{policy.filename} has an unterminated .PHONY continuation"
                )
            logical_lines.append((pending_number, pending_line))
        for line_number, raw_line in logical_lines:
            if in_define:
                in_define = not raw_line.startswith("endef")
                continue
            if raw_line.startswith("define "):
                if not policy.allow_toolchain_declarations:
                    return r[bool].fail(
                        f"{policy.filename} line {line_number} "
                        "declares a macro, which this profile forbids"
                    )
                in_define = True
                continue
            if not raw_line or raw_line.lstrip().startswith("#"):
                continue
            if raw_line[0].isspace():
                continue
            if c.Infra.MAKE_CONDITIONAL_RE.match(raw_line):
                continue
            if raw_line.startswith(".PHONY:"):
                declaration = raw_line.partition(":")[2].strip()
                names = declaration.split()
                if names and all(target_re.fullmatch(name) for name in names):
                    continue
            target = raw_line.partition(":")[0].strip() if ":" in raw_line else ""
            if target and target_re.fullmatch(target):
                continue
            if c.Infra.MAKE_ASSIGNMENT_RE.match(
                raw_line
            ) or c.Infra.MAKE_DIRECTIVE_RE.match(raw_line):
                if policy.allow_toolchain_declarations:
                    continue
                return r[bool].fail(
                    f"{policy.filename} line {line_number} "
                    "declares a variable, which this profile forbids"
                )
            if target and policy.allow_public_targets:
                continue
            return r[bool].fail(
                f"{policy.filename} line {line_number} is not a private custom handler"
            )
        return r[bool].ok(True)

    @staticmethod
    def _file_plan(
        root: Path,
        relative_path: str,
        rendered: str,
        *,
        mode: int = 0o644,
        source_states: t.VariadicTuple[m.Cli.AtomicFileState] = (),
    ) -> p.Result[m.Infra.CodegenFilePlan]:
        """Snapshot one target and bind it to exact desired bytes and mode."""
        project = root.expanduser().absolute()
        path = (project / relative_path).absolute()
        # Generation owns the destination directory of every artifact it
        # declares. Reading the before-state of a declared file whose parent
        # does not exist yet fails on the missing parent rather than reporting
        # an absent file, so a repository that has never rendered a nested
        # artifact — `.beads/config.yaml` on a fresh clone — could not even be
        # planned. Materializing the empty destination is idempotent and is the
        # generator's own responsibility.
        path.parent.mkdir(parents=True, exist_ok=True)
        before = u.Cli.atomic_read_binary_file_state(path, required=False)
        if before.failure:
            return r[m.Infra.CodegenFilePlan].from_failure(before)
        return r[m.Infra.CodegenFilePlan].ok(
            m.Infra.CodegenFilePlan(
                project=project,
                path=path,
                before=before.value,
                desired_content=rendered.encode(c.Cli.ENCODING_DEFAULT),
                desired_mode=mode,
                source_states=source_states,
            )
        )

    @staticmethod
    def _technical_branch(reference: str, patterns: t.StrSequence) -> bool:
        """Match one Git ref against the typed technical-branch policy."""
        short = reference
        for prefix in ("refs/heads/", "refs/remotes/origin/"):
            if short.startswith(prefix):
                short = short.removeprefix(prefix)
                break
        return any(
            fnmatchcase(short, pattern) or fnmatchcase(reference, pattern)
            for pattern in patterns
        )

    @classmethod
    def _branch_ancestry_plan(
        cls, target: m.Infra.RepositoryConformTarget
    ) -> p.Result[m.Infra.BranchAncestryPlan]:
        """Inventory local governed refs and prove descent from the baseline."""
        root = target.root
        baseline_reference = target.baseline_reference
        baseline_command = (c.Infra.GIT, "rev-parse", "--verify", baseline_reference)
        baseline_result = u.Cli.run_raw(baseline_command, cwd=root)
        if baseline_result.failure:
            return r[m.Infra.BranchAncestryPlan].fail(
                "provider baseline command failed: "
                f"command={' '.join(baseline_command)}; error={baseline_result.error}"
            )
        if baseline_result.value.outcome.raw_return_code != 0:
            return r[m.Infra.BranchAncestryPlan].fail(
                "provider baseline ref is missing: "
                f"{baseline_reference}; command={' '.join(baseline_command)}; "
                f"exit={baseline_result.value.outcome.raw_return_code}; "
                f"stderr={baseline_result.value.stderr.strip() or '<empty>'}"
            )
        baseline_sha = baseline_result.value.stdout.strip()
        # flext-9ehwb: `refs/remotes/origin/<lane>` is the remote's LIVE tip.
        # `actions/checkout` fetches at job start, so that tip advances whenever
        # another actor publishes to the same lane while this run waits in the
        # queue. Gating against it asks "has this commit already absorbed work
        # published after it was written?" -- unanswerable by construction, and
        # a perfectly linear commit fails with "does not descend from"
        # (run 31218338222). The question the gate actually owns is "was this
        # commit written on top of the lane?", so the baseline is pinned to the
        # merge base between the live tip and the commit that triggered the run.
        # That point is immutable for a given commit: concurrent publishers move
        # the tip, never the merge base. Outside CI GITHUB_SHA is unset and the
        # live tip remains the baseline, which is correct for a local checkout.
        triggering_sha = os.environ.get(c.Infra.ENV_VAR_GITHUB_SHA, "").strip()
        if triggering_sha:
            # GITHUB_SHA is the superproject's triggering commit (the PR
            # merge commit actions/checkout synthesizes). Inside a submodule
            # repo that SHA does not exist, so `git merge-base` fails with
            # exit 128 ("Not a valid commit name") and breaks `gen check` in
            # CI. Verify membership before anchoring the baseline through it:
            # only pin to the merge base when triggering_sha actually resolves
            # in the current repository (the workspace root). In a submodule
            # context the gitlink position is the immutable reference and the
            # live baseline tip remains the correct anchor.
            verify_command = (c.Infra.GIT, "cat-file", "-t", triggering_sha)
            verify_result = u.Cli.run_raw(verify_command, cwd=root)
            if verify_result.success and u.Cli.process_succeeded(
                verify_result.value.outcome
            ):
                merge_base_command = (
                    c.Infra.GIT,
                    "merge-base",
                    baseline_sha,
                    triggering_sha,
                )
                merge_base_result = u.Cli.run_raw(merge_base_command, cwd=root)
                if merge_base_result.failure:
                    return r[m.Infra.BranchAncestryPlan].fail(
                        "cannot anchor ancestry baseline to the triggering commit: "
                        f"command={' '.join(merge_base_command)}; "
                        f"error={merge_base_result.error}"
                    )
                if merge_base_result.value.outcome.raw_return_code != 0:
                    return r[m.Infra.BranchAncestryPlan].fail(
                        "triggering commit shares no history with the baseline: "
                        f"{c.Infra.ENV_VAR_GITHUB_SHA}={triggering_sha}; "
                        f"command={' '.join(merge_base_command)}; "
                        f"exit={merge_base_result.value.outcome.raw_return_code}; "
                        f"stderr={merge_base_result.value.stderr.strip() or '<empty>'}"
                    )
                baseline_sha = merge_base_result.value.stdout.strip()
        pending_merge_result = u.Cli.run_raw(
            (
                c.Infra.GIT,
                "merge-base",
                "--is-ancestor",
                baseline_sha,
                c.Infra.GIT_MERGE_HEAD,
            ),
        )
        if conformed.failure:
            return r[bool].from_failure(conformed)
        return u.Cli.run_checked([c.Infra.UV, "lock", "--project", str(root)], cwd=root)


__all__: list[str] = ["FlextInfraCodegenConform"]
