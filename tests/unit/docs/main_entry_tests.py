"""Public CLI routing tests for docs commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import docs_main, main as infra_main
from tests import u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraDocsMainEntry:
    """Verify docs commands through their public CLI entry points."""

    @staticmethod
    def _workspace(tmp_path: Path, *, fixable: bool = False) -> Path:
        workspace: Path = u.Tests.create_docs_workspace(
            tmp_path, project_names=("flext-a", "flext-b"), include_fixable_link=fixable
        )
        return workspace

    def test_requires_subcommand(self) -> None:
        """Return the usage exit code when docs has no subcommand."""
        tm.that(infra_main(["docs"]), eq=1)

    @pytest.mark.parametrize(
        "argv",
        [
            ["docs", "--help"],
            ["docs", "audit", "--help"],
            ["docs", "build", "--help"],
            ["docs", "fix", "--help"],
            ["docs", "generate", "--help"],
            ["docs", "serve", "--help"],
            ["docs", "validate", "--help"],
        ],
    )
    def test_help_routes(self, argv: t.SequenceOf[str]) -> None:
        """Expose help successfully for every public docs route."""
        tm.that(infra_main(argv), eq=0)

    def test_package_entrypoint_routes_through_docs_group(self) -> None:
        """Route the package entry point through the public docs command group."""
        tm.that(docs_main(["--help"]), eq=0)
        tm.that(docs_main(["audit", "--help"]), eq=0)
        tm.that(docs_main([]), eq=1)

    def test_audit_projects_filter_writes_selected_reports(
        self, tmp_path: Path
    ) -> None:
        """Keep custom relative reports under each explicitly selected project."""
        workspace = self._workspace(tmp_path)
        output_dir = tmp_path.name

        tm.that(
            infra_main([
                "docs",
                "audit",
                "--repository-root",
                str(workspace),
                "--output-dir",
                output_dir,
                "--projects",
                "flext-a",
            ]),
            eq=0,
        )
        tm.that((workspace / output_dir / "audit-report.md").exists(), eq=True)
        tm.that(
            (workspace / "flext-a" / output_dir / "audit-report.md").exists(), eq=True
        )
        tm.that(
            (workspace / "flext-b" / output_dir / "audit-report.md").exists(), eq=False
        )

    def test_fix_uses_public_route(self, tmp_path: Path) -> None:
        """Run fix through its public command route."""
        workspace = self._workspace(tmp_path, fixable=True)

        tm.that(
            infra_main(["docs", "fix", "--repository-root", str(workspace), "--apply"]),
            eq=0,
        )
        tm.that((workspace / "docs/README.md").read_text(), has="guides/setup.md")

    def test_generate_apply_rejects_publication_outside_conform(
        self, tmp_path: Path
    ) -> None:
        """Reject direct publication because conform owns the transaction."""
        workspace = self._workspace(tmp_path)

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
            eq=2,
        )
        tm.that((workspace / ".reports/docs/generate-report.md").exists(), eq=False)
        tm.that(
            (workspace / "flext-a/.reports/docs/generate-report.md").exists(), eq=False
        )
        tm.that(
            (workspace / "flext-b/.reports/docs/generate-report.md").exists(), eq=False
        )

    def test_build_uses_public_route(self, tmp_path: Path) -> None:
        """Run build through its public command route."""
        build_workspace = u.Tests.create_docs_workspace(tmp_path / "build-root")
        (build_workspace / "mkdocs.yml").write_text(
            "site_name: FLEXT docs\ndocs_dir: docs\nexclude_docs: |\n  README.md\n",
            encoding="utf-8",
        )
        tm.that(
            infra_main(["docs", "build", "--repository-root", str(build_workspace)]),
            eq=0,
        )
        tm.that((build_workspace / ".reports/docs/build-report.md").exists(), eq=True)
