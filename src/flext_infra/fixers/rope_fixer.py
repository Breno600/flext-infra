"""Rope-backed fix adapter for enforcement rules with semantic refactoring.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import operator
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, m, u
from flext_infra.detectors.class_placement_detector import (
    FlextInfraClassPlacementDetector,
)
from flext_infra.detectors.compatibility_alias_detector import (
    FlextInfraCompatibilityAliasDetector,
)
from flext_infra.detectors.inline_import_detector import FlextInfraInlineImportDetector
from flext_infra.detectors.private_import_bypass_detector import (
    FlextInfraPrivateImportBypassDetector,
)
from flext_infra.refactor.classvar_constant_autofix import (
    FlextInfraRefactorClassvarConstantAutofix,
)

from .base import FlextInfraFixerAdapter

if TYPE_CHECKING:
    from collections.abc import Callable

    from flext_infra import p, t


class FlextInfraRopeFixerAdapter(FlextInfraFixerAdapter):
    """Apply fixes by running rope-backed refactor operations per violation.

    Targets are canonical rope refactor short-names declared in the enforcement
    catalog.  Each target uses rope (and the existing detector infrastructure)
    to locate violations and rewrite source safely.
    """

    kind: ClassVar[str] = "rope"
    _PRIVATE_NAMESPACE_MIN_PARTS: ClassVar[int] = 2

    def __init__(self, repository_root: Path) -> None:
        """Bind the repository root used to open rope projects."""
        super().__init__(repository_root)

    @staticmethod
    def _empty_batch_result(
        project_dir: Path, rule_id: str, reason: str
    ) -> m.Infra.ProjectFixResult:
        """Return the project-level skip recorded when a batch selects no file."""
        return m.Infra.ProjectFixResult(
            project=project_dir.name,
            skipped=(
                m.Infra.SkippedViolation(
                    rule_id=rule_id, file_path=str(project_dir), reason=reason
                ),
            ),
        )

    @classmethod
    def _file_targets(
        cls,
        project_dir: Path,
        violations: t.SequenceOf[t.Pair[m.EnforcementRuleSpec, p.AttributeProbe]],
    ) -> t.VariadicTuple[m.Infra.FileFixTarget]:
        """Return one fix target per existing file named by a violation batch."""
        return tuple(
            m.Infra.FileFixTarget(file_path=file_path, record_path=str(file_path))
            for file_path in cls._collect_file_paths(project_dir, violations)
        )

    @override
    def can_fix(self, fix_action: m.EnforcementFixAction) -> bool:
        """Return whether this adapter handles ``fix_action``."""
        return (
            fix_action.kind == self.kind
            and fix_action.target in self._target_dispatch()
        )

    @override
    def fix_project(
        self,
        project_dir: Path,
        violations: t.SequenceOf[t.Pair[m.EnforcementRuleSpec, p.AttributeProbe]],
        ctx: m.Infra.FixEnforcementCommand,
    ) -> m.Infra.ProjectFixResult:
        """Apply rope fixes grouped by target."""
        if not violations:
            return m.Infra.ProjectFixResult(project=project_dir.name)
        fixed: list[m.Infra.FixedViolation] = []
        previewed: list[m.Infra.PreviewedViolation] = []
        skipped: list[m.Infra.SkippedViolation] = []
        failed: list[m.Infra.FailedFix] = []
        files_modified: set[str] = set()
        for target, target_violations in self._group_by_target(violations).items():
            handler = self._target_dispatch().get(target)
            if handler is None:
                rule_id = target_violations[0][0].id
                failed.append(
                    m.Infra.FailedFix(
                        rule_id=rule_id,
                        file_path=str(project_dir),
                        error=f"rope target {target} not registered",
                    )
                )
                continue
            result = handler(project_dir, target_violations, ctx)
            fixed.extend(result.fixed)
            previewed.extend(result.previewed)
            skipped.extend(result.skipped)
            failed.extend(result.failed)
            files_modified.update(result.files_modified)
        return self._build_project_fix_result(
            project_dir, fixed, previewed, skipped, failed, files_modified
        )

    def _target_dispatch(
        self,
    ) -> MutableMapping[
        str,
        Callable[
            [
                Path,
                t.SequenceOf[t.Pair[m.EnforcementRuleSpec, p.AttributeProbe]],
                m.Infra.FixEnforcementCommand,
            ],
            m.Infra.ProjectFixResult,
        ],
    ]:
        """Return bound rope target handlers for this adapter instance."""
        return {
            "classvar_relocation": self._fix_classvar_relocation,
            "rewrite_compatibility_alias": self._fix_compatibility_alias,
            "fix_silent_failure_sentinels": self._fix_silent_failure_sentinels,
            "hoist_inline_import": self._fix_hoist_inline_import,
            "rewrite_private_import_bypass": self._fix_private_import_bypass,
            "rewrite_library_abstraction": self._fix_library_abstraction,
            "one_class_per_module": self._fix_one_class_per_module,
            "remove_stub_file": self._fix_remove_stub_file,
        }

    @classmethod
    def _module_name_for_file(cls, file_path: Path, *, project_root: Path) -> str:
        """Return the import module for a Python file inside a project."""
        package_name = u.Infra.package_name_for_dir(
            file_path.parent, project_root=project_root
        )
        if file_path.name == c.Infra.INIT_PY:
            return package_name
        return f"{package_name}.{file_path.stem}" if package_name else ""

    @staticmethod
    def _constants_module_for_file(
        file_path: Path, *, module_name: str, project_root: Path
    ) -> str:
        """Return the canonical project constants module for a source file."""
        module_parts = tuple(module_name.split("."))
        package_name = module_parts[0] if module_parts else ""
        if not package_name:
            return ""
        if package_name in c.Infra.ROOT_WRAPPER_SEGMENTS:
            if "_constants" in module_parts:
                return ""
            if file_path.stem in {"", "__init__", "__main__", "__version__"}:
                return ""
            return FlextInfraRopeFixerAdapter._wrapper_constants_module_for_file(
                module_parts=module_parts, project_root=project_root
            )
        package_root = project_root / c.Infra.DEFAULT_SRC_DIR / package_name
        try:
            relative_parts = file_path.relative_to(package_root).parts
        except ValueError:
            return ""
        if not relative_parts:
            return ""
        first_part = relative_parts[0]
        if first_part == "_constants":
            return ""
        if first_part.startswith("_"):
            if (
                len(relative_parts)
                < FlextInfraRopeFixerAdapter._PRIVATE_NAMESPACE_MIN_PARTS
            ):
                return ""
            domain = Path(relative_parts[1]).stem
        elif len(relative_parts) == 1:
            domain = file_path.stem
        else:
            domain = first_part
        normalized_domain = domain.removeprefix("_")
        if normalized_domain in {"", "__init__", "__main__", "__version__"}:
            return ""
        return f"{package_name}._constants.{normalized_domain}"

    @staticmethod
    def _wrapper_constants_module_for_file(
        *, module_parts: t.StrSequence, project_root: Path
    ) -> str:
        """Return nearest existing wrapper ``_constants`` module."""
        candidate_parts = tuple(module_parts[:-1])
        while candidate_parts:
            candidate_module = ".".join((*candidate_parts, "_constants"))
            if FlextInfraRopeFixerAdapter._constants_module_exists(
                candidate_module, project_root=project_root
            ):
                return candidate_module
            candidate_parts = candidate_parts[:-1]
        return ".".join((*module_parts[:-1], "_constants"))

    @staticmethod
    def _constants_module_exists(module_name: str, *, project_root: Path) -> bool:
        """Return whether ``module_name`` resolves to an on-disk constants module."""
        relative = Path(*module_name.split("."))
        module_file = project_root / relative.with_suffix(".py")
        package_init = project_root / relative / c.Infra.INIT_PY
        return module_file.is_file() or package_init.is_file()

    def _run_file_fix_steps(
        self,
        *,
        project_dir: Path,
        violations: t.SequenceOf[t.Pair[m.EnforcementRuleSpec, p.AttributeProbe]],
        ctx: m.Infra.FixEnforcementCommand,
        step: Callable[
            [m.Infra.FileFixTarget, m.Infra.DetectorContext], m.Infra.FileFixOutcome
        ],
        targets: t.SequenceOf[m.Infra.FileFixTarget] | None = None,
        empty_batch_reason: str | None = None,
    ) -> m.Infra.ProjectFixResult:
        """Run one per-file fix step across a batch and aggregate its outcomes.

        Every rope target shares this skeleton: open one rope project, run a
        single step per file, and turn what that step reports into skipped,
        failed, fixed or previewed records. Only the step body varies, so the
        loop lives here and each target contributes just its own step.

        ``targets`` defaults to the existing files named by the batch; a target
        that iterates raw probes instead (reporting the probe's own path even
        when no file exists) passes its own sequence.
        """
        rule_id = self._rule_id(violations)
        selected = (
            self._file_targets(project_dir, violations) if targets is None else targets
        )
        if not selected and empty_batch_reason is not None:
            return self._empty_batch_result(project_dir, rule_id, empty_batch_reason)
        fixed: list[m.Infra.FixedViolation] = []
        previewed: list[m.Infra.PreviewedViolation] = []
        skipped: list[m.Infra.SkippedViolation] = []
        failed: list[m.Infra.FailedFix] = []
        files_modified: set[str] = set()
        with u.Infra.open_project(self._repository_root) as rope_project:
            for target in selected:
                outcome = step(
                    target,
                    m.Infra.DetectorContext(
                        file_path=target.file_path,
                        rope_project=rope_project,
                        project_name=project_dir.name,
                        project_root=project_dir,
                    ),
                )
                skipped.extend(
                    m.Infra.SkippedViolation(
                        rule_id=rule_id, file_path=target.record_path, reason=reason
                    )
                    for reason in outcome.skipped
                )
                failed.extend(
                    m.Infra.FailedFix(
                        rule_id=rule_id, file_path=target.record_path, error=error
                    )
                    for error in outcome.errors
                )
                if ctx.apply:
                    files_modified.update(outcome.files_modified)
                    fixed.extend(
                        m.Infra.FixedViolation(
                            rule_id=rule_id,
                            file_path=target.record_path,
                            message=message,
                        )
                        for message in outcome.messages
                    )
                else:
                    previewed.extend(
                        m.Infra.PreviewedViolation(
                            rule_id=rule_id,
                            file_path=target.record_path,
                            message=message,
                        )
                        for message in outcome.messages
                    )
        return self._build_project_fix_result(
            project_dir, fixed, previewed, skipped, failed, files_modified
        )

    @staticmethod
    def _detect_and_rewrite_step[V](
        *,
        detector: Callable[[m.Infra.DetectorContext], t.SequenceOf[V]],
        filter_violations: Callable[[t.SequenceOf[V]], t.SequenceOf[V]],
        rewrite: Callable[[m.Infra.DetectorContext, t.SequenceOf[V]], None],
        empty_reason: str,
        change_message: Callable[[int, bool], str],
        detector_error_detail: str,
        rewrite_error_detail: str,
        apply: bool,
    ) -> Callable[
        [m.Infra.FileFixTarget, m.Infra.DetectorContext], m.Infra.FileFixOutcome
    ]:
        """Build a per-file step that detects, filters, then rewrites in place."""

        def _step(
            target: m.Infra.FileFixTarget, detect_ctx: m.Infra.DetectorContext
        ) -> m.Infra.FileFixOutcome:
            try:
                file_violations = detector(detect_ctx)
            except c.EXC_BROAD_RUNTIME as exc:
                return m.Infra.FileFixOutcome(
                    errors=(f"{detector_error_detail}: {exc}",)
                )
            selected = filter_violations(file_violations)
            if not selected:
                return m.Infra.FileFixOutcome(skipped=(empty_reason,))
            try:
                rewrite(detect_ctx, selected)
            except c.EXC_BROAD_RUNTIME as exc:
                return m.Infra.FileFixOutcome(
                    errors=(f"{rewrite_error_detail}: {exc}",)
                )
            return m.Infra.FileFixOutcome(
                messages=(change_message(len(selected), apply),),
                files_modified=(target.record_path,),
            )

        return _step

    def _fix_silent_failure_sentinels(
        self,
        project_dir: Path,
        violations: t.SequenceOf[t.Pair[m.EnforcementRuleSpec, p.AttributeProbe]],
        ctx: m.Infra.FixEnforcementCommand,
    ) -> m.Infra.ProjectFixResult:
        """Rewrite deterministic silent-failure sentinels to failed Results."""

        def _step(
            target: m.Infra.FileFixTarget, detect_ctx: m.Infra.DetectorContext
        ) -> m.Infra.FileFixOutcome:
            resource = u.Infra.resolve_resource_from_path(
                detect_ctx.rope_project, target.file_path
            )
            if resource is None:
                return m.Infra.FileFixOutcome(skipped=("rope resource not found",))
            try:
                _updated, changes = u.Infra.fix_silent_failure_sentinels(
                    detect_ctx.rope_project, resource, apply=ctx.apply
                )
            except c.EXC_BROAD_RUNTIME as exc:
                return m.Infra.FileFixOutcome(
                    errors=(f"silent failure sentinel fix failed: {exc}",)
                )
            if not changes:
                return m.Infra.FileFixOutcome(skipped=("no changes produced",))
            return m.Infra.FileFixOutcome(
                messages=(
                    (
                        f"{'rewrote' if ctx.apply else 'would rewrite'} "
                        f"{len(changes)} silent sentinel fix(es)"
                    ),
                ),
                files_modified=(target.record_path,),
            )

        return self._run_file_fix_steps(
            project_dir=project_dir, violations=violations, ctx=ctx, step=_step
        )

    def _fix_compatibility_alias(
        self,
        project_dir: Path,
        violations: t.SequenceOf[t.Pair[m.EnforcementRuleSpec, p.AttributeProbe]],
        ctx: m.Infra.FixEnforcementCommand,
    ) -> m.Infra.ProjectFixResult:
        """Rewrite compatibility aliases using the canonical detector + rewriter."""

        def _rewrite(
            _detect_ctx: m.Infra.DetectorContext,
            file_violations: t.SequenceOf[m.Infra.CompatibilityAliasViolation],
        ) -> None:
            if ctx.apply:
                u.Infra.rewrite_compatibility_alias_violations(
                    violations=file_violations, parse_failures=[]
                )

        return self._run_file_fix_steps(
            project_dir=project_dir,
            violations=violations,
            ctx=ctx,
            empty_batch_reason="no files in violation batch",
            step=self._detect_and_rewrite_step(
                detector=FlextInfraCompatibilityAliasDetector.detect_file,
                filter_violations=lambda v: v,
                rewrite=_rewrite,
                empty_reason="no compatibility alias violations",
                change_message=lambda count, applying: (
                    f"{'rewrote' if applying else 'would rewrite'} "
                    f"{count} compatibility alias violation(s)"
                ),
                detector_error_detail="compatibility alias detector failed",
                rewrite_error_detail="compatibility alias rewrite failed",
                apply=ctx.apply,
            ),
        )

    def _fix_remove_stub_file(
        self,
        project_dir: Path,
        violations: t.SequenceOf[t.Pair[m.EnforcementRuleSpec, p.AttributeProbe]],
        ctx: m.Infra.FixEnforcementCommand,
    ) -> m.Infra.ProjectFixResult:
        """Remove source ``.pyi`` stubs when apply mode is enabled."""
        rule_id = self._rule_id(violations)
        fixed: list[m.Infra.FixedViolation] = []
        previewed: list[m.Infra.PreviewedViolation] = []
        skipped: list[m.Infra.SkippedViolation] = []
        failed: list[m.Infra.FailedFix] = []
        files_modified: set[str] = set()
        file_paths = self._collect_file_paths(project_dir, violations)
        stub_paths = tuple(path for path in file_paths if path.suffix == ".pyi")
        if not stub_paths:
            return self._empty_batch_result(
                project_dir, rule_id, "no .pyi stubs in violation batch"
            )
        for file_path in stub_paths:
            if not file_path.is_file():
                skipped.append(
                    m.Infra.SkippedViolation(
                        rule_id=rule_id,
                        file_path=str(file_path),
                        reason="stub file not found",
                    )
                )
                continue
            message = (
                f"{'would remove' if not ctx.apply else 'removed'} "
                f"source stub {file_path.relative_to(project_dir)}"
            )
            if not ctx.apply:
                previewed.append(
                    m.Infra.PreviewedViolation(
                        rule_id=rule_id, file_path=str(file_path), message=message
                    )
                )
                continue
            try:
                file_path.unlink()
            except OSError as exc:
                failed.append(
                    m.Infra.FailedFix(
                        rule_id=rule_id,
                        file_path=str(file_path),
                        error=f"stub removal failed: {exc}",
                    )
                )
                continue
            files_modified.add(str(file_path))
            fixed.append(
                m.Infra.FixedViolation(
                    rule_id=rule_id, file_path=str(file_path), message=message
                )
            )
        return self._build_project_fix_result(
            project_dir, fixed, previewed, skipped, failed, files_modified
        )

    def _fix_private_import_bypass(
        self,
        project_dir: Path,
        violations: t.SequenceOf[t.Pair[m.EnforcementRuleSpec, p.AttributeProbe]],
        ctx: m.Infra.FixEnforcementCommand,
    ) -> m.Infra.ProjectFixResult:
        """Rewrite private-module imports to their canonical facade equivalents."""

        def _rewrite(
            detect_ctx: m.Infra.DetectorContext,
            auto_fixable: t.SequenceOf[m.Infra.PrivateImportBypassViolation],
        ) -> None:
            u.Infra.rewrite_private_import_bypass_violations(
                rope_project=detect_ctx.rope_project,
                violations=auto_fixable,
                parse_failures=[],
                apply=ctx.apply,
            )

        return self._run_file_fix_steps(
            project_dir=project_dir,
            violations=violations,
            ctx=ctx,
            empty_batch_reason="no files in violation batch",
            step=self._detect_and_rewrite_step(
                detector=FlextInfraPrivateImportBypassDetector.detect_file,
                filter_violations=lambda detected: tuple(
                    violation for violation in detected if violation.symbol_exported
                ),
                rewrite=_rewrite,
                empty_reason="no auto-fixable private import bypass violations",
                change_message=lambda count, applying: (
                    f"{'rewrote' if applying else 'would rewrite'} "
                    f"{count} private import bypass violation(s)"
                ),
                detector_error_detail="private import bypass detector failed",
                rewrite_error_detail="private import bypass rewrite failed",
                apply=ctx.apply,
            ),
        )

    def _fix_library_abstraction(
        self,
        project_dir: Path,
        violations: t.SequenceOf[t.Pair[m.EnforcementRuleSpec, p.AttributeProbe]],
        ctx: m.Infra.FixEnforcementCommand,
    ) -> m.Infra.ProjectFixResult:
        """Hoist detector-approved FLEXT library imports to module scope."""
        return self._fix_inline_import_action(
            project_dir,
            violations,
            ctx,
            target_action="rewrite_library_abstraction",
            empty_reason="no library abstraction inline imports",
        )

    def _fix_hoist_inline_import(
        self,
        project_dir: Path,
        violations: t.SequenceOf[t.Pair[m.EnforcementRuleSpec, p.AttributeProbe]],
        ctx: m.Infra.FixEnforcementCommand,
    ) -> m.Infra.ProjectFixResult:
        """Hoist detector-approved inline stdlib imports to module scope."""
        return self._fix_inline_import_action(
            project_dir,
            violations,
            ctx,
            target_action="hoist_inline_import",
            empty_reason="no hoistable inline imports",
        )

    def _fix_inline_import_action(
        self,
        project_dir: Path,
        violations: t.SequenceOf[t.Pair[m.EnforcementRuleSpec, p.AttributeProbe]],
        ctx: m.Infra.FixEnforcementCommand,
        *,
        target_action: str,
        empty_reason: str,
    ) -> m.Infra.ProjectFixResult:
        """Apply one detector-approved inline-import fix action."""

        def _step(
            target: m.Infra.FileFixTarget, detect_ctx: m.Infra.DetectorContext
        ) -> m.Infra.FileFixOutcome:
            try:
                detected = FlextInfraInlineImportDetector.detect_file(detect_ctx)
            except c.EXC_BROAD_RUNTIME as exc:
                return m.Infra.FileFixOutcome(
                    errors=(f"inline import detector failed: {exc}",)
                )
            hoistable = tuple(
                violation
                for violation in detected
                if FlextInfraInlineImportDetector.fix_action_for(
                    module_name=violation.module_name,
                    is_importlib=violation.is_importlib,
                )
                == target_action
            )
            if not hoistable:
                return m.Infra.FileFixOutcome(skipped=(empty_reason,))
            resource = u.Infra.resolve_resource_from_path(
                detect_ctx.rope_project, target.file_path
            )
            if resource is None:
                return m.Infra.FileFixOutcome(skipped=("rope resource not found",))
            try:
                updated, changes = self._hoist_inline_import_source(
                    resource.read(), hoistable, file_path=target.file_path
                )
            except c.EXC_BROAD_RUNTIME as exc:
                return m.Infra.FileFixOutcome(
                    errors=(f"inline import hoist failed: {exc}",)
                )
            if not changes:
                return m.Infra.FileFixOutcome(skipped=("no changes produced",))
            if ctx.apply:
                resource.write(updated)
            return m.Infra.FileFixOutcome(
                messages=(
                    (
                        f"{'hoisted' if ctx.apply else 'would hoist'} "
                        f"{len(changes)} inline import(s) for {target_action}"
                    ),
                ),
                files_modified=(target.record_path,),
            )

        return self._run_file_fix_steps(
            project_dir=project_dir, violations=violations, ctx=ctx, step=_step
        )

    @classmethod
    def _hoist_inline_import_source(
        cls,
        source: str,
        violations: t.SequenceOf[m.Infra.InlineImportViolation],
        *,
        file_path: Path,
    ) -> t.Infra.TransformResult:
        """Return source with hoistable inline import statements at module scope."""
        tree = ast.parse(source, filename=str(file_path))
        lines = source.splitlines(keepends=True)
        line_ranges: list[t.Pair[int, int]] = []
        import_lines: list[str] = []
        for violation in violations:
            node = cls._find_inline_import_node(tree, violation.line)
            if node is None:
                continue
            start_line = node.lineno
            end_line = getattr(node, "end_lineno", start_line) or start_line
            line_ranges.append((start_line, end_line))
            import_lines.append(cls._import_line_for_node(node))
        if not line_ranges:
            return source, []
        updated_lines = list(lines)
        for start_line, end_line in sorted(line_ranges, reverse=True):
            del updated_lines[start_line - 1 : end_line]
        insert_at = u.Infra.find_import_insert_position(updated_lines)
        unique_imports = cls._unique_new_imports(updated_lines, import_lines)
        for index, import_line in enumerate(unique_imports):
            updated_lines.insert(insert_at + index, import_line)
        updated = "".join(updated_lines)
        compile(updated, str(file_path), "exec")
        return updated, unique_imports

    @staticmethod
    def _find_inline_import_node(
        tree: ast.Module, line: int
    ) -> ast.Import | ast.ImportFrom | None:
        """Find the import statement at a detector-reported line."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node.lineno == line:
                return node
        return None

    @staticmethod
    def _import_line_for_node(node: ast.Import | ast.ImportFrom) -> str:
        """Render a top-level import line from an AST import node."""
        if isinstance(node, ast.Import):
            names = ", ".join(
                f"{alias.name} as {alias.asname}" if alias.asname else alias.name
                for alias in node.names
            )
            return f"import {names}\n"
        module_prefix = "." * node.level
        module_name = f"{module_prefix}{node.module or ''}"
        names = ", ".join(
            f"{alias.name} as {alias.asname}" if alias.asname else alias.name
            for alias in node.names
        )
        return f"from {module_name} import {names}\n"

    @staticmethod
    def _unique_new_imports(
        lines: t.StrSequence, import_lines: t.StrSequence
    ) -> list[str]:
        """Return import lines that are not already present."""
        existing = {line.strip() for line in lines if line.strip()}
        unique: list[str] = []
        for import_line in import_lines:
            stripped = import_line.strip()
            if stripped in existing or stripped in {line.strip() for line in unique}:
                continue
            unique.append(import_line)
        return unique

    def _fix_classvar_relocation(
        self,
        project_dir: Path,
        violations: t.SequenceOf[t.Pair[m.EnforcementRuleSpec, p.AttributeProbe]],
        ctx: m.Infra.FixEnforcementCommand,
    ) -> m.Infra.ProjectFixResult:
        """Move class-level constants to canonical _constants modules."""

        def _step(
            target: m.Infra.FileFixTarget, detect_ctx: m.Infra.DetectorContext
        ) -> m.Infra.FileFixOutcome:
            if not target.file_path.is_file():
                return m.Infra.FileFixOutcome(skipped=("file not found",))
            try:
                all_violations = FlextInfraClassPlacementDetector.detect_file(
                    detect_ctx
                )
            except c.EXC_BROAD_RUNTIME:
                return m.Infra.FileFixOutcome(errors=("detector raised runtime error",))
            classvar_violations = [
                v for v in all_violations if v.action == "classvar_relocation"
            ]
            if not classvar_violations:
                return m.Infra.FileFixOutcome()
            module_name = self._module_name_for_file(
                target.file_path, project_root=project_dir
            )
            if not module_name:
                return m.Infra.FileFixOutcome(
                    skipped=("could not resolve module name",)
                )
            constants_module = self._constants_module_for_file(
                target.file_path, module_name=module_name, project_root=project_dir
            )
            if not constants_module:
                return m.Infra.FileFixOutcome(
                    errors=(
                        (
                            "could not resolve canonical constants module "
                            f"for {module_name}"
                        ),
                    )
                )
            errors: list[str] = []
            messages: list[str] = []
            files_modified: list[str] = []
            for violation in classvar_violations:
                class_full_name = f"{module_name}.{violation.base_class}"
                try:
                    result = FlextInfraRefactorClassvarConstantAutofix.apply(
                        project_dir,
                        class_full_name,
                        violation.name,
                        constants_module,
                        dry_run=not ctx.apply,
                    )
                except c.EXC_BROAD_RUNTIME as exc:
                    errors.append(f"autofix failed: {exc}")
                    continue
                files_modified.extend(
                    str(project_dir / touched) for touched in result.touched_files
                )
                messages.append(
                    f"{'would move' if not ctx.apply else 'moved'} "
                    f"{violation.base_class}.{violation.name} -> "
                    f"{constants_module}"
                )
            return m.Infra.FileFixOutcome(
                errors=tuple(errors),
                messages=tuple(messages),
                files_modified=tuple(files_modified),
            )

        return self._run_file_fix_steps(
            project_dir=project_dir,
            violations=violations,
            targets=tuple(
                m.Infra.FileFixTarget(
                    file_path=Path(getattr(probe, "file_path", "")),
                    record_path=getattr(probe, "file_path", ""),
                )
                for _rule, probe in violations
            ),
            ctx=ctx,
            step=_step,
        )

    def _fix_one_class_per_module(
        self,
        project_dir: Path,
        violations: t.SequenceOf[t.Pair[m.EnforcementRuleSpec, p.AttributeProbe]],
        ctx: m.Infra.FixEnforcementCommand,
    ) -> m.Infra.ProjectFixResult:
        """Move extra governed classes to their own canonical modules."""
        rule_id = self._rule_id(violations)
        targets = self._file_targets(project_dir, violations)
        if not targets:
            return self._empty_batch_result(
                project_dir, rule_id, "no files in violation batch"
            )
        layout = u.Infra.layout(project_dir)
        if layout is None:
            return m.Infra.ProjectFixResult(
                project=project_dir.name,
                failed=(
                    m.Infra.FailedFix(
                        rule_id=rule_id,
                        file_path=str(project_dir),
                        error="could not resolve project layout",
                    ),
                ),
            )
        package_dir = layout.package_dir

        def _step(
            target: m.Infra.FileFixTarget, detect_ctx: m.Infra.DetectorContext
        ) -> m.Infra.FileFixOutcome:
            resource = u.Infra.fetch_python_resource(
                detect_ctx.rope_project,
                target.file_path,
                skip_protected=True,
                skip_settings=True,
            )
            if resource is None:
                return m.Infra.FileFixOutcome(skipped=("rope resource not found",))
            class_infos = tuple(
                class_info
                for class_info in u.Infra.resolve_class_info(
                    detect_ctx.rope_project, resource
                )
                if not any(
                    base_name.rsplit(".", maxsplit=1)[-1] == "Warning"
                    for base_name in class_info.bases
                )
            )
            if len(class_infos) <= 1:
                return m.Infra.FileFixOutcome(
                    errors=(
                        (
                            "ENFORCE-067 selected a module without more than one "
                            "non-Warning top-level class"
                        ),
                    )
                )
            messages: list[str] = []
            files_modified: list[str] = []
            ordered_classes = sorted(class_infos, key=operator.attrgetter("line"))
            for extra_class in reversed(ordered_classes[1:]):
                target_file = u.Infra.class_target_file(
                    package_dir=package_dir,
                    source_file=target.file_path,
                    class_name=extra_class.name,
                    family=u.Infra.class_family(extra_class),
                )
                u.Infra.move_class(
                    m.Infra.ClassMoveRequest(
                        rope_project=detect_ctx.rope_project,
                        source_file=target.file_path,
                        target_file=target_file,
                        class_name=extra_class.name,
                        line=extra_class.line,
                        apply=ctx.apply,
                    )
                )
                files_modified.extend((target.record_path, str(target_file)))
                messages.append(
                    f"{'would move' if not ctx.apply else 'moved'} "
                    f"{extra_class.name} -> "
                    f"{target_file.relative_to(project_dir)}"
                )
            if not messages:
                return m.Infra.FileFixOutcome(skipped=("no classes could be moved",))
            return m.Infra.FileFixOutcome(
                messages=tuple(messages), files_modified=tuple(files_modified)
            )

        return self._run_file_fix_steps(
            project_dir=project_dir,
            violations=violations,
            targets=targets,
            ctx=ctx,
            step=_step,
        )
