"""Canonical alias quality gate (ENFORCE-080).

Flags imports of canonical short aliases (c/m/p/t/u) from ``flext_core`` inside
projects that re-export those aliases locally. Auto-fix rewrites them to the
project's own facade modules.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_core import r
from flext_infra import c, config, m, t, u
from flext_infra.detectors import (
    FlextInfraCompatibilityAliasDetector,
    FlextInfraCyclicImportDetector,
)
from flext_infra.gates import FlextInfraGate
from flext_infra.refactor.project_alias_migrator import (
    FlextInfraRefactorProjectAliasMigrator,
)

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraCanonicalAliasGate(FlextInfraGate):
    """Detect and fix foreign canonical alias imports (ENFORCE-080)."""

    gate_id: ClassVar[str] = "canonical-alias"
    gate_name: ClassVar[str] = "Canonical Alias"
    can_fix: ClassVar[bool] = True

    # Packages that define the canonical aliases themselves. Rewriting imports
    # inside them risks creating import cycles during package initialization.
    # Projects that only re-export aliases (e.g. flext_cli) are NOT listed here;
    # per-file facade guards protect their facade implementation files.
    _ALIAS_SOURCE_PACKAGES: ClassVar[frozenset[str]] = frozenset({
        c.Infra.PKG_CORE_UNDERSCORE
    })

    @staticmethod
    def _normalized_project_name(project_dir: Path) -> str:
        """Return the package name for a project directory (``flext-cli`` → ``flext_cli``)."""
        return project_dir.name.replace("-", "_")

    @staticmethod
    def _alias_files(project_dir: Path) -> p.Result[t.SequenceOf[Path]]:
        """Return Python files from configured namespace roots for alias checks.

        ENFORCE-080 owns every namespace a project publishes, ``tests`` included:
        a test module reaches the canonical aliases through ``from tests import
        c``, never through ``flext_core`` directly. Discovery therefore uses the
        same scope owner as this gate's own cycle analysis
        (``FlextInfraCyclicImportDetector.scan_project``), not the production-only
        ``config.Infra.source_scan.roots`` contract, which excludes ``tests``.
        """
        try:
            files = {
                file_path
                for directory_name in u.Infra.namespace_scan_dirs(project_dir)
                for file_path in u.Infra.iter_directory_python_files(
                    project_dir / directory_name
                )
            }
        except OSError as exc:
            return r[t.SequenceOf[Path]].fail_op("canonical-alias file scan", exc)
        return r[t.SequenceOf[Path]].ok(tuple(sorted(files)))

    @override
    def check(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> m.Infra.GateExecution:
        """Scan one project's Python sources for ENFORCE-080 violations."""
        _ = ctx
        started = time.monotonic()
        if self._normalized_project_name(project_dir) in self._ALIAS_SOURCE_PACKAGES:
            return self._neutral_skip_result(
                project_dir,
                started,
                message=f"{self.gate_id}: source package ({c.Infra.PKG_CORE_UNDERSCORE}) excluded from rewrite",
            )
        files_result = self._alias_files(project_dir)
        if files_result.failure:
            file_path_str = files_result.error or "canonical-alias scan failed"
            return self._build_single_issue_result(
                project_dir,
                Path(c.PYPROJECT_FILENAME),
                file_path_str,
                passed=False,
                started=started,
                ctx=ctx,
            )

        rope_project = u.Infra.init_rope_project(project_dir)
        try:
            issues: list[m.Infra.Issue] = []
            for file_path in files_result.value:
                migration_context = u.Infra.alias_migration_context(file_path)
                if migration_context.policy_owner in self._ALIAS_SOURCE_PACKAGES:
                    continue
                for violation in FlextInfraCompatibilityAliasDetector.detect_file(
                    m.Infra.DetectorContext(
                        file_path=file_path,
                        project_root=project_dir,
                        rope_project=rope_project,
                        project_name=project_dir.name,
                    )
                ):
                    if violation.module_name != migration_context.policy_owner:
                        continue
                    import_target = (
                        migration_context.import_root
                        if migration_context.import_root == c.Infra.DIR_TESTS
                        else f"{migration_context.import_root}.<facade>"
                    )
                    issues.append(
                        m.Infra.Issue(
                            file=str(file_path),
                            line=violation.line,
                            column=1,
                            code=self.gate_id,
                            message=(
                                f"canonical alias '{violation.alias_name}' "
                                f"imported from flext_core; use "
                                f"from {import_target} import "
                                f"{violation.alias_name}"
                            ),
                            severity="ERROR",
                        )
                    )
        finally:
            rope_project.close()

        return self._detected_gate_execution(
            project_dir, ctx, issues=issues, started=started
        )

    @override
    def fix(self, project_dir: Path, ctx: m.Infra.GateContext) -> m.Infra.GateExecution:
        """Apply ENFORCE-080 rewrites for the selected project."""
        if ctx.check_only or not ctx.apply_fixes:
            return self._check_only_fix_result(project_dir)
        started = time.monotonic()
        if self._normalized_project_name(project_dir) in self._ALIAS_SOURCE_PACKAGES:
            return self._neutral_skip_result(
                project_dir,
                started,
                message=f"{self.gate_id}: source package ({c.Infra.PKG_CORE_UNDERSCORE}) excluded from rewrite",
            )
        files_result = self._alias_files(project_dir)
        if files_result.failure:
            message = files_result.error or "canonical-alias fix failed"
            return self._build_single_issue_result(
                project_dir,
                project_dir,
                message,
                passed=False,
                started=started,
                ctx=ctx,
            )

        rope_project = u.Infra.init_rope_project(project_dir)
        try:
            violation_files = self._violation_files(
                project_dir=project_dir,
                rope_project=rope_project,
                file_paths=files_result.value,
            )
            plan_result = self._plan_edits(violation_files)
            if plan_result.failure:
                return self._fix_failure_result(
                    project_dir=project_dir,
                    file_path=project_dir,
                    message=plan_result.error or "canonical-alias planning failed",
                    started=started,
                    ctx=ctx,
                )
            edits = plan_result.value
            if not edits:
                return self.check(project_dir, ctx)
            updates = {edit.file_path: edit.updated_source for edit in edits}
            baseline_cycles = FlextInfraCyclicImportDetector.scan_project(
                project_root=project_dir, rope_project=rope_project
            )
            prospective_cycles = FlextInfraCyclicImportDetector.scan_project(
                project_root=project_dir,
                rope_project=rope_project,
                proposed_sources=updates,
            )
        finally:
            rope_project.close()
        baseline_signatures = {
            frozenset(violation.cycle) for violation in baseline_cycles
        }
        new_cycles = tuple(
            violation
            for violation in prospective_cycles
            if frozenset(violation.cycle) not in baseline_signatures
        )
        if new_cycles:
            cycle = " -> ".join(new_cycles[0].cycle)
            return self._fix_failure_result(
                project_dir=project_dir,
                file_path=project_dir,
                message=f"prospective import cycle blocks canonical-alias fix: {cycle}",
                started=started,
                ctx=ctx,
            )

        changed_files = tuple(edit.file_path for edit in edits)
        # protected_source_writes rolls the workspace back in its finally
        # block when the write phase fails; a residual OSError/RuntimeError
        # escapes loudly instead of being normalized into a fix result.
        write_ok, write_reports = u.Infra.protected_source_writes(
            updates,
            request=m.Infra.ProtectedSourceWritesRequest(
                workspace=project_dir,
                expected_sources={
                    edit.file_path: edit.original_source for edit in edits
                },
                gates=("lint",),
                post_write=lambda: self._format_files(changed_files),
                skip_pytest=True,
            ),
        )
        if not write_ok:
            return self._fix_failure_result(
                project_dir=project_dir,
                file_path=project_dir,
                message="canonical-alias transactional write failed: "
                + " | ".join(write_reports),
                started=started,
                ctx=ctx,
            )

        return self.check(project_dir, ctx)

    @staticmethod
    def _violation_files(
        *,
        project_dir: Path,
        rope_project: t.Infra.RopeProject,
        file_paths: t.SequenceOf[Path],
    ) -> t.VariadicTuple[Path]:
        """Return only files containing project-owned ENFORCE-080 violations."""
        selected: list[Path] = []
        for file_path in file_paths:
            context = u.Infra.alias_migration_context(file_path)
            violations = FlextInfraCompatibilityAliasDetector.detect_file(
                m.Infra.DetectorContext(
                    file_path=file_path,
                    project_root=project_dir,
                    rope_project=rope_project,
                    project_name=project_dir.name,
                )
            )
            if any(
                violation.module_name == context.policy_owner
                and violation.alias_name == violation.target_name
                for violation in violations
            ):
                selected.append(file_path)
        return tuple(selected)

    @staticmethod
    def _plan_edits(
        file_paths: t.SequenceOf[Path],
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Build immutable in-memory edits for detector-selected files."""
        edits: list[m.Infra.SemanticMigrationEdit] = []
        for file_path in file_paths:
            read = u.Cli.files_read_text(file_path)
            if read.failure:
                return r[tuple[m.Infra.SemanticMigrationEdit, ...]].from_failure(read)
            transformer = FlextInfraRefactorProjectAliasMigrator(file_path=file_path)
            try:
                updated, changes = transformer.apply_to_source(read.value)
            except ValueError as exc:
                return r[tuple[m.Infra.SemanticMigrationEdit, ...]].fail(
                    str(exc), exception=exc
                )
            if changes and updated != read.value:
                edits.append(
                    m.Infra.SemanticMigrationEdit(
                        file_path=file_path,
                        original_source=read.value,
                        updated_source=updated,
                        changes=tuple(changes),
                    )
                )
        return r[tuple[m.Infra.SemanticMigrationEdit, ...]].ok(tuple(edits))

    @staticmethod
    def _format_files(file_paths: t.SequenceOf[Path]) -> None:
        """Format a validated edit batch or raise to trigger rollback."""
        if not file_paths:
            return
        result = u.Cli.run_raw(
            [
                "ruff",
                "format",
                *config.Infra.codegen.make.ruff.format_apply,
                *[str(path) for path in file_paths],
            ],
            timeout=c.Infra.TIMEOUT_SHORT,
        )
        if result.failure:
            raise RuntimeError(result.error or "ruff format failed")
        output = result.value
        if not u.Cli.process_succeeded(output.outcome):
            detail = (output.stderr or output.stdout).strip()
            msg = f"ruff format failed ({output.outcome.raw_return_code}): {detail or 'no output'}"
            raise RuntimeError(msg)

    def _fix_failure_result(
        self,
        *,
        project_dir: Path,
        file_path: Path,
        message: str,
        started: float,
        ctx: m.Infra.GateContext,
    ) -> m.Infra.GateExecution:
        """Build a failed fix result for local rewrite failures."""
        return self._build_single_issue_result(
            project_dir, file_path, message, passed=False, started=started, ctx=ctx
        )


__all__: list[str] = ["FlextInfraCanonicalAliasGate"]
