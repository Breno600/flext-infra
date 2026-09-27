"""Behavior tests for FlextInfraDocServer — single-scope serve selection.

Real workspace fixtures only (no mocks): the serve phase resolves governed
scopes, keeps the ones carrying an ``mkdocs.yml``, and refuses ambiguous
multi-scope previews — the blocking dev-server call itself is covered by the
integration suite (tests/integration/docs_serve_e2e_tests.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import u
from flext_infra.docs.server import FlextInfraDocServer
from tests import c, m, u as tu

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocServer:
    """FlextInfraDocServer public-behavior tests (unit under test: docs serve)."""

    def _write_mkdocs_yml(self, scope_path: Path) -> None:
        (scope_path / "mkdocs.yml").write_text(
            "site_name: Demo\ndocs_dir: docs\n", encoding="utf-8"
        )

    # Why: flattened nested TestScopeSelection/TestRequestDefaults/TestServeUtility
    # sibling classes into this outer class — a nested class does not inherit the
    # outer one, so calling _write_mkdocs_yml via a throwaway instance was external
    # private-member access (ruff SLF001).
    def test_serve_without_mkdocs_yml_fails_with_guidance(self, tmp_path: Path) -> None:
        """Scope resolution governs which site a blocking preview may serve."""
        workspace = tu.Tests.create_docs_workspace(tmp_path)

        result = FlextInfraDocServer().serve(workspace)

        tm.fail(result)
        tm.that((result.error or ""), has="mkdocs.yml")
        tm.that((result.error or ""), has="docs generate")

    def test_serve_with_multiple_servable_scopes_requires_project(
        self, tmp_path: Path
    ) -> None:
        workspace = tu.Tests.create_docs_workspace(
            tmp_path, project_names=("flext-a", "flext-b")
        )
        self._write_mkdocs_yml(workspace)
        self._write_mkdocs_yml(workspace / "flext-a")

        result = FlextInfraDocServer().serve(workspace)

        tm.fail(result)
        tm.that((result.error or ""), has="--project")
        tm.that((result.error or ""), has="flext-a")

    def test_execute_propagates_selection_failure(self, tmp_path: Path) -> None:
        workspace = tu.Tests.create_docs_workspace(tmp_path)

        result = FlextInfraDocServer(repository_root=workspace).execute()

        tm.fail(result)

    def test_default_bind_address_is_localhost(self) -> None:
        """The public request model ships production-safe serve defaults."""
        server = FlextInfraDocServer()
        tm.that(server.dev_addr, eq="127.0.0.1:8000")
        tm.that(server.livereload, eq=True)
        tm.that(server.strict, eq=True)

    def test_output_dir_default_matches_docs_pipeline(self) -> None:
        server = FlextInfraDocServer()
        tm.that(str(server.output_dir), eq=c.Infra.DEFAULT_DOCS_OUTPUT_DIR)

    def test_serve_scope_without_mkdocs_yml_returns_failure(
        self, tmp_path: Path
    ) -> None:
        """u.Infra.docs_serve_mkdocs fails loud without mkdocs.yml."""
        scope = m.Infra.DocScope(
            name="flext-demo", path=tmp_path, report_dir=tmp_path / ".reports/docs"
        )

        report = u.Infra.docs_serve_mkdocs(
            scope, dev_addr="127.0.0.1:18000", livereload=False, strict=True
        )

        tm.that(report.phase, eq="serve")
        tm.that(report.result, eq=c.Infra.ResultStatus.FAIL)
        tm.that(report.passed, eq=False)
