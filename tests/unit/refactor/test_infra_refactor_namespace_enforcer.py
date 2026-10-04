"""Unit tests for the namespace enforcer's rule-catalog relocations.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

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
            "    def run(self) -> str:\n"
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
            "    def run(self) -> str:\n"
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
