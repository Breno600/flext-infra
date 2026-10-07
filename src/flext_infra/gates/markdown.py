"""FLEXT markdown quality gate.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from flext_infra._config import config
from flext_infra.constants import c
from flext_infra.gates.markdown_support import FlextInfraMarkdownGateBase
from flext_infra.models import m

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra.protocols import p
    from flext_infra.gates.typings import t


class FlextInfraMarkdownGate(FlextInfraMarkdownGateBase):
    """Markdown quality gate."""

    gate_id: ClassVar[str] = c.Infra.MARKDOWN
    gate_name: ClassVar[str] = "Markdown"
    # Fixable findings are repaired by the native linter. The findings that
    # remain after repair come back under rumdl's declared findings status:
    # the repair verb completes and reports them, and the read-only gate
    # enforces them.
    can_fix: ClassVar[bool] = True

    @staticmethod
    @override
    def _findings_exit_codes() -> t.VariadicTuple[int]:
        """Exit statuses with which rumdl reports its findings.

        Returns:
            The findings statuses declared for rumdl in the tooling config.

        """
        return config.Infra.tooling.tools.markdown.findings_exit_codes

    @staticmethod
    def _resolve_config_args(project_dir: Path) -> t.StrSequence:
        """Resolve only the repository-local markdown settings owner.

        Returns:
            The resulting ``t.StrSequence``.

        """
        config_path = project_dir / c.Infra.MARKDOWNLINT_CONFIG_FILENAME
        if not config_path.is_file():
            return ["--no-config"]
        return ["--config", str(config_path.resolve())]

    def _resolve_exclude_args(self, project_dir: Path) -> t.StrSequence:
        """Build ``--exclude`` from .markdownlintignore patterns.

        ``rumdl`` only applies ignore patterns when scanning directories,
        not when files are passed explicitly on the command line. The gate
        collects files explicitly, so the generated ignore projection is read
        once and its patterns are forwarded via ``--exclude`` to replicate
        standard tool behavior.

        Returns:
            The resulting ``t.StrSequence``.

        """
        patterns = self.read_ignore_patterns(
            project_dir,
            c.Infra.MARKDOWNLINT_IGNORE_FILENAME,
        )
        if not patterns:
            return ()
        return ["--exclude", ",".join(patterns)]

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
        return self._rumdl_command(project_dir, check_dirs)

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
        return self._rumdl_command(project_dir, targets, "--fix")

    def _rumdl_command(
        self,
        project_dir: Path,
        targets: t.StrSequence,
        *mode_args: str,
    ) -> t.StrSequence:
        """Keep check and fix on the same rumdl invocation contract.

        Returns:
            The rumdl invocation over ``targets`` with the mode's flags.

        """
        return self._python_console_script_command(
            c.Infra.RUMDL,
            "check",
            *mode_args,
            "--no-cache",
            "--color",
            "never",
            "--output-format",
            "text",
            "--deny-config-warnings",
            *self._resolve_config_args(project_dir),
            *self._resolve_exclude_args(project_dir),
            *targets,
        )

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
            if match.group("msg").strip().endswith("[fixed]"):
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
