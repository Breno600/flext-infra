"""Detect silent failure sentinels via Rope-backed AST scanning."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import m, u

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraSilentFailureDetector:
    """Detect branches that hide failures behind generic sentinel returns."""

    @staticmethod
    def detect_file(ctx: m.Infra.DetectorContext) -> t.SequenceOf[m.Infra.Issue]:
        """Detect silent-failure findings in one Python file."""
        resource = u.Infra.fetch_python_resource(ctx.rope_project, ctx.file_path)
        if resource is None:
            return []
        file_path = ctx.file_path
        source = resource.read()
        if not source.strip():
            return []
        display_path = file_path
        if ctx.project_root is not None and file_path.is_relative_to(ctx.project_root):
            display_path = file_path.relative_to(ctx.project_root)
        tree = FlextInfraSilentFailureDetector._rope_module_ast(
            ctx.rope_project,
            resource,
        )
        if tree is None:
            return []
        return tuple(
            m.Infra.Issue(
                file=str(display_path),
                line=finding.line,
                column=finding.column,
                code=finding.kind,
                message=finding.detail,
            )
            for finding in u.Infra.collect_silent_failure_findings(
                tree,
                source,
                is_test_module=FlextInfraSilentFailureDetector._is_test_module(
                    file_path,
                ),
            )
        )

    @classmethod
    def detect_violations(
        cls,
        ctx: m.Infra.DetectorContext,
    ) -> t.SequenceOf[m.Infra.SilentFailureViolation]:
        """Return silent-failure violations with kind + fix_action for census."""
        resource = u.Infra.fetch_python_resource(ctx.rope_project, ctx.file_path)
        if resource is None:
            return ()
        source = resource.read()
        if not source.strip():
            return ()
        tree = cls._rope_module_ast(ctx.rope_project, resource)
        if tree is None:
            return ()
        return tuple(
            m.Infra.SilentFailureViolation(
                file=str(ctx.file_path),
                line=finding.line,
                kind=finding.kind,
                detail=finding.detail,
                fix_action=finding.fix_action,
            )
            for finding in u.Infra.collect_silent_failure_findings(
                tree,
                source,
                is_test_module=cls._is_test_module(ctx.file_path),
            )
        )

    @classmethod
    def fixable_kinds(cls) -> frozenset[str]:
        """Kinds that ``fix_silent_failure_sentinels`` can auto-correct."""
        return frozenset({"silent-failure-guard", "silent-failure-except"})

    @staticmethod
    def _is_test_module(file_path: Path) -> bool:
        """Return whether ``file_path`` lives under a tests tree.

        Why (cosmos-3flk9): a test teardown legitimately suppresses lifecycle
        errors (a child process that already died) via ``contextlib.suppress``;
        that is process reaping, not a silenced production failure.
        """
        return any(part == "tests" for part in file_path.parts)

    @staticmethod
    def _rope_module_ast(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
    ) -> ast.Module | None:
        """Return the rope-backed module AST; rope parse failures escape loudly."""
        pymodule = u.Infra.resolve_pymodule(rope_project, resource)
        tree = pymodule.get_ast()
        return tree if isinstance(tree, ast.Module) else None


__all__: list[str] = ["FlextInfraSilentFailureDetector"]
