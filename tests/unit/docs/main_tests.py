"""Public validation-flow tests for the docs CLI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import main as infra_main
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsMain:
    """Public validation-flow tests for the docs CLI."""

    def test_docs_cli_validate_fails_before_generation(self, tmp_path: Path) -> None:
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
            (workspace / "flext-a/.reports/docs/validate-report.md").exists(), eq=True
        )

    def test_docs_cli_generate_apply_rejects_a_second_publication_owner(
        self, tmp_path: Path
    ) -> None:
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))

        tm.that(
            (
                infra_main([
                    "docs",
                    "generate",
                    "--repository-root",
                    str(workspace),
                    "--apply",
                    "--projects",
                    "flext-a",
                ])
                == 2
            ),
            eq=True,
        )
