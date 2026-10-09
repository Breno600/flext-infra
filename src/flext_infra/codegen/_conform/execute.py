"""Transactional execution of conformance plans.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Self, override

from flext_infra import c, config, m, p, r, t, u
from flext_infra.codegen import FlextInfraCodegenTransaction
from flext_infra.codegen._conform.execute_directed import (
    FlextInfraCodegenConformExecuteDirected,
)
from flext_infra.codegen.lazy_init import FlextInfraCodegenLazyInit
from flext_infra.codegen.mise_artifacts import FlextInfraCodegenMiseArtifacts


class FlextInfraCodegenConformExecute(FlextInfraCodegenConformExecuteDirected):
    """Transactional execution of conformance plans.

    The chain is linear in dependency order, so execution statically inherits
    everything it calls: bootstrap (service root, request state) <- gitignore
    <- docs ownership <- beads routes <- file plans <- pyproject policy <-
    context render <- artifact render <- existing plan <- scaffold plan <- plan
    <- execute scaffold <- directed file publication <- execute.
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
        prelude = cls._validated_request_prelude(root, initial_workspace)
        if prelude.failure:
            return r[m.Infra.CodegenResult].from_failure(prelude)
        if initial_workspace is not None and not root.is_dir():
            created = cls._bootstrap_request_root(root)
            if created.failure:
                return r[m.Infra.CodegenResult].from_failure(created)
            bootstrap = tuple(created.value)
        if initial_workspace is not None and not (root / c.Infra.GIT_DIR).exists():
            initialized = cls._initialize_request_git(root, initial_workspace)
            if initialized.failure:
                return r[m.Infra.CodegenResult].from_failure(initialized)
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

    @staticmethod
    def _validated_request_prelude(
        root: Path,
        initial_workspace: m.Infra.WorkspaceSpec | None,
    ) -> p.Result[bool]:
        """Validate the scaffold provenance and the declared integration branch.

        The project's declared scaffold source is validated before any
        filesystem effect: a silent acceptance would materialize a whole tree
        whose declared provenance was never a direct Git requirement, and the
        declaration is the scaffold's provenance input, not decoration. The
        supplied WorkspaceSpec already owns the declared integration branch;
        require it before materialization instead of a second divergent input.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if initial_workspace is None:
            return r[bool].ok(value=True)
        if not (root / c.PYPROJECT_FILENAME).exists():
            source = FlextInfraCodegenConformExecute._validated_scaffold_source(
                root,
                initial_workspace,
            )
            if source.failure:
                return r[bool].from_failure(source)
        if (
            not (root / c.Infra.GIT_DIR).exists()
            and initial_workspace.integration is None
        ):
            return r[bool].fail(
                "initial integration is required to initialize repository Git: "
                "declare --repository-branch",
            )
        return r[bool].ok(value=True)

    @staticmethod
    def _validated_scaffold_source(
        root: Path,
        initial_workspace: m.Infra.WorkspaceSpec,
    ) -> p.Result[bool]:
        """Validate the declared scaffold provenance before any filesystem effect.

        A silent acceptance would materialize a whole tree whose declared
        provenance was never a direct Git requirement, and the declaration is
        the scaffold's provenance input, not decoration.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        source = u.Infra.flext_integration_line(
            codegen=config.Infra.codegen,
            repository_root=root,
            bootstrap_source=initial_workspace.flext_source,
        )
        if source.failure:
            return r[bool].from_failure(source)
        declared = (
            initial_workspace.project.flext_source
            if initial_workspace.project is not None
            else None
        )
        if declared is None:
            return r[bool].ok(value=True)
        distribution = config.Infra.codegen.infra_repository.distribution
        if u.Infra.dep_name(declared) != distribution:
            return r[bool].fail(
                f"scaffold source must declare {distribution}: {declared}",
            )
        parsed = u.Infra.declared_git_source(declared)
        if parsed.failure:
            return r[bool].from_failure(parsed)
        requirement_url, requirement_ref = parsed.value
        if (
            not requirement_url.startswith("https://")
            or not requirement_ref
            or u.Infra.ref_is_commit(requirement_ref)
        ):
            return r[bool].fail(
                "infrastructure source must declare an HTTPS Git URL "
                f"and integration line (never a commit): {declared}",
            )
        return r[bool].ok(value=True)

    @staticmethod
    def _bootstrap_request_root(
        root: Path,
    ) -> p.Result[t.VariadicTuple[m.Cli.AtomicDirectoryState]]:
        """Plan and create the guarded root directory chain for a new project.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Cli.AtomicDirectoryState]]
            ``.

        """
        planned = u.Cli.atomic_plan_directory_chain(root)
        if planned.failure:
            return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].from_failure(planned)
        created = u.Cli.atomic_create_directory_chain_guarded(
            planned.value,
            permission_mode=0o755,
        )
        if created.failure:
            return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].from_failure(created)
        return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].ok(tuple(created.value))

    @staticmethod
    def _initialize_request_git(
        root: Path,
        initial_workspace: m.Infra.WorkspaceSpec,
    ) -> p.Result[bool]:
        """Initialize the unborn repository Git from its declared integration.

        Git owns no answer for an unborn repository: the caller declares the
        integration branch and a missing declaration fails loudly.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if initial_workspace.integration is None:
            return r[bool].fail(
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
            return r[bool].from_failure(initialized)
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
            return r[bool].from_failure(remote)
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
            return r[bool].from_failure(committed)
        return r[bool].ok(value=True)

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
        if surface in {
            c.Infra.CodegenConformSurface.LAZY_INIT,
            c.Infra.CodegenConformSurface.FACADES,
        }:
            return self._execute_lazy_init(request)
        if surface is c.Infra.CodegenConformSurface.ALL:
            return self._execute_managed(request)
        if (
            surface is c.Infra.CodegenConformSurface.MISE_CONFIG
            and c.Infra.CodegenConformMode(request.mode)
            is c.Infra.CodegenConformMode.CHECK
        ):
            transaction = FlextInfraCodegenTransaction(
                FlextInfraCodegenMiseArtifacts(repository_root=request.root),
            )
            return transaction.run_files_locked(
                {"@bootstrap-0": request.root.expanduser().resolve()},
                lambda _scope_root: self._execute_plan(request),
                prepare=False,
            )
        if c.Infra.CodegenConformMode(request.mode) is c.Infra.CodegenConformMode.APPLY:
            if surface in {
                c.Infra.CodegenConformSurface.MAKEFILE,
                c.Infra.CodegenConformSurface.DOCS_CONFIG,
                c.Infra.CodegenConformSurface.PYPROJECT,
                c.Infra.CodegenConformSurface.MISE_CONFIG,
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
            if request.what == c.Infra.CodegenConformSurface.MISE_CONFIG:
                checked = FlextInfraCodegenMiseArtifacts.validate_config_file(
                    request.root / c.Infra.MISE_TOML_FILENAME,
                )
                if checked.failure:
                    return r[m.Infra.CodegenResult].from_failure(checked)
            return r[m.Infra.CodegenResult].ok(m.Infra.CodegenResult(plan=plan))
        surface = c.Infra.CodegenConformSurface(request.what)
        if surface not in {
            c.Infra.CodegenConformSurface.MAKEFILE,
            c.Infra.CodegenConformSurface.DOCS_CONFIG,
            c.Infra.CodegenConformSurface.PYPROJECT,
            c.Infra.CodegenConformSurface.MISE_CONFIG,
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
        written = self._publish_bootstrap_phase(
            request,
            plan,
            transaction,
            roots,
            scope_root,
        )
        if written.failure:
            return r[m.Infra.CodegenResult].from_failure(written)
        verified = self.plan(request)
        if verified.failure:
            return r[m.Infra.CodegenResult].from_failure(verified)
        fixed_point = u.Infra.codegen_fixed_point(
            verified.value.files,
            subject="Makefile bootstrap",
        )
        if fixed_point.failure:
            return r[m.Infra.CodegenResult].from_failure(fixed_point)
        return r[m.Infra.CodegenResult].ok(
            m.Infra.CodegenResult(plan=verified.value, written_files=written.value),
        )

    def _publish_bootstrap_phase(
        self,
        request: m.Infra.CodegenConformRequest,
        plan: m.Infra.CodegenPlan,
        transaction: FlextInfraCodegenTransaction,
        roots: t.MappingKV[str, Path],
        scope_root: Path,
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Authorize the surface contract, then publish its changed files.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]`` with the written
            bootstrap files.

        """
        surface = c.Infra.CodegenConformSurface(request.what)
        destinations = self.surface_contract(surface).destinations
        if not destinations:
            return r[t.VariadicTuple[Path]].fail(
                f"bootstrap requires declared destinations for {surface}",
            )
        expected_paths = {
            request.root.expanduser().resolve() / path for path in destinations
        }
        if {file.path for file in plan.files} != expected_paths:
            return r[t.VariadicTuple[Path]].fail(
                f"bootstrap plan does not own the declared destinations for {surface}",
            )
        changed = tuple(
            file for file in plan.files if u.Infra.codegen_file_requires_effect(file)
        )
        if any(
            file.desired_content is None or file.desired_mode is None
            for file in changed
        ):
            return r[t.VariadicTuple[Path]].fail(
                f"bootstrap cannot delete a declared destination for {surface}",
            )
        if not changed:
            if surface is c.Infra.CodegenConformSurface.MISE_CONFIG:
                checked = self._verify_bootstrap(request)
                if checked.failure:
                    return r[t.VariadicTuple[Path]].from_failure(checked)
            return r[t.VariadicTuple[Path]].ok(())
        inputs = {
            state.path: state for file in plan.files for state in file.source_states
        }
        analysis = m.Infra.CodegenPhaseAnalysis(
            phase=c.Infra.CodegenStagedFilePhase.CONFORM_BOOTSTRAP,
            files=plan.files,
            inputs=tuple(inputs.values()),
        )
        return transaction.publish_file_phase_locked(
            scope_root,
            roots,
            analysis,
            m.Infra.CodegenPhasePublicationPolicy(
                directories=tuple(
                    sorted({
                        file.path.parent
                        for file in changed
                        if not file.path.parent.is_dir()
                    }),
                ),
                validator=lambda: self._verify_bootstrap(request),
            ),
            staged_validator=(
                self._validate_mise_stage
                if surface is c.Infra.CodegenConformSurface.MISE_CONFIG
                else None
            ),
        )

    @staticmethod
    def _validate_mise_stage(
        session: m.Infra.CodegenTransactionSession,
        publications: t.VariadicTuple[m.Infra.CodegenStagedFile],
    ) -> p.Result[m.Infra.CodegenTransactionSession]:
        """Reject invalid staged TOML before the journal publishes its replacement.

        Returns:
            The unchanged session or the exact declaration failure.
        """
        result_type = r[m.Infra.CodegenTransactionSession]
        if len(publications) != 1 or publications[0].replacement is None:
            return result_type.fail("mise-config requires one staged replacement")
        checked = FlextInfraCodegenMiseArtifacts.validate_config_file(
            publications[0].replacement.path,
        )
        if checked.failure:
            return result_type.from_failure(checked)
        u.Cli.info("stage=mise-config-staged-validation files=1 installs=0")
        return result_type.ok(session)

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
        if request.what == c.Infra.CodegenConformSurface.MISE_CONFIG:
            checked = FlextInfraCodegenMiseArtifacts.validate_config_file(
                request.root / c.Infra.MISE_TOML_FILENAME,
            )
            if checked.failure:
                return checked
        return u.Infra.codegen_fixed_point(planned.value.files, subject="bootstrap")

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
        policy = ports.participant_policy(request.root)
        if policy.failure:
            return r[m.Infra.CodegenResult].from_failure(policy)
        mise_owner = FlextInfraCodegenMiseArtifacts(repository_root=request.root)
        transaction = FlextInfraCodegenTransaction(
            mise_owner,
            participant_policy=policy.value,
        )
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

    @staticmethod
    def _lazy_phase(
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
                        f"lazy-init input changed across repository plans: "
                        f"{state.path}",
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
        config_plans = self.mise_config_plans(plan)
        if config_plans.failure:
            return r[m.Infra.CodegenResult].from_failure(config_plans)
        mode = c.Infra.CodegenConformMode(request.mode)
        if mode is c.Infra.CodegenConformMode.CHECK:
            return self._execute_managed_check(
                request,
                transaction,
                scope_root,
                plan,
                ports,
            )
        session = transaction.begin_locked(scope_root, config_plans.value, plan.files)
        if session.failure:
            return r[m.Infra.CodegenResult].from_failure(session)
        return transaction.publish_prepared_locked(
            session.value,
            lambda current: self._publish_managed_locked(
                request,
                plan,
                transaction=transaction,
                session=current,
                ports=ports,
            ),
        )

    def _execute_managed_check(
        self,
        request: m.Infra.CodegenConformRequest,
        transaction: FlextInfraCodegenTransaction,
        scope_root: Path,
        plan: m.Infra.CodegenPlan,
        ports: m.Infra.CodegenConformPorts,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Prove the conform, lazy-init, and docs surfaces drift-free in check mode.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenResult]``.

        """
        config_plans = self.mise_config_plans(plan)
        if config_plans.failure:
            return r[m.Infra.CodegenResult].from_failure(config_plans)
        static = self._check_codegen_and_lazy_drift(
            request,
            plan,
            transaction,
            scope_root,
            config_plans.value,
        )
        if static.failure:
            return r[m.Infra.CodegenResult].from_failure(static)
        return self._check_docs_drift(request, plan, ports)

    def _check_codegen_and_lazy_drift(
        self,
        request: m.Infra.CodegenConformRequest,
        plan: m.Infra.CodegenPlan,
        transaction: FlextInfraCodegenTransaction,
        scope_root: Path,
        config_plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
    ) -> p.Result[bool]:
        """Run the workspace routes, the locked reality check, and both drifts.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        routes = self.conform_workspace_beads_routes(request)
        if routes.failure:
            return r[bool].from_failure(routes)
        reality = transaction.validate_locked(scope_root, config_plans)
        if reality.failure:
            return r[bool].from_failure(reality)
        changed = tuple(
            file for file in plan.files if u.Infra.codegen_file_requires_effect(file)
        )
        if (drift := self._drift_message(changed, "codegen")) is not None:
            return r[bool].fail(drift)
        lazy_analysis = self._lazy_phase(request, plan)
        if lazy_analysis.failure:
            return r[bool].from_failure(lazy_analysis)
        lazy_changed = tuple(
            file
            for file in lazy_analysis.value.files
            if u.Infra.codegen_file_requires_effect(file)
        )
        if (lazy_drift := self._drift_message(lazy_changed, "lazy-init")) is not None:
            return r[bool].fail(lazy_drift)
        return r[bool].ok(value=True)

    def _check_docs_drift(
        self,
        request: m.Infra.CodegenConformRequest,
        plan: m.Infra.CodegenPlan,
        ports: m.Infra.CodegenConformPorts,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Plan and drift-check the docs surface, then report the fixed point.

        Why (X-47): DECLARED scope excludes the workspace root repository
        from ``plan.repositories``; docs generation must not render the root
        as an output scope either, or its report_dir escapes the transaction
        layout that already excludes root for that same scope. Root guides
        remain readable sources for members regardless of this flag.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenResult]``.

        """
        docs_include_root = any(
            repository.name == plan.workspace.repository.name
            for repository in plan.repositories
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
        if (docs_drift := self._drift_message(docs_changed, "docs")) is not None:
            return r[m.Infra.CodegenResult].fail(docs_drift)
        return r[m.Infra.CodegenResult].ok(m.Infra.CodegenResult(plan=plan))

    def _publish_managed_locked(
        self,
        request: m.Infra.CodegenConformRequest,
        plan: m.Infra.CodegenPlan,
        transaction: FlextInfraCodegenTransaction,
        session: m.Infra.CodegenTransactionSession,
        ports: m.Infra.CodegenConformPorts,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Complete every post-begin phase through prepared-state recovery.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenResult]``.

        """
        lazy = self._append_lazy_phase(request, plan, transaction, session)
        if lazy.failure:
            return r[m.Infra.CodegenResult].from_failure(lazy)
        session, owned_lazy_analysis = lazy.value
        docs = self._append_docs_phase(request, plan, transaction, session, ports)
        if docs.failure:
            return r[m.Infra.CodegenResult].from_failure(docs)
        with_docs, docs_analysis = docs.value
        verified_plan: list[m.Infra.CodegenPlan] = []
        published = transaction.commit_locked(
            with_docs,
            lambda: self._validate_managed_fixed_point(
                request,
                with_docs,
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

    def _append_lazy_phase(
        self,
        request: m.Infra.CodegenConformRequest,
        plan: m.Infra.CodegenPlan,
        transaction: FlextInfraCodegenTransaction,
        session: m.Infra.CodegenTransactionSession,
    ) -> p.Result[
        t.Pair[m.Infra.CodegenTransactionSession, m.Infra.CodegenPhaseAnalysis]
    ]:
        """Plan and append the lazy-init phase owned by this transaction.

        A path already planned by conform has exactly one publication owner
        in the transaction: the lazy-init phase keeps only the paths conform
        does not plan, and that same filtered receipt is published and
        verified at the fixed point.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenTransactionSession,
                m.Infra.CodegenPhaseAnalysis]]``.

        """
        result_type = r[
            t.Pair[m.Infra.CodegenTransactionSession, m.Infra.CodegenPhaseAnalysis]
        ]
        lazy_analysis = self._lazy_phase(request, plan)
        if lazy_analysis.failure:
            aborted = transaction.abort_locked(
                session,
                lazy_analysis.error or "lazy-init planning failed",
            )
            return result_type.from_failure(aborted)
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
            return result_type.from_failure(extended)
        return result_type.ok((extended.value, owned_lazy_analysis))

    def _append_docs_phase(
        self,
        request: m.Infra.CodegenConformRequest,
        plan: m.Infra.CodegenPlan,
        transaction: FlextInfraCodegenTransaction,
        session: m.Infra.CodegenTransactionSession,
        ports: m.Infra.CodegenConformPorts,
    ) -> p.Result[
        t.Pair[m.Infra.CodegenTransactionSession, m.Infra.CodegenPhaseAnalysis]
    ]:
        """Authorize docs directories, publish the docs files, and analyze them.

        Why (X-47): DECLARED scope excludes the workspace root repository
        from ``plan.repositories``; docs generation must not render the root
        as an output scope either, or its report_dir escapes the transaction
        layout that already excludes root for that same scope. Root guides
        remain readable sources for members regardless of this flag.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenTransactionSession,
                m.Infra.CodegenPhaseAnalysis]]``.

        """
        result_type = r[
            t.Pair[m.Infra.CodegenTransactionSession, m.Infra.CodegenPhaseAnalysis]
        ]
        docs_include_root = any(
            repository.name == plan.workspace.repository.name
            for repository in plan.repositories
        )
        docs_generator = ports.docs_planner(
            repository_root=request.root,
            projects=tuple(repository.name for repository in plan.repositories),
            include_root=docs_include_root,
        )
        docs_bundle = docs_generator.prepare_bundle()
        if docs_bundle.failure:
            return result_type.from_failure(docs_bundle)
        docs_directories = docs_generator.required_directories(docs_bundle.value)
        if docs_directories.failure:
            return result_type.from_failure(docs_directories)
        owned_docs_directories = self._owned_docs_directories(
            request,
            plan,
            docs_directories.value,
        )
        with_directories = transaction.append_directories_locked(
            session,
            "docs",
            owned_docs_directories,
        )
        if with_directories.failure:
            return result_type.from_failure(with_directories)
        docs_plans = docs_generator.plan_files(docs_bundle.value)
        if docs_plans.failure:
            return result_type.from_failure(docs_plans)
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
            return result_type.from_failure(with_docs)
        return result_type.ok((with_docs.value, docs_analysis))

    @staticmethod
    def _allow_direnv_after_apply(
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
            return r[bool].ok(value=False)
        roots = {
            path.expanduser().resolve().parent
            for path in written_files
            if path.name == c.Infra.ENVRC_FILENAME
        }
        if not roots:
            return r[bool].ok(value=False)
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
        return r[bool].ok(value=True)

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
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraCodegenConformExecute"]
