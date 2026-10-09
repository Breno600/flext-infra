"""CLI contract tests for the centralized validate CLI group.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import main
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraValidateCli:
    """Exercise the public validate CLI entrypoints."""

    @staticmethod
    def test_stub_validate_accepts_all_flag(tmp_path: Path) -> None:
        """Test stub validate accepts all flag."""
        workspace = tmp_path / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)

        tm.that(
            main([
                "validate",
                "stub-validate",
                "--repository-root",
                str(workspace),
                "--all",
            ]),
            eq=0,
        )

    @staticmethod
    def test_stub_validate_help_returns_zero() -> None:
        """Test stub validate help returns zero."""
        tm.that(main(["validate", "stub-validate", "--help"]), eq=0)

    @staticmethod
    def _rule_project(tmp_path: Path, source: str) -> Path:
        """Create a package project whose own catalog declares one rule.

        Returns:
            The resulting ``Path``.

        """
        project = tmp_path / "namespace-contract"
        config_path = project / c.Infra.CODEMOD_CONFIG_RELPATH
        rules = config_path.parent / c.Cli.RULES_DIR_NAME
        rules.mkdir(parents=True)
        package = project / "src" / "namespace_contract"
        package.mkdir(parents=True)
        (project / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "namespace-contract"\nversion = "1.0.0"\n'
            "dependencies = []\n",
            encoding="utf-8",
        )
        u.Tests.copy_tracked_mise_seeds(project)
        config_path.write_text(
            f"ruleDirs: [{c.Cli.RULES_DIR_NAME}]\n",
            encoding="utf-8",
        )
        (rules / "contract.yml").write_text(
            "id: namespace-contract\nlanguage: Python\nseverity: error\n"
            "message: Observed contract\nrule:\n  pattern: first($VALUE)\n",
            encoding="utf-8",
        )
        (package / "__init__.py").write_text(source, encoding="utf-8")
        return project

    def test_namespace_validate_passes_without_findings(self, tmp_path: Path) -> None:
        """Test namespace validate passes on a package without findings.

        An empty source tree is not evidence of conformance: the scan refuses
        it, so the passing case scans one real, rule-clean package module.
        """
        project = self._rule_project(
            tmp_path,
            '"""Namespace contract fixture."""\n\n'
            "from __future__ import annotations\n\nVALUE = 1\n",
        )
        # The consumer cannot select a Mise shim; resolution belongs to Make.
        tm.that((project / c.Infra.MISE_TOML_FILENAME).exists(), eq=False)

        exit_code = main([
            "validate",
            "namespace",
            "--repository-root",
            str(project),
        ])

        tm.that(exit_code, eq=0)

    def test_namespace_validate_exits_nonzero_for_rule_findings(
        self,
        tmp_path: Path,
    ) -> None:
        """Test namespace validate exits nonzero for rule findings."""
        project = self._rule_project(tmp_path, "first(1)\n")

        exit_code = main([
            "validate",
            "namespace",
            "--repository-root",
            str(project),
        ])

        tm.that(exit_code, eq=1)
