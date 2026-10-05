"""Public entrypoint tests for ``FlextInfraDocAuditor.main``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import FlextInfraCli, main
from tests import u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraAuditorCli:
    """Public entrypoint behavior for ``FlextInfraDocAuditor.main``."""

    @staticmethod
    def test_auditor_main_help_exits_zero() -> None:
        """Test auditor main help exits zero."""
        tm.that(main(["docs", "audit", "--help"]), eq=0)

    @staticmethod
    def test_auditor_main_writes_reports_for_selected_project(
        tmp_path: Path,
    ) -> None:
        """Test auditor main writes reports for selected project."""
        workspace = u.Tests.create_docs_workspace(
            tmp_path,
            project_names=("flext-a", "flext-b"),
        )

        tm.that(
            (
                main([
                    "docs",
                    "audit",
                    "--repository-root",
                    str(workspace),
                    "--projects",
                    "flext-a",
                ])
                == 0
            ),
            eq=True,
        )
        tm.that((workspace / ".reports/docs/audit-report.md").exists(), eq=True)
        tm.that((workspace / "flext-a/.reports/docs/audit-report.md").exists(), eq=True)
        tm.that(
            not (workspace / "flext-b/.reports/docs/audit-report.md").exists(),
            eq=True,
        )

    @staticmethod
    @pytest.mark.parametrize("package_entrypoint", [False, True])
    @staticmethod
    def test_auditor_main_finding_exits_nonzero(
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        *,
        package_entrypoint: bool,
    ) -> None:
        """Test auditor main finding exits nonzero."""
        workspace = u.Tests.create_docs_workspace(tmp_path)
        (workspace / "docs/README.md").write_text(
            "# Docs\n\n[Broken](missing.md)\n",
            encoding="utf-8",
        )

        argv = ["audit", "--repository-root", str(workspace)]
        result = (
            FlextInfraCli.docs_main(argv)
            if package_entrypoint
            else main(["docs", *argv])
        )
        tm.that(result, eq=1)
        captured = capsys.readouterr()
        tm.that("Audit completed successfully" in captured.out + captured.err, eq=False)
        tm.that(
            (workspace / ".reports/docs/audit-report.md").read_text(encoding="utf-8"),
            has="missing.md",
        )

    @staticmethod
    @pytest.mark.parametrize("option", ["--strict", "--strict-mode", "--no-strict"])
    @staticmethod
    def test_auditor_cli_rejects_removed_modes(
        tmp_path: Path,
        option: str,
    ) -> None:
        """The old CLI forms cannot select an alternative audit policy."""
        workspace = u.Tests.create_docs_workspace(tmp_path)
        tm.that(
            main(["docs", "audit", "--repository-root", str(workspace), option]),
            ne=0,
        )
        tm.that((workspace / ".reports/docs/audit-report.md").exists(), eq=False)

    @staticmethod
    def test_auditor_cli_medium_finding_exits_nonzero(tmp_path: Path) -> None:
        """A policy finding stays reported and fails the public entrypoint."""
        workspace = u.Tests.create_docs_workspace(tmp_path)
        (workspace / "docs/README.md").write_text("Retired phrase\n", encoding="utf-8")
        payload: t.JsonDict = {"audit": {"forbidden_terms": ["Retired phrase"]}}
        tm.ok(u.Cli.json_write(workspace / "docs/docs_config.json", payload))
        tm.that(main(["docs", "audit", "--repository-root", str(workspace)]), eq=1)
        markdown = (workspace / ".reports/docs/audit-report.md").read_text(
            encoding="utf-8",
        )
        tm.that(markdown, has="forbidden_term")
        tm.that(markdown, has="medium")
