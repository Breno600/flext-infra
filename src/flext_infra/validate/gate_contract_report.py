"""Gate contract reporting."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, m, t, u

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraGateContractReportMixin:
    """Render gate contract validation output."""

    @staticmethod
    def _eprint(message: str) -> None:
        _ = sys.stderr.write(f"{message}\n")

    @staticmethod
    def _report_path_for(root: Path) -> Path:
        return root / ".claude" / "skills" / "scripts-infra" / "report.json"

    @staticmethod
    def _visible_scripts(
        scripts: t.SequenceOf[m.Infra.GateContractScriptInfo],
    ) -> t.SequenceOf[m.Infra.GateContractScriptInfo]:
        return tuple(
            script
            for script in scripts
            if script.role != "other" or bool(script.violations)
        )

    @staticmethod
    def _gate_scripts(
        scripts: t.SequenceOf[m.Infra.GateContractScriptInfo],
    ) -> t.SequenceOf[m.Infra.GateContractScriptInfo]:
        return tuple(
            script for script in scripts if script.role in {"validator", "fixer"}
        )

    def _print_script_result(self, script: m.Infra.GateContractScriptInfo) -> None:
        errors = len(script.violations)
        status = (
            f"{c.Infra.RED}FAIL{c.Infra.RESET}"
            if errors
            else f"{c.Infra.GREEN}OK{c.Infra.RESET}"
        )
        detail = f"{errors} error(s)" if errors else "contract compliant"
        u.Cli.formatters_print(
            f"{script.path:<60} {script.role:<10} {status:<22} {detail}"
        )
        for violation in script.violations:
            u.Cli.formatters_print(
                f"  {c.Infra.RED}[{violation.check}]{c.Infra.RESET} {violation.message}"
            )

    def _print_results(
        self, scripts: t.SequenceOf[m.Infra.GateContractScriptInfo]
    ) -> None:
        u.Cli.formatters_print(f"{c.Infra.CYAN}Gate Contract Validation{c.Infra.RESET}")
        u.Cli.formatters_print(
            f"{c.Infra.CYAN}{'SCRIPT':<60} {'ROLE':<10} {'STATUS':<10} DETAILS{c.Infra.RESET}"
        )
        for script in self._visible_scripts(scripts):
            self._print_script_result(script)

    @staticmethod
    def _violation_rows(
        scripts: t.SequenceOf[m.Infra.GateContractScriptInfo],
    ) -> t.SequenceOf[t.JsonDict]:
        def violation_key(row: t.JsonDict) -> t.Pair[str, str]:
            return str(row.get("script", "")), str(row.get("check", ""))

        rows = [
            t.json_dict_adapter().validate_python(violation.model_dump())
            for script in scripts
            for violation in script.violations
        ]
        return tuple(sorted(rows, key=violation_key))

    def _summary_for(
        self, scripts: t.SequenceOf[m.Infra.GateContractScriptInfo]
    ) -> m.Infra.GateContractSummary:
        gate_scripts = self._gate_scripts(scripts)
        errors = sum(len(script.violations) for script in scripts)
        ok = sum(1 for script in gate_scripts if not script.violations)
        return m.Infra.GateContractSummary(
            errors=errors, gate_scripts=len(gate_scripts), ok=ok, warnings=0
        )

    def _write_report(
        self,
        root: Path,
        scripts: t.SequenceOf[m.Infra.GateContractScriptInfo],
        mode: str,
    ) -> p.Result[Path]:
        report_path = self._report_path_for(root)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        summary = self._summary_for(scripts)
        violations: t.JsonValue = t.json_value_adapter().validate_python(
            list(self._violation_rows(scripts))
        )
        payload: t.JsonMapping = {
            "checked": len(self._visible_scripts(scripts)),
            "errors": summary.errors,
            "mode": mode,
            "violations": violations,
        }
        write = u.Cli.json_write(
            report_path,
            payload,
            options=m.Cli.JsonWriteOptions(indent=2, sort_keys=True),
        )
        if write.failure:
            return r[Path].from_failure(write)
        return r[Path].ok(report_path)

    def _print_summary(
        self, summary: m.Infra.GateContractSummary, report_path: Path
    ) -> None:
        u.Cli.formatters_print(
            f"\n{c.Infra.CYAN}Summary:{c.Infra.RESET} "
            f"gate_scripts={summary.gate_scripts} "
            f"{c.Infra.GREEN}ok={summary.ok}{c.Infra.RESET} "
            f"{c.Infra.RED}errors={summary.errors}{c.Infra.RESET}"
        )
        u.Cli.formatters_print(f"Report: {report_path}")


__all__: list[str] = ["FlextInfraGateContractReportMixin"]
