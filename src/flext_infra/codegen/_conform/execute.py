"""Transactional execution of conformance plans."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Self, override

from flext_core import r

from ... import c, config, m, p, t, u
from ...docs import FlextInfraDocGenerator
from ...validate import FlextInfraValidateFreshImport
from ...workspace import FlextInfraWorkspaceDetector
from .. import (
    FlextInfraCodegenLazyInit,
    FlextInfraCodegenMiseArtifacts,
    FlextInfraCodegenTransaction,
)
from .plan import FlextInfraCodegenConformPlan


class _ConformExecuteRoles:
    if TYPE_CHECKING:
        request: m.Infra.CodegenConformRequest | None
        repository_root: Path
        initial_workspace: m.Infra.WorkspaceSpec | None

        def plan(
            self, request: m.Infra.CodegenConformRequest
        ) -> p.Result[m.Infra.CodegenPlan]: ...

        @staticmethod
        def mise_config_plans(
            plan: m.Infra.CodegenPlan,
        ) -> p.Result[t.VariadicTuple[m.Infra.CodegenFilePlan]]: ...

        def conform_workspace_beads_routes(
            self, request: m.Infra.CodegenConformRequest
        ) -> p.Result[bool]: ...

        @staticmethod
        def owned_docs_files(
            request: m.Infra.CodegenConformRequest,
            files: t.SequenceOf[m.Infra.CodegenFilePlan],
        ) -> t.VariadicTuple[m.Infra.CodegenFilePlan]: ...

        @classmethod
        def _owned_docs_directories(
            cls,
            request: m.Infra.CodegenConformRequest,
            plan: m.Infra.CodegenPlan,
            directories: t.SequenceOf[Path],
        ) -> t.VariadicTuple[Path]: ...


class FlextInfraCodegenConformExecute(
    _ConformExecuteRoles, FlextInfraCodegenConformPlan
):
    """Transactional execution of conformance plans."""

    @classmethod
    def execute_request(
        cls: type[Self],
        request: m.Infra.CodegenConformRequest,
        initial_workspace: m.Infra.WorkspaceSpec | None = None,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Execute one already validated public CLI request."""
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
        # The supplied WorkspaceSpec already owns the declared integration branch.
        # Require it before materialization instead of a second divergent input.
        if (
            initial_workspace is not None
            and not (root / c.Infra.GIT_DIR).exists()
            and initial_workspace.integration is None
        ):
            return r[m.Infra.CodegenResult].fail(
                "initial integration is required to initialize repository Git: "
                "declare --repository-branch"
            )
        if initial_workspace is not None and not root.is_dir():
            planned = u.Cli.atomic_plan_directory_chain(root)
            if planned.failure:
                return r[m.Infra.CodegenResult].from_failure(planned)
            created = u.Cli.atomic_create_directory_chain_guarded(
                planned.value, permission_mode=0o755
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
                    "Git: declare --repository-branch"
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
            repository_root=root, request=request, initial_workspace=initial_workspace
        )
        try:
            result = service.execute()
        except Exception as exc:
            rollback = cls._rollback_request_bootstrap(
                root, initialized_git=initialized_git, directories=bootstrap
            )
            if rollback.failure:
                exc.add_note(f"scaffold bootstrap rollback failed: {rollback.error}")
            raise
        if result.success:
            return result
        rollback = cls._rollback_request_bootstrap(
            root, initialized_git=initialized_git, directories=bootstrap
        )
        if rollback.failure:
            return r[m.Infra.CodegenResult].fail(
                f"{result.error or 'generation failed'}; "
                f"scaffold bootstrap rollback failed: {rollback.error}"
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
        """Undo only Git and root directories created by this invocation."""
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
        """Run check or apply and require a verified fixed point."""
        request = self.request or m.Infra.CodegenConformRequest(
            root=self.repository_root
        )
        surface = c.Infra.CodegenConformSurface(request.what)
        if surface is c.Infra.CodegenConformSurface.ALL:
            return self._execute_managed(request)
        if c.Infra.CodegenConformMode(request.mode) is c.Infra.CodegenConformMode.APPLY:
            mise_owner = FlextInfraCodegenMiseArtifacts(repository_root=request.root)
            transaction = FlextInfraCodegenTransaction(mise_owner)
            return transaction.run_locked(
                prepare=False, operation=lambda _scope_root: self._execute_plan(request)
            )
        return self._execute_plan(request)

    def _execute_plan(
        self, request: m.Infra.CodegenConformRequest
    ) -> p.Result[m.Infra.CodegenResult]:
        """Execute a non-toolchain conform surface without widening its scope."""
        u.Cli.header("Codegen Conform")
        u.Cli.info(
            f"stage=plan mode={request.mode} scope={request.scope} "
            f"what={request.what} root={request.root}"
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
        if surface is not c.Infra.CodegenConformSurface.MAKEFILE:
            return r[m.Infra.CodegenResult].fail(
                "partial codegen apply is prohibited; use the complete all surface"
            )
        expected_path = request.root.expanduser().resolve() / c.Infra.MAKEFILE_FILENAME
        if (
            any(file.path != expected_path for file in plan.files)
            or len(plan.files) != 1
        ):
            return r[m.Infra.CodegenResult].fail(
                "Makefile bootstrap plan must own exactly the root dispatcher"
            )
        written: t.VariadicTuple[Path] = ()
        if changed:
            (file,) = changed
            before = u.Infra.codegen_file_before_state(file)
            if before.failure:
                return r[m.Infra.CodegenResult].from_failure(before)
            if file.desired_content is None or file.desired_mode is None:
                return r[m.Infra.CodegenResult].fail(
                    "Makefile bootstrap cannot delete its dispatcher"
                )
            published = u.Cli.atomic_write_binary_file_guarded(
                before.value, file.desired_content, permission_mode=file.desired_mode
            )
            if published.failure:
                return r[m.Infra.CodegenResult].from_failure(published)
            written = (file.path,)
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
                f"Makefile bootstrap did not reach a fixed point: {residual[0].path}"
            )
        return r[m.Infra.CodegenResult].ok(
            m.Infra.CodegenResult(plan=verified.value, written_files=written)
        )

    def _execute_managed(
        self, request: m.Infra.CodegenConformRequest
    ) -> p.Result[m.Infra.CodegenResult]:
        """Run complete conformance inside the sole generation lock."""
        mode = c.Infra.CodegenConformMode(request.mode)
        mise_owner = FlextInfraCodegenMiseArtifacts(repository_root=request.root)
        transaction = FlextInfraCodegenTransaction(mise_owner)
        return transaction.run_locked(
            prepare=mode is c.Infra.CodegenConformMode.APPLY,
            operation=lambda scope_root: self._execute_managed_locked(
                request, scope_root, transaction
            ),
        )

    def _execute_managed_locked(
        self,
        request: m.Infra.CodegenConformRequest,
        scope_root: Path,
        transaction: FlextInfraCodegenTransaction,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Materialize scaffold parents, then run one locked generation cycle."""
        prepared = self._prepare_scaffold_directories(request)
        if prepared.failure:
            return r[m.Infra.CodegenResult].from_failure(prepared)
        try:
            result = self._execute_managed_locked_cycles(
                request, scope_root, transaction
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
                f"scaffold directory rollback failed: {rollback.error}"
            )
        return result

    def _execute_managed_locked_cycles(
        self,
        request: m.Infra.CodegenConformRequest,
        scope_root: Path,
        transaction: FlextInfraCodegenTransaction,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Re-plan from the current tree while a mid-cycle source race persists."""
        attempts = 0
        result = r[m.Infra.CodegenResult].fail("unreached")
        while attempts < c.Infra.CONFORM_SOURCE_RACE_CYCLES:
            attempts += 1
            result = self._execute_managed_locked_prepared(
                request, scope_root, transaction
            )
            if result.success or not self._is_source_race(result.error):
                return result
            u.Cli.info(
                "stage=publish mode=converge "
                f"attempt={attempts}/{c.Infra.CONFORM_SOURCE_RACE_CYCLES} "
                f"reason={result.error}; re-planning from current tree"
            )
        return result

    @staticmethod
    def _is_source_race(error: str | None) -> bool:
        """Return whether one failure signature is a mid-cycle source mutation."""
        message = error or ""
        return any(marker in message for marker in c.Infra.CONFORM_SOURCE_RACE_MARKERS)

    def _lazy_phase(
        self, request: m.Infra.CodegenConformRequest
    ) -> p.Result[m.Infra.CodegenPhaseAnalysis]:
        """Single lazy-init analysis pass per conform invocation.

        One call site; both CHECK (drift detection) and APPLY
        (phase publication + receipt) consume the same analysis.
        ADR-014: lazy-init ownership stays inside conform's
        transaction.
        """
        return FlextInfraCodegenLazyInit(repository_root=request.root).plan_files()

    def _execute_managed_locked_prepared(
        self,
        request: m.Infra.CodegenConformRequest,
        scope_root: Path,
        transaction: FlextInfraCodegenTransaction,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Plan, publish, and validate one prepared locked generation cycle."""
        u.Cli.header("Codegen Conform")
        u.Cli.info(
            f"stage=plan mode={request.mode} scope={request.scope} "
            f"what={request.what} root={request.root} lock_scope={scope_root}"
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
                    f"codegen drift detected: {paths}\n{report}"
                )
            lazy_analysis = self._lazy_phase(request)
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
                    f"lazy-init drift detected: {paths}\n{report}"
                )
            docs_generator = FlextInfraDocGenerator(
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
                    f"docs drift detected: {paths}\n{report}"
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
    ) -> p.Result[m.Infra.CodegenResult]:
        """Complete every post-begin phase through prepared-state recovery."""
        lazy_analysis = self._lazy_phase(request)
        if lazy_analysis.failure:
            aborted = transaction.abort_locked(
                session, lazy_analysis.error or "lazy-init planning failed"
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
            session, owned_lazy_analysis.phase, owned_lazy_analysis.files
        )
        if extended.failure:
            return r[m.Infra.CodegenResult].from_failure(extended)
        docs_generator = FlextInfraDocGenerator(
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
            request, plan, docs_directories.value
        )
        with_directories = transaction.append_directories_locked(
            extended.value, "docs", owned_docs_directories
        )
        if with_directories.failure:
            return r[m.Infra.CodegenResult].from_failure(with_directories)
        docs_plans = docs_generator.plan_files(docs_bundle.value)
        if docs_plans.failure:
            return r[m.Infra.CodegenResult].from_failure(docs_plans)
        owned_docs_files = self.owned_docs_files(request, docs_plans.value)
        docs_analysis = m.Infra.CodegenPhaseAnalysis(
            phase="docs", files=owned_docs_files, inputs=docs_bundle.value.source_states
        )
        with_docs = transaction.append_phase_locked(
            with_directories.value, "docs", owned_docs_files
        )
        if with_docs.failure:
            return r[m.Infra.CodegenResult].from_failure(with_docs)
        verified_plan: list[m.Infra.CodegenPlan] = []
        published = transaction.commit_locked(
            with_docs.value,
            lambda: self._validate_managed_fixed_point(
                request,
                with_docs.value,
                transaction,
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
            m.Infra.CodegenResult(plan=verified_plan[0], written_files=published.value)
        )

    def _prepare_scaffold_directories(
        self, request: m.Infra.CodegenConformRequest
    ) -> p.Result[t.VariadicTuple[m.Cli.AtomicDirectoryState]]:
        """Create config-declared scaffold parent chains under the generation lock."""
        if (
            c.Infra.CodegenConformMode(request.mode)
            is not c.Infra.CodegenConformMode.APPLY
        ):
            return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].ok(())
        scaffolding = self.initial_workspace
        workspace = scaffolding
        if workspace is None:
            workspace_result = FlextInfraWorkspaceDetector.load_workspace_spec(
                request.root.expanduser().resolve()
            )
            if workspace_result.failure:
                return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].from_failure(
                    workspace_result
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
                    "scaffold workspace has no project metadata"
                )
            return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].ok(())
        profile = workspace.repository.role
        root = request.root.expanduser().resolve()
        directories = {root, root / c.Infra.MISE_LAUNCHER_DIRECTORY}
        for entry in config.Infra.codegen.templates.entries:
            if profile not in entry.profiles:
                continue
            destination = entry.destination.format(
                package_name=project.package_name, ns=project.namespace_attribute
            )
            relative = Path(destination)
            if relative.is_absolute() or ".." in relative.parts:
                return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].fail(
                    f"template destination escapes repository root: {destination}"
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
                        f"{rollback.error}"
                    )
                return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].from_failure(
                    planned
                )
            materialized = u.Cli.atomic_create_directory_chain_guarded(
                planned.value, permission_mode=0o755
            )
            if materialized.failure:
                rollback = self._rollback_scaffold_directories(tuple(created))
                if rollback.failure:
                    return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].fail(
                        f"{materialized.error}; scaffold directory rollback failed: "
                        f"{rollback.error}"
                    )
                return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].from_failure(
                    materialized
                )
            created.extend(materialized.value)
        return r[t.VariadicTuple[m.Cli.AtomicDirectoryState]].ok(tuple(created))

    @staticmethod
    def _rollback_scaffold_directories(
        created: t.VariadicTuple[m.Cli.AtomicDirectoryState],
    ) -> p.Result[bool]:
        """Remove only directories created by this locked scaffold attempt."""
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
                (c.Infra.CLI_DIRENV, "allow", str(root)), cwd=root, timeout=60
            )
            if result.failure:
                return r[bool].from_failure(result)
            if not u.Cli.process_succeeded(result.value.outcome):
                return r[bool].fail(
                    f"direnv allow failed for {root}: "
                    f"{result.value.stderr.strip() or result.value.stdout.strip()}"
                )
        return r[bool].ok(True)

    def _validate_managed_fixed_point(
        self,
        request: m.Infra.CodegenConformRequest,
        session: m.Infra.CodegenTransactionSession,
        transaction: FlextInfraCodegenTransaction,
        lazy_analysis: m.Infra.CodegenPhaseAnalysis,
        docs_analysis: m.Infra.CodegenPhaseAnalysis,
        verified_plan: list[m.Infra.CodegenPlan],
    ) -> p.Result[bool]:
        """Replan conform against live bytes before the journal can commit.

        This re-plan is the cycle's authoritative final plan: nothing that
        changes generated content publishes between it and the journal commit,
        so the caller reuses ``verified_plan`` as its result instead of
        planning the whole fleet a second time.
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
                f"codegen publication did not reach a fixed point: {paths}\n{drift}"
            )
        u.Cli.info("stage=verify-lazy-init-receipt")
        lazy_fixed_point = transaction.validate_phase_analysis_locked(lazy_analysis)
        if lazy_fixed_point.failure:
            return r[bool].from_failure(lazy_fixed_point)
        u.Cli.info("stage=verify-docs-receipt")
        docs_fixed_point = transaction.validate_phase_analysis_locked(docs_analysis)
        if docs_fixed_point.failure:
            return r[bool].from_failure(docs_fixed_point)
        mise = FlextInfraCodegenMiseArtifacts(repository_root=request.root)
        plan = session.plan
        if isinstance(plan, m.Infra.MiseToolchainWorkspacePlan):
            project_layouts = (p.layout for p in plan.projects)
        else:
            project_layouts = plan.layout.projects
        for project_layout in project_layouts:
            validated = mise.validate_artifacts(project_layout.root)
            if validated.failure:
                return r[bool].from_failure(validated)
        u.Cli.info("stage=verify-fresh-imports")
        imported = FlextInfraValidateFreshImport(
            repository_root=request.root
        ).build_report(
            publications=lazy_analysis.publications,
            repository_roots=self.fresh_import_repository_roots(
                request.root, verified.value.repositories
            ),
        )
        if imported.failure:
            return r[bool].from_failure(imported)
        if not imported.value.passed:
            return r[bool].fail(
                "\n".join((imported.value.summary, *imported.value.violations))
            )
        return r[bool].ok(True)

    @staticmethod
    def fresh_import_repository_roots(
        root: Path, repositories: t.VariadicTuple[m.Infra.RepositoryRef]
    ) -> t.VariadicTuple[Path]:
        """Resolve the fresh-import probe scope from declared repositories.

        Fresh-import probes validate Python publications, so only declared
        Python packages enter the scope: a repository whose manifest carries
        ``package: false`` (a workspace umbrella root, for example) owns no
        importable layout, and requiring one there made ``make gen`` fail on
        every such checkout regardless of what conform actually published.
        """
        return tuple(
            root / repository.path for repository in repositories if repository.package
        )


__all__: list[str] = ["FlextInfraCodegenConformExecute"]
