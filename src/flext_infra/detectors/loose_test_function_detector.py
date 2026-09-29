"""Detect module-level ``test_*`` functions outside a ``Tests*`` class via rope.

Test ownership is derived from the real project tree and pytest's canonical
module/function convention. No parallel registry controls discovery.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, m, u

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraLooseTestFunctionDetector:
    """Flag module-level ``test_*`` functions that live outside a ``Tests*`` class."""

    @staticmethod
    def _is_test_file(ctx: m.Infra.DetectorContext) -> bool:
        """Return whether the real source path belongs to the project test tree."""
        root = ctx.project_root or ctx.file_path.parent
        try:
            relative = ctx.file_path.resolve().relative_to(root.resolve())
        except ValueError:
            relative = ctx.file_path
        return (
            c.Infra.DIR_TESTS in relative.parts
            and relative.suffix == c.Infra.EXT_PYTHON
        )

    @classmethod
    def detect_file(
        cls, ctx: m.Infra.DetectorContext
    ) -> t.SequenceOf[m.Infra.LooseTestFunctionViolation]:
        """Return one violation per loose ``test_*`` function in a test module."""
        if not cls._is_test_file(ctx):
            return []
        res = u.Infra.resolve_resource_from_path(ctx.rope_project, ctx.file_path)
        if res is None:
            return []
        try:
            pymodule = u.Infra.resolve_pymodule(ctx.rope_project, res)
        except u.Infra.rope_runtime_errors() as exc:
            msg = (
                f"loose-test-function detector could not analyze {ctx.file_path}: "
                f"{type(exc).__name__}: {exc!s}"
            )
            raise RuntimeError(msg) from exc
        violations: list[m.Infra.LooseTestFunctionViolation] = []
        for definition in u.Infra.scope_definitions(pymodule):
            if definition.kind != c.Infra.RopeScopeKind.FUNCTION:
                continue
            if not definition.is_module_level:
                continue
            if not definition.name.startswith(c.Infra.NAMESPACE_PYTEST_MODULE_PREFIX):
                continue
            violations.append(
                m.Infra.LooseTestFunctionViolation(
                    file=str(ctx.file_path),
                    line=definition.line,
                    name=definition.name,
                    suggestion=(
                        f"Nest {definition.name} inside the module's single test class."
                    ),
                )
            )
        return violations


__all__: list[str] = ["FlextInfraLooseTestFunctionDetector"]
