"""Unit tests for the accessor migration orchestrator's rewrite contract.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import c
from flext_infra.refactor.accessor_migration import (
    FlextInfraAccessorMigrationOrchestrator,
)
from tests import u

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import t

_SOURCE_NAME = next(iter(c.ENFORCEMENT_ACCESSOR_RENAMES))
_REPLACEMENT_NAME = c.ENFORCEMENT_ACCESSOR_RENAMES[_SOURCE_NAME][0]


def _legacy_module_source() -> str:
    """Return a module defining and calling the catalog's first rename source."""
    return (
        "from __future__ import annotations\n"
        "\n"
        f"def {_SOURCE_NAME}(flag: bool) -> bool:\n"
        "    return flag\n"
        "\n"
        "\n"
        f"value = {_SOURCE_NAME}(True)\n"
    )


def _materialize_fixture(tmp_path: Path) -> t.Triple[Path, Path, Path]:
    """Build one workspace whose origin-named package owns the rename target.

    Returns:
        The resulting ``t.Triple[Path, Path, Path]``.
    """
    workspace, project, pkg = u.Tests.namespace_workspace(
        tmp_path,
        package_name="flext_core",
    )
    origin_file = pkg / "legacy.py"
    _ = origin_file.write_text(_legacy_module_source(), encoding="utf-8")
    foreign_pkg = project / "src" / "other_pkg"
    foreign_pkg.mkdir(parents=True, exist_ok=True)
    _ = (foreign_pkg / "__init__.py").write_text("", encoding="utf-8")
    foreign_file = foreign_pkg / "legacy.py"
    _ = foreign_file.write_text(_legacy_module_source(), encoding="utf-8")
    u.Tests.provision_checkout(workspace)
    return workspace, origin_file, foreign_file


class TestsFlextInfraRefactorInfraRefactorAccessorMigration:
    """Behavior contract for test_infra_refactor_accessor_migration."""

    @staticmethod
    def test_dry_run_reports_pending_change_and_writes_nothing(
        tmp_path: Path,
    ) -> None:
        """A run without ``apply`` never writes sources and says it is dry."""
        workspace, origin_file, _foreign_file = _materialize_fixture(tmp_path)
        source_before = origin_file.read_text(encoding="utf-8")
        orchestrator = FlextInfraAccessorMigrationOrchestrator(
            repository_root=workspace,
            apply_changes=False,
        )

        result = orchestrator.execute()

        tm.that(result.failure, eq=False)
        tm.that(result.value.dry_run, eq=True)
        tm.that(result.value.automated_change_count > 0, eq=True)
        tm.that(origin_file.read_text(encoding="utf-8"), eq=source_before)

    @staticmethod
    def test_dry_run_publishes_the_report_receipt(tmp_path: Path) -> None:
        """Every run publishes the structured receipt under ``.reports``."""
        workspace, _origin_file, _foreign_file = _materialize_fixture(tmp_path)
        orchestrator = FlextInfraAccessorMigrationOrchestrator(
            repository_root=workspace,
            apply_changes=False,
        )

        result = orchestrator.execute()

        tm.that(result.failure, eq=False)
        receipt = (
            workspace / c.Infra.ACCESSOR_MIGRATION_REPORT_RELATIVE_PATH
        ).resolve()
        tm.that(receipt.exists(), eq=True)
        published = json.loads(receipt.read_text(encoding="utf-8"))
        tm.that(published["dry_run"], eq=True)
        tm.that(published["workspace"], eq=str(workspace))

    @staticmethod
    def test_apply_renames_origin_owned_and_leaves_foreign_homonym(
        tmp_path: Path,
    ) -> None:
        """Only occurrences defined inside the origin package are renamed."""
        workspace, origin_file, foreign_file = _materialize_fixture(tmp_path)
        orchestrator = FlextInfraAccessorMigrationOrchestrator(
            repository_root=workspace,
            apply_changes=True,
        )

        result = orchestrator.execute()

        tm.that(result.failure, eq=False)
        tm.that(result.value.dry_run, eq=False)
        origin_source = origin_file.read_text(encoding="utf-8")
        tm.that(origin_source, has=f"def {_REPLACEMENT_NAME}(")
        tm.that(origin_source, has=f"= {_REPLACEMENT_NAME}(True)")
        tm.that(origin_source, lacks=f"def {_SOURCE_NAME}(")
        foreign_source = foreign_file.read_text(encoding="utf-8")
        tm.that(foreign_source, eq=_legacy_module_source())
        skipped_reasons = tuple(
            change.reason
            for file_report in result.value.files
            for change in file_report.warnings
            if change.reason.startswith("Skipped homonym")
        )
        tm.that(skipped_reasons, empty=False)

    @staticmethod
    def test_apply_is_idempotent_on_the_second_pass(tmp_path: Path) -> None:
        """A second pass over the migrated tree finds nothing left to rename."""
        workspace, origin_file, _foreign_file = _materialize_fixture(tmp_path)
        first = FlextInfraAccessorMigrationOrchestrator(
            repository_root=workspace,
            apply_changes=True,
        ).execute()
        tm.that(first.failure, eq=False)
        migrated_source = origin_file.read_text(encoding="utf-8")

        second = FlextInfraAccessorMigrationOrchestrator(
            repository_root=workspace,
            apply_changes=True,
        ).execute()

        tm.that(second.failure, eq=False)
        tm.that(second.value.automated_change_count, eq=0)
        tm.that(origin_file.read_text(encoding="utf-8"), eq=migrated_source)

    @staticmethod
    def test_module_filter_scopes_the_scanned_files(tmp_path: Path) -> None:
        """``target_module`` keeps only files under the declared module path."""
        workspace, _origin_file, _foreign_file = _materialize_fixture(tmp_path)
        unfiltered = FlextInfraAccessorMigrationOrchestrator(
            repository_root=workspace,
            apply_changes=False,
        ).execute()
        tm.that(unfiltered.failure, eq=False)

        filtered = FlextInfraAccessorMigrationOrchestrator(
            repository_root=workspace,
            apply_changes=False,
            target_module="flext_core.legacy",
        ).execute()

        tm.that(filtered.failure, eq=False)
        tm.that(
            filtered.value.files_scanned < unfiltered.value.files_scanned,
            eq=True,
        )
        tm.that(filtered.value.files_scanned > 0, eq=True)

    @staticmethod
    def test_manual_warnings_stay_advisory_and_external_contracts_exempt(
        tmp_path: Path,
    ) -> None:
        """Public accessor warnings never rewrite; external contracts stay silent."""
        workspace, _project, pkg = u.Tests.namespace_workspace(
            tmp_path,
            package_name="flext_core",
        )
        advisory_file = pkg / "advisory.py"
        _ = advisory_file.write_text(
            "from __future__ import annotations\n"
            "\n"
            "def get_value() -> int:\n"
            "    return 1\n"
            "\n"
            "\n"
            "def get_field_value() -> int:\n"
            "    return 2\n",
            encoding="utf-8",
        )
        u.Tests.provision_checkout(workspace)
        orchestrator = FlextInfraAccessorMigrationOrchestrator(
            repository_root=workspace,
            apply_changes=True,
        )

        result = orchestrator.execute()

        tm.that(result.failure, eq=False)
        advisory_source = advisory_file.read_text(encoding="utf-8")
        tm.that(advisory_source, has="def get_value() -> int:")
        tm.that(advisory_source, has="def get_field_value() -> int:")
        warning_names = tuple(
            change.original_name
            for file_report in result.value.files
            for change in file_report.warnings
        )
        tm.that(warning_names, has="get_value")
        tm.that(warning_names, lacks="get_field_value")
