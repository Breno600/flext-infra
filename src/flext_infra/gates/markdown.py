"""FLEXT markdown quality gate.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, m
from flext_infra.gates.markdown_support import FlextInfraMarkdownGateBase

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraMarkdownGate(FlextInfraMarkdownGateBase):
    """Markdown quality gate."""

    gate_id: ClassVar[str] = c.Infra.MARKDOWN
    gate_name: ClassVar[str] = "Markdown"
    # Fixable findings are repaired by the native linter. The findings that
    # remain after repair come back under rumdl's declared findings status:
    # the repair verb completes and reports them, and the read-only gate
    # enforces them.
    can_fix: ClassVar[bool] = True

    @override
    def _build_check_command(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        check_dirs: t.StrSequence,
    ) -> t.StrSequence:
        """Lint the collected Markdown files read-only.

        Returns:
            The rumdl check invocation.

        """
        _ = ctx
        return self._rumdl_command(project_dir, "check", check_dirs)

    @override
    def _build_fix_command(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        targets: t.StrSequence,
    ) -> t.StrSequence:
        """Repair fixable findings and return the linter's residual verdict.

        Returns:
            The resulting ``t.StrSequence``.

        """
        _ = ctx
        return self._rumdl_command(project_dir, "check", targets, "--fix")

    @override
    def _parse_check_output(
        self,
        result: p.Cli.CommandOutput,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Parse rumdl output, discarding lines marking already-applied fixes.

        Returns:
            The resulting ``t.Pair[bool, t.SequenceOf[m.Infra.Issue]]``.

        """
        _ = ctx
        issues: t.MutableSequenceOf[m.Infra.Issue] = []
        for line in (result.stdout + "\n" + result.stderr).splitlines():
            match = c.Infra.MARKDOWN_RE.match(line.strip())
            if not match:
                continue
            if match.group("msg").strip().endswith(c.Infra.MARKDOWN_FIXED_SUFFIX):
                continue
            issues.append(
                m.Infra.Issue(
                    file=match.group("file"),
                    line=int(match.group("line")),
                    column=int(match.group("col") or 1),
                    code=match.group("code"),
                    message=match.group("msg"),
                ),
            )
        return self._finalize_parse_result(result, project_dir, issues, c.Infra.RUMDL)


__all__: list[str] = ["FlextInfraMarkdownGate"]
