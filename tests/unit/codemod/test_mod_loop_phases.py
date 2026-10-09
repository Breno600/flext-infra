"""Unit tests for the mod loop's callback repair phases.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, infra, m
from flext_infra.codemod import (
    FlextInfraAccessorRenamePhase,
    FlextInfraApplyRenames,
    FlextInfraCodemodBatchApply,
    FlextInfraModGateEngine,
    FlextInfraNamespaceRelocationPhase,
)
from tests import u

_SOURCE_NAME = next(iter(c.ENFORCEMENT_ACCESSOR_RENAMES))
_REPLACEMENT_NAME = c.ENFORCEMENT_ACCESSOR_RENAMES[_SOURCE_NAME][0]


class _RecordingProgress:
    """Minimal real ModProgress transport that records emissions for asserts."""

    def __init__(self) -> None:
        """Initialize an empty emission log."""
        self.messages: list[str] = []

    def emit(self, message: str) -> None:
        """Record one progress line."""
        self.messages.append(message)

    def emit_rename(self, report: m.Infra.ApplyRenamesReport) -> None:
        """Record one rename campaign summary."""
        self.messages.append(f"rename occurrences={report.occurrences}")


def _phase_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    """Build one workspace owning a protocol violation and a rename target.

    Returns ``(workspace, project, service_file, legacy_file, foreign_file)``;
    the phases are driven with ``project`` as the repository root, exactly as
    the mod loop runs inside one repository.

    Returns:
        The resulting ``tuple[Path, Path, Path, Path, Path]``.
    """
    workspace, project, pkg = u.Tests.namespace_workspace(
        tmp_path,
        package_name="flext_core",
    )
    u.Tests.copy_tracked_mise_seeds(project)
    service_file = pkg / "service.py"
    _ = service_file.write_text(
        "from __future__ import annotations\n"
        "from typing import Protocol\n\n"
        "class ServiceContract(Protocol):\n"
        '    """Service contract under relocation."""\n'
        "\n"
        "    def run(self) -> str:\n"
        '        """Run the contract."""\n'
        "        ...\n",
        encoding="utf-8",
    )
    legacy_file = pkg / "legacy.py"
    _ = legacy_file.write_text(
        "from __future__ import annotations\n"
        "\n"
        f"def {_SOURCE_NAME}(flag: bool) -> bool:\n"
        "    return flag\n"
        "\n"
        "\n"
        f"value = {_SOURCE_NAME}(True)\n",
        encoding="utf-8",
    )
    foreign_pkg = project / "src" / "other_pkg"
    foreign_pkg.mkdir(parents=True, exist_ok=True)
    _ = (foreign_pkg / "__init__.py").write_text("", encoding="utf-8")
    foreign_file = foreign_pkg / "legacy.py"
    _ = foreign_file.write_text(
        "from __future__ import annotations\n"
        "\n"
        f"def {_SOURCE_NAME}(flag: bool) -> bool:\n"
        "    return flag\n",
        encoding="utf-8",
    )
    u.Tests.provision_checkout(workspace)
    return workspace, project, service_file, legacy_file, foreign_file


class TestsFlextInfraCodemodLoopPhases:
    """Behavior contract for test_mod_loop_phases."""

    @staticmethod
    def test_managed_scanner_keeps_resolution_outside_consumer_cwd(
        tmp_path: Path,
    ) -> None:
        """Resolve at the declared owner, then scan a tree with no Mise declaration."""
        project = u.Tests.create_codegen_project(
            tmp_path=tmp_path,
            name="scan-target",
            pkg_name="scan_target",
            files={"module.py": "value = 1\n"},
        )
        owner = Path(__file__).resolve().parents[3]
        binary = tm.ok(u.Infra.managed_mise_binary("ast-grep", owner))
        tm.that(binary.is_absolute(), eq=True)
        tm.that((project / c.Infra.MISE_TOML_FILENAME).exists(), eq=False)
        report = tm.ok(FlextInfraModGateEngine.scan(project, fix=False))
        tm.that(
            any(entry.file.name == "module.py" for entry in report.entries), eq=True
        )

    @staticmethod
    def test_namespace_phase_relocates_from_the_loop_scan(
        tmp_path: Path,
    ) -> None:
        """The relocation callback consumes the loop's own preflight scan."""
        _workspace, project, service_file, _legacy, _foreign = _phase_fixture(
            tmp_path,
        )
        with infra.rope_workspace(project) as rope:
            preflight = FlextInfraModGateEngine.scan(project, fix=False).unwrap()
            phase = FlextInfraNamespaceRelocationPhase()

            changed = phase.apply(project, preflight, rope)

        tm.that(changed.failure, eq=False)
        tm.that(changed.value, eq=True)
        protocols_file = service_file.parent / "protocols.py"
        tm.that(protocols_file.exists(), eq=True)
        tm.that(
            protocols_file.read_text(encoding="utf-8"),
            has="class ServiceContract(Protocol):",
        )

    @staticmethod
    def test_accessor_phase_renames_only_origin_owned_occurrences(
        tmp_path: Path,
    ) -> None:
        """The accessor callback keeps foreign homonyms untouched in the loop."""
        _workspace, project, _service, legacy_file, foreign_file = _phase_fixture(
            tmp_path,
        )
        with infra.rope_workspace(project) as rope:
            preflight = FlextInfraModGateEngine.scan(project, fix=False).unwrap()
            phase = FlextInfraAccessorRenamePhase()

            changed = phase.apply(project, preflight, rope)

        tm.that(changed.failure, eq=False)
        tm.that(changed.value, eq=True)
        legacy_source = legacy_file.read_text(encoding="utf-8")
        tm.that(legacy_source, has=f"def {_REPLACEMENT_NAME}(")
        tm.that(legacy_source, lacks=f"def {_SOURCE_NAME}(")
        foreign_source = foreign_file.read_text(encoding="utf-8")
        tm.that(foreign_source, has=f"def {_SOURCE_NAME}(")

    @staticmethod
    @pytest.mark.slow
    def test_batch_loop_runs_callback_phases_to_the_fixed_point(
        tmp_path: Path,
    ) -> None:
        """One ``refactor mod`` loop converges with both callback phases wired."""
        _workspace, project, service_file, legacy_file, foreign_file = _phase_fixture(
            tmp_path,
        )
        progress = _RecordingProgress()
        with infra.rope_workspace(project) as rope:
            result = FlextInfraCodemodBatchApply(
                repository_root=project,
                apply_changes=True,
                check_only=False,
                dry_run=False,
                rename_runner=FlextInfraApplyRenames(),
                progress=progress,
                rope=rope,
                rename_inputs=(),
                phase_callbacks=(
                    FlextInfraNamespaceRelocationPhase(),
                    FlextInfraAccessorRenamePhase(),
                ),
            ).execute()

        tm.that(result.failure, eq=False)
        tm.that(
            (service_file.parent / "protocols.py").exists(),
            eq=True,
        )
        legacy_source = legacy_file.read_text(encoding="utf-8")
        tm.that(legacy_source, has=f"def {_REPLACEMENT_NAME}(")
        tm.that(
            foreign_file.read_text(encoding="utf-8"),
            has=f"def {_SOURCE_NAME}(",
        )
        tm.that(
            progress.messages,
            has="mod: phase namespace-relocations changed sources",
        )
        tm.that(
            progress.messages,
            has="mod: phase accessor-rename changed sources",
        )
