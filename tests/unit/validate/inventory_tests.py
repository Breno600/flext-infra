"""Tests for FlextInfraInventoryService.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra.validate.inventory import FlextInfraInventoryService
from tests import m, u


class TestsFlextInfraInventory:
    """Core, script-scanning, and report-generation tests for FlextInfraInventoryService."""

    def test_generate_empty_workspace(self, tmp_path: Path) -> None:
        """Empty workspace returns success with zero scripts."""
        service = FlextInfraInventoryService()
        report: m.Infra.InventoryReport = tm.ok(service.generate(tmp_path))
        tm.that(report, is_=m.Infra.InventoryReport)
        tm.that(report.total_scripts, eq=0)

    def test_generate_with_output_dir(self, tmp_path: Path) -> None:
        """Generate creates reports in output directory."""
        service = FlextInfraInventoryService()
        output_dir = tmp_path / "reports"
        output_dir.mkdir()
        tm.ok(service.generate(tmp_path, output_dir=output_dir))

    def test_generate_scans_python_scripts(self, tmp_path: Path) -> None:
        """Python scripts are detected."""
        service = FlextInfraInventoryService()
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "test.py").write_text("#!/usr/bin/env python3\nu.Cli.print('hello')")
        tm.ok(service.generate(tmp_path))

    def test_generate_scans_bash_scripts(self, tmp_path: Path) -> None:
        """Bash scripts are detected."""
        service = FlextInfraInventoryService()
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "test.sh").write_text("#!/bin/bash\necho 'hello'")
        tm.ok(service.generate(tmp_path))

    def test_generate_counts_multiple_scripts(self, tmp_path: Path) -> None:
        """All scripts are counted."""
        service = FlextInfraInventoryService()
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "script1.py").write_text("")
        (scripts / "script2.sh").write_text("")
        (scripts / "script3.py").write_text("")
        report: m.Infra.InventoryReport = tm.ok(service.generate(tmp_path))
        tm.that(report.total_scripts, eq=3)

    def test_generate_finds_nested_scripts(self, tmp_path: Path) -> None:
        """Scripts in nested directories are found."""
        service = FlextInfraInventoryService()
        subdir = tmp_path / "scripts" / "subdir"
        subdir.mkdir(parents=True)
        (tmp_path / "scripts" / "script1.py").write_text("")
        (subdir / "script2.sh").write_text("")
        report: m.Infra.InventoryReport = tm.ok(service.generate(tmp_path))
        tm.that(report.total_scripts, eq=2)

    def test_generate_ignores_non_script_files(self, tmp_path: Path) -> None:
        """Non-script files are excluded from count."""
        service = FlextInfraInventoryService()
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "script.py").write_text("")
        (scripts / "readme.txt").write_text("")
        (scripts / "settings.json").write_text("")
        report: m.Infra.InventoryReport = tm.ok(service.generate(tmp_path))
        tm.that(report.total_scripts, eq=1)

    def test_generate_missing_scripts_dir(self, tmp_path: Path) -> None:
        """Missing scripts directory returns zero scripts."""
        service = FlextInfraInventoryService()
        report: m.Infra.InventoryReport = tm.ok(service.generate(tmp_path))
        tm.that(report.total_scripts, eq=0)

    def test_generate_sorts_scripts_alphabetically(self, tmp_path: Path) -> None:
        """The written inventory lists scripts in sorted path order."""
        service = FlextInfraInventoryService()
        output_dir = tmp_path / "reports"
        output_dir.mkdir()
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        for name in ("z_script.py", "a_script.py", "m_script.py"):
            (scripts / name).write_text("")
        report: m.Infra.InventoryReport = tm.ok(
            service.generate(tmp_path, output_dir=output_dir)
        )
        payloads = [
            tm.ok(u.Cli.json_read(Path(path))) for path in report.reports_written
        ]
        inventory = next(payload for payload in payloads if "scripts" in payload)
        tm.that(
            inventory["scripts"],
            eq=["scripts/a_script.py", "scripts/m_script.py", "scripts/z_script.py"],
        )

    def test_generate_returns_reports_written_list(self, tmp_path: Path) -> None:
        """Reports written is a list."""
        service = FlextInfraInventoryService()
        output_dir = tmp_path / "reports"
        output_dir.mkdir()
        report: m.Infra.InventoryReport = tm.ok(
            service.generate(tmp_path, output_dir=output_dir)
        )
        tm.that(report.reports_written, is_=list)

    def test_generate_creates_inventory_report(self, tmp_path: Path) -> None:
        """Inventory report is created with scripts."""
        service = FlextInfraInventoryService()
        output_dir = tmp_path / "reports"
        output_dir.mkdir()
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "test.py").write_text("")
        tm.ok(service.generate(tmp_path, output_dir=output_dir))

    def test_generate_nonexistent_workspace(self, tmp_path: Path) -> None:
        """Nonexistent workspace still returns success."""
        service = FlextInfraInventoryService()
        result = service.generate(tmp_path / "nonexistent")
        tm.that(result.success, eq=True)

    def test_generate_write_to_readonly_dir_fails(self, tmp_path: Path) -> None:
        """Writing to read-only output directory fails."""
        service = FlextInfraInventoryService()
        output_dir = tmp_path / "reports"
        output_dir.mkdir()
        output_dir.chmod(0o444)
        try:
            result = service.generate(tmp_path, output_dir=output_dir)
            tm.that(result.failure, eq=True)
        finally:
            output_dir.chmod(0o755)
