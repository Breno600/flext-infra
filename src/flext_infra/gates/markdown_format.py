"""FLEXT markdown formatting gate: ``rumdl fmt``, owned by ``make fmt``.

rumdl is the fleet's markdown linter and formatter (ADR-025). The read-only
side (``rumdl fmt --check``) validates inside ``make check``; the mutating
side (``rumdl fmt``) is reached only through the gate's fix contract from
``make fmt`` — the gate deliberately never appears in
``CANONICAL_FIXABLE_GATE_IDS``, so every tool runs exactly one operation per
verb and no verb repeats another's work. Both sides read the generated
``.markdownlint.json`` the ``markdown`` gate reads: one rule set, one owner.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import itertools
import time
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, m
from flext_infra.gates.markdown_support import FlextInfraMarkdownGateBase

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraMarkdownFormatGate(FlextInfraMarkdownGateBase):
    """Markdown formatting gate."""

    gate_id: ClassVar[str] = c.Infra.MARKDOWN_FORMAT
    gate_name: ClassVar[str] = "Markdown Format"
    can_fix: ClassVar[bool] = True

    @override
    def check(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> m.Infra.GateExecution:
        """Run ``rumdl fmt --check`` against the generated rule set.

        Returns:
            The resulting ``m.Infra.GateExecution``.

        """
        config_path = project_dir / c.Infra.MARKDOWNLINT_CONFIG_FILENAME
        if not config_path.is_file():
            # .markdownlint.json is a codegen-managed artifact (policy full):
            # absence is a generation gap reported loud with the exact path,
            # never a silent fall back to the tool's built-in defaults.
            return self._build_single_issue_result(
                project_dir,
                Path(c.PYPROJECT_FILENAME),
                (
                    f"generated {c.Infra.MARKDOWNLINT_CONFIG_FILENAME} is absent: "
                    f"{config_path}; run make gen"
                ),
                passed=False,
                started=time.monotonic(),
            )
        return super().check(project_dir, ctx)

    @override
    def _build_check_command(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        check_dirs: t.StrSequence,
    ) -> t.StrSequence:
        """Build the read-only ``rumdl fmt --check`` pass.

        Returns:
            The resulting ``t.StrSequence``.

        """
        _ = ctx
        return self._rumdl_command(project_dir, "fmt", check_dirs, "--check")

    @override
    def _build_fix_command(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        targets: t.StrSequence,
    ) -> t.StrSequence:
        """Build the single mutating pass: ``rumdl fmt``.

        Returns:
            The resulting ``t.StrSequence``.

        """
        _ = ctx
        return self._rumdl_command(project_dir, "fmt", targets)

    @override
    def _parse_check_output(
        self,
        result: p.Cli.CommandOutput,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Parse ``rumdl fmt --check``: one finding per file it would rewrite.

        The check pass prints a unified diff per file it would rewrite; the
        ``--- <file>`` / ``+++ <file>`` header pair names that file. Findings
        the formatter cannot repair belong to the ``markdown`` gate, and the
        mutating pass prints no diff, so neither yields a finding here.

        Returns:
            The resulting ``t.Pair[bool, t.SequenceOf[m.Infra.Issue]]``.

        """
        _ = ctx
        old_header, new_header = c.Infra.MARKDOWN_FORMAT_DIFF_HEADERS
        lines = result.stdout.splitlines()
        issues: t.MutableSequenceOf[m.Infra.Issue] = [
            m.Infra.Issue(
                file=current.removeprefix(old_header),
                line=1,
                column=1,
                code=self.gate_id,
                message="file is not rumdl-formatted (repair belongs to `make fmt`)",
            )
            for current, following in itertools.pairwise(lines)
            if current.startswith(old_header)
            and following == new_header + current.removeprefix(old_header)
        ]
        return self._finalize_parse_result(
            result,
            project_dir,
            issues,
            c.Infra.RUMDL,
        )


__all__: list[str] = ["FlextInfraMarkdownFormatGate"]
