"""Violations sweep: repair through the canonical verbs, prove the reduction.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import override

from flext_infra import c, m, p, r, u
from flext_infra.base import s
from flext_infra.codemod.batch_gates import FlextInfraModGateEngine


class FlextInfraRefactorViolationsSweep(s[m.Infra.ViolationsSweepReport]):
    """Run the canonical repair sequence and prove no violation total increased.

    The sweep measures the repository's mod scan totals, runs the repository's
    own canonical repair verbs in order (``make fix``, ``make fmt``,
    ``make mod`` — the same surface every agent and developer runs), measures
    again, and fails the command the moment any total increased: automation
    may reduce a tree's violations, never grow them. The before/after totals
    are published as one receipt under the repository's reports.
    """

    @override
    def execute(self) -> p.Result[m.Infra.ViolationsSweepReport]:
        """Scan, repair through the canonical verbs, rescan, publish, verdict.

        Returns:
            The resulting ``p.Result[m.Infra.ViolationsSweepReport]``.

        """
        root = self.repository_root
        before_scan = FlextInfraModGateEngine.scan(root, fix=False)
        if before_scan.failure:
            return r[m.Infra.ViolationsSweepReport].from_failure(before_scan)
        before = m.Infra.ViolationsTotals.from_scan_report(before_scan.value)
        for verb in c.Infra.VIOLATIONS_SWEEP_REPAIR_VERBS:
            repaired = u.Cli.run_checked([c.Infra.MAKE, verb], cwd=root)
            if repaired.failure:
                return r[m.Infra.ViolationsSweepReport].from_failure(repaired)
        after_scan = FlextInfraModGateEngine.scan(root, fix=False)
        if after_scan.failure:
            return r[m.Infra.ViolationsSweepReport].from_failure(after_scan)
        after = m.Infra.ViolationsTotals.from_scan_report(after_scan.value)
        report = m.Infra.ViolationsSweepReport(
            schema_version=c.Infra.VIOLATIONS_SWEEP_REPORT_SCHEMA_VERSION,
            repository_root=root.resolve(),
            repair_verbs=tuple(c.Infra.VIOLATIONS_SWEEP_REPAIR_VERBS),
            before=before,
            after=after,
        )
        published = u.Infra.publish_refactor_report_evidence(
            root,
            report,
            relative_path=c.Infra.VIOLATIONS_SWEEP_REPORT_RELATIVE_PATH,
        )
        if published.failure:
            return r[m.Infra.ViolationsSweepReport].from_failure(published)
        increased = report.increased_totals
        if increased:
            return r[m.Infra.ViolationsSweepReport].fail(
                "violations sweep grew "
                + ", ".join(
                    f"{name} {getattr(before, name)}->{getattr(after, name)}"
                    for name in increased
                ),
            )
        return r[m.Infra.ViolationsSweepReport].ok(report)


__all__: list[str] = ["FlextInfraRefactorViolationsSweep"]
