"""Gate contract validation service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, override

from flext_core import r
from flext_infra import c, m

from ..base import s
from .gate_contract_checks import FlextInfraGateContractChecksMixin
from .gate_contract_report import FlextInfraGateContractReportMixin
from .gate_contract_scan import FlextInfraGateContractScanMixin

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraGateContractValidator(
    s[bool],
    FlextInfraGateContractScanMixin,
    FlextInfraGateContractChecksMixin,
    FlextInfraGateContractReportMixin,
):
    """Validate workspace gate scripts against the scripts-infra contract."""

    check_all: Annotated[
        bool,
        m.Field(description="Validate scripts that are not validators or fixers"),
    ] = False
    mode: Annotated[c.Infra.OperationMode, m.Field(description="Validation mode")] = (
        c.Infra.OperationMode.BASELINE
    )

    def run(self) -> p.Result[m.Infra.GateContractRunResult]:
        """Run validation and return the CLI outcome."""
        result_type = m.Infra.GateContractRunResult
        root = self.repository_root.resolve()
        if not root.is_dir():
            return r[result_type].fail(f"root directory not found: {root}")
        scripts = self._tracked_scripts(root)
        if scripts.failure:
            return r[result_type].from_failure(scripts)
        results = tuple(
            self._validate_script(root, script, check_all=self.check_all)
            for script in scripts.value
        )
        self._print_results(results)
        report_result = self._write_report(root, results, str(self.mode))
        if report_result.failure:
            return r[result_type].from_failure(report_result)
        summary = self._summary_for(results)
        self._print_summary(summary, report_result.value)
        exit_code = (
            int(c.Infra.ScriptExitCode.FAIL)
            if summary.errors > 0
            else int(c.Infra.ScriptExitCode.PASS)
        )
        return r[result_type].ok(
            result_type(exit_code=exit_code, violation_count=summary.errors),
        )

    @override
    def execute(self) -> p.Result[bool]:
        """Execute validation as a service."""
        return self.run().flat_map(
            lambda outcome: (
                r[bool].ok(True)
                if outcome.exit_code == int(c.Infra.ScriptExitCode.PASS)
                else r[bool].fail(
                    f"gate contract found {outcome.violation_count} error(s)",
                )
            ),
        )


__all__: list[str] = ["FlextInfraGateContractValidator"]
