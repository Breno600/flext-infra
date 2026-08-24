"""Unified, fail-closed conformance for new and existing repositories.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import re
import sys
import time
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Annotated, override

from flext_core import r
from flext_infra import config, p
from flext_infra.base import s
from flext_infra.basemk.custom_policy import FlextInfraCustomMkPolicy
from flext_infra.codegen.managed_conflicts import FlextInfraCodegenManagedConflicts
from flext_infra.constants import c
from flext_infra.deps.modernizer import FlextInfraPyprojectModernizer
from flext_infra.models import m
from flext_infra.services.codegen import FlextInfraCodegen
from flext_infra.typings import t
from flext_infra.utilities import u
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector


class FlextInfraCodegenConform(s[m.Infra.CodegenResult]):
    """Plan every selected output, then atomically write only a clean plan."""

    @staticmethod
    def _managed_pyproject_state(
        root: Path, codegen: m.Infra.CodegenConfigSpec
    ) -> p.Result[tuple[str, p.ProjectMetadata]]:
        """Load metadata from the recoverable owner projection without writing."""
        pyproject = root / c.Infra.PYPROJECT_FILENAME
        read = u.Cli.files_read_text(pyproject)
        if read.failure:
            return r[tuple[str, p.ProjectMetadata]].fail(
                read.error or f"pyproject read failed: {pyproject}"
            )
        owners = tuple(
            managed
            for managed in codegen.managed_files
            if managed.path.as_posix() == c.Infra.PYPROJECT_FILENAME
        )
        if len(owners) != 1:
            return r[tuple[str, p.ProjectMetadata]].fail(
                "pyproject managed owner must resolve exactly once"
            )
        recovered = FlextInfraCodegenManagedConflicts.recover_toml(
            read.value, conflict_sections=owners[0].conflict_sections
        )
        if recovered.failure:
            return r[tuple[str, p.ProjectMetadata]].fail(
                recovered.error or f"managed pyproject recovery failed: {pyproject}"
            )
        payload = u.Cli.toml_mapping_from_text(recovered.value)
        if payload is None:
            return r[tuple[str, p.ProjectMetadata]].fail(
                f"managed pyproject remains invalid TOML after recovery: {pyproject}"
            )
        try:
            document = m.PyprojectDocument.model_validate(payload)
        except c.ValidationError as exc:
            return r[tuple[str, p.ProjectMetadata]].fail_op(
                f"managed pyproject metadata validation ({pyproject})", exc
            )
        metadata = u.build_project_metadata(root.resolve(), document)
        return r[tuple[str, p.ProjectMetadata]].ok((recovered.value, metadata))

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
                    dependencies_only=True,
                    delegates=False,
                    templates=False,
                    custom=False,
                )
            case c.Infra.CodegenConformSurface.PYPROJECT:
                return m.Infra.CodegenConformSurfaceContract(
                    destinations=frozenset({c.Infra.PYPROJECT_FILENAME}),
                    delegates=False,
                    templates=False,
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

    # NOTE (multi-agent, mro-wkii.17 / agent: codex): this is the only
    # orchestrator for Make/toolchain/source conformance. Rendering stays in
    # flext-cli; Git-source TOML policy and attached detection are composed from
    # their separately owned u.Infra/workspace services.
    request: Annotated[
        m.Infra.CodegenConformRequest | None,
        m.Field(default=None, exclude=True, description="Validated conform request"),
    ] = None
    initial_workspace: Annotated[
        m.Infra.WorkspaceSpec | None,
        m.Field(
            default=None,
            exclude=True,
            description="Validated initial manifest included in the atomic plan",
        ),
    ] = None

    @classmethod
    def execute_request(
        cls,
        request: m.Infra.CodegenConformRequest,
        initial_workspace: m.Infra.WorkspaceSpec | None = None,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Execute one already validated public CLI request."""
        service = cls(
            workspace_root=request.root.expanduser().resolve(),
            request=request,
            initial_workspace=initial_workspace,
        )
        return service.execute()

    @override
    def execute(self) -> p.Result[m.Infra.CodegenResult]:
        """Run check or apply and require a verified fixed point."""
        request = self.request or m.Infra.CodegenConformRequest(
            root=self.workspace_root
        )
        u.Cli.header("Codegen Conform")
        u.Cli.info(
            f"stage=plan mode={request.mode} scope={request.scope} "
            f"what={request.what} root={request.root}"
        )
        planned = self.plan(request)
        if planned.failure:
            return r[m.Infra.CodegenResult].fail(
                planned.error or "codegen conform planning failed"
            )
        plan = planned.value
        mode = c.Infra.CodegenConformMode(request.mode)
        # Ledger routing is verified before drift reporting so a namespace
        for beads_plan in plan.beads:
            verified_beads = self._verify_beads_plan(beads_plan)
            if verified_beads.failure:
                return r[m.Infra.CodegenResult].fail(
                    verified_beads.error or "Beads ledger verification failed"
                )
        # A declared workflow hook that was never installed is drift exactly
        # like a stale managed file: check reports it, apply activates it.
        for hooks_plan in plan.hooks:
            verified_hooks = self._verify_hooks_plan(
                hooks_plan, allow_missing=mode is not c.Infra.CodegenConformMode.CHECK
            )
            if verified_hooks.failure:
                return r[m.Infra.CodegenResult].fail(
                    verified_hooks.error or "git hook verification failed"
                )
        changed = tuple(file for file in plan.files if file.changed)
        if mode is c.Infra.CodegenConformMode.CHECK:
            if changed:
                paths = ", ".join(str(file.path) for file in changed)
                return r[m.Infra.CodegenResult].fail(f"codegen drift detected: {paths}")
            return r[m.Infra.CodegenResult].ok(m.Infra.CodegenResult(plan=plan))
        written: list[Path] = []
        total_changed = len(changed)
        u.Cli.info(f"stage=apply changed={total_changed}")
        for write_index, file in enumerate(changed, start=1):
            u.Cli.emit_raw(f"  write [{write_index}/{total_changed}] {file.path}\n")
            if file.absent:
                target = file.path.expanduser().resolve()
                try:
                    target.relative_to(plan.request.root.expanduser().resolve())
                except ValueError:
                    return r[m.Infra.CodegenResult].fail(
                        f"absent path escapes repository root: {file.path}"
                    )
                if target.exists():
                    if not target.is_file():
                        return r[m.Infra.CodegenResult].fail(
                            f"absent path is not a regular file: {target}"
                        )
                    removed = r.create_from_callable(
                        lambda path=target: (path.unlink(), path)[1],
                        error_code="E_CODEGEN_ABSENT_UNLINK",
                    )
                    if removed.failure:
                        return r[m.Infra.CodegenResult].fail(
                            removed.error or f"absent path unlink failed: {target}"
                        )
                written.append(file.path)
                continue
            result = u.Cli.atomic_write_text_file(file.path, file.rendered)
            if result.failure:
                return r[m.Infra.CodegenResult].fail(
                    result.error
                    or (
                        f"stage=apply position={write_index}/{total_changed} "
                        f"path={file.path}: atomic write failed"
                    )
                )
            written.append(file.path)
        u.Cli.info("stage=verify-fixed-point")
        # Activate the hooks the emitted config declares. This runs before the
        # fixed-point re-plan so that verification observes the installed state.
        for hooks_plan in plan.hooks:
            installed_hooks = self._install_hooks_plan(hooks_plan)
            if installed_hooks.failure:
                return r[m.Infra.CodegenResult].fail(
                    installed_hooks.error or "git hook installation failed"
                )
        verified = self.plan(request)
        if verified.failure:
            return r[m.Infra.CodegenResult].fail(
                verified.error
                or "stage=verify-fixed-point: post-apply conform verification failed"
            )
        verified_plan = verified.value
        residual = tuple(file for file in verified_plan.files if file.changed)
        if residual:
            paths = ", ".join(str(file.path) for file in residual)
            return r[m.Infra.CodegenResult].fail(
                f"codegen apply did not reach a fixed point: {paths}"
            )
        return r[m.Infra.CodegenResult].ok(
            m.Infra.CodegenResult(plan=verified_plan, written_files=tuple(written))
        )

    def plan(
        self, request: m.Infra.CodegenConformRequest
    ) -> p.Result[m.Infra.CodegenPlan]:
        """Build and validate the complete selection without writing."""
        config_spec = config.Infra.codegen
        root = request.root.expanduser().resolve()
        workspace_root = root
        workspace = self.initial_workspace
        prepared_pyprojects: dict[Path, tuple[str, p.ProjectMetadata]] = {}
        current_pyproject_state: tuple[str, p.ProjectMetadata] | None = None
        if self.initial_workspace is None:
            current_pyproject = self._managed_pyproject_state(root, config_spec)
            if current_pyproject.failure:
                return r[m.Infra.CodegenPlan].fail(
                    current_pyproject.error
                    or f"managed pyproject preparation failed: {root}"
                )
            current_pyproject_state = current_pyproject.value
            prepared_pyprojects[root] = current_pyproject_state
        if workspace is None:
            topology_result = FlextInfraWorkspaceDetector.resolve_topology_roots(root)
            if topology_result.failure:
                return r[m.Infra.CodegenPlan].fail(
                    topology_result.error or "workspace topology resolution failed"
                )
            resolved_root, identity_root, governing_root = topology_result.value
            workspace_root = (
                resolved_root if identity_root == governing_root else governing_root
            )
            workspace_result = FlextInfraWorkspaceDetector.load_workspace_spec(
                workspace_root,
                project_metadata=(
                    current_pyproject_state[1]
                    if workspace_root == root and current_pyproject_state is not None
                    else None
                ),
            )
            if workspace_result.failure:
                return r[m.Infra.CodegenPlan].fail(
                    workspace_result.error or "workspace manifest load failed"
                )
            workspace = workspace_result.value
        current_repository = workspace.repository
        if self.initial_workspace is not None and root != workspace_root:
            try:
                current_path = root.relative_to(workspace_root).as_posix()
            except ValueError as exc:
                return r[m.Infra.CodegenPlan].fail_op(
                    "repository workspace resolution", exc
                )
            current_matches = tuple(
                repository
                for repository in workspace.members
                if repository.path.as_posix() == current_path
            )
            if len(current_matches) != 1:
                return r[m.Infra.CodegenPlan].fail(
                    f"repository is not one declared workspace member: {current_path}"
                )
            current_repository = current_matches[0]
        if self.initial_workspace is None:
            if current_pyproject_state is None:
                return r[m.Infra.CodegenPlan].fail(
                    f"existing repository has no prepared pyproject: {root}"
                )
            current_target_result = FlextInfraWorkspaceDetector.conform_target(
                root, workspace, project_metadata=current_pyproject_state[1]
            )
            if current_target_result.failure:
                return r[m.Infra.CodegenPlan].fail(
                    current_target_result.error
                    or "repository conformance target resolution failed"
                )
            current_target = current_target_result.value
            current_repository = current_target.repository
        else:
            baseline_branch_result = u.Infra.repository_baseline_branch(
                root,
                fallback=next(
                    item.branch
                    for item in config_spec.providers
                    if item.name == current_repository.provider
                ),
            )
            if baseline_branch_result.failure:
                return r[m.Infra.CodegenPlan].fail(
                    baseline_branch_result.error
                    or f"integration baseline resolution failed: {root}"
                )
            current_repository_role = current_repository.role
            current_make_profile = {
                c.Infra.RepositoryRole.WORKSPACE_ROOT: (
                    c.Infra.MakeProfile.WORKSPACE_ROOT
                ),
                c.Infra.RepositoryRole.WORKSPACE_MEMBER: (
                    c.Infra.MakeProfile.WORKSPACE_MEMBER
                ),
                c.Infra.RepositoryRole.STANDALONE: c.Infra.MakeProfile.STANDALONE,
            }[current_repository_role]
            current_target = m.Infra.RepositoryConformTarget(
                repository=current_repository,
                root=root,
                make_profile=current_make_profile,
                beads_enabled=(
                    current_make_profile is c.Infra.MakeProfile.WORKSPACE_ROOT
                ),
                routing_only=False,
                canonical_project_name=current_repository.distribution,
                baseline_branch=baseline_branch_result.value,
                ci_enabled=True,
                external_dependency_paths=workspace.external_dependency_paths,
                technical_branch_patterns=(
                    config_spec.branch_policy.technical_branch_patterns
                ),
                governed_branch_patterns=(
                    config_spec.branch_policy.governed_branch_patterns
                ),
            )
        selected_result = self._select_repositories(
            request, workspace, current_repository
        )
        if selected_result.failure:
            return r[m.Infra.CodegenPlan].fail(
                selected_result.error or "repository selection failed"
            )
        selected = selected_result.value
        contract = self._surface_contract(c.Infra.CodegenConformSurface(request.what))
        files: list[m.Infra.CodegenFilePlan] = []
        environments: list[m.Infra.UvEnvironmentPlan] = []
        beads_plans: list[m.Infra.BeadsPlan] = []
        hooks_plans: list[m.Infra.HooksPlan] = []
        ancestry_plans: list[m.Infra.BranchAncestryPlan] = []
        total_repositories = len(selected)
        u.Cli.info(f"stage=plan repositories={total_repositories}")
        for repository_index, repository in enumerate(selected, start=1):
            repository_started = time.monotonic()
            u.Cli.progress(
                repository_index, total_repositories, repository.name, "conform"
            )
            repository_root = (
                current_target.root
                if repository.name == current_target.repository.name
                else self._repository_root(workspace_root, workspace, repository)
            )
            repository_root = repository_root.resolve()
            if repository_root.exists() and not repository_root.is_dir():
                return r[m.Infra.CodegenPlan].fail(
                    f"declared repository path is not a directory: {repository_root}"
                )
            if not repository_root.is_dir() and self.initial_workspace is None:
                return r[m.Infra.CodegenPlan].fail(
                    f"declared repository checkout is missing: {repository_root}"
                )
            pyproject_state = prepared_pyprojects.get(repository_root)
            is_scaffold_root = (
                self.initial_workspace is not None
                and repository.name == workspace.repository.name
            )
            if pyproject_state is None and not is_scaffold_root:
                prepared = self._managed_pyproject_state(repository_root, config_spec)
                if prepared.failure:
                    return r[m.Infra.CodegenPlan].fail(
                        prepared.error
                        or f"managed pyproject preparation failed: {repository_root}"
                    )
                pyproject_state = prepared.value
                prepared_pyprojects[repository_root] = pyproject_state
            if repository.name == current_target.repository.name:
                target = current_target
            else:
                if pyproject_state is None:
                    return r[m.Infra.CodegenPlan].fail(
                        f"existing repository has no prepared pyproject: {repository_root}"
                    )
                target_result = FlextInfraWorkspaceDetector.conform_target(
                    repository_root, workspace, project_metadata=pyproject_state[1]
                )
                if target_result.failure:
                    return r[m.Infra.CodegenPlan].fail(
                        target_result.error
                        or f"repository target resolution failed: {repository_root}"
                    )
                target = target_result.value
            # NOTE (multi-agent, mro-45r9): attached members consume the parent
            # topology SSOT; a duplicate member-local manifest is never required.
            # mro-j47u (codex): existing repositories cannot reach the scaffold
            # catalog. Project creation is the only template-rendering lifecycle.
            if is_scaffold_root:
                repository_plan = self._plan_scaffold_repository(
                    root=repository_root,
                    repository=repository,
                    target=target,
                    workspace=workspace,
                    codegen=config_spec,
                    contract=contract,
                )
            else:
                if pyproject_state is None:
                    return r[m.Infra.CodegenPlan].fail(
                        f"existing repository has no prepared pyproject: {repository_root}"
                    )
                repository_plan = self._plan_existing_repository(
                    root=repository_root,
                    workspace_root=workspace_root,
                    repository=repository,
                    target=target,
                    workspace=workspace,
                    codegen=config_spec,
                    contract=contract,
                    pyproject_source=pyproject_state[0],
                    project_metadata=pyproject_state[1],
                )
            if repository_plan.failure:
                return r[m.Infra.CodegenPlan].fail(
                    repository_plan.error
                    or (
                        f"stage=plan position={repository_index}/"
                        f"{total_repositories} repository={repository.name}: "
                        f"repository planning failed: {repository_root}"
                    )
                )
            ast_grep_plan = self._plan_ast_grep_surfaces(
                root=repository_root, codegen=config_spec, contract=contract
            )
            if ast_grep_plan.failure:
                return r[m.Infra.CodegenPlan].fail(
                    ast_grep_plan.error
                    or (
                        f"stage=plan position={repository_index}/"
                        f"{total_repositories} repository={repository.name}: "
                        f"ast-grep rule projection failed: {repository_root}"
                    )
                )
            governed = self._complete_governed_plans(
                repository_root,
                (*repository_plan.value, *ast_grep_plan.value),
                config_spec,
                contract,
                profile=target.make_profile,
                workspace=workspace,
            )
            if governed.failure:
                return r[m.Infra.CodegenPlan].fail(
                    governed.error
                    or (
                        f"stage=plan position={repository_index}/"
                        f"{total_repositories} repository={repository.name}: "
                        f"artifact ownership planning failed: {repository_root}"
                    )
                )
            files.extend(governed.value)
            environments.append(
                self._uv_environment_plan(
                    root=repository_root,
                    workspace_root=workspace_root,
                    target=target,
                    workspace=workspace,
                    config=config_spec,
                )
            )
            ledger_identity = self.ledger_identity_for_target(workspace, target)
            ledger_root_result = self._beads_ledger_root(repository_root)
            if ledger_root_result.failure:
                return r[m.Infra.CodegenPlan].fail(
                    ledger_root_result.error
                    or f"unable to resolve Beads ledger root: {repository_root}"
                )
            beads_plans.append(
                m.Infra.BeadsPlan(
                    repository_root=repository_root,
                    enabled=target.beads_enabled,
                    # Why (ai-hub-qwoc): canonical_prefix verifies the LIVE
                    # Beads ledger's issue-prefix (hyphenated, matches real
                    # issue IDs) -- it must never be workspace.ledger_id,
                    # which is the separate Dolt-safe database identifier and
                    # can differ (e.g. "ai_hub" database vs "ai-hub" issues).
                    # Why (mro-dz4ib / mro-cdzxf): WORKSPACE_MEMBER targets
                    # inherit the governing workspace's prefix, because a
                    # member consumes that ledger and owns none of its own.
                    # A workspace that declares no ledger yields no identity,
                    # and this plan is then never `enabled`, so the prefix is
                    # carried for reporting from the repository's own name.
                    canonical_prefix=(
                        ledger_identity[0]
                        if ledger_identity is not None
                        else target.canonical_project_name
                    ),
                    ledger_root=ledger_root_result.value,
                    ledger_id=workspace.ledger_id,
                )
            )
            # A repository the plan is about to CREATE has no git directory to
            # interrogate yet, so it carries no hook plan: hooks belong to a
            # provisioned checkout, and the next conform run over it plans them.
            hooks_directory = (
                self._hooks_directory(repository_root)
                if (repository_root / c.Infra.GIT_DIR).exists()
                else None
            )
            if hooks_directory is not None:
                if hooks_directory.failure:
                    return r[m.Infra.CodegenPlan].fail(
                        hooks_directory.error
                        or f"unable to resolve git hooks directory: {repository_root}"
                    )
                declared_stages = self._declared_hook_stages(
                    config_spec.make, target.make_profile
                )
                hooks_plans.append(
                    m.Infra.HooksPlan(
                        repository_root=repository_root,
                        hooks_directory=hooks_directory.value,
                        stages=declared_stages,
                        # Every workflow stage this profile does NOT declare is
                        # retired here, so a profile losing its hook config also
                        # loses the installed shim that pointed at it.
                        retired_stages=tuple(
                            stage
                            for stage in self._workflow_hook_stages(config_spec.make)
                            if stage not in declared_stages
                        ),
                    )
                )
            if self.initial_workspace is None:
                ancestry_result = self._branch_ancestry_plan(target)
                if ancestry_result.failure:
                    return r[m.Infra.CodegenPlan].fail(
                        ancestry_result.error
                        or (
                            f"stage=plan position={repository_index}/"
                            f"{total_repositories} repository={repository.name}: "
                            f"branch ancestry inventory failed: {repository_root}"
                        )
                    )
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
                beads=tuple(beads_plans),
                hooks=tuple(hooks_plans),
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
        owned_destinations = frozenset(
            destination
            for claim in codegen.managed_destination_ownership
            if claim.project == root.name
            for destination in claim.destinations
        )
        for file in planned:
            relative = file.path.relative_to(root)
            governed = governed_by_path.get(relative)
            if governed is None:
                completed.append(file)
                continue
            represented.add(relative)
            completed.append(
                file.model_copy(
                    update={"owner": governed.owner, "policy": governed.policy}
                )
            )
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
                    # Why: profile-excluded managed workflows must not survive as
                    # "keep current" ghosts (ci-matrix on workspace-member).
                    if (
                        relative.parts[:2] == (".github", "workflows")
                        and path.is_file()
                    ):
                        orphan_read = u.Cli.files_read_text(path)
                        if orphan_read.failure:
                            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                                orphan_read.error
                                or f"orphan workflow read failed: {path}"
                            )
                        # A project may own hand-written source at a managed
                        # destination its profile does not inherit. Keep it, but
                        # only while it is not itself a generated projection, so
                        # a retired projection is still pruned.
                        if (
                            relative.as_posix() in owned_destinations
                            and c.Infra.TEMPLATE_GENERATED_MARKER
                            not in orphan_read.value
                        ):
                            continue
                        completed.append(
                            m.Infra.CodegenFilePlan(
                                path=path,
                                owner=governed.owner,
                                policy=governed.policy,
                                rendered="",
                                expected_sha256=u.Cli.sha256_content(""),
                                current_sha256=u.Cli.sha256_content(orphan_read.value),
                                changed=True,
                                absent=True,
                            )
                        )
                    continue
            current = ""
            if path.is_file():
                read = u.Cli.files_read_text(path)
                if read.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                        read.error or f"governed artifact read failed: {path}"
                    )
                current = read.value
            digest = u.Cli.sha256_content(current) if path.is_file() else ""
            if (
                governed.policy == "merge"
                and governed.owner == c.Infra.CODEGEN_OWNER_VSCODE
            ):
                # Owner-merge dispatch: owners with a canonical document merge
                # (vscode settings today) produce their rendered content here.
                merged = FlextInfraCodegen.render_vscode_settings(root)
                if merged.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                        merged.error or f"vscode settings merge failed: {path}"
                    )
                if merged.value != current:
                    completed.append(
                        m.Infra.CodegenFilePlan(
                            path=path,
                            owner=governed.owner,
                            policy=governed.policy,
                            rendered=merged.value,
                            expected_sha256=u.Cli.sha256_content(merged.value),
                            current_sha256=digest,
                            changed=True,
                        )
                    )
                    continue
            if governed.policy == "merge" and relative.as_posix() == c.Infra.GITIGNORE:
                # NOTE (mro-jnm1.2): the canonical .gitignore body is rendered
                # from the same base/gitignore.j2 + computed
                # CodegenConfigSpec.gitignore_sections used by `codegen new` —
                # ONE render mechanism derived from the artifact SSOT.
                # Per-project exception fields land with mro-jnm1.3.
                rendered_gitignore = FlextInfraCodegenConform._render_gitignore(
                    codegen,
                    profile=profile,
                    project_name=root.name,
                    workspace=workspace,
                )
                if rendered_gitignore.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                        rendered_gitignore.error or f"gitignore render failed: {path}"
                    )
                if rendered_gitignore.value != current:
                    completed.append(
                        m.Infra.CodegenFilePlan(
                            path=path,
                            owner=governed.owner,
                            policy=governed.policy,
                            rendered=rendered_gitignore.value,
                            expected_sha256=u.Cli.sha256_content(
                                rendered_gitignore.value
                            ),
                            current_sha256=digest,
                            changed=True,
                        )
                    )
                    continue
            completed.append(
                m.Infra.CodegenFilePlan(
                    path=path,
                    owner=governed.owner,
                    policy=governed.policy,
                    rendered=current,
                    expected_sha256=digest or u.Cli.sha256_content(current),
                    current_sha256=digest,
                    changed=False,
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
    ) -> p.Result[str]:
        """Render the canonical ``.gitignore`` for one named project.

        Public seam consumed by the layout engine (mro-0wuz): per-project
        layout ``gitignore_additions`` from the layout SSOT are appended as
        one trailing derived section so conform and layout never diverge.
        """
        return FlextInfraCodegenConform._render_gitignore(
            codegen, profile=profile, project_name=project_name, workspace=workspace
        )

    @staticmethod
    def _render_gitignore(
        codegen: m.Infra.CodegenConfigSpec,
        *,
        profile: c.Infra.MakeProfile,
        project_name: str | None = None,
        workspace: m.Infra.WorkspaceSpec | None = None,
    ) -> p.Result[str]:
        """Render the canonical ``.gitignore`` body via the single template.

        NOTE (mro-jnm1.2): ``codegen new`` renders ``base/gitignore.j2`` with
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
        # member directory, so their whitelist is DERIVED from the live workspace
        # topology instead of a hardcoded name glob: declaring a member in
        # `config/workspace.yaml` is the single source that makes it trackable.
        # Nested paths need every ancestor unignored, otherwise git never
        # descends far enough to reach the member itself.
        member_patterns: list[str] = []
        if workspace is not None:
            for member in workspace.members:
                parts = member.path.as_posix().strip("/").split("/")
                # Every ancestor is unignored so git can descend into the
                # member, then its contents are unignored with the `/**` form.
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
                    name="WHITELIST: governed workspace members (derived)",
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
        context = m.Infra.GitignoreRenderSpec(gitignore_sections=tuple(sections))
        return u.Cli.template_render(templates_root / entry.source, context)

    @staticmethod
    def _select_repositories(
        request: m.Infra.CodegenConformRequest,
        workspace: m.Infra.WorkspaceSpec,
        current_repository: m.Infra.RepositoryRef,
    ) -> p.Result[tuple[m.Infra.RepositoryRef, ...]]:
        """Resolve self/members/all from the governing topology manifest."""
        scope = c.Infra.CodegenConformScope(request.scope)
        if scope is c.Infra.CodegenConformScope.SELF:
            selected = (current_repository,)
        elif scope is c.Infra.CodegenConformScope.MEMBERS:
            if not workspace.members:
                return r[tuple[m.Infra.RepositoryRef, ...]].fail(
                    "members scope requires a workspace-root manifest"
                )
            selected = tuple(workspace.members)
        else:
            selected = (workspace.repository, *workspace.members)
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
    ) -> Path:
        """Resolve one selected checkout without sibling discovery."""
        if repository.name == workspace.repository.name:
            return root
        resolved: Path = (root / repository.path).resolve()
        return resolved

    @staticmethod
    def _existing_python_dirs(
        root: Path,
        codegen: m.Infra.CodegenConfigSpec,
        target: m.Infra.RepositoryConformTarget,
    ) -> t.StrSequence:
        """Return the canonical Python roots this plan leaves on disk.

        ``u.Infra.analyzer_python_roots`` is the single owner shared with the
        deps modernizer and the extra-paths sync, so no surface can select a
        different set and erase what another just wrote.

        mro-be9ld: a root counts only when this plan actually materializes a
        file INSIDE it, or when it already exists on disk. Matching the first
        path segment of every rendered destination also accepted roots the
        plan never creates (an external scaffold declares examples/ and
        scripts/ but writes neither), so the first pass emitted pyright
        environments for absent directories and the verification pass removed
        them again -- apply never reached a fixed point.
        """
        rendered_roots = {
            Path(entry.destination).parts[0]
            for entry in codegen.templates.entries
            if target.make_profile in entry.profiles
            and entry.delegate == "render"
            and Path(entry.destination).suffix in {".py", ".pyi"}
        }
        discovered_roots = frozenset(u.Infra.discover_python_dirs(root))
        declared = tuple(
            directory
            for directory in config.Infra.tooling.tools.pyright.path_rules.env_dirs
            if directory in rendered_roots or directory in discovered_roots
        )
        roots: t.StrSequence = u.Infra.analyzer_python_roots(root, declared)
        return roots

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
        # mro-j47u (codex): new and existing repositories share the exact same
        # root-scoped modernizer pipeline, so first generation is a fixed point.
        # NOTE(mro-p68a.5, agent codex): a declared member consumes its parent
        # tooling profile even before the atomic scaffold creates files on disk.
        tooling_root = target.root
        modernizer = FlextInfraPyprojectModernizer(
            workspace_root=tooling_root, skip_check=True
        )
        # Both plan paths MUST declare the same Python roots or their renders
        # diverge and conform never converges: the modernizer would add a
        # pyright environment for a directory on disk (e.g. tools/) that the
        # scaffold-only view does not know about, and the next check would
        # remove it again, forever. _existing_python_dirs is the complete set.
        declared_python_dirs = self._existing_python_dirs(root, codegen, target)
        declared_python_dirs_are_complete = (
            target.make_profile is not c.Infra.MakeProfile.WORKSPACE_ROOT
        )
        tooling_result = modernizer.resolve_tooling_context(
            project_name=repository.distribution,
            package_name=project.package_name,
            path=pyproject,
            declared_python_dirs=declared_python_dirs,
            declared_python_dirs_are_complete=declared_python_dirs_are_complete,
        )
        if tooling_result.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                tooling_result.error or f"tooling render failed: {pyproject}"
            )
        context_result = self._project_render_context(
            repository, target, workspace, codegen, tooling_runtime=tooling_result.value
        )
        if context_result.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                context_result.error or "project render context is invalid"
            )
        context = context_result.value
        # Workspace root owns resolution for attached members (uv reads
        # exclude-dependencies only from the workspace root). Members still
        # receive their own routed excludes for standalone CI clones.
        if target.make_profile is c.Infra.MakeProfile.WORKSPACE_ROOT:
            uv_exclude_dependencies = tuple(codegen.uv_exclude_dependencies)
        else:
            uv_exclude_dependencies = tuple(
                item
                for item in codegen.uv_exclude_dependencies
                if item.project == repository.distribution
            )
        planned: list[m.Infra.CodegenFilePlan] = []
        templates_root = (
            self._package_root() / "templates" / codegen.templates.root
        ).resolve()
        has_devcontainer = self._has_devcontainer(target.root)
        seen_destinations: set[str] = set()
        for entry in codegen.templates.entries:
            if profile not in entry.profiles:
                continue
            if (
                contract.destinations is not None
                and entry.destination not in contract.destinations
            ):
                continue
            source = (templates_root / entry.source).resolve()
            if not source.is_relative_to(templates_root) or not source.is_file():
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"template source is missing or escapes its root: {entry.source}"
                )
            destination = entry.destination.format(
                package_name=context.package_name, ns=context.ns
            )
            relative = Path(destination)
            if relative.is_absolute() or ".." in relative.parts:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"template destination escapes repository root: {destination}"
                )
            if self._skips_beads_client_config(destination, workspace, target):
                continue
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
        for entry in codegen.templates.entries:
            if profile not in entry.profiles:
                continue
            if (
                contract.destinations is not None
                and entry.destination not in contract.destinations
            ):
                continue
            if not contract.delegates:
                continue
            # mro-i6nq.10: One formatted path governs validation and planning.
            destination = entry.destination.format(
                package_name=context.package_name, ns=context.ns
            )
            if entry.delegate == "manifest":
                # NOTE (multi-agent, mro-wkii.17 / agent: uv_overlay_owner):
                # template rendering retains the canonical context instance.
                rendered_manifest = u.Cli.template_render(
                    templates_root / entry.source, context
                )
                if rendered_manifest.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                        rendered_manifest.error
                        or f"manifest render failed: {entry.source}"
                    )
                manifest_validation = self._validate_initial_manifest(
                    rendered_manifest.value, workspace
                )
                if manifest_validation.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                        manifest_validation.error
                        or "initial workspace manifest validation failed"
                    )
                manifest_plan = self._file_plan(
                    root,
                    destination,
                    rendered_manifest.value,
                    source_template=Path(entry.source),
                )
                if manifest_plan.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                        manifest_plan.error or "workspace manifest planning failed"
                    )
                planned.append(manifest_plan.value)
                continue
            if entry.delegate != "render":
                continue
            if destination == c.Infra.PYPROJECT_FILENAME:
                continue
            if self._skips_beads_client_config(destination, workspace, target):
                continue
            artifact_context = self._artifact_render_context(
                dist=context.dist,
                repository=repository,
                target=target,
                workspace=workspace,
                codegen=codegen,
                destination=destination,
                tooling_runtime=tooling_result.value,
                project_context=context,
                has_devcontainer=has_devcontainer,
            )
            if artifact_context.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    artifact_context.error
                    or f"artifact render context failed: {destination}"
                )
            rendered = u.Cli.template_render(
                templates_root / entry.source, artifact_context.value
            )
            if rendered.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    rendered.error
                    or (
                        f"stage=templates repository={repository.name} "
                        f"template={entry.source}: template render failed"
                    )
                )
            file_plan = self._file_plan(
                root, destination, rendered.value, source_template=Path(entry.source)
            )
            if file_plan.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    file_plan.error
                    or f"managed file planning failed: {entry.destination}"
                )
            planned.append(file_plan.value)
        if not contract.pyproject:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(planned))
        pyproject_entry = next(
            (
                item
                for item in codegen.templates.entries
                if item.destination == c.Infra.PYPROJECT_FILENAME
                and profile in item.profiles
                and item.delegate == "render"
            ),
            None,
        )
        if pyproject_entry is None:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                "pyproject template is missing from codegen configuration"
            )
        pyproject_render = u.Cli.template_render(
            templates_root / pyproject_entry.source, context
        )
        if pyproject_render.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                pyproject_render.error or "pyproject template render failed"
            )
        initial_tooling = modernizer.conform_source(
            pyproject_render.value,
            path=pyproject,
            format_source=False,
            declared_python_dirs=declared_python_dirs,
            declared_python_dirs_are_complete=declared_python_dirs_are_complete,
        )
        if initial_tooling.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                initial_tooling.error or f"initial tooling conform failed: {pyproject}"
            )
        prepared_result = u.Infra.pyproject_conform(
            initial_tooling.value,
            providers=codegen.providers,
            workspace=workspace,
            workspace_mode=c.Infra.WorkspaceMode.STANDALONE,
            toolchain=codegen.toolchain,
            required_dev_dependencies=codegen.scaffold.project.dev,
            uv_exclude_dependencies=uv_exclude_dependencies,
            uv_exclude_newer=self._uv_exclude_newer(repository, workspace, codegen),
        )
        if prepared_result.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                prepared_result.error or f"pyproject prepare failed: {pyproject}"
            )
        final_tooling = modernizer.conform_source(
            prepared_result.value,
            path=pyproject,
            declared_python_dirs=declared_python_dirs,
            declared_python_dirs_are_complete=declared_python_dirs_are_complete,
        )
        if final_tooling.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                final_tooling.error or f"final tooling conform failed: {pyproject}"
            )
        pyproject_plan = self._file_plan(
            root, c.Infra.PYPROJECT_FILENAME, final_tooling.value
        )
        if pyproject_plan.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                pyproject_plan.error or f"pyproject planning failed: {pyproject}"
            )
        planned.append(pyproject_plan.value)
        # mro-68rcj: a projection this profile must not carry is RETIRED, not
        # merely skipped. Skipping left 31 members owning an orphan hook config
        # that gen neither rendered nor removed.
        retired = self.retired_projection_plans(root, profile)
        if retired.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                retired.error or f"retired projection planning failed: {root}"
            )
        planned.extend(retired.value)
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(planned))

    def _plan_existing_repository(
        self,
        *,
        root: Path,
        workspace_root: Path,
        repository: m.Infra.RepositoryRef,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        contract: m.Infra.CodegenConformSurfaceContract,
        pyproject_source: str,
        project_metadata: p.ProjectMetadata,
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Conform every declared managed surface in an existing repository."""
        u.Cli.info(f"  stage=pyproject repository={repository.name}")
        pyproject = root / c.Infra.PYPROJECT_FILENAME
        if not pyproject.is_file():
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                f"existing repository has no pyproject.toml: {root}; "
                "scaffold templates are available only through codegen new"
            )
        dist = project_metadata.project.name
        if dist != repository.distribution:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                "PEP 621 project name does not match catalog distribution: "
                f"{dist} != {repository.distribution}"
            )
        workspace_mode = (
            c.Infra.WorkspaceMode.WORKSPACE
            if target.make_profile is c.Infra.MakeProfile.WORKSPACE_ROOT
            else c.Infra.WorkspaceMode.STANDALONE
        )
        # Workspace root owns resolution for attached members (uv reads
        # exclude-dependencies only from the workspace root). Members still
        # receive their own routed excludes for standalone CI clones.
        if target.make_profile is c.Infra.MakeProfile.WORKSPACE_ROOT:
            uv_exclude_dependencies = tuple(codegen.uv_exclude_dependencies)
        else:
            uv_exclude_dependencies = tuple(
                item
                for item in codegen.uv_exclude_dependencies
                if item.project == repository.distribution
            )
        if contract.dependencies_only:
            dependency_result = u.Infra.pyproject_dependencies_conform(
                pyproject_source,
                providers=codegen.providers,
                workspace=workspace,
                workspace_mode=workspace_mode,
            )
            if dependency_result.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    dependency_result.error
                    or f"pyproject dependency conform failed: {pyproject}"
                )
            dependency_plan = self._file_plan(
                root, c.Infra.PYPROJECT_FILENAME, dependency_result.value
            )
            if dependency_plan.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    dependency_plan.error
                    or f"pyproject dependency planning failed: {pyproject}"
                )
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok((dependency_plan.value,))
        modernizer = FlextInfraPyprojectModernizer(
            workspace_root=workspace_root, skip_check=True
        )
        # Both plan paths must declare the SAME Python roots or their renders
        # diverge and conform never converges. _existing_python_dirs unions the
        # roots this plan renders with the roots already on disk, which is the
        # complete set for an existing tree.
        declared_python_dirs = self._existing_python_dirs(root, codegen, target)
        declared_python_dirs_are_complete = (
            target.make_profile is not c.Infra.MakeProfile.WORKSPACE_ROOT
        )
        tooling_context = modernizer.resolve_tooling_context(
            project_name=repository.distribution,
            package_name=project_metadata.package_name,
            path=pyproject,
            declared_python_dirs=declared_python_dirs,
            declared_python_dirs_are_complete=declared_python_dirs_are_complete,
        )
        if tooling_context.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                tooling_context.error or f"tooling render failed: {pyproject}"
            )
        if not contract.pyproject:
            return self._plan_existing_templates(
                root=root,
                repository=repository,
                target=target,
                workspace=workspace,
                codegen=codegen,
                tooling_runtime=tooling_context.value,
                contract=contract,
            )
        prepared_result = u.Infra.pyproject_conform(
            pyproject_source,
            providers=codegen.providers,
            workspace=workspace,
            workspace_mode=workspace_mode,
            toolchain=codegen.toolchain,
            required_dev_dependencies=codegen.scaffold.project.dev,
            uv_exclude_dependencies=uv_exclude_dependencies,
            uv_exclude_newer=self._uv_exclude_newer(repository, workspace, codegen),
        )
        if prepared_result.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                prepared_result.error or f"pyproject preparation failed: {pyproject}"
            )
        # Dependency topology is conformed before tooling so the modernizer is
        # the final owner of TOML ordering, comments, and type-checker settings.
        # It preserves the already canonical dependency source declarations.
        # Declare the canonical roots this plan leaves on disk. Analyzer paths
        # are otherwise derived from directories that EXIST, and the same plan
        # also materializes managed roots (tests/), so the rendered pyproject
        # omitted them and the NEXT plan re-derived them — apply never reached
        # its fixed point.
        tooling_result = modernizer.conform_source(
            prepared_result.value,
            path=pyproject,
            declared_python_dirs=declared_python_dirs,
            declared_python_dirs_are_complete=declared_python_dirs_are_complete,
        )
        if tooling_result.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                tooling_result.error or f"tooling conform failed: {pyproject}"
            )
        pyproject_plan = self._file_plan(
            root, c.Infra.PYPROJECT_FILENAME, tooling_result.value
        )
        if pyproject_plan.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                pyproject_plan.error or f"pyproject planning failed: {pyproject}"
            )
        planned = [pyproject_plan.value]
        if not contract.templates:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(planned))
        # NOTE(mro-p68a.5, agent codex): managed_files is the existing-tree
        # ownership SSOT; templates.entries remains the single render manifest.
        managed_result = self._plan_existing_templates(
            root=root,
            repository=repository,
            target=target,
            workspace=workspace,
            codegen=codegen,
            tooling_runtime=tooling_context.value,
            contract=contract,
        )
        if managed_result.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                managed_result.error or f"managed template planning failed: {root}"
            )
        planned.extend(managed_result.value)
        if contract.custom:
            custom_result = self._plan_existing_custom(
                root, codegen, profile=target.make_profile.value
            )
            if custom_result.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    custom_result.error or f"custom Make validation failed: {root}"
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
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Render configured overwrite-owned templates for an existing tree."""
        u.Cli.info(f"  stage=templates repository={repository.name}")
        profile = target.make_profile
        templates_root = (
            self._package_root() / "templates" / codegen.templates.root
        ).resolve()
        planned: list[m.Infra.CodegenFilePlan] = []
        has_devcontainer = self._has_devcontainer(target.root)
        owned_destinations = frozenset(
            destination
            for claim in codegen.managed_destination_ownership
            if claim.project == repository.name
            for destination in claim.destinations
        )
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
            if (
                managed.policy in {"delegated", "manual"}
                or managed.path == Path(c.Infra.PYPROJECT_FILENAME)
                or managed.path == Path(c.Infra.CUSTOM_MAKE_FILENAME)
            ):
                continue
            if self._skips_beads_client_config(
                managed.path.as_posix(), workspace, target
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
            u.Cli.emit_raw(f"  template {entry.source} -> {entry.destination}\n")
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
            if profile not in entry.profiles:
                # Why: profile-excluded managed workflows must not keep firing
                # (ci-matrix on workspace-member). Prune the orphan projection.
                if (
                    managed.path.parts[:2] == (".github", "workflows")
                    and path.is_file()
                ):
                    # Why: mro-4p0t orphan_read avoids Result[str] vs str overlap on current.
                    orphan_read = u.Cli.files_read_text(path)
                    if orphan_read.failure:
                        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                            orphan_read.error or f"orphan workflow read failed: {path}"
                        )
                    # A project may own hand-written source at a managed
                    # destination it does not inherit by profile. Pruning it
                    # would delete real source on every gen. The claim is
                    # ignored once the file carries the generated marker, so a
                    # retired projection is still pruned and a stale claim can
                    # never resurrect one.
                    if (
                        entry.destination in owned_destinations
                        and c.Infra.TEMPLATE_GENERATED_MARKER not in orphan_read.value
                    ):
                        continue
                    planned.append(
                        m.Infra.CodegenFilePlan(
                            path=path,
                            owner=managed.owner,
                            policy=managed.policy,
                            rendered="",
                            expected_sha256=u.Cli.sha256_content(""),
                            current_sha256=u.Cli.sha256_content(orphan_read.value),
                            changed=True,
                            absent=True,
                        )
                    )
                continue
            if managed.policy == "create-only" and path.is_file():
                current = u.Cli.files_read_text(path)
                if current.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                        current.error or f"managed file read failed: {path}"
                    )
                file_plan = self._file_plan(root, entry.destination, current.value)
                if file_plan.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                        file_plan.error
                        or f"managed file planning failed: {entry.destination}"
                    )
                planned.append(file_plan.value)
                continue
            if managed.policy == "create-only" and path.exists():
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"create-only destination is not a regular file: {path}"
                )
            if managed.policy == "create-only":
                continue
            artifact_context = self._artifact_render_context(
                dist=repository.distribution,
                repository=repository,
                target=target,
                workspace=workspace,
                codegen=codegen,
                destination=entry.destination,
                tooling_runtime=tooling_runtime,
                project_context=None,
                has_devcontainer=has_devcontainer,
            )
            if artifact_context.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    artifact_context.error
                    or f"managed artifact context failed: {entry.destination}"
                )
            rendered = u.Cli.template_render(
                templates_root / entry.source, artifact_context.value
            )
            if rendered.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    rendered.error or f"template render failed: {entry.source}"
                )
            rendered_content = rendered.value
            if entry.destination == c.Infra.GITMODULES and path.is_file():
                current = u.Cli.files_read_text(path)
                if current.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                        current.error or f"managed file read failed: {path}"
                    )
                rendered_content = self._merge_gitmodules(
                    current.value,
                    rendered.value,
                    managed_paths=frozenset(
                        member.path.as_posix() for member in workspace.members
                    ),
                )
            file_plan = self._file_plan(
                root,
                entry.destination,
                rendered_content,
                source_template=Path(entry.source),
            )
            if file_plan.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    file_plan.error
                    or f"managed file planning failed: {entry.destination}"
                )
            planned.append(file_plan.value)
        # mro-68rcj: an existing tree that still carries a projection excluded
        # from its profile has it RETIRED here. Skipping the entry left the file
        # orphaned -- owned by nobody, never re-rendered, never removed.
        retired = self.retired_projection_plans(root, profile)
        if retired.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                retired.error or f"retired projection planning failed: {root}"
            )
        planned.extend(retired.value)
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(planned))

    @staticmethod
    def _absent_file_plan(path: Path, current: str) -> m.Infra.CodegenFilePlan:
        """Plan the removal of one retired projection."""
        return m.Infra.CodegenFilePlan(
            path=path,
            rendered="",
            expected_sha256=u.Cli.sha256_content(""),
            current_sha256=u.Cli.sha256_content(current),
            changed=True,
            absent=True,
        )

    @classmethod
    def retired_projection_plans(
        cls, root: Path, profile: c.Infra.MakeProfile
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        r"""Plan removal of generated files this profile must not carry.

        Operator law mro-68rcj: git hooks belong to the workspace ROOT only, and
        the template already encodes that by excluding workspace-member from its
        profiles. But a non-matching profile was merely SKIPPED, never retired,
        so 31 members kept an orphan .pre-commit-config.yaml that ``make gen``
        neither owned nor removed -- each carrying a stale entry shape that
        failed with \"Executable `CI=Y` not found\".

        A projection excluded from a profile is retired for that profile. Only
        files still carrying the generator banner are removed, so a hand-written
        file that happens to share the name is never touched.
        """
        codegen = config.Infra.codegen
        planned: list[m.Infra.CodegenFilePlan] = []
        for entry in codegen.templates.entries:
            if profile in entry.profiles or "{" in entry.destination:
                continue
            path = root / Path(entry.destination)
            if not path.is_file():
                continue
            current = u.Cli.files_read_text(path)
            if current.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    current.error or f"retired projection read failed: {path}"
                )
            if c.Infra.TEMPLATE_GENERATED_MARKER not in current.value:
                continue
            planned.append(cls._absent_file_plan(path, current.value))
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(planned))

    def _plan_ast_grep_surfaces(
        self,
        *,
        root: Path,
        codegen: m.Infra.CodegenConfigSpec,
        contract: m.Infra.CodegenConformSurfaceContract,
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Own the ast-grep project contract without projecting packaged rules.

        Why: rules travel inside the installed packages
        (``flext_infra/codemod/rules`` discovered through the
        importlib.resources cascade in ``flext_infra/codemod/discovery.py``),
        so conform no longer copies them into ``<project>/ast-grep-rules/``.
        ``sgconfig.yml`` is rendered from the SSOT only when the repository
        owns hand-written rules; retired projections (generated marker
        present) are pruned and hand-written files are never touched.
        """
        if contract.destinations is not None:
            # Partial surfaces never select ast-grep artifacts; the complete
            # surface owns the sgconfig decision and the projection prune.
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(())
        surfaces: list[tuple[Path, bool]] = [
            (Path(codegen.sgconfig.rule_dirs[0]), True)
        ]
        if codegen.sgconfig.test_dirs:
            surfaces.append((Path(codegen.sgconfig.test_dirs[0]), False))
        planned: list[m.Infra.CodegenFilePlan] = []
        own_rules = False
        for destination_dir, is_rule_dir in surfaces:
            target_dir = root / destination_dir
            if not target_dir.is_dir():
                continue
            for existing in sorted(target_dir.rglob("*.yml")):
                current = u.Cli.files_read_text(existing)
                if current.failure:
                    return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                        current.error or f"ast-grep rule read failed: {existing}"
                    )
                if current.value.startswith("# @generated by flext_infra codegen"):
                    planned.append(self._absent_file_plan(existing, current.value))
                    continue
                if is_rule_dir:
                    own_rules = True
        sgconfig_path = root / "sgconfig.yml"
        if own_rules:
            templates_root = (
                self._package_root() / "templates" / codegen.templates.root
            ).resolve()
            rendered = u.Cli.template_render(
                templates_root / "base/sgconfig.yml.j2", codegen.sgconfig
            )
            if rendered.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    rendered.error or "sgconfig.yml render failed"
                )
            sgconfig_plan = self._file_plan(root, "sgconfig.yml", rendered.value)
            if sgconfig_plan.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    sgconfig_plan.error or "sgconfig.yml planning failed"
                )
            planned.append(sgconfig_plan.value)
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(planned))
        if sgconfig_path.is_file():
            current = u.Cli.files_read_text(sgconfig_path)
            if current.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    current.error or f"sgconfig read failed: {sgconfig_path}"
                )
            if current.value.startswith("# @generated by flext_infra codegen"):
                planned.append(self._absent_file_plan(sgconfig_path, current.value))
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(planned))

    @staticmethod
    def _workspace_root_rel(workspace: m.Infra.WorkspaceSpec) -> str:
        """Return the environment root owned by the inferred target."""
        if workspace.project is not None:
            project_root_rel: str = workspace.project.workspace_root_rel
            return project_root_rel
        return "."

    @staticmethod
    def _uv_exclude_newer(
        repository: m.Infra.RepositoryRef,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
    ) -> str:
        """Return the cooldown window governing this repository's ``[tool.uv]``.

        The fleet default is a rolling window. A project that declares a
        security floor through ``override-dependencies`` cannot use it: once
        the pinned version ages past the window it is excluded, the floor is
        unsatisfiable, and resolution fails with no code change. Such a
        project declares an absolute cutoff through the repository policy
        overlay instead of hand-editing the generated ``pyproject.toml``.
        """
        overlay = next(
            (
                item
                for item in workspace.repository_policy_overlays
                if item.project == repository.distribution
            ),
            None,
        )
        if overlay is not None and overlay.uv_exclude_newer is not None:
            pinned: str = overlay.uv_exclude_newer
            return pinned
        fleet: str = codegen.toolchain.uv_exclude_newer
        return fleet

    @staticmethod
    def _merge_gitmodules(
        current: str, managed: str, *, managed_paths: frozenset[str]
    ) -> str:
        """Replace governed submodule sections and preserve every foreign block."""
        matches = tuple(c.Infra.GITMODULE_SECTION_RE.finditer(current))
        if not matches:
            preserved = current
        else:
            parts = [current[: matches[0].start()]]
            for index, match in enumerate(matches):
                end = (
                    matches[index + 1].start()
                    if index + 1 < len(matches)
                    else len(current)
                )
                block = current[match.start() : end]
                path_match = c.Infra.GITMODULE_PATH_RE.search(block)
                if path_match is None or path_match.group(1) not in managed_paths:
                    parts.append(block)
            preserved = "".join(parts)
        if not managed:
            return preserved
        separator = "" if not preserved or preserved.endswith("\n\n") else "\n"
        return f"{preserved}{separator}{managed}"

    @staticmethod
    def _infra_repository(
        workspace: m.Infra.WorkspaceSpec,
    ) -> p.Result[m.Infra.RepositoryRef]:
        """Resolve the repository that owns the infrastructure CLI.

        The owner is read from the live workspace topology when that topology
        declares it. A standalone consumer legitimately declares no
        flext-infra member, so the reference is then derived from the provider
        contract. Either way nothing is looked up in a project catalog, which
        flext-infra is forbidden to own.
        """
        matches = tuple(
            item
            for item in (workspace.repository, *workspace.members)
            if item.distribution == config.Infra.name
        )
        if len(matches) > 1:
            return r[m.Infra.RepositoryRef].fail(
                "workspace topology declares more than one "
                f"{config.Infra.name} checkout"
            )
        if matches:
            return r[m.Infra.RepositoryRef].ok(matches[0])
        return r[m.Infra.RepositoryRef].ok(
            u.Infra.derived_repository_ref(
                config.Infra.name, provider=config.Infra.codegen.providers[0]
            )
        )

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
    ) -> p.Result[tuple[m.Infra.ManagedGitlinkSpec, ...]]:
        """Resolve provider baselines only for mutable governed members."""
        resolved: list[m.Infra.ManagedGitlinkSpec] = []
        for repository in workspace.members:
            provider = cls._repository_provider(repository, codegen)
            if provider.failure:
                return r[tuple[m.Infra.ManagedGitlinkSpec, ...]].fail(
                    provider.error or f"member provider is invalid: {repository.name}"
                )
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
    def _infra_source_root_rel(
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        infra_repository: m.Infra.RepositoryRef,
    ) -> str | None:
        """Return a local engine source path only when the workspace declares it."""
        if target.make_profile is not c.Infra.MakeProfile.WORKSPACE_ROOT:
            return None
        workspace_repositories: tuple[m.Infra.RepositoryRef, ...] = (
            workspace.repository,
            *workspace.members,
        )
        local: m.Infra.RepositoryRef | None = next(
            (
                item
                for item in workspace_repositories
                if item.distribution == infra_repository.distribution
                and item.url == infra_repository.url
                and item.provider == infra_repository.provider
            ),
            None,
        )
        if local is None:
            return None
        workspace_root_rel = FlextInfraCodegenConform._workspace_root_rel(workspace)
        local_path: Path = local.path
        return (Path(workspace_root_rel) / local_path).as_posix()

    def _artifact_render_context(
        self,
        *,
        dist: str,
        repository: m.Infra.RepositoryRef,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        destination: str,
        tooling_runtime: m.Infra.ToolingRuntimeContext,
        project_context: m.Infra.ProjectRenderContext | None,
        has_devcontainer: bool,
    ) -> p.Result[p.Model]:
        """Resolve one governed artifact to its canonical typed render input."""
        if destination == c.Infra.GITIGNORE:
            profile = target.make_profile
            sections = tuple(
                section
                for section in codegen.gitignore_sections
                if not section.profiles or profile in section.profiles
            )
            # Why (ai-hub-qwoc): mro-jnm1.3 seam -- a project-local overlay
            # extends the fleet-wide scaffold sections instead of the
            # generated .gitignore being hand-edited (which `codegen conform`
            # would then treat as WIP and refuse to regenerate).
            overlay = next(
                (
                    item
                    for item in workspace.repository_policy_overlays
                    if item.project == repository.distribution
                ),
                None,
            )
            if overlay is not None and overlay.extra_ignored_patterns:
                sections = (
                    *sections,
                    m.Infra.ScaffoldGitignoreSectionSpec(
                        name="Project-local exceptions (config/workspace.yaml overlay)",
                        patterns=overlay.extra_ignored_patterns,
                    ),
                )
            return r[p.Model].ok(
                m.Infra.GitignoreRenderSpec(gitignore_sections=sections)
            )
        if destination == ".pre-commit-config.yaml":
            return r[p.Model].ok(
                m.Infra.MakeWorkflowRenderSpec(dist=dist, make=codegen.make)
            )
        if destination in {".markdownlint.json", ".markdownlintignore"}:
            # The markdown templates read only tooling.tools.markdown, so the
            # render input carries exactly that: demanding the full project
            # context broke the standalone flext-infra checkout, which has no
            # project metadata to give.
            return r[p.Model].ok(
                m.Infra.MarkdownlintRenderSpec(tooling=config.Infra.tooling)
            )
        if destination in {".envrc", ".mise.toml", ".python-version"}:
            return r[p.Model].ok(codegen.toolchain)
        if destination == c.Infra.BEADS_CONFIG_RELPATH:
            server = codegen.toolchain.beads.server
            if server is None:
                return r[p.Model].fail(
                    "Beads ledger server is not declared in the toolchain SSOT"
                )
            identity = self.ledger_identity_for_target(workspace, target)
            if identity is None:
                return r[p.Model].fail(
                    f"workspace {workspace.name!r} declares no Beads ledger, so "
                    f"{destination} has no identity to render"
                )
            issue_prefix, database = identity
            return r[p.Model].ok(
                m.Infra.BeadsConfigRenderSpec(
                    issue_prefix=issue_prefix,
                    database=database,
                    server=server,
                    routing=target.routing_only and not target.beads_enabled,
                )
            )
        if destination == c.Infra.BEADS_METADATA_RELPATH:
            server = codegen.toolchain.beads.server
            if server is None:
                return r[p.Model].fail(
                    "Beads ledger server is not declared in the toolchain SSOT"
                )
            identity = self.ledger_identity_for_target(workspace, target)
            if identity is None:
                return r[p.Model].fail(
                    f"workspace {workspace.name!r} declares no Beads ledger, so "
                    f"{destination} has no identity to render"
                )
            database = identity[1]
            return r[p.Model].ok(
                m.Infra.BeadsMetadataRenderSpec(database=database, server=server)
            )
        if destination.startswith(".github/"):
            provider = self._repository_provider(repository, codegen)
            if provider.failure:
                return r[p.Model].fail(
                    provider.error or "workflow provider resolution failed"
                )
            workspace_repositories = (
                tuple(workspace.members)
                if target.make_profile is c.Infra.MakeProfile.WORKSPACE_ROOT
                else ()
            )
            # Dependabot aborts the entire update job ("Neither .devcontainer.json
            # nor .devcontainer/devcontainer.json ... found") when the
            # devcontainers ecosystem is declared for a repository that ships no
            # devcontainer, so the entry is projected only where one exists.
            return r[p.Model].ok(
                m.Infra.GithubWorkflowRenderSpec(
                    has_devcontainer=has_devcontainer,
                    dist=dist,
                    make_profile=target.make_profile,
                    repository_branch=provider.value.branch,
                    python_version=codegen.toolchain.python_version,
                    github_actions=codegen.github_actions,
                    make=codegen.make,
                    workspace_repositories=workspace_repositories,
                    checkout_submodules=codegen.checkout_submodules_overrides.get(
                        dist, codegen.checkout_submodules
                    ),
                    private_submodules=codegen.ci_private_submodules.get(dist),
                    ci_matrix_auto_run=target.ci_matrix_auto_run,
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
                )
            )
        if destination in {c.Infra.MAKEFILE_FILENAME, ".gitmodules"}:
            profile = target.make_profile
            members = (
                tuple(workspace.members)
                if profile is c.Infra.MakeProfile.WORKSPACE_ROOT
                else ()
            )
            infra_repository = self._infra_repository(workspace)
            if infra_repository.failure:
                return r[p.Model].fail(
                    infra_repository.error
                    or "infrastructure CLI repository resolution failed"
                )
            infra_provider = self._repository_provider(infra_repository.value, codegen)
            if infra_provider.failure:
                return r[p.Model].fail(
                    infra_provider.error or "infrastructure provider resolution failed"
                )
            gitlinks = self._managed_gitlinks(workspace, codegen)
            if gitlinks.failure:
                return r[p.Model].fail(
                    gitlinks.error or "managed Gitlink resolution failed"
                )
            return r[p.Model].ok(
                m.Infra.MakefileRenderSpec(
                    pytest=config.Infra.tooling.tools.pytest,
                    dist=dist,
                    infra_cli=config.Infra.name,
                    infra_repository=infra_repository.value,
                    infra_repository_branch=infra_provider.value.branch,
                    infra_source_root_rel=self._infra_source_root_rel(
                        target, workspace, infra_repository.value
                    ),
                    make_profile=profile,
                    makefile_custom_include=c.Infra.MAKEFILE_CUSTOM_INCLUDE,
                    # R12 moved the public verbs into this projection; the custom.mk
                    # monopoly guard must travel with them (same policy SSOT base.mk uses).
                    custom_mk_reserved=" ".join(
                        sorted(FlextInfraCustomMkPolicy.reserved_targets())
                    ),
                    workspace_root_rel=FlextInfraCodegenConform._workspace_root_rel(
                        workspace
                    ),
                    workspace_members=tuple(
                        item.path.as_posix() for item in workspace.members
                    ),
                    workspace_repositories=members,
                    workspace_gitlinks=gitlinks.value,
                    uv_link_mode=codegen.toolchain.uv_link_mode,
                    uv_exclude_newer_package=codegen.toolchain.uv_exclude_newer_package,
                    uv_exclude_newer=FlextInfraCodegenConform._uv_exclude_newer(
                        repository, workspace, codegen
                    ),
                    make=codegen.make,
                    extra_verbs=repository.extra_verbs,
                    script_dispatch=repository.script_dispatch,
                    orchestrated_verbs=c.Infra.ORCHESTRATED_PROJECT_VERBS,
                    workspace_cli_group=c.Infra.CLI_GROUP_WORKSPACE,
                    project_selection_conflict_error=(
                        c.Infra.PROJECT_SELECTION_CONFLICT_ERROR
                    ),
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
        if project_context is not None:
            return r[p.Model].ok(project_context)
        context_result = self._project_render_context(
            repository, target, workspace, codegen, tooling_runtime=tooling_runtime
        )
        if context_result.failure:
            return r[p.Model].fail(
                context_result.error
                or f"managed artifact context failed: {destination}"
            )
        return r[p.Model].ok(context_result.value)

    @staticmethod
    def _has_devcontainer(root: Path) -> bool:
        return (root / ".devcontainer.json").is_file() or any(
            candidate.is_file()
            for candidate in (root / ".devcontainer").glob("**/devcontainer.json")
        )

    @staticmethod
    def make_render_context(
        repository: m.Infra.RepositoryRef,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        *,
        tooling_runtime: m.Infra.ToolingRuntimeContext,
    ) -> p.Result[m.Infra.MakeRenderContext]:
        """Build the typed context consumed by the generated Makefile."""
        profile = target.make_profile
        infra_repository = FlextInfraCodegenConform._infra_repository(workspace)
        if infra_repository.failure:
            return r[m.Infra.MakeRenderContext].fail(
                infra_repository.error
                or "infrastructure CLI repository resolution failed"
            )
        infra_provider = FlextInfraCodegenConform._repository_provider(
            infra_repository.value, codegen
        )
        if infra_provider.failure:
            return r[m.Infra.MakeRenderContext].fail(
                infra_provider.error or "infrastructure provider resolution failed"
            )
        members = (
            tuple(workspace.members)
            if profile is c.Infra.MakeProfile.WORKSPACE_ROOT
            else ()
        )
        gitlinks = FlextInfraCodegenConform._managed_gitlinks(workspace, codegen)
        if gitlinks.failure:
            return r[m.Infra.MakeRenderContext].fail(
                gitlinks.error or "managed Gitlink resolution failed"
            )
        return r[m.Infra.MakeRenderContext].ok(
            m.Infra.MakeRenderContext(
                pytest=config.Infra.tooling.tools.pytest,
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
                infra_repository=infra_repository.value,
                infra_repository_branch=infra_provider.value.branch,
                infra_source_root_rel=FlextInfraCodegenConform._infra_source_root_rel(
                    target, workspace, infra_repository.value
                ),
                python_version=codegen.toolchain.python_version,
                uv_link_mode=codegen.toolchain.uv_link_mode,
                uv_exclude_newer_package=codegen.toolchain.uv_exclude_newer_package,
                uv_exclude_newer=FlextInfraCodegenConform._uv_exclude_newer(
                    repository, workspace, codegen
                ),
                make_profile=profile,
                orchestrated_verbs=c.Infra.ORCHESTRATED_PROJECT_VERBS,
                workspace_cli_group=c.Infra.CLI_GROUP_WORKSPACE,
                project_selection_conflict_error=(
                    c.Infra.PROJECT_SELECTION_CONFLICT_ERROR
                ),
                workspace_root_rel=FlextInfraCodegenConform._workspace_root_rel(
                    workspace
                ),
                makefile_custom_include=c.Infra.MAKEFILE_CUSTOM_INCLUDE,
                # R12 moved the public verbs into this projection; the custom.mk
                # monopoly guard must travel with them (same policy SSOT base.mk uses).
                custom_mk_reserved=" ".join(
                    sorted(FlextInfraCustomMkPolicy.reserved_targets())
                ),
                workspace_members=tuple(
                    item.path.as_posix() for item in workspace.members
                ),
                workspace_repositories=members,
                workspace_gitlinks=gitlinks.value,
                extra_verbs=repository.extra_verbs,
                script_dispatch=repository.script_dispatch,
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
    ) -> p.Result[m.Infra.ProjectRenderContext]:
        """Build the complete typed context consumed by project templates."""
        if workspace.project is None:
            return r[m.Infra.ProjectRenderContext].fail(
                f"workspace has no project metadata: {workspace.name}"
            )
        project = workspace.project
        dependency_profile = next(
            (
                item
                for item in codegen.scaffold.project.dependency_profiles
                if item.upstream == project.upstream
            ),
            None,
        )
        if dependency_profile is None:
            return r[m.Infra.ProjectRenderContext].fail(
                f"unsupported scaffold upstream: {project.upstream}"
            )
        if project.license not in codegen.scaffold.project.supported_licenses:
            supported = ", ".join(codegen.scaffold.project.supported_licenses)
            return r[m.Infra.ProjectRenderContext].fail(
                f"unsupported scaffold license: {project.license}; "
                f"supported licenses: {supported}"
            )
        profile = target.make_profile
        infra_repository = FlextInfraCodegenConform._infra_repository(workspace)
        if infra_repository.failure:
            return r[m.Infra.ProjectRenderContext].fail(
                infra_repository.error
                or "infrastructure CLI repository resolution failed"
            )
        infra_provider = FlextInfraCodegenConform._repository_provider(
            infra_repository.value, codegen
        )
        if infra_provider.failure:
            return r[m.Infra.ProjectRenderContext].fail(
                infra_provider.error or "infrastructure provider resolution failed"
            )
        repository_provider = FlextInfraCodegenConform._repository_provider(
            repository, codegen
        )
        if repository_provider.failure:
            return r[m.Infra.ProjectRenderContext].fail(
                repository_provider.error or "repository provider resolution failed"
            )
        flext_provider = repository_provider.value
        members = (
            tuple(workspace.members)
            if profile is c.Infra.MakeProfile.WORKSPACE_ROOT
            else ()
        )
        gitlinks = FlextInfraCodegenConform._managed_gitlinks(workspace, codegen)
        if gitlinks.failure:
            return r[m.Infra.ProjectRenderContext].fail(
                gitlinks.error or "managed Gitlink resolution failed"
            )
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
            if profile is not c.Infra.MakeProfile.WORKSPACE_ROOT
            else ()
        )
        # Emit only the .gitignore sections that apply to this profile: a
        # section with no declared profiles is universal; a workspace-root-only
        # section (member-directory allowlist, workspace manifest, submodule/
        # Beads coordination) never reaches a member or standalone .gitignore.
        profile_gitignore_sections = tuple(
            section
            for section in codegen.gitignore_sections
            if not section.profiles or profile in section.profiles
        )
        return r[m.Infra.ProjectRenderContext].ok(
            m.Infra.ProjectRenderContext(
                pytest=config.Infra.tooling.tools.pytest,
                scaffold=codegen.scaffold,
                gitignore_sections=profile_gitignore_sections,
                dependency_profile=dependency_profile,
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
                infra_repository=infra_repository.value,
                infra_repository_branch=infra_provider.value.branch,
                infra_source_root_rel=FlextInfraCodegenConform._infra_source_root_rel(
                    target, workspace, infra_repository.value
                ),
                python_version=codegen.toolchain.python_version,
                uv_link_mode=codegen.toolchain.uv_link_mode,
                uv_exclude_newer_package=codegen.toolchain.uv_exclude_newer_package,
                uv_exclude_newer=FlextInfraCodegenConform._uv_exclude_newer(
                    repository, workspace, codegen
                ),
                make_profile=profile,
                orchestrated_verbs=c.Infra.ORCHESTRATED_PROJECT_VERBS,
                workspace_cli_group=c.Infra.CLI_GROUP_WORKSPACE,
                project_selection_conflict_error=(
                    c.Infra.PROJECT_SELECTION_CONFLICT_ERROR
                ),
                workspace_root_rel=FlextInfraCodegenConform._workspace_root_rel(
                    workspace
                ),
                makefile_custom_include=c.Infra.MAKEFILE_CUSTOM_INCLUDE,
                # R12 moved the public verbs into this projection; the custom.mk
                # monopoly guard must travel with them (same policy SSOT base.mk uses).
                custom_mk_reserved=" ".join(
                    sorted(FlextInfraCustomMkPolicy.reserved_targets())
                ),
                workspace_members=tuple(
                    item.path.as_posix() for item in workspace.members
                ),
                workspace_repositories=members,
                workspace_gitlinks=gitlinks.value,
                extra_verbs=repository.extra_verbs,
                script_dispatch=repository.script_dispatch,
                tooling=config.Infra.tooling,
                environment_path_prepends=(codegen.toolchain.environment_path_prepends),
                beads_tool_selector=codegen.toolchain.beads.selector,
                beads_tool_version=codegen.toolchain.beads.version,
                beads_enabled=target.beads_enabled,
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
                description=project.description,
                version=project.version,
                license=project.license,
                python_required_version=codegen.toolchain.python_required_version,
                kubectl_version=codegen.toolchain.kubectl_version,
                helm_version=codegen.toolchain.helm_version,
                kind_version=codegen.toolchain.kind_version,
                taplo_version=codegen.toolchain.taplo_version,
                ast_grep_version=codegen.toolchain.ast_grep_version,
                gitleaks_version=codegen.toolchain.gitleaks_version,
                tokei_version=codegen.toolchain.tokei_version,
                qlty_version=codegen.toolchain.qlty_version,
                go_version=codegen.toolchain.go_version,
                author_name=project.author_name,
                author_email=project.author_email,
                repository=project.homepage,
                homepage=project.homepage,
                documentation=project.documentation,
                flext_git_base_url=flext_provider.base_url,
                flext_git_branch=(
                    workspace.integration.branch
                    if workspace.integration is not None
                    and workspace.integration.provider == flext_provider.name
                    else flext_provider.branch
                ),
                repository_provider=repository.provider,
                repository_git_url=repository.url,
                repository_branch=u.Infra.resolve_integration_branch(
                    workspace, repository_provider.value
                ),
                workspace_manifest_version=c.Infra.WORKSPACE_MANIFEST_VERSION,
                workspace_repository=repository,
                year=project.year,
                workspace_exclusions=tuple(workspace.exclusions),
                workspace_policy_overlays=tuple(workspace.repository_policy_overlays),
                workspace_integration=workspace.integration,
            )
        )

    @classmethod
    def _validate_initial_manifest(
        cls, rendered: str, expected: m.Infra.WorkspaceSpec
    ) -> p.Result[bool]:
        """Validate rendered manifest syntax, schema, model, and exact payload."""
        parsed = u.Cli.yaml_parse(rendered)
        if parsed.failure:
            return r[bool].fail(parsed.error or "workspace manifest YAML is invalid")
        schema = cls._package_root() / "schemas" / c.Infra.WORKSPACE_SCHEMA_FILENAME
        schema_result = u.Cli.schema_validate(parsed.value, schema)
        if schema_result.failure:
            return r[bool].fail(
                schema_result.error or "workspace manifest schema is invalid"
            )
        try:
            validated = m.Infra.WorkspaceSpec.model_validate(parsed.value)
        except c.ValidationError as exc:
            return r[bool].fail_op("workspace manifest model validation", exc)
        if validated != expected:
            return r[bool].fail("rendered workspace manifest differs from input model")
        return r[bool].ok(True)

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
        if not path.is_file():
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(())
        read = u.Cli.files_read_text(path)
        if read.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                read.error or f"custom Make read failed: {path}"
            )
        validation = self.validate_custom_make(read.value, policy)
        if validation.failure:
            return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                validation.error or f"invalid custom Make handlers: {path}"
            )
        digest = u.Cli.sha256_content(read.value)
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok((
            m.Infra.CodegenFilePlan(
                path=path,
                rendered=read.value,
                expected_sha256=digest,
                current_sha256=digest,
                changed=False,
            ),
        ))

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
            effective_line = raw_line
            effective_number = line_number
            if pending_line is not None:
                joined = pending_line + " " + raw_line.strip()
                if joined.rstrip().endswith("\\"):
                    pending_line = joined.rstrip()[:-1].rstrip()
                    continue
                effective_line = joined
                effective_number = pending_number
                pending_line = None
            logical_lines.append((effective_number, effective_line))
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
    def _rendered_conflict_marker(rendered: str) -> str | None:
        """Return the first Git conflict delimiter, or ``None`` when clean.

        Every unambiguous fence is reported: ``<<<<<<<`` opens a conflict,
        ``|||||||`` is the diff3 common ancestor, and ``>>>>>>>`` closes it.
        A lone ``=======`` is NOT reported, because it is also a Markdown
        Setext underline; a real conflict always carries one of the fences
        above, so nothing is missed by ignoring the ambiguous separator.
        """
        fences = ("<<<<<<<", "|||||||", ">>>>>>>")
        return next(
            (
                line
                for line in rendered.splitlines()
                if line.rstrip() in fences
                or line.startswith(tuple(f"{fence} " for fence in fences))
            ),
            None,
        )

    def _file_plan(
        self,
        root: Path,
        relative_path: str,
        rendered: str,
        *,
        source_template: Path | None = None,
    ) -> p.Result[m.Infra.CodegenFilePlan]:
        """Compare one expected output and mark whether it changed."""
        path = root / relative_path
        marker = self._rendered_conflict_marker(rendered)
        if marker is not None:
            source = source_template or Path("<derived conform output>")
            return r[m.Infra.CodegenFilePlan].fail(
                "rendered managed artifact contains Git conflict delimiter: "
                f"template={source} destination={relative_path} "
                f"repository={root} path={path} delimiter={marker}"
            )
        if path.exists() and not path.is_file():
            return r[m.Infra.CodegenFilePlan].fail(
                f"managed destination is not a regular file: {path}"
            )
        current = ""
        if path.is_file():
            read = u.Cli.files_read_text(path)
            if read.failure:
                return r[m.Infra.CodegenFilePlan].fail(
                    read.error or f"managed file read failed: {path}"
                )
            current = read.value
        expected_sha = u.Cli.sha256_content(rendered)
        current_sha = u.Cli.sha256_content(current) if path.is_file() else ""
        changed = current != rendered
        return r[m.Infra.CodegenFilePlan].ok(
            m.Infra.CodegenFilePlan(
                path=path,
                rendered=rendered,
                expected_sha256=expected_sha,
                current_sha256=current_sha,
                changed=changed,
                blocked=False,
                reason="",
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
        """Inventory governed refs and prove descent from the provider baseline."""
        root = target.root
        # Refresh the provider baseline from origin when a remote exists so
        # CI/local gates do not compare against a stale remote-tracking SHA.
        # Fixtures and offline clones keep the existing tracking ref.
        # mro-38p39: this is the only network call in the plan, so it is the one
        # most able to hang. An unreachable or slow remote blocked conform for as
        # long as git waited (measured 7.44s cumulative in a single unit test).
        # It is time-boxed like every other bounded subprocess here; exceeding the
        # box is soft, exactly like a failed fetch below.
        remote_probe = u.Cli.run_raw(
            (c.Infra.GIT, "remote", "get-url", "origin"), cwd=root
        )
        if (
            remote_probe.success
            and remote_probe.value.exit_code == 0
            and remote_probe.value.stdout.strip()
        ):
            fetch_command = (
                c.Infra.GIT,
                "fetch",
                "--no-tags",
                "--prune",
                "origin",
                (
                    f"+refs/heads/{target.baseline_branch}:"
                    f"refs/remotes/origin/{target.baseline_branch}"
                ),
            )
            fetch_result = u.Cli.run_raw(
                fetch_command, cwd=root, timeout=c.Infra.TIMEOUT_SHORT
            )
            if fetch_result.failure or fetch_result.value.exit_code != 0:
                # Soft: ancestry still validates against the local tracking ref
                # when present; hard-fail only if that ref is missing below.
                pass
        has_origin = (
            remote_probe.success
            and remote_probe.value.exit_code == 0
            and remote_probe.value.stdout.strip()
        )
        baseline_reference = f"refs/remotes/origin/{target.baseline_branch}"
        baseline_command = (c.Infra.GIT, "rev-parse", "--verify", baseline_reference)
        baseline_result = u.Cli.run_raw(baseline_command, cwd=root)
        if baseline_result.failure:
            return r[m.Infra.BranchAncestryPlan].fail(
                "provider baseline command failed: "
                f"command={' '.join(baseline_command)}; error={baseline_result.error}"
            )
        if baseline_result.value.exit_code != 0:
            if not has_origin:
                # No remote origin (fixture/offline clone): skip provider
                # baseline ancestry — only local refs are enumerated below.
                baseline_sha = ""
            else:
                return r[m.Infra.BranchAncestryPlan].fail(
                    "provider baseline ref is missing: "
                    f"{baseline_reference}; command={' '.join(baseline_command)}; "
                    f"exit={baseline_result.value.exit_code}; "
                    f"stderr={baseline_result.value.stderr.strip() or '<empty>'}"
                )
        else:
            baseline_sha = baseline_result.value.stdout.strip()
        current_branch_result = u.Cli.run_raw(
            (c.Infra.GIT, "rev-parse", "--abbrev-ref", "HEAD"), cwd=root
        )
        current_branch_ref = ""
        if current_branch_result.success and current_branch_result.value.exit_code == 0:
            current_branch = current_branch_result.value.stdout.strip()
            if current_branch != "HEAD":
                current_branch_ref = f"refs/heads/{current_branch}"
        merge_heads: tuple[str, ...] = ()
        merge_head_path = u.Cli.run_raw(
            (c.Infra.GIT, "rev-parse", "--git-path", "MERGE_HEAD"), cwd=root
        )
        if merge_head_path.success and merge_head_path.value.exit_code == 0:
            resolved_merge_head = root / merge_head_path.value.stdout.strip()
            if resolved_merge_head.is_file():
                merge_heads = tuple(
                    line.strip()
                    for line in resolved_merge_head.read_text(
                        encoding="utf-8"
                    ).splitlines()
                    if line.strip()
                )
        refs_command = (
            c.Infra.GIT,
            "for-each-ref",
            "--format=%(refname)%09%(objectname)",
            "refs/heads",
            "refs/remotes/origin",
        )
        refs_result = u.Cli.run_raw(refs_command, cwd=root)
        if refs_result.failure:
            return r[m.Infra.BranchAncestryPlan].fail(
                "cannot enumerate governed refs: "
                f"command={' '.join(refs_command)}; error={refs_result.error}"
            )
        if refs_result.value.exit_code != 0:
            return r[m.Infra.BranchAncestryPlan].fail(
                "cannot enumerate governed refs: "
                f"command={' '.join(refs_command)}; "
                f"exit={refs_result.value.exit_code}; "
                f"stderr={refs_result.value.stderr.strip() or '<empty>'}"
            )
        observations: list[tuple[str, str]] = []
        for line in refs_result.value.stdout.splitlines():
            reference, separator, sha = line.partition("\t")
            if not separator or not reference or not sha:
                return r[m.Infra.BranchAncestryPlan].fail(
                    f"malformed Git ref inventory entry: {line}"
                )
            if reference == "refs/remotes/origin/HEAD":
                continue
            observations.append((reference, sha))
        worktrees_command = (c.Infra.GIT, "worktree", "list", "--porcelain")
        worktrees_result = u.Cli.run_raw(worktrees_command, cwd=root)
        if worktrees_result.failure:
            return r[m.Infra.BranchAncestryPlan].fail(
                "cannot enumerate registered worktrees: "
                f"command={' '.join(worktrees_command)}; "
                f"error={worktrees_result.error}"
            )
        if worktrees_result.value.exit_code != 0:
            return r[m.Infra.BranchAncestryPlan].fail(
                "cannot enumerate registered worktrees: "
                f"command={' '.join(worktrees_command)}; "
                f"exit={worktrees_result.value.exit_code}; "
                f"stderr={worktrees_result.value.stderr.strip() or '<empty>'}"
            )
        worktree_path = ""
        worktree_sha = ""
        worktree_branch = "detached"
        for line in (*worktrees_result.value.stdout.splitlines(), ""):
            if line.startswith("worktree "):
                worktree_path = line.removeprefix("worktree ")
            elif line.startswith("HEAD "):
                worktree_sha = line.removeprefix("HEAD ")
            elif line.startswith("branch "):
                worktree_branch = line.removeprefix("branch ")
            elif line == "bare":
                worktree_path = ""
                worktree_sha = ""
                worktree_branch = "detached"
            elif not line and worktree_path:
                if not worktree_sha:
                    return r[m.Infra.BranchAncestryPlan].fail(
                        f"worktree has no HEAD: {worktree_path}"
                    )
                if Path(worktree_path).resolve() != root.resolve():
                    worktree_path = ""
                    worktree_sha = ""
                    worktree_branch = "detached"
                    continue
                if worktree_branch == "detached":
                    # Detached checkouts (e.g., temporary CI/worktree transactions)
                    # are not governed branch refs; skip them.
                    worktree_path = ""
                    worktree_sha = ""
                    worktree_branch = "detached"
                    continue
                observations.append((
                    f"worktree:{worktree_path}:{worktree_branch}",
                    worktree_sha,
                ))
                worktree_path = ""
                worktree_sha = ""
                worktree_branch = "detached"
        references: list[m.Infra.BranchAncestryRef] = []
        for reference, sha in sorted(observations):
            policy_reference = (
                reference.rpartition(":")[2]
                if reference.startswith("worktree:")
                else reference
            )
            # mro-e9j0.6: ancestry is a development-line rule. Only refs on the
            # governed allowlist are gated; parked releases (0.10/0.11), snapshots
            # and lane branches are inventoried but must never block conform.
            excluded = cls._technical_branch(
                policy_reference, target.technical_branch_patterns
            ) or not cls._technical_branch(
                policy_reference, target.governed_branch_patterns
            )
            # Only enforce ancestry on active checkouts: the current branch and
            # registered worktrees. Shared local/remote branches that are not
            # currently checked out are excluded from this repository-local gate.
            if not excluded and not reference.startswith("worktree:"):
                is_remote = reference.startswith("refs/remotes/")
                is_other_local = (
                    reference.startswith("refs/heads/")
                    and reference != current_branch_ref
                )
                if is_remote or is_other_local:
                    excluded = True
            ancestor: bool | None = None
            if not excluded and baseline_sha:
                # Ancestry validation requires a resolved baseline SHA;
                # skip when absent (fixture/offline clone without origin).
                ancestry_command = (
                    c.Infra.GIT,
                    "merge-base",
                    "--is-ancestor",
                    baseline_sha,
                    sha,
                )
                ancestry_result = u.Cli.run_raw(ancestry_command, cwd=root)
                if ancestry_result.failure:
                    return r[m.Infra.BranchAncestryPlan].fail(
                        "cannot validate branch ancestry: "
                        f"{reference}; command={' '.join(ancestry_command)}; "
                        f"error={ancestry_result.error}"
                    )
                if ancestry_result.value.exit_code not in {0, 1}:
                    return r[m.Infra.BranchAncestryPlan].fail(
                        "Git ancestry validation failed: "
                        f"{reference}; command={' '.join(ancestry_command)}; "
                        f"exit={ancestry_result.value.exit_code}; "
                        f"stderr={ancestry_result.value.stderr.strip() or '<empty>'}"
                    )
                ancestor = ancestry_result.value.exit_code == 0
                if not ancestor and policy_reference == current_branch_ref:
                    for merge_head in merge_heads:
                        merge_ancestry = u.Cli.run_raw(
                            (
                                c.Infra.GIT,
                                "merge-base",
                                "--is-ancestor",
                                baseline_sha,
                                merge_head,
                            ),
                            cwd=root,
                        )
                        if merge_ancestry.failure:
                            return r[m.Infra.BranchAncestryPlan].fail(
                                "cannot validate merge parent ancestry: "
                                f"{merge_head}; error={merge_ancestry.error}"
                            )
                        if merge_ancestry.value.exit_code not in {0, 1}:
                            return r[m.Infra.BranchAncestryPlan].fail(
                                "Git merge parent ancestry validation failed: "
                                f"{merge_head}; exit={merge_ancestry.value.exit_code}; "
                                f"stderr={merge_ancestry.value.stderr.strip() or '<empty>'}"
                            )
                        if merge_ancestry.value.exit_code == 0:
                            ancestor = True
                            break
            references.append(
                m.Infra.BranchAncestryRef(
                    reference=reference, sha=sha, excluded=excluded, ancestor=ancestor
                )
            )
        return r[m.Infra.BranchAncestryPlan].ok(
            m.Infra.BranchAncestryPlan(
                repository_root=root,
                baseline_reference=baseline_reference or "HEAD",
                baseline_sha=baseline_sha or "HEAD",
                references=tuple(references),
            )
        )

    @staticmethod
    def _uv_environment_plan(
        *,
        root: Path,
        workspace_root: Path,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        config: m.Infra.CodegenConfigSpec,
    ) -> m.Infra.UvEnvironmentPlan:
        """Describe the exact setup overlay without executing uv."""
        del workspace_root
        workspace_environment = (
            target.make_profile is c.Infra.MakeProfile.WORKSPACE_ROOT
        )
        environment_root = target.root
        groups: tuple[str, ...] = ("dev", "codegen")
        editable_repositories: tuple[m.Infra.RepositoryRef, ...] = ()
        if workspace_environment:
            groups = (*groups, "workspace")
            editable_repositories = tuple(
                item
                for item in (workspace.repository, *workspace.members)
                if item.package and item.editable and not item.read_only
            )
        return m.Infra.UvEnvironmentPlan(
            project_root=root,
            environment_root=environment_root,
            lock_path=environment_root / c.Infra.UV_LOCK_FILENAME,
            python_version=config.toolchain.python_version,
            groups=groups,
            editable_repositories=editable_repositories,
        )

    def _skips_beads_client_config(
        self,
        destination: str,
        workspace: m.Infra.WorkspaceSpec,
        target: m.Infra.RepositoryConformTarget,
    ) -> bool:
        """Report whether one destination is a Beads artifact this target skips.

        Two independent reasons (mro-z89e, mro-cdzxf): the target participates
        in no ledger at all, or its governing workspace declares none.
        """
        if destination not in {
            c.Infra.BEADS_CONFIG_RELPATH,
            c.Infra.BEADS_METADATA_RELPATH,
        }:
            return False
        if not (target.beads_enabled or target.routing_only):
            return True
        return self.ledger_identity_for_target(workspace, target) is None

    @staticmethod
    def ledger_identity_for_target(
        workspace: m.Infra.WorkspaceSpec, _target: m.Infra.RepositoryConformTarget
    ) -> tuple[str, str] | None:
        """Return ``(issue_prefix, database)``, or ``None`` when there is none.

        Both identifiers are DECLARED by the tracker-owning workspace; neither is
        inferred from the other or from the target's name. ``WorkspaceSpec``
        validation refuses a half-declared ledger, so a manifest that declares a
        database has already declared its issue prefix. Beadless manifests
        declare neither and return no identity.
        """
        if workspace.ledger_id is None or workspace.ledger_prefix is None:
            return None
        return workspace.ledger_prefix, workspace.ledger_id

    @staticmethod
    def _declares_hook_config(profile: c.Infra.MakeProfile) -> bool:
        """Answer whether the SSOT projects a hook config onto this profile.

        The template manifest entry for ``.pre-commit-config.yaml`` -- not a
        second literal list here -- decides which profiles own a hook chain.
        """
        return any(
            profile in entry.profiles
            for entry in config.Infra.codegen.templates.entries
            if entry.destination == c.Infra.PRE_COMMIT_CONFIG_FILENAME
        )

    @staticmethod
    def _workflow_hook_stages(make_spec: m.Infra.MakeSpec) -> tuple[str, ...]:
        """Derive every git hook stage the workflow SSOT knows about.

        A context named ``pre_commit``/``pre_push`` in config/codegen.yaml is
        what makes the corresponding git hook part of the contract, so adding a
        hook context to the SSOT extends this with no code change.
        """
        contexts = {
            context
            for step in make_spec.workflow
            for context in step.contexts
            if context.startswith("pre_")
        }
        return tuple(sorted(context.replace("_", "-") for context in contexts))

    @classmethod
    def _declared_hook_stages(
        cls, make_spec: m.Infra.MakeSpec, profile: c.Infra.MakeProfile
    ) -> tuple[str, ...]:
        """Narrow the workflow stages to those this profile must have installed.

        A profile the manifest gives no hook config to declares no stages: it
        must end with its hooks UNINSTALLED. Deriving stages from the workflow
        alone installed pre-commit/pre-push into all 31 members whose config
        the same SSOT retires, leaving a shim pointing at a deleted file.
        """
        if not cls._declares_hook_config(profile):
            return ()
        return cls._workflow_hook_stages(make_spec)

    @classmethod
    def _hooks_directory(cls, repository_root: Path) -> p.Result[Path]:
        """Resolve the real hook directory, honouring worktrees and submodules.

        A linked worktree and a submodule both keep hooks outside ``.git/hooks``
        of the checkout, so asking git is the only correct resolution.
        """
        probe = u.Cli.capture(
            [c.Infra.GIT, "rev-parse", "--git-path", "hooks"], cwd=repository_root
        )
        if probe.failure:
            return r[Path].fail(
                probe.error
                or f"unable to resolve git hooks directory: {repository_root}"
            )
        resolved = Path(probe.value.strip())
        if not resolved.is_absolute():
            resolved = repository_root / resolved
        return r[Path].ok(resolved)

    @classmethod
    def _verify_hooks_plan(
        cls, plan: m.Infra.HooksPlan, *, allow_missing: bool
    ) -> p.Result[bool]:
        """Fail closed when the installed hooks disagree with the contract.

        Emitting .pre-commit-config.yaml without activating it left every lane
        committing and pushing ungated while conform still reported success.
        The reverse is drift too: a checkout the SSOT gives no hook config to
        must not carry an installed shim pointing at that absent file.
        """
        retired = tuple(
            stage
            for stage in plan.retired_stages
            if (plan.hooks_directory / stage).is_file()
        )
        if retired and not allow_missing:
            return r[bool].fail(
                "git hook is installed for a profile that declares none: "
                + ", ".join(
                    f"{stage} ({plan.hooks_directory / stage})" for stage in retired
                )
            )
        if not plan.stages:
            return r[bool].ok(True)
        missing = tuple(
            stage
            for stage in plan.stages
            if not (plan.hooks_directory / stage).is_file()
        )
        if not missing:
            drifted: list[str] = []
            for stage in plan.stages:
                hook_path = plan.hooks_directory / stage
                content = u.Cli.files_read_text(hook_path)
                marker = f"--hook-type={stage}"
                if content.failure or marker not in content.value:
                    drifted.append(f"{stage} ({hook_path})")
            if not drifted:
                return r[bool].ok(True)
            return r[bool].fail(
                "git hook is not managed by pre-commit: " + ", ".join(drifted)
            )
        if allow_missing:
            return r[bool].ok(True)
        return r[bool].fail(
            "git hook is not installed: "
            + ", ".join(
                f"{stage} ({plan.hooks_directory / stage})" for stage in missing
            )
        )

    @classmethod
    def _install_hooks_plan(cls, plan: m.Infra.HooksPlan) -> p.Result[bool]:
        """Converge installed hooks onto the contract, both ways.

        pre-commit owns the hook shim it emits, so installation AND retirement
        delegate to it rather than writing or deleting a second, divergent shim
        here. ``pre-commit uninstall`` needs no config present and leaves a
        foreign hook it did not write untouched, so retiring is safe on a
        checkout whose config the same run just removed.
        """
        retired = cls._retire_hooks_plan(plan)
        if retired.failure:
            return retired
        if not plan.stages:
            return cls._verify_hooks_plan(plan, allow_missing=False)
        command = [sys.executable, "-m", "pre_commit", "install"]
        for stage in plan.stages:
            command.extend(("-t", stage))
        installed = u.Cli.run_checked(command, cwd=plan.repository_root)
        if installed.failure:
            return r[bool].fail(
                installed.error
                or f"git hook installation failed: {plan.repository_root}"
            )
        return cls._verify_hooks_plan(plan, allow_missing=False)

    @classmethod
    def _retire_hooks_plan(cls, plan: m.Infra.HooksPlan) -> p.Result[bool]:
        """Uninstall every hook stage this checkout must not carry."""
        retired = tuple(
            stage
            for stage in plan.retired_stages
            if (plan.hooks_directory / stage).is_file()
        )
        if not retired:
            return r[bool].ok(True)
        command = [sys.executable, "-m", "pre_commit", "uninstall"]
        for stage in retired:
            command.extend(("-t", stage))
        uninstalled = u.Cli.run_checked(command, cwd=plan.repository_root)
        if uninstalled.failure:
            return r[bool].fail(
                uninstalled.error
                or f"git hook retirement failed: {plan.repository_root}"
            )
        return r[bool].ok(True)

    @staticmethod
    def _beads_ledger_root(workspace_root: Path) -> p.Result[Path]:
        """Resolve the principal checkout owning the workspace ledger."""
        topology = FlextInfraWorkspaceDetector.resolve_topology_roots(workspace_root)
        if topology.failure:
            return r[Path].fail(
                topology.error or "unable to resolve the governing workspace root"
            )
        return r[Path].ok(topology.value[2])

    @staticmethod
    def _beads_binary(ledger_root: Path) -> p.Result[Path]:
        """Resolve the mise-managed Beads binary pinned by the ledger root."""
        resolved = u.Cli.run_raw(["mise", "which", "bd"], cwd=ledger_root)
        if resolved.failure or resolved.value.exit_code != 0:
            return r[Path].fail(f"mise-managed Beads CLI is unavailable: {ledger_root}")
        binary = Path(resolved.value.stdout.strip())
        if not binary.is_file():
            return r[Path].fail(f"mise-resolved Beads CLI is not a file: {binary}")
        return r[Path].ok(binary)

    @classmethod
    def _beads_command(
        cls, plan: m.Infra.BeadsPlan, *arguments: str
    ) -> p.Result[p.Cli.CommandOutput]:
        """Run the ledger-root Beads binary, never an ambient PATH resolution."""
        ledger_root = plan.ledger_root
        binary = cls._beads_binary(ledger_root)
        if binary.failure:
            return r[p.Cli.CommandOutput].fail(
                binary.error or "mise-managed Beads CLI is unavailable"
            )
        return u.Cli.run_raw([str(binary.value), *arguments], cwd=ledger_root)

    @staticmethod
    def beads_declaration(
        repository_root: Path,
    ) -> p.Result[m.Infra.BeadsTrackerDeclaration]:
        """Parse the repository's committed tracker declaration, once.

        mro-o0cc: a committed ``.beads/config.yaml`` (e.g. the shared ``mro``
        ledger on the machine-wide Dolt server) is the tracker declaration for
        that repository; deriving the namespace from the repository name and
        rejecting the declared one inverted the SSOT. The file is parsed at
        this boundary into a validated model — absence and an invalid payload
        are failures the caller decides about, never a substituted string.
        """
        config_path = repository_root / ".beads" / "config.yaml"
        if not config_path.is_file():
            return r[m.Infra.BeadsTrackerDeclaration].fail(
                f"repository declares no Beads tracker: {config_path}"
            )
        loaded = u.Cli.yaml_load_mapping(config_path)
        try:
            declaration = m.Infra.BeadsTrackerDeclaration.model_validate({
                "issue_prefix": loaded.get("issue-prefix")
            })
        except c.ValidationError as exc:
            return r[m.Infra.BeadsTrackerDeclaration].fail_op(
                f"Beads tracker declaration is invalid: {config_path}", exc
            )
        return r[m.Infra.BeadsTrackerDeclaration].ok(declaration)

    @staticmethod
    def declared_beads_prefix(repository_root: Path, *, fallback: str) -> str:
        """Return the committed tracker prefix, falling back to the derived name.

        mro-o0cc: a committed ``.beads/config.yaml`` (e.g. the shared ``mro``
        ledger on the machine-wide Dolt server) is the tracker declaration for
        that repository; deriving the namespace from the repository name and
        rejecting the declared one inverted the SSOT; the derived name is only
        the default for repositories without a committed tracker config.
        """
        config_path = repository_root / ".beads" / "config.yaml"
        if not config_path.is_file():
            return fallback
        loaded = u.Cli.yaml_load_mapping(config_path)
        prefix = loaded.get("issue-prefix")
        if isinstance(prefix, str) and prefix.strip():
            return prefix.strip()
        return fallback

    @classmethod
    def _verify_beads_plan(cls, plan: m.Infra.BeadsPlan) -> p.Result[bool]:
        """Validate the principal ledger route and fail closed on disagreement.

        Worktrees that route to a principal ledger never own the tracker
        lifecycle: verification is skipped there and re-run at the real tree on
        apply.
        """
        if plan.routes_to_principal_ledger:
            return r[bool].ok(True)
        if os.environ.get(c.Infra.ENV_VAR_GITHUB_ACTIONS) == "true":
            # CI runners are ephemeral and do not carry a live Dolt tracker;
            # the Beads lifecycle is owned by development machines, not CI.
            return r[bool].ok(True)
        if not plan.enabled:
            beads_dir = plan.repository_root / ".beads"
            if not beads_dir.exists():
                return r[bool].ok(True)
            # Routing-only projections (attached standalones / worktree routes)
            # may commit config.yaml + metadata.json without owning tracker
            # state. Fail only when additional tracker artifacts appear.
            # dolt-server.port is a runtime probe written by the CLI when it
            # connects to the shared server; it is not tracker state.
            routing_only_names = frozenset({
                "config.yaml",
                "metadata.json",
                "dolt-server.port",
            })
            extra = tuple(
                path.name
                for path in beads_dir.iterdir()
                if path.name not in routing_only_names and not path.name.startswith(".")
            )
            if extra:
                return r[bool].fail(
                    f"Beads is disabled but tracker state exists: {beads_dir} "
                    f"({', '.join(sorted(extra))})"
                )
            return r[bool].ok(True)
        ledger_root = plan.ledger_root
        # Why: mise owns the binaries it declares. Re-auditing the resolved
        # version and digest here ran BEFORE the drift report, so a binary that
        # diverged from the pin aborted `make gen WHAT=apply` — the very command
        # that regenerates `.mise.toml` and installs the right one. Conform only
        # needs the CLI to answer; the toolchain owns which build that is.
        version = cls._beads_command(plan, "version")
        if version.failure or version.value.exit_code != 0:
            return r[bool].fail(f"mise-managed Beads CLI is unavailable: {ledger_root}")
        # Why: associating Beads with a workspace is OPTIONAL. A repository that
        # tracks no issues carries no `.beads/`, and that is a valid shape — not
        # a conform failure. Verify the ledger only when one actually exists.
        beads_dir = ledger_root / ".beads"
        if not beads_dir.exists():
            return r[bool].ok(True)
        if not beads_dir.is_dir():
            return r[bool].fail(f"Beads ledger path is not a directory: {beads_dir}")
        info = cls._beads_command(plan, "info", "--json")
        if info.failure or info.value.exit_code != 0:
            return r[bool].fail(f"Beads ledger inspection failed: {beads_dir}")
        parsed = u.Cli.json_parse(info.value.stdout)
        if parsed.failure:
            return r[bool].fail(f"Beads info returned invalid JSON: {beads_dir}")
        payload = u.Cli.json_as_mapping(parsed.value)
        tracker_config = u.Cli.json_deep_mapping(payload, "config")
        issue_prefix = u.Cli.json_pick_str(tracker_config, "issue_prefix")
        if issue_prefix != plan.canonical_prefix:
            return r[bool].fail(
                "Beads namespace mismatch: "
                f"{issue_prefix or '<missing>'} != {plan.canonical_prefix}"
            )
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraCodegenConform"]
