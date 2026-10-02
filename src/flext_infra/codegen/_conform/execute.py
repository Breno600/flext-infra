"""Transactional execution of conformance plans.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Self, override

from flext_core import r
from flext_infra import c, config, m, p, t, u
from flext_infra.codegen import (
    FlextInfraCodegenLazyInit,
    FlextInfraCodegenMiseArtifacts,
    FlextInfraCodegenTransaction,
)
from flext_infra.codegen._conform.plan import FlextInfraCodegenConformPlan
from flext_infra.workspace import FlextInfraWorkspaceDetector


class FlextInfraCodegenConformExecute(FlextInfraCodegenConformPlan):
    """Transactional execution of conformance plans.

    The chain is linear in dependency order, so execution statically inherits
    everything it calls: bootstrap (service root, request state) <- gitignore
    <- docs ownership <- beads routes <- file plans <- pyproject policy <-
    context render <- artifact render <- existing plan <- scaffold plan <- plan
    <- execute.
    """

    @classmethod
    def execute_request(
        cls: type[Self],
        request: m.Infra.CodegenConformRequest,
        initial_workspace: m.Infra.WorkspaceSpec | None = None,
        *,
        ports: m.Infra.CodegenConformPorts | None,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Execute one already validated request with the facade-wired ports.

        ``ports`` is required at every call: the complete surface consumes it,
        and a single-file surface declares its absence explicitly with ``None``.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenResult]``.

        """
        root = request.root.expanduser().resolve()
        bootstrap: t.VariadicTuple[m.Cli.AtomicDirectoryState] = ()
        initialized_git = False
        if initial_workspace is not None and not (root / c.PYPROJECT_FILENAME).exists():
            source = u.Infra.flext_integration_line(
                codegen=config.Infra.codegen,
                repository_root=root,
                bootstrap_source=initial_workspace.flext_source,
            )
            if source.failure:
                return r[m.Infra.CodegenResult].from_failure(source)
            # The project's declared scaffold source is validated before any
            # filesystem effect: a silent acceptance would materialize a whole
            # tree whose declared provenance was never a direct Git
            # requirement, and the declaration is the scaffold's provenance
            # input, not decoration.
            declared = (
                initial_workspace.project.flext_source
                if initial_workspace.project is not None
                else None
            )
            if declared is not None:
                distribution = config.Infra.codegen.infra_repository.distribution
                if u.Infra.dep_name(declared) != distribution:
                    return r[m.Infra.CodegenResult].fail(
                        f"scaffold source must declare {distribution}: {declared}",
                    )
                parsed = u.Infra.declared_git_source(declared)
                if parsed.failure:
                    return r[m.Infra.CodegenResult].from_failure(parsed)
                requirement_url, requirement_ref = parsed.value
                if (
                    not requirement_url.startswith("https://")
                    or not requirement_ref
                    or u.Infra.ref_is_commit(requirement_ref)
                ):
                    return r[m.Infra.CodegenResult].fail(
                        "infrastructure source must declare an HTTPS Git URL "
                        f"and integration line (never a commit): {declared}",
                    )
        # The supplied WorkspaceSpec already owns the declared integration branch.
        # Require it before materialization instead of a second divergent input.
        if (
            initial_workspace is not None
            and not (root / c.Infra.GIT_DIR).exists()
            and initial_workspace.integration is None
        ):
            return r[m.Infra.CodegenResult].fail(
                "initial integration is required to initialize repository Git: "
                "declare --repository-branch",
            )
        if initial_workspace is not None and not root.is_dir():
            planned = u.Cli.atomic_plan_directory_chain(root)
            if planned.failure:
                return r[m.Infra.CodegenResult].from_failure(planned)
            created = u.Cli.atomic_create_directory_chain_guarded(
                planned.value,
                permission_mode=0o755,
            )
            if created.failure:
                return r[m.Infra.CodegenResult].from_failure(created)
            bootstrap = tuple(created.value)
        if initial_workspace is not None and not (root / c.Infra.GIT_DIR).exists():
            # Git owns no answer for an unborn repository: the caller declares
            # the integration branch and a missing declaration fails loudly.
            if initial_workspace.integration is None:
                return r[m.Infra.CodegenResult].fail(
                    "initial branch is required to initialize the repository "
                    "Git: declare --repository-branch",
                )
            initialized = u.Cli.run_checked([
                c.Infra.GIT,
                "init",
                "--initial-branch",
                initial_workspace.integration.branch,
                str(root),
            ])
            if initialized.failure:
                return r[m.Infra.CodegenResult].from_failure(initialized)
            remote = u.Cli.run_checked([
                c.Infra.GIT,
                "-C",
                str(root),
                "remote",
                "add",
                c.Infra.GIT_DEFAULT_REMOTE,
                initial_workspace.repository.url,
            ])
            if remote.failure:
                return r[m.Infra.CodegenResult].from_failure(remote)
            committed = u.Cli.run_checked([
                c.Infra.GIT,
                "-C",
                str(root),
                "commit",
                "--allow-empty",
                "-m",
                "chore: initialize generated project",
            ])
            if committed.failure:
                return r[m.Infra.CodegenResult].from_failure(committed)
            initialized_git = True
        service = cls(
            repository_root=root,
            request=request,
            initial_workspace=initial_workspace,
            ports=ports,
        )
        try:
            result = service.execute()
        except Exception as exc:
            rollback = cls._rollback_request_bootstrap(
                root,
                initialized_git=initialized_git,
                directories=bootstrap,
            )
            if rollback.failure:
                exc.add_note(f"scaffold bootstrap rollback failed: {rollback.error}")
            raise
        if result.success:
            return result
        rollback = cls._rollback_request_bootstrap(
            root,
            initialized_git=initialized_git,
            directories=bootstrap,
        )
        if rollback.failure:
            return r[m.Infra.CodegenResult].fail(
                f"{result.error or 'generation failed'}; "
                f"scaffold bootstrap rollback failed: {rollback.error}",
            )
        return result

    @classmethod
    def _rollback_request_bootstrap(
        cls,
        root: Path,
        *,
        initialized_git: bool,
        directories: t.VariadicTuple[m.Cli.AtomicDirectoryState],
    ) -> p.Result[bool]:
        """Undo only Git and root directories created by this invocation.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if initialized_git:
            inventory = u.Cli.atomic_inventory_physical_tree(root / c.Infra.GIT_DIR)
            if inventory.failure:
                return r[bool].fail(f"Git rollback inventory failed: {inventory.error}")
            cleaned = u.Cli.atomic_cleanup_physical_tree_guarded(inventory.value)
            if cleaned.failure:
                return r[bool].fail(f"Git rollback failed: {cleaned.error}")
        return cls._rollback_scaffold_directories(directories)

    @override
    def execute(self) -> p.Result[m.Infra.CodegenResult]:
        """Run check or apply and require a verified fixed point.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenResult]``.

        """
        request = self.request or m.Infra.CodegenConformRequest(
            root=self.repository_root,
        )
        surface = c.Infra.CodegenConformSurface(request.what)
        if surface is c.Infra.CodegenConformSurface.ALL:
            return self._execute_managed(request)
        if c.Infra.CodegenConformMode(request.mode) is c.Infra.CodegenConformMode.APPLY:
            if surface in {
                c.Infra.CodegenConformSurface.MAKEFILE,
                c.Infra.CodegenConformSurface.DOCS_CONFIG,
                c.Infra.CodegenConformSurface.PYPROJECT,
            }:
                return self._execute_plan(request)
            mise_owner = FlextInfraCodegenMiseArtifacts(repository_root=request.root)
            transaction = FlextInfraCodegenTransaction(mise_owner)
            return transaction.run_locked(
                prepare=False,
                operation=lambda _scope_root: self._execute_plan(request),
            )
        return self._execute_plan(request)

    def _execute_plan(
        self,
        request: m.Infra.CodegenConformRequest,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Execute a non-toolchain conform surface without widening its scope.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenResult]``.

        """
        u.Cli.header("Codegen Conform")
        u.Cli.info(
            f"stage=plan mode={request.mode} scope={request.scope} "
            f"what={request.what} root={request.root}",
        )
        planned = self.plan(request)
        if planned.failure:
            return r[m.Infra.CodegenResult].from_failure(planned)
        plan = planned.value
        mode = c.Infra.CodegenConformMode(request.mode)
        changed = tuple(
            file for file in plan.files if u.Infra.codegen_file_requires_effect(file)
        )
        if mode is c.Infra.CodegenConformMode.CHECK:
            if changed:
                paths = ", ".join(str(file.path) for file in changed)
                return r[m.Infra.CodegenResult].fail(f"codegen drift detected: {paths}")
            return r[m.Infra.CodegenResult].ok(m.Infra.CodegenResult(plan=plan))
        surface = c.Infra.CodegenConformSurface(request.what)
        if surface not in {
            c.Infra.CodegenConformSurface.MAKEFILE,
            c.Infra.CodegenConformSurface.DOCS_CONFIG,
            c.Infra.CodegenConformSurface.PYPROJECT,
        }:
            return r[m.Infra.CodegenResult].fail(
                "partial codegen apply is prohibited; use the complete all surface",
            )
        mise_owner = FlextInfraCodegenMiseArtifacts(repository_root=request.root)
        transaction = FlextInfraCodegenTransaction(mise_owner)
        root = request.root.expanduser().resolve()
        roots = {"@bootstrap-0": root}
        return transaction.run_files_locked(
            roots,
            lambda scope_root: self._publish_bootstrap_locked(
                request,
                transaction,
                roots,
                scope_root,
            ),
        )

    def _publish_bootstrap_locked(
        self,
        request: m.Infra.CodegenConformRequest,
        transaction: FlextInfraCodegenTransaction,
        roots: t.MappingKV[str, Path],
        scope_root: Path,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Publish the entire declared bootstrap surface in one journaled phase.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenResult]``.
        """
        planned = self.plan(request)
        if planned.failure:
            return r[m.Infra.CodegenResult].from_failure(planned)
        plan = planned.value
        surface = c.Infra.CodegenConformSurface(request.what)
        destinations = self.surface_contract(surface).destinations
        if not destinations:
            return r[m.Infra.CodegenResult].fail(
                f"bootstrap requires declared destinations for {surface}",
            )
        expected_paths = {
            request.root.expanduser().resolve() / path for path in destinations
        }
        if {file.path for file in plan.files} != expected_paths:
            return r[m.Infra.CodegenResult].fail(
                f"bootstrap plan does not own the declared destinations for {surface}",
            )
        changed = tuple(
            file for file in plan.files if u.Infra.codegen_file_requires_effect(file)
        )
        if any(
            file.desired_content is None or file.desired_mode is None
            for file in changed
        ):
            return r[m.Infra.CodegenResult].fail(
                f"bootstrap cannot delete a declared destination for {surface}",
            )
        written: t.VariadicTuple[Path] = ()
        if changed:
            inputs = {
                state.path: state for file in plan.files for state in file.source_states
            }
            analysis = m.Infra.CodegenPhaseAnalysis(
                phase="conform-bootstrap",
                files=plan.files,
                inputs=tuple(inputs.values()),
            )
            published = transaction.publish_file_phase_locked(
                scope_root,
                roots,
                analysis,
                tuple(
                    sorted({
                        file.path.parent
                        for file in changed
                        if not file.path.parent.is_dir()
                    }),
                ),
                lambda: self._verify_bootstrap(request),
            )
            if published.failure:
                return r[m.Infra.CodegenResult].from_failure(published)
            written = published.value
        verified = self.plan(request)
        if verified.failure:
            return r[m.Infra.CodegenResult].from_failure(verified)
        residual = tuple(
            file
            for file in verified.value.files
            if u.Infra.codegen_file_requires_effect(file)
        )
        if residual:
            return r[m.Infra.CodegenResult].fail(
                f"Makefile bootstrap did not reach a fixed point: {residual[0].path}",
            )
        return r[m.Infra.CodegenResult].ok(
            m.Infra.CodegenResult(plan=verified.value, written_files=written),
        )

    def _verify_bootstrap(
        self,
        request: m.Infra.CodegenConformRequest,
    ) -> p.Result[bool]:
        """Validate the public conform plan reaches a fixed point before commit.

        Returns:
            The resulting ``p.Result[bool]``.
        """
        planned = self.plan(request)
        if planned.failure:
            return r[bool].from_failure(planned)
        residual = tuple(
            file
            for file in planned.value.files
            if u.Infra.codegen_file_requires_effect(file)
        )
        if residual:
            return r[bool].fail(
                f"bootstrap did not reach a fixed point: {residual[0].path}",
            )
        return r[bool].ok(True)

    def _execute_managed(
        self,
        request: m.Infra.CodegenConformRequest,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Run complete conformance inside the sole generation lock.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenResult]``.

        """
        ports = self.ports
        if ports is None:
            return r[m.Infra.CodegenResult].fail(
                "complete conform requires the facade-wired docs and fresh-import "
                "ports; run it through FlextInfra.codegen_conform",
            )
        mode = c.Infra.CodegenConformMode(request.mode)
        mise_owner = FlextInfraCodegenMiseArtifacts(repository_root=request.root)
        transaction = FlextInfraCodegenTransaction(mise_owner)
        return transaction.run_locked(
            prepare=mode is c.Infra.CodegenConformMode.APPLY,
            operation=lambda scope_root: self._execute_managed_locked(
                request,
                scope_root,
                transaction,
                ports,
            ),
        )

    def _execute_managed_locked(
        self,
        request: m.Infra.CodegenConformRequest,
        scope_root: Path,
        transaction: FlextInfraCodegenTransaction,
        ports: m.Infra.CodegenConformPorts,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Materialize scaffold parents, then run one locked generation cycle.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenResult]``.

        """
        prepared = self._prepare_scaffold_directories(request)
        if prepared.failure:
            return r[m.Infra.CodegenResult].from_failure(prepared)
        try:
            result = self._execute_managed_locked_prepared(
                request,
                scope_root,
                transaction,
                ports,
            )
        except Exception as exc:
            rollback = self._rollback_scaffold_directories(prepared.value)
            if rollback.failure:
                exc.add_note(f"scaffold directory rollback failed: {rollback.error}")
            raise
        if result.success:
            return result
        rollback = self._rollback_scaffold_directories(prepared.value)
        if rollback.failure:
            return r[m.Infra.CodegenResult].fail(
                f"{result.error or 'generation failed'}; "
                f"scaffold directory rollback failed: {rollback.error}",
            )
        return result

    def _lazy_phase(
        self,
        request: m.Infra.CodegenConformRequest,
        plan: m.Infra.CodegenPlan,
    ) -> p.Result[m.Infra.CodegenPhaseAnalysis]:
        """Plan each selected repository through its own Rope boundary.

        One call site; both CHECK (drift detection) and APPLY
        (phase publication + receipt) consume the same analysis.
        ADR-014: lazy-init ownership stays inside conform's
        transaction. Lazy-init plans exactly the repositories conform
        rewrites: the selected mutable ``internal_flext`` repositories of
        ``plan``, never a scope-excluded root or a third-party checkout.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenPhaseAnalysis]``.

        """
        files: list[m.Infra.CodegenFilePlan] = []
        inputs: t.MutableMappingKV[Path, m.Cli.AtomicFileState] = {}
        publications: list[m.Infra.LazyInitPlan] = []
        for repository in plan.repositories:
            if repository.kind is not c.Infra.ProjectKind.INTERNAL_FLEXT:
                continue
            root = (request.root / repository.path).resolve()
            analysis = FlextInfraCodegenLazyInit(
                repository_root=root,
                project_scope_roots=(root,),
            ).plan_files()
            if analysis.failure:
                return r[m.Infra.CodegenPhaseAnalysis].from_failure(analysis)
            files.extend(analysis.value.files)
            publications.extend(analysis.value.publications)
            for state in analysis.value.inputs:
                existing = inputs.get(state.path)
                if existing is not None and existing != state:
                    return r[m.Infra.CodegenPhaseAnalysis].fail(
                        f"lazy-init input changed across repository plans: {state.path}",
                    )
                inputs[state.path] = state
        return r[m.Infra.CodegenPhaseAnalysis].ok(
            m.Infra.CodegenPhaseAnalysis(
                phase="lazy-init",
                files=tuple(files),
                inputs=tuple(inputs[path] for path in sorted(inputs)),
                publications=tuple(publications),
            ),
        )

    def _execute_managed_locked_prepared(
        self,
        request: m.Infra.CodegenConformRequest,
        scope_root: Path,
        transaction: FlextInfraCodegenTransaction,
        ports: m.Infra.CodegenConformPorts,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Plan, publish, and validate one prepared locked generation cycle.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenResult]``.

        """
        u.Cli.header("Codegen Conform")
        u.Cli.info(
            f"stage=plan mode={request.mode} scope={request.scope} "
            f"what={request.what} root={request.root} lock_scope={scope_root}",
        )
        planned = self.plan(request)
        if planned.failure:
            return r[m.Infra.CodegenResult].from_failure(planned)
        plan = planned.value
        # Why (X-47): DECLARED scope excludes the workspace root repository
        # from `plan.repositories`; docs generation must not render the root
        # as an output scope either, or its report_dir escapes the transaction
        # layout that already excludes root for that same scope. Root guides
        # remain readable sources for members regardless of this flag.
        docs_include_root = any(
            repository.name == plan.workspace.repository.name
            for repository in plan.repositories
        )
        config_plans = self.mise_config_plans(plan)
        if config_plans.failure:
            return r[m.Infra.CodegenResult].from_failure(config_plans)
        changed = tuple(
            file for file in plan.files if u.Infra.codegen_file_requires_effect(file)
        )
        mode = c.Infra.CodegenConformMode(request.mode)
        if mode is c.Infra.CodegenConformMode.CHECK:
            routes = self.conform_workspace_beads_routes(request)
            if routes.failure:
                return r[m.Infra.CodegenResult].from_failure(routes)
            reality = transaction.validate_locked(scope_root, config_plans.value)
            if reality.failure:
                return r[m.Infra.CodegenResult].from_failure(reality)
            if changed:
                paths = ", ".join(str(file.path) for file in changed)
                report = u.Infra.codegen_file_drift_report(changed)
                return r[m.Infra.CodegenResult].fail(
                    f"codegen drift detected: {paths}\n{report}",
                )
            lazy_analysis = self._lazy_phase(request, plan)
            if lazy_analysis.failure:
                return r[m.Infra.CodegenResult].from_failure(lazy_analysis)
            lazy_changed = tuple(
                file
                for file in lazy_analysis.value.files
                if u.Infra.codegen_file_requires_effect(file)
            )
            if lazy_changed:
                paths = ", ".join(str(file.path) for file in lazy_changed)
                report = u.Infra.codegen_file_drift_report(lazy_changed)
                return r[m.Infra.CodegenResult].fail(
                    f"lazy-init drift detected: {paths}\n{report}",
                )
            docs_generator = ports.docs_planner(
                repository_root=request.root,
                projects=tuple(repository.name for repository in plan.repositories),
                include_root=docs_include_root,
            )
            docs_bundle = docs_generator.prepare_bundle()
            if docs_bundle.failure:
                return r[m.Infra.CodegenResult].from_failure(docs_bundle)
            docs_plans = docs_generator.plan_files(docs_bundle.value)
            if docs_plans.failure:
                return r[m.Infra.CodegenResult].from_failure(docs_plans)
            docs_changed = tuple(
                file
                for file in self.owned_docs_files(request, docs_plans.value)
                if u.Infra.codegen_file_requires_effect(file)
            )
            if docs_changed:
                paths = ", ".join(str(file.path) for file in docs_changed)
                report = u.Infra.codegen_file_drift_report(docs_changed)
                return r[m.Infra.CodegenResult].fail(
                    f"docs drift detected: {paths}\n{report}",
                )
            return r[m.Infra.CodegenResult].ok(m.Infra.CodegenResult(plan=plan))
        session = transaction.begin_locked(scope_root, config_plans.value, plan.files)
        if session.failure:
            return r[m.Infra.CodegenResult].from_failure(session)
        return transaction.publish_prepared_locked(
            session.value,
            lambda current: self._publish_managed_locked(
                request,
                plan,
                docs_include_root=docs_include_root,
                transaction=transaction,
                session=current,
                ports=ports,
            ),
        )

    def _publish_managed_locked(
        self,
        request: m.Infra.CodegenConformRequest,
        plan: m.Infra.CodegenPlan,
        *,
        docs_include_root: bool,
        transaction: FlextInfraCodegenTransaction,
        session: m.Infra.CodegenTransactionSession,
        ports: m.Infra.CodegenConformPorts,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Complete every post-begin phase through prepared-state recovery.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenResult]``.

        """
        lazy_analysis = self._lazy_phase(request, plan)
        if lazy_analysis.failure:
            aborted = transaction.abort_locked(
                session,
                lazy_analysis.error or "lazy-init planning failed",
            )
            return r[m.Infra.CodegenResult].from_failure(aborted)
        # A path already planned by conform has exactly one publication owner
        # in the transaction: the lazy-init phase keeps only the paths conform
        # does not plan, and that same filtered receipt is published and
        # verified at the fixed point.
        conform_paths = frozenset(file.path for file in plan.files)
        owned_lazy_analysis = m.Infra.CodegenPhaseAnalysis(
            phase=lazy_analysis.value.phase,
            files=tuple(
                file
                for file in lazy_analysis.value.files
                if file.path not in conform_paths
            ),
            inputs=lazy_analysis.value.inputs,
            publications=lazy_analysis.value.publications,
        )
        extended = transaction.append_phase_locked(
            session,
            owned_lazy_analysis.phase,
            owned_lazy_analysis.files,
        )
        if extended.failure:
            return r[m.Infra.CodegenResult].from_failure(extended)
        docs_generator = ports.docs_planner(
            repository_root=request.root,
            projects=tuple(repository.name for repository in plan.repositories),
            include_root=docs_include_root,
        )
        docs_bundle = docs_generator.prepare_bundle()
        if docs_bundle.failure:
            return r[m.Infra.CodegenResult].from_failure(docs_bundle)
        docs_directories = docs_generator.required_directories(docs_bundle.value)
        if docs_directories.failure:
            return r[m.Infra.CodegenResult].from_failure(docs_directories)
        owned_docs_directories = self._owned_docs_directories(
            request,
            plan,
            docs_directories.value,
        )
        with_directories = transaction.append_directories_locked(
            extended.value,
            "docs",
            owned_docs_directories,
        )
        if with_directories.failure:
            return r[m.Infra.CodegenResult].from_failure(with_directories)
        docs_plans = docs_generator.plan_files(docs_bundle.value)
        if docs_plans.failure:
            return r[m.Infra.CodegenResult].from_failure(docs_plans)
        owned_docs_files = self.owned_docs_files(request, docs_plans.value)
        docs_analysis = m.Infra.CodegenPhaseAnalysis(
            phase="docs",
            files=owned_docs_files,
            inputs=docs_bundle.value.source_states,
        )
        with_docs = transaction.append_phase_locked(
            with_directories.value,
            "docs",
            owned_docs_files,
        )
        if with_docs.failure:
            return r[m.Infra.CodegenResult].from_failure(with_docs)
        verified_plan: list[m.Infra.CodegenPlan] = []
        published = transaction.commit_locked(
            with_docs.value,
            lambda: self._validate_managed_fixed_point(
                request,
                with_docs.value,
                owned_lazy_analysis,
                docs_analysis,
                verified_plan,
            ),
        )
        if published.failure:
            return r[m.Infra.CodegenResult].from_failure(published)
        routes = self.conform_workspace_beads_routes(request)
        if routes.failure:
            return r[m.Infra.CodegenResult].from_failure(routes)
        allowed = self._allow_direnv_after_apply(request, published.value)
        if allowed.failure:
            return r[m.Infra.CodegenResult].from_failure(allowed)
        return r[m.Infra.CodegenResult].ok(
            m.Infra.CodegenResult(plan=verified_plan[0], written_files=published.value),
        )

    def _prepare_scaffold_directories(
        self,
        request: m.Infra.CodegenConformRequest,
    ) -> p.Result[t.VariadicTuple[m.Cli.AtomicDirectoryState]]:
        """Create config-declared scaffold parent chains under the generation lock.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Cli.AtomicDirectoryState]]``.

        """
        if (
            c.Infra.CodegenConformMode(request.mode)
            is not c.Infra.CodegenConformMode.APPLY
        ):
            return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].ok(())
        scaffolding = self.initial_workspace
        workspace = scaffolding
        if workspace is None:
            workspace_result = FlextInfraWorkspaceDetector.load_workspace_spec(
                request.root.expanduser().resolve(),
            )
            if workspace_result.failure:
                return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].from_failure(
                    workspace_result,
                )
            workspace = workspace_result.value
        project = workspace.project
        if project is None:
            # Scaffolding a new project requires its declared metadata, and that
            # path supplies the workspace explicitly. Conforming a repository
            # that declares no project block has no scaffold chain to create —
            # nothing to do is not invalid input, and treating it as an error
            # made `make gen` unusable in every repository without its
            # own manifest.
            if scaffolding is not None:
                return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].fail(
                    "scaffold workspace has no project metadata",
                )
            return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].ok(())
        profile = workspace.repository.role
        root = request.root.expanduser().resolve()
        directories = {root, root / c.Infra.MISE_LAUNCHER_DIRECTORY}
        for entry in config.Infra.codegen.templates.entries:
            if profile not in entry.profiles:
                continue
            if entry.requires_beads and workspace.beads is None:
                continue
            destination = entry.destination.format(
                package_name=project.package_name,
                ns=project.namespace_attribute,
            )
            relative = Path(destination)
            if relative.is_absolute() or ".." in relative.parts:
                return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].fail(
                    f"template destination escapes repository root: {destination}",
                )
            directories.add((root / relative).parent)
        created: list[m.Cli.AtomicDirectoryState] = []
        for directory in sorted(directories, key=u.Infra.path_depth):
            planned = u.Cli.atomic_plan_directory_chain(directory)
            if planned.failure:
                rollback = self._rollback_scaffold_directories(tuple(created))
                if rollback.failure:
                    return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].fail(
                        f"{planned.error}; scaffold directory rollback failed: "
                        f"{rollback.error}",
                    )
                return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].from_failure(
                    planned,
                )
            materialized = u.Cli.atomic_create_directory_chain_guarded(
                planned.value,
                permission_mode=0o755,
            )
            if materialized.failure:
                rollback = self._rollback_scaffold_directories(tuple(created))
                if rollback.failure:
                    return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].fail(
                        f"{materialized.error}; scaffold directory rollback failed: "
                        f"{rollback.error}",
                    )
                return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].from_failure(
                    materialized,
                )
            created.extend(materialized.value)
        return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].ok(tuple(created))

    @staticmethod
    def _rollback_scaffold_directories(
        created: t.VariadicTuple[m.Cli.AtomicDirectoryState],
    ) -> p.Result[bool]:
        """Remove only directories created by this locked scaffold attempt.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for state in reversed(created):
            removed = u.Cli.atomic_delete_empty_directory_guarded(state)
            if removed.failure:
                return removed
        return r[bool].ok(True)

    def _allow_direnv_after_apply(
        self,
        request: m.Infra.CodegenConformRequest,
        written_files: t.VariadicTuple[Path],
    ) -> p.Result[bool]:
        """Heal the direnv allow for every ``.envrc`` this apply published.

        ``make setup`` authorizes the rendered ``.envrc`` once; a later conform
        apply legitimately rewrites it (content-hash changes) and every
        subsequent command blocks on direnv's stale-allow warning. The
        generator owns the file it renders, so apply heals the allow itself
        instead of leaving every environment stale until the operator re-runs
        setup.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if (
            c.Infra.CodegenConformMode(request.mode)
            is not c.Infra.CodegenConformMode.APPLY
        ):
            return r[bool].ok(False)
        roots = {
            path.expanduser().resolve().parent
            for path in written_files
            if path.name == c.Infra.ENVRC_FILENAME
        }
        if not roots:
            return r[bool].ok(False)
        for root in sorted(roots):
            result = u.Cli.run_raw(
                (c.Infra.CLI_DIRENV, "allow", str(root)),
                cwd=root,
                timeout=c.Infra.TIMEOUT_SHORT,
            )
            if result.failure:
                return r[bool].from_failure(result)
            if not u.Cli.process_succeeded(result.value.outcome):
                return r[bool].fail(
                    f"direnv allow failed for {root}: "
                    f"{result.value.stderr.strip() or result.value.stdout.strip()}",
                )
        return r[bool].ok(True)

    def _validate_managed_fixed_point(
        self,
        request: m.Infra.CodegenConformRequest,
        session: m.Infra.CodegenTransactionSession,
        lazy_analysis: m.Infra.CodegenPhaseAnalysis,
        docs_analysis: m.Infra.CodegenPhaseAnalysis,
        verified_plan: list[m.Infra.CodegenPlan],
    ) -> p.Result[bool]:
        """Replan conform against live bytes before the journal can commit.

        This re-plan is the cycle's authoritative final plan: nothing that
        changes generated content publishes between it and the journal commit,
        so the caller reuses ``verified_plan`` as its result instead of
        planning the whole fleet a second time.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        u.Cli.info("stage=verify-fixed-point")
        verified = self.plan(request)
        if verified.failure:
            return r[bool].from_failure(verified)
        verified_plan.append(verified.value)
        residual = tuple(
            file
            for file in verified.value.files
            if u.Infra.codegen_file_requires_effect(file)
        )
        if residual:
            paths = ", ".join(str(file.path) for file in residual)
            drift = u.Infra.codegen_file_drift_report(residual)
            return r[bool].fail(
                f"codegen publication did not reach a fixed point: {paths}\n{drift}",
            )
        u.Cli.info("stage=verify-lazy-init-receipt")
        lazy_fixed_point = FlextInfraCodegenTransaction.validate_phase_analysis_locked(
            lazy_analysis,
        )
        if lazy_fixed_point.failure:
            return r[bool].from_failure(lazy_fixed_point)
        u.Cli.info("stage=verify-docs-receipt")
        docs_fixed_point = FlextInfraCodegenTransaction.validate_phase_analysis_locked(
            docs_analysis,
        )
        if docs_fixed_point.failure:
            return r[bool].from_failure(docs_fixed_point)
        mise = FlextInfraCodegenMiseArtifacts(repository_root=request.root)
        plan = session.plan
        if isinstance(plan, m.Infra.MiseToolchainWorkspacePlan):
            project_layouts = tuple(project.layout for project in plan.projects)
        else:
            project_layouts = plan.layout.projects
        for project_layout in project_layouts:
            validated = mise.validate_artifacts(
                project_layout.root,
                plan.layout.scope_root,
            )
            if validated.failure:
                return r[bool].from_failure(validated)
        # The fresh-process import proof needs the runtime make setup
        # provisions, so it belongs to make check (the fresh-import gate):
        # generation must publish a project that has no runtime yet.
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraCodegenConformExecute"]
