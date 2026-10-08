"""One atomic campaign for declared candidate recovery projections.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, m, p, r, t, u


class FlextInfraCandidateBootstrapService:
    """Plan every declared target before one journaled publication."""

    def __init__(
        self,
        planner: p.Infra.CandidateBootstrapPlanner,
        transaction: p.Infra.CandidateBootstrapTransaction,
    ) -> None:
        """Wire the declared-target planner to its atomic publisher."""
        self._planner = planner
        self._transaction = transaction

    def execute(
        self,
        source_root: Path,
        workspace: m.Infra.WorkspaceSpec,
        command: m.Infra.CandidateBootstrapCommand,
        manifest_state: m.Cli.AtomicFileState,
    ) -> p.Result[bool]:
        """Publish a fixed point for the entire typed target declaration.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        targets = workspace.candidate_bootstrap_targets
        if not targets:
            return r[bool].fail("candidate bootstrap targets are not declared")
        roots: t.MutableMappingKV[str, Path] = {}
        for index, target in enumerate(targets):
            identity = u.Infra.exact_worktree_root(
                (source_root / target.path).resolve(strict=True),
            )
            if identity.failure:
                return r[bool].from_failure(identity)
            roots[f"@candidate-{index}"] = identity.value.repo_root
        if len(set(roots.values())) != len(roots):
            return r[bool].fail(
                "candidate bootstrap targets resolve to duplicate worktrees",
            )
        if command.dry_run or command.check_only or not command.apply_changes:
            return self._verify(roots, targets, manifest_state)

        def publish(scope_root: Path) -> p.Result[bool]:
            planned = self._plan(roots, targets, manifest_state)
            if planned.failure:
                return r[bool].from_failure(planned)
            analysis = planned.value
            changed = tuple(
                plan
                for plan in analysis.files
                if u.Infra.codegen_file_requires_effect(plan)
            )
            if not changed:
                return self._verify(roots, targets, manifest_state)
            committed = self._transaction.publish_file_phase_locked(
                scope_root,
                roots,
                analysis,
                m.Infra.CodegenPhasePublicationPolicy(
                    directories=(),
                    validator=lambda: self._verify(roots, targets, manifest_state),
                ),
            )
            if committed.failure:
                return r[bool].from_failure(committed)
            return r[bool].ok(value=True)

        return self._transaction.run_files_locked(roots, publish)

    def _plan(
        self,
        roots: t.MappingKV[str, Path],
        targets: m.Infra.CandidateBootstrapTargets,
        manifest_state: m.Cli.AtomicFileState,
    ) -> p.Result[m.Infra.CodegenPhaseAnalysis]:
        """Compose one immutable receipt from all conform planners.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenPhaseAnalysis]``.

        """
        files: list[m.Infra.CodegenFilePlan] = []
        inputs: t.MutableMappingKV[Path, m.Cli.AtomicFileState] = {
            manifest_state.path: manifest_state,
        }
        for root, target in zip(roots.values(), targets, strict=True):
            request = m.Infra.CodegenConformRequest(
                root=root,
                what=target.what,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.CHECK,
            )
            planned = self._planner.plan(request)
            if planned.failure:
                return r[m.Infra.CodegenPhaseAnalysis].from_failure(planned)
            destinations = self._planner.surface_contract(target.what).destinations
            if not destinations:
                return r[m.Infra.CodegenPhaseAnalysis].fail(
                    f"candidate bootstrap has no declared destinations: {root}",
                )
            for file in planned.value.files:
                files.append(file)
                for state in file.source_states:
                    previous = inputs.get(state.path)
                    if previous is not None and previous != state:
                        return r[m.Infra.CodegenPhaseAnalysis].fail(
                            f"candidate bootstrap observed two states for {state.path}",
                        )
                    inputs[state.path] = state
        return r[m.Infra.CodegenPhaseAnalysis].ok(
            m.Infra.CodegenPhaseAnalysis(
                phase=c.Infra.CodegenStagedFilePhase.CANDIDATE_BOOTSTRAP,
                files=tuple(files),
                inputs=tuple(inputs.values()),
            ),
        )

    def _verify(
        self,
        roots: t.MappingKV[str, Path],
        targets: m.Infra.CandidateBootstrapTargets,
        manifest_state: m.Cli.AtomicFileState,
    ) -> p.Result[bool]:
        """Require unchanged declarations and a complete post-publication fixed point.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        observed = u.Cli.atomic_read_binary_file_state(
            manifest_state.path,
            required=True,
        )
        if observed.failure:
            return r[bool].from_failure(observed)
        if observed.value != manifest_state:
            return r[bool].fail(
                "candidate bootstrap declaration changed during publication",
            )
        planned = self._plan(roots, targets, manifest_state)
        if planned.failure:
            return r[bool].from_failure(planned)
        return u.Infra.codegen_fixed_point(
            planned.value.files,
            subject="candidate bootstrap",
        )


__all__: list[str] = ["FlextInfraCandidateBootstrapService"]
