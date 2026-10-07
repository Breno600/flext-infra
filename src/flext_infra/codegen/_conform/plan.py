"""Conformance plan selection and repository topology resolution.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import time
from pathlib import Path

from flext_core import r
from flext_infra import c, m, p, t, u
from flext_infra._config import config
from flext_infra.codegen._conform.scaffold_plan import (
    FlextInfraCodegenConformScaffoldPlan,
)
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector


class FlextInfraCodegenConformPlan(FlextInfraCodegenConformScaffoldPlan):
    """Conformance planning across scaffold and existing repositories."""

    def plan(
        self,
        request: m.Infra.CodegenConformRequest,
    ) -> p.Result[m.Infra.CodegenPlan]:
        """Build and validate the complete selection without writing.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenPlan]``.

        """
        config_spec = config.Infra.codegen
        root = request.root.expanduser().resolve()
        targets = self._planning_workspace(request, root)
        if targets.failure:
            return r[m.Infra.CodegenPlan].from_failure(targets)
        workspace, current_target, current_repository = targets.value
        selected_result = self._select_repositories(
            request,
            workspace,
            current_repository,
        )
        if selected_result.failure:
            return r[m.Infra.CodegenPlan].from_failure(selected_result)
        selected = selected_result.value
        contract = self.surface_contract(c.Infra.CodegenConformSurface(request.what))
        gathered = self._gathered_repository_plans(
            root,
            workspace,
            current_target,
            selected,
            contract,
        )
        if gathered.failure:
            return r[m.Infra.CodegenPlan].from_failure(gathered)
        files, environments = gathered.value
        return r[m.Infra.CodegenPlan].ok(
            m.Infra.CodegenPlan(
                request=request,
                repositories=selected,
                workspace=workspace,
                make_spec=config_spec.make,
                uv_environments=tuple(environments),
                files=tuple(files),
            ),
        )

    def _planning_workspace(
        self,
        request: m.Infra.CodegenConformRequest,
        root: Path,
    ) -> p.Result[
        t.Triple[
            m.Infra.WorkspaceSpec,
            m.Infra.RepositoryConformTarget,
            m.Infra.RepositoryRef,
        ]
    ]:
        """Load the planning workspace and its current conformance target.

        Returns:
            The resulting ``p.Result[t.Triple[m.Infra.WorkspaceSpec,
                m.Infra.RepositoryConformTarget, m.Infra.RepositoryRef]]``.

        """
        result_type = r[
            t.Triple[
                m.Infra.WorkspaceSpec,
                m.Infra.RepositoryConformTarget,
                m.Infra.RepositoryRef,
            ]
        ]
        workspace = self.initial_workspace
        if workspace is None:
            workspace_result = FlextInfraWorkspaceDetector.load_workspace_spec(
                root,
                allow_unprovisioned_members=(
                    request.what
                    in {
                        c.Infra.CodegenConformSurface.MAKEFILE,
                        c.Infra.CodegenConformSurface.DOCS_CONFIG,
                        c.Infra.CodegenConformSurface.PYPROJECT,
                    }
                ),
            )
            if workspace_result.failure:
                return result_type.from_failure(workspace_result)
            workspace = workspace_result.value
        current_repository = workspace.repository
        if self.initial_workspace is None:
            current_target_result = FlextInfraWorkspaceDetector.conform_target(
                root,
                workspace,
            )
            if current_target_result.failure:
                return result_type.from_failure(current_target_result)
            current_target = current_target_result.value
            current_repository = current_target.repository
        else:
            current_target = m.Infra.RepositoryConformTarget(
                repository=current_repository,
                root=root,
                make_profile=current_repository.role,
                beads=workspace.beads,
                project=workspace.project,
                canonical_project_name=current_repository.distribution,
                ci_enabled=True,
                publishes_release=current_repository.publishes_release,
                gascity_enabled=workspace.gascity_enabled,
                external_dependency_paths=workspace.external_dependency_paths,
            )
        return result_type.ok((workspace, current_target, current_repository))

    def _gathered_repository_plans(
        self,
        root: Path,
        workspace: m.Infra.WorkspaceSpec,
        current_target: m.Infra.RepositoryConformTarget,
        selected: t.VariadicTuple[m.Infra.RepositoryRef],
        contract: m.Infra.CodegenConformSurfaceContract,
    ) -> p.Result[
        t.Pair[list[m.Infra.CodegenFilePlan], list[m.Infra.UvEnvironmentPlan]]
    ]:
        """Plan every selected repository and collect its governed file plans.

        Returns:
            The resulting ``p.Result[t.Pair[list[m.Infra.CodegenFilePlan],
                list[m.Infra.UvEnvironmentPlan]]]``.

        """
        result_type = r[
            t.Pair[list[m.Infra.CodegenFilePlan], list[m.Infra.UvEnvironmentPlan]]
        ]
        config_spec = config.Infra.codegen
        files: list[m.Infra.CodegenFilePlan] = []
        environments: list[m.Infra.UvEnvironmentPlan] = []
        total_repositories = len(selected)
        u.Cli.info(f"stage=plan repositories={total_repositories}")
        for repository_index, repository in enumerate(selected, start=1):
            repository_started = time.monotonic()
            u.Cli.progress(
                repository_index,
                total_repositories,
                repository.name,
                "conform",
            )
            u.Cli.info(
                f"  stage=topology repository={repository.name} "
                f"role={repository.role.value} kind={repository.kind.value}",
            )
            if repository.kind is not c.Infra.ProjectKind.INTERNAL_FLEXT:
                u.Cli.info(
                    f"  stage=skip repository={repository.name} "
                    f"kind={repository.kind.value} is not rewritten by generation",
                )
                continue
            planned_inputs = self._repository_planning_inputs(
                root,
                workspace,
                current_target,
                repository,
            )
            if planned_inputs.failure:
                return result_type.from_failure(planned_inputs)
            repository_root, target, local_workspace = planned_inputs.value
            planned = self._governed_repository_plans(
                repository,
                workspace,
                target,
                local_workspace,
                contract,
            )
            if planned.failure:
                return result_type.from_failure(planned)
            governed_plans, retired_plans = planned.value
            files.extend(governed_plans)
            files.extend(retired_plans)
            environments.append(
                self.uv_environment_plan(
                    root=repository_root,
                    target=target,
                    workspace=local_workspace,
                    config=config_spec,
                ),
            )
            u.Cli.status(
                "conform",
                repository.name,
                result=True,
                elapsed=time.monotonic() - repository_started,
            )
        return result_type.ok((files, environments))

    def _repository_planning_inputs(
        self,
        root: Path,
        workspace: m.Infra.WorkspaceSpec,
        current_target: m.Infra.RepositoryConformTarget,
        repository: m.Infra.RepositoryRef,
    ) -> p.Result[
        t.Triple[
            Path,
            m.Infra.RepositoryConformTarget,
            m.Infra.WorkspaceSpec,
        ]
    ]:
        """Resolve one repository's checkout root, target, and local workspace.

        Returns:
            The resulting ``p.Result[t.Triple[Path,
                m.Infra.RepositoryConformTarget, m.Infra.WorkspaceSpec]]``.

        """
        result_type = r[
            t.Triple[
                Path,
                m.Infra.RepositoryConformTarget,
                m.Infra.WorkspaceSpec,
            ]
        ]
        resolved = self._resolved_repository_root(
            root,
            workspace,
            current_target,
            repository,
        )
        if resolved.failure:
            return result_type.from_failure(resolved)
        repository_root = resolved.value
        is_current_repository = repository.name == current_target.repository.name
        if is_current_repository:
            return result_type.ok(
                (repository_root, current_target, workspace),
            )
        local = self._member_local_workspace(workspace, repository, repository_root)
        if local.failure:
            return result_type.from_failure(local)
        local_workspace = local.value
        target_result = FlextInfraWorkspaceDetector.conform_target(
            repository_root,
            local_workspace,
        )
        if target_result.failure:
            return result_type.from_failure(target_result)
        target = target_result.value
        if repository.path != Path():
            target = target.model_copy(update={"repository": repository})
        return result_type.ok((repository_root, target, local_workspace))

    def _resolved_repository_root(
        self,
        root: Path,
        workspace: m.Infra.WorkspaceSpec,
        current_target: m.Infra.RepositoryConformTarget,
        repository: m.Infra.RepositoryRef,
    ) -> p.Result[Path]:
        """Resolve and authenticate one repository's checkout root.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        result_type = r[Path]
        is_current_repository = repository.name == current_target.repository.name
        if is_current_repository:
            repository_root = current_target.root
            if repository_root != root:
                return result_type.fail(
                    "current conformance target differs from the requested root: "
                    f"{repository_root} != {root}",
                )
            return result_type.ok(repository_root)
        # The governing root is the requested checkout, never the
        # previous iteration's member: resolving the second declared
        # repository against the first produced <root>/alpha/beta.
        repository_root_result = self._repository_root(root, workspace, repository)
        if repository_root_result.failure:
            return result_type.from_failure(repository_root_result)
        repository_root = repository_root_result.value
        if repository_root.exists() and not repository_root.is_dir():
            return result_type.fail(
                f"declared repository path is not a directory: {repository_root}",
            )
        if not repository_root.is_dir() and self.initial_workspace is None:
            return result_type.fail(
                f"declared repository checkout is missing: {repository_root}",
            )
        return result_type.ok(repository_root)

    @staticmethod
    def _member_local_workspace(
        workspace: m.Infra.WorkspaceSpec,
        repository: m.Infra.RepositoryRef,
        repository_root: Path,
    ) -> p.Result[m.Infra.WorkspaceSpec]:
        """Load the local workspace a declared member plans from.

        Returns:
            The resulting ``p.Result[m.Infra.WorkspaceSpec]``.

        """
        if repository.path != Path():
            declared_member = FlextInfraWorkspaceDetector.load_workspace_spec(
                repository_root,
            )
            if declared_member.failure:
                return r[m.Infra.WorkspaceSpec].from_failure(declared_member)
            local_repository = repository.model_copy(update={"path": Path()})
            # The parent owns topology and selection; the member owns its
            # project metadata, including the runtime dependency profile
            # and the namespace production scope it declares.
            return r[m.Infra.WorkspaceSpec].ok(
                m.Infra.WorkspaceSpec(
                    name=repository.name,
                    docs_audit=declared_member.value.docs_audit,
                    beads=workspace.beads,
                    repository=local_repository,
                    project=declared_member.value.project,
                    namespace_scan_dirs=(declared_member.value.namespace_scan_dirs),
                    candidate_dependencies=workspace.candidate_dependencies,
                    superproject_members=(declared_member.value.superproject_members),
                ),
            )
        local_workspace_result = FlextInfraWorkspaceDetector.load_workspace_spec(
            repository_root,
        )
        if local_workspace_result.failure:
            return r[m.Infra.WorkspaceSpec].from_failure(local_workspace_result)
        return r[m.Infra.WorkspaceSpec].ok(local_workspace_result.value)

    def _governed_repository_plans(
        self,
        repository: m.Infra.RepositoryRef,
        workspace: m.Infra.WorkspaceSpec,
        target: m.Infra.RepositoryConformTarget,
        local_workspace: m.Infra.WorkspaceSpec,
        contract: m.Infra.CodegenConformSurfaceContract,
    ) -> p.Result[t.Pair[list[m.Infra.CodegenFilePlan], list[m.Infra.CodegenFilePlan]]]:
        """Plan one repository's governed files and its retired projections.

        Returns:
            The resulting ``p.Result[t.Pair[list[m.Infra.CodegenFilePlan],
                list[m.Infra.CodegenFilePlan]]]``.

        """
        result_type = r[
            t.Pair[list[m.Infra.CodegenFilePlan], list[m.Infra.CodegenFilePlan]]
        ]
        config_spec = config.Infra.codegen
        if (
            self.initial_workspace is not None
            and repository.name == workspace.repository.name
        ):
            repository_plan = self._plan_scaffold_repository(
                target=target,
                workspace=local_workspace,
                codegen=config_spec,
                contract=contract,
            )
        else:
            repository_plan = self._plan_existing_repository(
                target=target,
                workspace=local_workspace,
                codegen=config_spec,
                contract=contract,
            )
        if repository_plan.failure:
            return result_type.from_failure(repository_plan)
        governed = self._complete_governed_plans(
            target,
            repository_plan.value,
            config_spec,
            contract,
        )
        if governed.failure:
            return result_type.from_failure(governed)
        governed_files = list(governed.value)
        retired_files: list[m.Infra.CodegenFilePlan] = []
        if contract.complete_governed:
            retired = self.retired_projection_plans(
                target.root,
                target.make_profile,
            )
            if retired.failure:
                return result_type.from_failure(retired)
            governed_paths = {item.path for item in governed.value}
            retired_files.extend(
                item for item in retired.value if item.path not in governed_paths
            )
        return result_type.ok((governed_files, retired_files))

    @staticmethod
    def _select_repositories(
        request: m.Infra.CodegenConformRequest,
        workspace: m.Infra.WorkspaceSpec,
        current_repository: m.Infra.RepositoryRef,
    ) -> p.Result[t.VariadicTuple[m.Infra.RepositoryRef]]:
        """Resolve self/subprojects/all from the local read-only topology.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.RepositoryRef]]``.

        """
        scope = c.Infra.CodegenConformScope(request.scope)
        selected: t.VariadicTuple[m.Infra.RepositoryRef]
        if scope is c.Infra.CodegenConformScope.SELF:
            selected = (current_repository,)
        elif scope is c.Infra.CodegenConformScope.DECLARED:
            if not workspace.subprojects:
                return r[t.VariadicTuple[m.Infra.RepositoryRef]].fail(
                    "subprojects scope requires local .gitmodules entries",
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
            return r[t.VariadicTuple[m.Infra.RepositoryRef]].fail(
                "selected repositories do not permit code generation",
            )
        return r[t.VariadicTuple[m.Infra.RepositoryRef]].ok(mutable)

    @staticmethod
    def _repository_root(
        root: Path,
        workspace: p.Infra.WorkspaceSpec,
        repository: p.Infra.RepositoryRef,
    ) -> p.Result[Path]:
        """Resolve one declared checkout without escaping its workspace owner.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        if repository.name == workspace.repository.name:
            return r[Path].ok(root)
        resolved_root = root.resolve()
        resolved: Path = (resolved_root / repository.path).resolve()
        if not resolved.is_relative_to(resolved_root):
            return r[Path].fail(
                "declared repository path escapes workspace root: "
                f"{repository.path.as_posix()}",
            )
        return r[Path].ok(resolved)

    @staticmethod
    def _repository_provider(
        repository: m.Infra.RepositoryRef,
    ) -> p.Result[m.Infra.ProviderIdentitySpec]:
        """Resolve one repository to its self-declared provider identity.

        Returns:
            The resulting ``p.Result[m.Infra.ProviderIdentitySpec]``.

        """
        return u.Infra.repository_provider(repository)
