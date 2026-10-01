"""FLEXT module-cap SUPREME LAW (§3.1) quality gate.

Enforces the per-module logical-LOC ceiling using scc's code-line count.
Per-class / per-method / per-function caps require AST and are out of scope
for this tool-driven gate (scc reports at file granularity only).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, config, m, u
from flext_infra.gates.base_gate import FlextInfraGate

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraLocCapGate(FlextInfraGate):
    """Flag any module whose scc `Code` LOC exceeds the config-owned ceiling."""

    gate_id: ClassVar[str] = "loc-cap"
    gate_name: ClassVar[str] = "MODULE-LOC SUPREME LAW"
    can_fix: ClassVar[bool] = False

    @override
    def _build_check_command(
        self, project_dir: Path, ctx: m.Infra.GateContext, check_dirs: t.StrSequence
    ) -> t.StrSequence:
        """Run scc over the project's Python directories, emitting per-file JSON."""
        _ = project_dir, ctx
        return [c.Infra.SCC_BINARY, "--format", "json", "--by-file", *check_dirs]

    @override
    def _parse_check_output(
        self, result: p.Cli.CommandOutput, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Parse scc JSON into one Issue per over-cap module."""
        _ = ctx
        if not u.Cli.process_succeeded(result.outcome):
            return (
                False,
                (
                    m.Infra.Issue(
                        file="<scc>",
                        line=0,
                        column=0,
                        code="LOC_CAP_EXEC",
                        message=result.stderr or "scc execution failed",
                        severity="ERROR",
                    ),
                ),
            )
        issues = self._files_over_cap(
            result.stdout, config.Infra.codegen.loc_cap.max_lines, project_dir
        )
        return len(issues) == 0, issues

    @staticmethod
    def _issue_for_over_cap(path: str, code: int, cap: int) -> m.Infra.Issue:
        """Build the ``LOC_CAP`` issue for one module past the SUPREME LAW cap."""
        return m.Infra.Issue(
            file=path,
            line=code,
            column=0,
            code="LOC_CAP",
            message=f"{code} code LOC exceeds {cap}-line SUPREME LAW",
            severity="ERROR",
        )

    @classmethod
    def _files_over_cap(
        cls, scc_json: str, cap: int, project_dir: Path
    ) -> t.VariadicTuple[m.Infra.Issue]:
        """Extract over-cap modules from an `scc --format json --by-file` payload.

        SCC paths are relative to its project working directory, not the caller.
        Parsing and header-read failures propagate. Generated facades carry
        AUTOGEN_HEADER and are exempt: their size is the generator's obligation,
        enforced by its own contract — the SUPREME LAW caps authored modules.
        """
        report = m.Infra.SccReport.model_validate_json(scc_json, strict=True)
        return tuple(
            cls._issue_for_over_cap(file.location, file.code, cap)
            for language in report.root
            if language.name == c.Infra.SCC_PYTHON_LANG
            for file in language.files
            if file.code > cap
            and not cls._is_generated_facade(project_dir / file.location)
        )

    @staticmethod
    def _is_generated_facade(path: Path) -> bool:
        """Return True when the file opens with the generator's AUTOGEN_HEADER."""
        with path.open(encoding=c.Cli.ENCODING_DEFAULT) as handle:
            return handle.readline().startswith(c.Infra.AUTOGEN_HEADER)


__all__: list[str] = ["FlextInfraLocCapGate"]
