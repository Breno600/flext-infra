"""Project namespace validation through the one rule engine.

The namespace laws are rule data (the ast-grep rule catalog and its project
context predicates); this service reports one project's findings of that
catalog in the declared namespace scope. It owns no rule.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, override

from flext_infra import m, p, r, t, u
from flext_infra.base import s
from flext_infra.codemod.batch_gates import FlextInfraModGateEngine

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraNamespaceValidator(s[bool]):
    """Report one project's rule-catalog findings in its namespace scope."""

    @override
    def execute(self) -> p.Result[bool]:
        """Execute namespace validation for the configured repository root.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        report_result = self.build_report()
        if report_result.failure:
            return r[bool].from_failure(report_result)
        return r[bool].ok(report_result.value.passed)

    def build_report(self) -> p.Result[m.Infra.ValidationReport]:
        """Scan the project with the rule engine and report its findings.

        Each violation reads ``[<rule-id>] <file>:<line> — <message>``. The
        scope is the project's declared ``[tool.flext.namespace].scan_dirs``
        when it declares one, every scanned file otherwise.

        Returns:
            The resulting ``p.Result[m.Infra.ValidationReport]``.

        """


        project_root = self.repository_root.resolve()
        scanned = FlextInfraModGateEngine.scan(project_root, fix=False)
        if scanned.failure:
            return r[m.Infra.ValidationReport].from_failure(scanned)
        violations = tuple(
            f"[{entry.rule_id}] {entry.file.as_posix()}:"
            f"{self._line(entry)} — {self._message(entry)}"
            for entry in scanned.value.entries
            if self._in_declared_scan_scope(project_root / entry.file, project_root)
        )
        passed = not violations
        return r[m.Infra.ValidationReport].ok(
            m.Infra.ValidationReport(
                passed=passed,
                violations=violations,
                summary=(
                    "namespace validation passed"
                    if passed
                    else f"{len(violations)} namespace violation(s) found"
                ),
            ),
        )

    @staticmethod
    def _line(entry: m.Infra.ModScanFinding) -> int:
        """Return the 1-based starting line of one finding.

        Returns:
            The 1-based starting line of one finding.

        Raises:
            TypeError: If ast-grep finding without a start line.

        """
        start = entry.range["start"]
        line = start.get("line") if isinstance(start, Mapping) else None
        if not isinstance(line, int):
            msg = f"ast-grep finding without a start line: {entry.rule_id}"
            raise TypeError(msg)
        return line + 1

    @staticmethod
    def _message(entry: m.Infra.ModScanFinding) -> str:
        """Return the rule's message for one finding.

        Returns:
            The rule's message for one finding.

        Raises:
            TypeError: If ast-grep finding without a message.

        """
        message = entry.payload.get("message")
        if not isinstance(message, str):
            msg = f"ast-grep finding without a message: {entry.rule_id}"
            raise TypeError(msg)
        return " ".join(message.split())

    @staticmethod
    def _in_declared_scan_scope(filepath: Path, project_root: Path) -> bool:
        """Return whether ``filepath`` lies inside the declared namespace scope.

        Returns:
            Whether ``filepath`` lies inside the declared namespace scope.

        """
        declared = u.Infra.namespace_meta(project_root).get("scan_dirs")
        if not isinstance(declared, list) or not declared:
            return True
        scope = frozenset(str(item).strip() for item in declared if str(item).strip())
        return filepath.relative_to(project_root).parts[0] in scope


__all__: t.StrSequence = ("FlextInfraNamespaceValidator",)
