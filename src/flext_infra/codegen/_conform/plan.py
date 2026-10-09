"""Conformance plan selection and repository topology resolution.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

from flext_infra import c, config, m, p, r, t, u
from flext_infra.codegen._conform.scaffold_plan import (
    FlextInfraCodegenConformScaffoldPlan,
)
from flext_infra.codegen.lazy_init import FlextInfraCodegenLazyInit
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
        if request.what in {
            c.Infra.CodegenConformSurface.LAZY_INIT,
            c.Infra.CodegenConformSurface.FACADES,
        }:
            planned = self._plan_single_surface(request)
            if planned.failure:
                return r[m.Infra.CodegenPlan].from_failure(planned)
            return r[m.Infra.CodegenPlan].ok(planned.value[0])
        return self._plan_repositories(request)

    def _plan_single_surface(
        self,
        request: m.Infra.CodegenConformRequest,
    ) -> p.Result[t.Pair[m.Infra.CodegenPlan, m.Infra.CodegenPhaseAnalysis]]:
        """Plan the declared facade or lazy-init surface of one repository.

        Returns:
            The public plan and its complete authenticated phase analysis.

        """
        if request.what == c.Infra.CodegenConformSurface.FACADES:
            return self._plan_facade(request)
        return self._plan_lazy_init(request)

    def _plan_repositories(
        self,
        request: m.Infra.CodegenConformRequest,
    ) -> p.Result[m.Infra.CodegenPlan]:
        """Build the governed plans for the selected repository topology.

        Returns:
            The complete repository plan or its first planning failure.

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

    def _plan_facade(
        self,
        request: m.Infra.CodegenConformRequest,
    ) -> p.Result[t.Pair[m.Infra.CodegenPlan, m.Infra.CodegenPhaseAnalysis]]:
        """Plan one declared facade through its canonical family renderer.

        Args:
            request: The conform request containing the root and destination module.

        Returns:
            The plan and authenticated phase analysis, or the first failure.
        """
        result_type = r[t.Pair[m.Infra.CodegenPlan, m.Infra.CodegenPhaseAnalysis]]
        root = request.root.expanduser().resolve()
        topology = self._planning_workspace(request, root)
        if topology.failure:
            return result_type.from_failure(topology)
        workspace, _target, repository = topology.value
        destination_result = self._facade_destination(root, request.module)
        if destination_result.failure:
            return result_type.from_failure(destination_result)
        destination = destination_result.value
        analyzed = self._facade_analysis(root, destination)
        if analyzed.failure:
            return result_type.from_failure(analyzed)
        analysis = analyzed.value
        plan = m.Infra.CodegenPlan(
            request=request,
            repositories=(repository,),
            workspace=workspace,
            make_spec=config.Infra.codegen.make,
            uv_environments=(),
            files=analysis.files,
        )
        return result_type.ok((plan, analysis))

    @staticmethod
    def _facade_destination(root: Path, module: str | None) -> p.Result[Path]:
        """Validate a direct module destination in the existing package.

        Returns:
            The destination path or the original destination diagnostic.

        """
        layout = u.Infra.layout(root)
        if layout is None or module is None:
            return r[Path].fail(
                "facades requires an existing package and destination",
            )
        package_name, separator, module_name = module.partition(".")
        if (
            not separator
            or package_name != layout.package_dir.name
            or not package_name.isidentifier()
            or not module_name.isidentifier()
        ):
            return r[Path].fail(
                "facades --module must name a direct package module",
            )
        return r[Path].ok(layout.package_dir / f"{module_name}{c.Infra.EXT_PYTHON}")

    def _facade_analysis(
        self,
        root: Path,
        destination: Path,
    ) -> p.Result[m.Infra.CodegenPhaseAnalysis]:
        """Render and stage exactly one facade with its authenticated inputs.

        Returns:
            The selected file analysis or its first planning failure.

        """
        result_type = r[m.Infra.CodegenPhaseAnalysis]
        snapshots = self._facade_sources(root, destination)
        if snapshots.failure:
            return result_type.from_failure(snapshots)
        family, states, sources = snapshots.value
        rendered = self._render_facade(destination, family, sources)
        if rendered.failure:
            return result_type.from_failure(rendered)
        mode = states[0].mode
        if mode is None:
            return result_type.fail(
                f"facade input has no authenticated mode: {destination}",
            )
        file = self.file_plan(
            root,
            destination.relative_to(root).as_posix(),
            rendered.value,
            mode=mode,
            source_states=tuple(states),
        )
        if file.failure:
            return result_type.from_failure(file)
        return result_type.ok(
            m.Infra.CodegenPhaseAnalysis(
                phase=c.Infra.CodegenStagedFilePhase.CONFORM,
                files=(file.value,),
                inputs=tuple(states),
            ),
        )

    @staticmethod
    def _facade_family(source: str) -> p.Result[Literal["t", "u", "p", "m"]]:
        """Identify the selected renderer from the module's published declaration.

        Returns:
            The unique supported facade family or a declaration failure.

        """
        result_type = r[Literal["t", "u", "p", "m"]]
        match tuple(sorted(u.Infra.facade_letter_names_source(source))):
            case ("t",):
                return result_type.ok("t")
            case ("u",):
                return result_type.ok("u")
            case ("p",):
                return result_type.ok("p")
            case ("m",):
                return result_type.ok("m")
            case _:
                return result_type.fail(
                    "selected facade destination must declare one supported family",
                )

    @classmethod
    def _facade_sources(
        cls,
        root: Path,
        destination: Path,
    ) -> p.Result[
        t.Triple[
            Literal["t", "u", "p", "m"],
            list[m.Cli.AtomicFileState],
            dict[Path, str],
        ]
    ]:
        """Authenticate owners and consumers before family rendering.

        Returns:
            The family, ordered source states and decoded source, or a failure.

        """
        result_type = r[
            t.Triple[
                Literal["t", "u", "p", "m"],
                list[m.Cli.AtomicFileState],
                dict[Path, str],
            ]
        ]
        selected = cls._facade_source_state(root, destination)
        if selected.failure:
            return result_type.from_failure(selected)
        state, source = selected.value
        declared = cls._facade_family(source)
        if declared.failure:
            return result_type.from_failure(declared)
        family = declared.value
        states = [state]
        sources = {destination: source}
        # Type projection reads only its private family; the other renderers
        # also resolve executable consumers throughout the selected package.
        scan_root = destination.parent
        if family == "t":
            scan_root /= u.Infra.facade_families()[family].directory
        for path in sorted(scan_root.rglob(c.Infra.EXT_PYTHON_GLOB)):
            if path == destination:
                continue
            snapshot = cls._facade_source_state(root, path)
            if snapshot.failure:
                return result_type.from_failure(snapshot)
            state, source = snapshot.value
            states.append(state)
            sources[path] = source
        return result_type.ok((family, states, sources))

    @staticmethod
    def _facade_source_state(
        root: Path,
        path: Path,
    ) -> p.Result[t.Pair[m.Cli.AtomicFileState, str]]:
        """Read one required source without escaping the selected repository.

        Returns:
            Its authenticated state and decoded source, or the first failure.

        """
        result_type = r[t.Pair[m.Cli.AtomicFileState, str]]
        if not path.resolve().is_relative_to(root):
            return result_type.fail(f"facade input escapes repository: {path}")
        snapshot = u.Cli.atomic_read_binary_file_state(path, required=True)
        if snapshot.failure:
            return result_type.from_failure(snapshot)
        state = snapshot.value
        if state.content is None:
            return result_type.fail(f"facade input is absent: {path}")
        return result_type.ok((state, state.content.decode(c.Cli.ENCODING_DEFAULT)))

    @staticmethod
    def _render_facade(
        destination: Path,
        family: Literal["t", "u", "p", "m"],
        sources: t.MappingKV[Path, str],
    ) -> p.Result[str]:
        """Reuse the canonical renderer without selecting a different destination.

        Returns:
            Rendered source for exactly the requested declaring module.

        """
        if family == "t":
            return r[str].ok(
                u.Infra.render_type_facade(destination.parent, destination, sources),
            )
        if u.Infra.facade_module_path(destination.parent, family) != destination:
            return r[str].fail("selected facade differs from its declaring module")
        rendered = u.Infra.render_utility_facade(destination.parent, family=family)
        if rendered is None:
            return r[str].fail(f"selected facade has no private {family} owners")
        return r[str].ok(rendered)

    def _plan_lazy_init(
        self,
        request: m.Infra.CodegenConformRequest,
    ) -> p.Result[t.Pair[m.Infra.CodegenPlan, m.Infra.CodegenPhaseAnalysis]]:
        """Plan only initializer destinations in one authenticated repository.

        Returns:
            The public plan and its complete authenticated lazy-init receipt.

        """
        result_type = r[t.Pair[m.Infra.CodegenPlan, m.Infra.CodegenPhaseAnalysis]]
        root = request.root.expanduser().resolve()
        topology = self._planning_workspace(request, root)
        if topology.failure:
            return result_type.from_failure(topology)
        workspace, _target, repository = topology.value
        selected = self._select_repositories(request, workspace, repository)
        if selected.failure:
            return result_type.from_failure(selected)
        planned = FlextInfraCodegenLazyInit(
            repository_root=root,
            project_scope_roots=(root,),
            target_module=request.module,
        ).plan_files()
        if planned.failure:
            return result_type.from_failure(planned)
        # Support-file retirement is not part of this initializer-only surface.
        analysis = planned.value.model_copy(
            update={
                "files": tuple(
                    file
                    for file in planned.value.files
                    if file.path.name == c.Infra.INIT_PY
                ),
            },
        )
        plan = m.Infra.CodegenPlan(
            request=request,
            repositories=selected.value,
            workspace=workspace,
            make_spec=config.Infra.codegen.make,
            uv_environments=(),
            files=analysis.files,
        )
        return result_type.ok((plan, analysis))

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
                        c.Infra.CodegenConformSurface.MISE_CONFIG,
                    }
                ),
            )
            if workspace_result.failure:
                return result_type.from_failure(workspace_result)
            workspace = workspace_result.value
        current_repository = workspace.repository
        if self.initial_workspace is None and request.what not in {
            c.Infra.CodegenConformSurface.MAKEFILE,
            c.Infra.CodegenConformSurface.PYPROJECT,
            c.Infra.CodegenConformSurface.MISE_CONFIG,
        }:
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
