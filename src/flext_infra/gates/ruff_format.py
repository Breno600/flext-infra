"""Ruff format gate implementation.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, config, m, r, t, u
from flext_infra.gates.base_gate import FlextInfraGate

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraRuffFormatGate(FlextInfraGate):
    """Gate for Ruff formatter checks and fixes."""

    gate_id: ClassVar[str] = c.Infra.FORMAT
    gate_name: ClassVar[str] = "Ruff Format"
    can_fix: ClassVar[bool] = True

    @override
    def _build_check_command(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        check_dirs: t.StrSequence,
    ) -> t.StrSequence:
        """Build the format verdict command from the config-owned flags.

        Returns:
            The resulting ``t.StrSequence``.

        """
        _ = project_dir, ctx
        return self._python_module_command(
            c.Infra.RUFF,
            c.Infra.FORMAT,
            *config.Infra.codegen.make.ruff.format_check,
            *check_dirs,
        )

    @override
    def _get_check_dirs(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.StrSequence:
        """Format every project-owned Python root, or the project itself.

        Returns:
            The owned Python roots, falling back to the project directory.

        """
        _ = ctx
        return self._existing_check_dirs(project_dir) or ["."]

    @override
    def _parse_check_output(
        self,
        result: p.Cli.CommandOutput,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Report each file Ruff would reformat once, from its check listing.

        Returns:
            The run's verdict and one finding per file left unformatted.

        """
        _ = project_dir, ctx
        issues: t.MutableSequenceOf[m.Infra.Issue] = []
        if not u.Cli.process_succeeded(result.outcome) and result.stdout.strip():
            seen: t.Infra.StrSet = set()
            for line in result.stdout.strip().splitlines():
                raw = line.strip()
                if not raw:
                    continue
                match = c.Infra.RUFF_FORMAT_FILE_RE.match(raw)
                resolved = match.group(1).strip() if match else raw
                if not resolved or resolved in seen:
                    continue
                if match or (
                    resolved.endswith(c.Infra.EXT_PYTHON) and " " not in resolved
                ):
                    seen.add(resolved)
                    issues.append(
                        m.Infra.Issue(
                            file=resolved,
                            line=0,
                            column=0,
                            code=c.Infra.FORMAT,
                            message="Would be reformatted",
                        ),
                    )
        return u.Cli.process_succeeded(result.outcome), issues

    @override
    def _build_fix_command(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        targets: t.StrSequence,
    ) -> t.StrSequence:
        """Build fix command.

        Returns:
            The resulting ``t.StrSequence``.

        """
        _ = project_dir, ctx
        return self._python_module_command(
            c.Infra.RUFF,
            c.Infra.FORMAT,
            *config.Infra.codegen.make.ruff.format_apply,
            *targets,
        )

    @classmethod
    def format_files(
        cls,
        repository_root: Path,
        paths: t.SequenceOf[Path],
    ) -> p.Result[bool]:
        """Format an explicit path list with the config-owned apply flags.

        One batched invocation over exactly the rewritten files: a rewrite
        publisher (``make mod``) needs its output formatter-clean at write
        time, because the mod circuit enforces canonical formatting on the
        first pass after applying instead of deferring to a project-wide
        ``make fmt`` sweep.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if not paths:
            return r[bool].ok(value=True)
        command = cls._python_module_command(
            c.Infra.RUFF,
            c.Infra.FORMAT,
            *config.Infra.codegen.make.ruff.format_apply,
            *(str(path) for path in paths),
        )
        run = u.Cli.run_raw(command, cwd=repository_root)
        if run.failure:
            return r[bool].from_failure(run)
        if not u.Cli.process_succeeded(run.value.outcome):
            return r[bool].fail(run.value.stdout)
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraRuffFormatGate"]
