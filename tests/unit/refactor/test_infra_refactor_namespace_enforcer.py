"""Unit tests for the namespace enforcer's rule-catalog relocations.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, m
from flext_infra.refactor.namespace_enforcer import FlextInfraNamespaceEnforcer
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRefactorInfraRefactorNamespaceEnforcer:
    """Behavior contract for test_infra_refactor_namespace_enforcer."""

    @staticmethod
    def test_namespace_enforcer_apply_moves_manual_protocol_to_protocols_file(
        tmp_path: Path,
    ) -> None:
        """Move a manual protocol into the canonical protocols module."""
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path)
        service_file = pkg / "service.py"
        _ = service_file.write_text(
            "from __future__ import annotations\n"
            "from typing import Protocol\n\n"
            "class ServiceContract(Protocol):\n"
            '    """Service contract under relocation."""\n'
            "\n"
            "    def run(self) -> str:\n"
            '        """Run the contract."""\n'
            "        ...\n\n"
            "class ServiceImpl:\n"
            "    def run(self) -> str:\n"
            "        return 'ok'",
            encoding="utf-8",
        )
        u.Tests.provision_checkout(workspace)

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=True,
        )

        tm.that(report.projects[0].relocation_findings, eq=0)
        protocols_file = pkg / "protocols.py"
        tm.that(protocols_file.exists(), eq=True)

        protocols_source = protocols_file.read_text(encoding="utf-8")
        tm.that(protocols_source, has="class ServiceContract(Protocol):")
        tm.that(protocols_source, has="from __future__ import annotations")
        tm.that(protocols_source, has="from typing import Protocol")

    @staticmethod
    @pytest.mark.slow
    def test_namespace_enforcer_apply_keeps_autofixes_when_other_violations_remain(
        tmp_path: Path,
    ) -> None:
        """Relocate what a rule repairs and leave the detection-only finding."""
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path)
        service_file = pkg / "service.py"
        _ = service_file.write_text(
            "from __future__ import annotations\n"
            "import logging\n"
            "from typing import Protocol\n\n"
            "logger = logging.getLogger(__name__)\n\n"
            "class ServiceContract(Protocol):\n"
            '    """Service contract under relocation."""\n'
            "\n"
            "    def run(self) -> str:\n"
            '        """Run the contract."""\n'
            "        ...\n",
            encoding="utf-8",
        )
        u.Tests.provision_checkout(workspace)

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=True,
        )

        tm.that(report.projects[0].relocation_findings, eq=0)
        tm.that(service_file.read_text(encoding="utf-8"), has="logger = ")
        tm.that((pkg / "protocols.py").exists(), eq=True)
        tm.that(
            (pkg / "protocols.py").read_text(encoding="utf-8"),
            has="class ServiceContract(Protocol):",
        )
        tm.that(
            service_file.read_text(encoding="utf-8"),
            lacks="class ServiceContract(Protocol):",
        )

    @staticmethod
    def test_namespace_enforcer_respects_tool_flext_namespace_scan_dirs(
        tmp_path: Path,
    ) -> None:
        """Respect configured namespace scan directories."""
        workspace, project, _pkg = u.Tests.namespace_workspace(
            tmp_path,
            pyproject=(
                "[project]\nname='sample'\n\n"
                "[tool.flext.namespace]\nscan_dirs = ['src']\n"
            ),
        )
        examples_dir = project / "examples"
        examples_dir.mkdir(parents=True)
        _ = (examples_dir / "constants.py").write_text(
            "from __future__ import annotations\n\nclass DemoConstants:\n    pass\n",
            encoding="utf-8",
        )
        alias_file = examples_dir / "aliases.py"
        alias_source = "from __future__ import annotations\n\ntype LocalAlias = str\n"
        _ = alias_file.write_text(alias_source, encoding="utf-8")

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=True,
        )

        tm.that(report.projects, empty=False)
        tm.that(alias_file.read_text(encoding="utf-8"), eq=alias_source)

    @staticmethod
    def test_namespace_enforcer_skips_dynamic_dirs_by_default(
        tmp_path: Path,
    ) -> None:
        """Skip dynamic directories when no scan override is declared."""
        workspace, project, _pkg = u.Tests.namespace_workspace(tmp_path)
        docs_dir = project / "docs"
        docs_dir.mkdir(parents=True)
        _ = (docs_dir / "contracts.py").write_text(
            "from __future__ import annotations\n"
            "from typing import Protocol\n\n"
            "class HiddenContract(Protocol):\n"
            "    def run(self) -> str:\n"
            '        """Run the contract."""\n'
            "        ...\n",
            encoding="utf-8",
        )

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=False,
        )

        tm.that(report.projects[0].relocation_findings, eq=0)

    @staticmethod
    def test_namespace_enforcer_apply_keeps_script_shebang_when_adding_future(
        tmp_path: Path,
    ) -> None:
        """Preserve a script shebang while adding the future import."""
        workspace, project, _pkg = u.Tests.namespace_workspace(tmp_path)
        scripts_dir = project / "scripts"
        scripts_dir.mkdir(parents=True)
        script_file = scripts_dir / "run.py"
        _ = script_file.write_text(
            "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\nu.Cli.print('ok')\n",
            encoding="utf-8",
        )
        u.Tests.provision_checkout(workspace)

        _ = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(apply=True)

        rewritten_lines = script_file.read_text(encoding="utf-8").splitlines()
        tm.that(rewritten_lines[0], eq="#!/usr/bin/env python3")
        tm.that(rewritten_lines[1], eq="# -*- coding: utf-8 -*-")
        tm.that(rewritten_lines, has="from __future__ import annotations")

    @staticmethod
    def test_namespace_enforcer_apply_inserts_future_after_single_line_module_docstring(
        tmp_path: Path,
    ) -> None:
        """Insert the future import after a one-line module docstring."""
        workspace, project, _pkg = u.Tests.namespace_workspace(tmp_path)
        scripts_dir = project / "scripts"
        scripts_dir.mkdir(parents=True)
        target_file = scripts_dir / "base_improved.py"
        _ = target_file.write_text(
            '"""Improved test base with high automation and real functionality."""\n'
            "from pathlib import Path\n"
            "\n"
            "class DemoMigrationTestBase:\n"
            '    """Highly automated test base with real functionality patterns."""\n'
            "    temp_dir: Path\n",
            encoding="utf-8",
        )
        u.Tests.provision_checkout(workspace)

        _ = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(apply=True)

        rewritten_lines = target_file.read_text(encoding="utf-8").splitlines()
        tm.that(rewritten_lines[0].startswith('"""Improved test base'), eq=True)
        future_index = rewritten_lines.index("from __future__ import annotations")
        import_index = rewritten_lines.index("from pathlib import Path")
        tm.that(future_index > 0, eq=True)
        tm.that(future_index < import_index, eq=True)

    @staticmethod
    def test_namespace_enforcer_does_not_rewrite_indented_import_aliases(
        tmp_path: Path,
    ) -> None:
        """Leave indented import aliases unchanged."""
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path, declare=False)
        service_file = pkg / "service.py"
        _ = service_file.write_text(
            "from __future__ import annotations\n\n"
            "def runner() -> None:\n"
            "    from flext_core import System\n"
            "    _ = System\n",
            encoding="utf-8",
        )

        _ = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(apply=True)

        service_source = service_file.read_text(encoding="utf-8")
        tm.that(service_source, has="    from flext_core import System")

    @staticmethod
    def test_namespace_enforcer_does_not_rewrite_multiline_import_alias_blocks(
        tmp_path: Path,
    ) -> None:
        """Leave multiline import alias blocks unchanged."""
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path, declare=False)
        module_file = pkg / "constants.py"
        _ = module_file.write_text(
            "from __future__ import annotations\n"
            "from flext_infra import (\n"
            "    FlextInfraConstantsCore,\n"
            "    FlextInfraConstantsSharedInfra,\n"
            ")\n"
            "\n"
            "class DemoConstants:\n"
            "    CORE = FlextInfraConstantsCore\n"
            "    SHARED = FlextInfraConstantsSharedInfra\n",
            encoding="utf-8",
        )

        _ = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(apply=True)

        module_source = module_file.read_text(encoding="utf-8")
        tm.that(module_source, has="from flext_infra import (")
        tm.that(module_source, has="FlextInfraConstantsCore")
        tm.that(module_source, has="FlextInfraConstantsSharedInfra")
        tm.that(module_source, has="CORE = FlextInfraConstantsCore")
        tm.that(module_source, has="SHARED = FlextInfraConstantsSharedInfra")

    @staticmethod
    def test_namespace_enforcer_apply_hoists_function_local_stdlib_import(
        tmp_path: Path,
    ) -> None:
        """Hoist a function-local standard-library import to the module block."""
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path)
        service_file = pkg / "service.py"
        _ = service_file.write_text(
            "from __future__ import annotations\n\n"
            "class SampleService:\n"
            "    def run(self) -> str:\n"
            "        import os\n\n"
            "        return os.sep\n",
            encoding="utf-8",
        )
        u.Tests.provision_checkout(workspace)
        enforcer = FlextInfraNamespaceEnforcer(repository_root=workspace)

        pending = enforcer.enforce(apply=False)
        report = enforcer.enforce(apply=True)

        tm.that(pending.projects[0].relocation_findings > 0, eq=True)
        tm.that(report.projects[0].relocation_findings, eq=0)
        lines = service_file.read_text(encoding="utf-8").splitlines()
        tm.that(lines, has="import os")
        tm.that(lines, lacks="        import os")

    @staticmethod
    def test_namespace_enforcer_apply_is_idempotent_on_the_second_pass(
        tmp_path: Path,
    ) -> None:
        """A second apply over the enforced tree relocates nothing new."""
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path)
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
        u.Tests.provision_checkout(workspace)
        enforcer = FlextInfraNamespaceEnforcer(repository_root=workspace)

        _first = enforcer.enforce(apply=True)
        enforced_sources = {
            path: path.read_text(encoding="utf-8") for path in sorted(pkg.rglob("*.py"))
        }

        second = enforcer.enforce(apply=True)

        tm.that(second.projects[0].relocation_findings, eq=0)
        for path, source in enforced_sources.items():
            tm.that(path.read_text(encoding="utf-8"), eq=source)

    @staticmethod
    def test_namespace_enforcer_publishes_the_report_receipt(
        tmp_path: Path,
    ) -> None:
        """The command payload publishes the structured receipt under ``.reports``."""
        workspace, _project, _pkg = u.Tests.namespace_workspace(tmp_path)
        u.Tests.provision_checkout(workspace)

        result = FlextInfraNamespaceEnforcer.execute_command(
            m.Infra.RefactorNamespaceEnforceInput(repository_root=workspace),
        )

        tm.that(result.failure, eq=False)
        receipt = (workspace / c.Infra.NAMESPACE_ENFORCE_REPORT_RELATIVE_PATH).resolve()
        tm.that(receipt.exists(), eq=True)
        published = json.loads(receipt.read_text(encoding="utf-8"))
        tm.that(published["workspace"], eq=str(workspace))
        tm.that(published["projects"], empty=False)

    @staticmethod
    def test_namespace_enforcer_report_mode_fails_on_findings_after_publishing(
        tmp_path: Path,
    ) -> None:
        """Remaining relocation findings fail the verdict; the receipt is published.

        A gate fails on every finding it counts: the report pass publishes the
        structured receipt first, then returns the failure naming the
        violations instead of a green verdict carrying them.
        """
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path)
        _ = (pkg / "service.py").write_text(
            "from __future__ import annotations\n"
            "from typing import Protocol\n\n"
            "class ServiceContract(Protocol):\n"
            '    """Service contract awaiting relocation."""\n'
            "\n"
            "    def run(self) -> str:\n"
            '        """Run the contract."""\n'
            "        ...\n",
            encoding="utf-8",
        )
        u.Tests.provision_checkout(workspace)

        result = FlextInfraNamespaceEnforcer.execute_command(
            m.Infra.RefactorNamespaceEnforceInput(repository_root=workspace),
        )

        tm.fail(result, has="Namespace violations found")
        receipt = (workspace / c.Infra.NAMESPACE_ENFORCE_REPORT_RELATIVE_PATH).resolve()
        published = json.loads(receipt.read_text(encoding="utf-8"))
        tm.that(published["projects"][0]["relocation_findings"] > 0, eq=True)
        tm.that(published["has_violations"], eq=True)

    @staticmethod
    def test_namespace_enforcer_leaves_detection_only_findings_to_their_owner(
        tmp_path: Path,
    ) -> None:
        """Detection-only findings are never relocation residue.

        The enforcer owns the rope relocations its rules declare; findings no
        relocation repairs stay with the rule catalog's own gate (``make mod``)
        and never inflate the enforcer's residue.
        """
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path)
        _ = (pkg / "service.py").write_text(
            "from __future__ import annotations\n"
            "import logging\n"
            "from typing import Protocol\n\n"
            "logger = logging.getLogger(__name__)\n\n"
            "class ServiceContract(Protocol):\n"
            '    """Service contract under relocation."""\n'
            "\n"
            "    def run(self) -> str:\n"
            '        """Run the contract."""\n'
            "        ...\n",
            encoding="utf-8",
        )
        u.Tests.provision_checkout(workspace)

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=True,
        )

        tm.that(report.projects[0].relocation_findings, eq=0)
        tm.that((pkg / "protocols.py").exists(), eq=True)

    @staticmethod
    def test_namespace_enforcer_apply_clears_the_pending_relocations(
        tmp_path: Path,
    ) -> None:
        """The apply pass performs the relocations the report pass counted."""
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path)
        _ = (pkg / "service.py").write_text(
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
        u.Tests.provision_checkout(workspace)
        enforcer = FlextInfraNamespaceEnforcer(repository_root=workspace)

        pending = enforcer.enforce(apply=False)
        applied = enforcer.enforce(apply=True)

        tm.that(pending.projects[0].relocation_findings > 0, eq=True)
        tm.that(applied.projects[0].relocation_findings, eq=0)
        tm.that((pkg / "protocols.py").exists(), eq=True)

    @staticmethod
    def test_namespace_enforcer_invalid_declaration_fails_before_any_effect(
        tmp_path: Path,
    ) -> None:
        """An invalid namespace declaration escapes loud; no project is touched.

        Project resolution validates every declaration before the first
        relocation, so the healthy project keeps its source untouched.
        """
        workspace = tmp_path / "workspace"
        _healthy, healthy_pkg = u.Tests.demo_project(workspace, name="healthy-proj")
        _ = (healthy_pkg / "service.py").write_text(
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
        broken, _broken_pkg = u.Tests.demo_project(workspace, name="broken-proj")
        _ = (broken / "pyproject.toml").write_text(
            "[project]\nname='broken-proj'\n\n"
            "[tool.flext.namespace]\nenabled = 'yes'\n",
            encoding="utf-8",
        )
        u.Tests.declare_workspace_projects(workspace, ("healthy-proj", "broken-proj"))
        u.Tests.provision_checkout(workspace)

        with pytest.raises(TypeError, match="must be a boolean"):
            FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(apply=True)

        tm.that((healthy_pkg / "protocols.py").exists(), eq=False)

    @staticmethod
    def test_namespace_enforcer_render_text_reports_the_totals(
        tmp_path: Path,
    ) -> None:
        """The text report carries the aggregate counters the operator reads."""
        workspace, _project, pkg = u.Tests.namespace_workspace(tmp_path)
        _ = (pkg / "service.py").write_text(
            "from __future__ import annotations\n"
            "import logging\n"
            "from typing import Protocol\n\n"
            "logger = logging.getLogger(__name__)\n\n"
            "class ServiceContract(Protocol):\n"
            '    """Service contract under relocation."""\n'
            "\n"
            "    def run(self) -> str:\n"
            '        """Run the contract."""\n'
            "        ...\n",
            encoding="utf-8",
        )
        u.Tests.provision_checkout(workspace)

        report = FlextInfraNamespaceEnforcer(repository_root=workspace).enforce(
            apply=True,
        )
        rendered = FlextInfraNamespaceEnforcer.render_text(report)

        tm.that(rendered, has="Violations: NO")
        tm.that(rendered, has="Relocation findings: 0")
        tm.that(rendered, has=f"Files scanned: {report.projects[0].files_scanned}")
