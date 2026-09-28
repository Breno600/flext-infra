"""Regression tests for stale-symbol docs auditing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from tests import m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraAuditorStaleSymbols:
    """Regression tests for stale-symbol docs auditing."""

    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_demo_pyproject(self, root: Path) -> None:
        """Declare the demo distribution the public-contract reader resolves."""
        self._write(
            root / "pyproject.toml",
            (
                "[project]\n"
                'name = "demo-pkg"\n'
                'version = "0.1.0"\n'
                'description = "Demo public exports project"\n'
            ),
        )

    def _write_demo_facade(self, package_root: Path) -> None:
        """Publish one documented concrete symbol through a re-exporting facade."""
        self._write(
            package_root / "facade.py",
            (
                '"""Demo public facade."""\n\n'
                "from demo_pkg._internal import LiveSymbol\n\n"
                '__all__: list[str] = ["LiveSymbol"]\n'
            ),
        )
        self._write(
            package_root / "_internal.py",
            (
                '"""Demo internal implementation."""\n\n'
                "class LiveSymbol:\n"
                '    """Concrete public symbol docs."""\n'
            ),
        )

    def _stale_symbol_scope(self, tmp_path: Path) -> m.Infra.DocScope:
        workspace = tmp_path / "workspace"
        project = workspace / "flext-demo"
        package_root = project / "src" / "flext_demo"
        self._write(
            workspace / "docs" / "docs_config.json",
            (
                "{\n"
                '  "audit": {\n'
                '    "stale_symbols": ["LiveSymbol", "DeadSymbol"],\n'
                '    "stale_symbol_exempt_paths": []\n'
                "  }\n"
                "}\n"
            ),
        )
        self._write(
            project / "pyproject.toml",
            (
                "[project]\n"
                'name = "flext-demo"\n'
                'version = "0.1.0"\n'
                'description = "Demo docs audit project"\n'
            ),
        )
        self._write(
            package_root / "__init__.py",
            (
                '"""Demo package for stale-symbol docs tests."""\n\n'
                "class LiveSymbol:\n"
                '    """Exported live symbol."""\n\n'
                '__all__ = ["LiveSymbol"]\n'
            ),
        )
        return m.Infra.DocScope(
            name="flext-demo",
            path=project,
            report_dir=project / ".reports" / "docs",
            package_name="flext_demo",
            # Why: `docs_config.json` above lives at the workspace root, not
            # under `project` — this is a genuine member-project scope.
            repository_root_override=workspace,
        )

    def test_generated_api_reference_accepts_live_public_symbol(
        self, tmp_path: Path
    ) -> None:
        scope = self._stale_symbol_scope(tmp_path)
        self._write(
            scope.path / "docs" / "api-reference" / "generated" / "overview.md",
            "# API\n\nPublic symbol exports: `LiveSymbol`\n",
        )

        issues = u.Infra.docs_stale_symbol_issues(scope)

        tm.that(issues, eq=[])

    def test_generated_api_reference_reports_missing_public_symbol(
        self, tmp_path: Path
    ) -> None:
        scope = self._stale_symbol_scope(tmp_path)
        self._write(
            scope.path / "docs" / "api-reference" / "generated" / "overview.md",
            "# API\n\nPublic symbol exports: `DeadSymbol`\n",
        )

        issues = u.Infra.docs_stale_symbol_issues(scope)

        tm.that(len(issues), eq=1)
        tm.that(issues[0].issue_type, eq="stale_symbol")
        tm.that(issues[0].message, eq="contains `DeadSymbol`")

    def test_manual_docs_report_live_symbol_mentions(self, tmp_path: Path) -> None:
        scope = self._stale_symbol_scope(tmp_path)
        self._write(
            scope.path / "docs" / "guides" / "manual.md",
            "# Manual\n\nDo not mention LiveSymbol in curated prose.\n",
        )

        issues = u.Infra.docs_stale_symbol_issues(scope)

        tm.that(len(issues), eq=1)
        tm.that(issues[0].file, eq="docs/guides/manual.md")
        tm.that(issues[0].message, eq="contains `LiveSymbol`")

    def test_public_contract_resolves_local_tuple_public_exports(
        self, tmp_path: Path
    ) -> None:
        """Generated ABI ``__all__ = tuple(_PUBLIC_EXPORTS)`` must yield a contract."""
        package_root = tmp_path / "src" / "demo_pkg"
        self._write(
            tmp_path / "pyproject.toml",
            (
                "[project]\n"
                'name = "demo-pkg"\n'
                'version = "0.1.0"\n'
                'description = "Demo local public exports project"\n'
            ),
        )
        self._write(
            package_root / "__init__.py",
            (
                '"""Demo package."""\n\n'
                "from typing import TYPE_CHECKING\n\n"
                "from flext_core.lazy import build_lazy_import_map, install_lazy_exports\n\n"
                "if TYPE_CHECKING:\n"
                "    from demo_pkg.facade import LiveSymbol as LiveSymbol\n\n"
                "_LAZY_MODULES: dict[str, t.VariadicTuple[str]] = {\n"
                '    ".facade": ("LiveSymbol",),\n'
                "}\n\n"
                "_LAZY_IMPORTS = build_lazy_import_map(_LAZY_MODULES, sort_keys=False)\n\n"
                '_PUBLIC_EXPORTS: t.VariadicTuple[str] = ("LiveSymbol",)\n'
                "__all__: t.VariadicTuple[str] = tuple(_PUBLIC_EXPORTS)\n\n"
                "install_lazy_exports(\n"
                "    __name__,\n"
                "    globals(),\n"
                "    _LAZY_IMPORTS,\n"
                "    public_exports=__all__,\n"
                ")\n"
            ),
        )
        self._write(
            package_root / "facade.py",
            (
                '"""Demo public facade."""\n\n'
                "class LiveSymbol:\n"
                '    """Concrete public symbol docs."""\n'
            ),
        )

        contract = u.Infra.public_contract(tmp_path, "demo_pkg")
        exports = contract["exports"]
        tm.that(exports, is_=list)
        tm.that(exports, has="LiveSymbol")
        tm.that(bool(exports), eq=True)

    def test_public_contract_resolves_imported_lazy_public_exports(
        self, tmp_path: Path
    ) -> None:
        package_root = tmp_path / "src" / "demo_pkg"
        self._write_demo_pyproject(tmp_path)
        self._write(
            package_root / "__init__.py",
            (
                '"""Demo package."""\n\n'
                "from typing import TYPE_CHECKING\n\n"
                "from demo_pkg._exports import DEMO_PUBLIC_EXPORTS\n"
                "from flext_core.lazy import install_lazy_exports\n\n"
                "if TYPE_CHECKING:\n"
                "    from demo_pkg.facade import LiveSymbol as LiveSymbol\n\n"
                "install_lazy_exports(\n"
                "    __name__,\n"
                "    globals(),\n"
                "    {},\n"
                "    public_exports=DEMO_PUBLIC_EXPORTS,\n"
                ")\n"
            ),
        )
        self._write_demo_facade(package_root)
        self._write(
            package_root / "_exports.py",
            (
                '"""Demo export registry."""\n\n'
                "from demo_pkg._exports_parts.all_names import DEMO_PUBLIC_EXPORTS\n"
            ),
        )
        self._write(
            package_root / "_exports_parts" / "all_names.py",
            (
                '"""Demo public export names."""\n\n'
                'DEMO_PUBLIC_EXPORTS: t.VariadicTuple[str] = ("LiveSymbol",)\n'
            ),
        )

        contract = u.Infra.public_contract(tmp_path, "demo_pkg")
        exports = contract["exports"]
        public_symbols = contract["public_symbols"]

        tm.that(exports, is_=list)
        tm.that(public_symbols, is_=list)
        tm.that(exports, has="LiveSymbol")
        tm.that(public_symbols, has="LiveSymbol")

        issues = u.Infra.docstring_issues(tmp_path, contract)

        tm.that(issues, eq=[])

    def test_public_contract_resolves_imported_lazy_import_map(
        self, tmp_path: Path
    ) -> None:
        package_root = tmp_path / "src" / "demo_pkg"
        self._write_demo_pyproject(tmp_path)
        self._write(
            package_root / "__init__.py",
            (
                '"""Demo package."""\n\n'
                "from demo_pkg._exports import DEMO_LAZY_IMPORTS, DEMO_PUBLIC_EXPORTS\n"
                "from flext_core.lazy import install_lazy_exports\n\n"
                "install_lazy_exports(\n"
                "    __name__,\n"
                "    globals(),\n"
                "    DEMO_LAZY_IMPORTS,\n"
                "    public_exports=DEMO_PUBLIC_EXPORTS,\n"
                ")\n"
            ),
        )
        self._write(
            package_root / "_exports.py",
            (
                '"""Demo export registry."""\n\n'
                "from demo_pkg._exports_part import DEMO_LAZY_IMPORTS_PART\n\n"
                "DEMO_LAZY_IMPORTS = {**DEMO_LAZY_IMPORTS_PART}\n"
                'DEMO_PUBLIC_EXPORTS: t.VariadicTuple[str] = ("LiveSymbol",)\n'
            ),
        )
        self._write(
            package_root / "_exports_part.py",
            (
                '"""Demo export registry part."""\n\n'
                "from flext_core.lazy import build_lazy_import_map\n\n"
                "DEMO_LAZY_IMPORTS_PART = build_lazy_import_map(\n"
                "    {'.facade': ('LiveSymbol',)},\n"
                ")\n"
            ),
        )
        self._write_demo_facade(package_root)

        contract = u.Infra.public_contract(tmp_path, "demo_pkg")

        tm.that(contract["target_map"], eq={"LiveSymbol": "demo_pkg.facade"})
        tm.that(u.Infra.docstring_issues(tmp_path, contract), eq=[])

    def test_docstring_issues_accepts_direct_part_flext_docstring(
        self, tmp_path: Path
    ) -> None:
        package_root = tmp_path / "src" / "demo_pkg"
        self._write_demo_pyproject(tmp_path)
        self._write(
            package_root / "__init__.py",
            (
                '"""Demo package."""\n\n'
                "from demo_pkg.part_02 import LiveSymbol\n\n"
                '__all__ = ["LiveSymbol"]\n'
            ),
        )
        self._write(
            package_root / "part_01.py",
            (
                '"""Demo base part."""\n\n'
                "class LiveSymbol:\n"
                '    """Canonical public symbol docs."""\n'
            ),
        )
        self._write(
            package_root / "part_02.py",
            (
                '"""Demo final part."""\n\n'
                "from demo_pkg.part_01 import LiveSymbol as LiveSymbolPart01\n\n"
                "class LiveSymbol(LiveSymbolPart01):\n"
                "    pass\n"
            ),
        )

        contract = u.Infra.public_contract(tmp_path, "demo_pkg")
        issues = u.Infra.docstring_issues(tmp_path, contract)

        tm.that(issues, eq=[])
