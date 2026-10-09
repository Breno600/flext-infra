"""Read the SARIF report ``check run`` wrote back into typed findings.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_cli import u

from flext_infra import c, m, r, t

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraUtilitiesLogParser:
    """Read the SARIF report ``check run`` wrote back into typed findings."""

    @staticmethod
    def check_report_findings(
        repository_root: Path,
        *,
        reports_dir: Path,
    ) -> p.Result[t.VariadicTuple[m.Infra.SarifResult]]:
        """Read the SARIF report ``check run`` wrote into typed findings.

        ``reports_dir`` is the exact invocation directory printed by ``check run``,
        not its shared base. Relative values are anchored at ``repository_root``.
        No implicit latest report is selected from concurrent or historical runs.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.SarifResult]]``.

        """
        report_dir = (
            u.Cli.resolve_report_dir(
                repository_root,
                c.Infra.PROJECT,
                c.Infra.VERB_CHECK,
            )
            if reports_dir is None
            else (repository_root / reports_dir).resolve()
        )
        sarif_path = report_dir / c.Infra.CHECK_REPORT_SARIF_FILENAME
        if not sarif_path.is_file():
            return r[t.VariadicTuple[m.Infra.SarifResult]].fail(
                f"check report not found: {sarif_path}",
            )
        return u.validate_value(
            m.Infra.SarifReport,
            sarif_path.read_text(encoding=c.Cli.ENCODING_DEFAULT),
            from_json=True,
        ).map(lambda report: tuple(res for run in report.runs for res in run.results))


__all__: list[str] = ["FlextInfraUtilitiesLogParser"]
