"""Public validation-flow tests for the docs CLI.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import main as infra_main
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsMain:
    """Public validation-flow tests for the docs CLI."""

    @staticmethod
    def test_docs_cli_validate_fails_before_generation(tmp_path: Path) -> None:
        """Test docs cli validate fails before generation."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))

        tm.that(
            (
                infra_main([
                    "docs",
                    "validate",
                    "--repository-root",
                    str(workspace),
                    "--projects",
                    "flext-a",
                ])
                == 1
            ),
            eq=True,
        )
        tm.that((workspace / ".reports/docs/validate-report.md").exists(), eq=True)
        tm.that(
            (workspace / "flext-a/.reports/docs/validate-report.md").exists(),
            eq=True,
        )

    @staticmethod
    def test_docs_cli_generate_apply_rejects_a_second_publication_owner(
        tmp_path: Path,
    ) -> None:
        """Test docs cli generate apply rejects a second publication owner."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))

        tm.that(
            infra_main([
                "docs",
                "generate",
                "--repository-root",
                str(workspace),
                "--apply",
                "--projects",
                "flext-a",
            ]),
            eq=c.Infra.ScriptExitCode.USAGE,
        )
