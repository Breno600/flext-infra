"""Tests for the rope-native syntactic structure boundary."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import c, m, u
from tests import t


class TestsFlextInfraRopeStructure:
    """Behavior contract for the LogicalLineFinder-backed structure boundary."""

    _SOURCE = (
        "from typing import ClassVar, TYPE_CHECKING\n"
        "import importlib\n"
        "if TYPE_CHECKING:\n"
        "    from foo import Bar\n"
        "type MyAlias = int\n"
        "class Widget:\n"
        "    CONST: ClassVar[int] = 1\n"
        "    plain = 2\n"
        "    def method(self):\n"
        "        import os\n"
        "        return os\n"
    )
    _MULTILINE_IMPORT = (
        "from package.private import (  # inline explanation\n    ExportedName,\n)\n"
    )

    def test_first_party_namespaces_require_live_python_sources(
        self, tmp_path: Path
    ) -> None:
        src = tmp_path / c.Infra.DEFAULT_SRC_DIR
        for name in ("empty", "cache_only", "regular", "namespace", "stubs"):
            (src / name).mkdir(parents=True)
        for relative in (
            "cache_only/__pycache__/removed.pyc",
            "cache_only/__pycache__/removed.py",
            "regular/__init__.py",
            "namespace/nested/module.py",
            "stubs/module.pyi",
            "invalid-name/module.py",
        ):
            path = src / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("value: int\n", encoding="utf-8")

        tm.that(
            u.Infra.discover_first_party_namespaces(tmp_path),
            eq=["namespace", "regular", "stubs"],
        )

    def _by_line(self) -> t.MutableMappingKV[int, m.Infra.LogicalStatement]:
        return {s.line: s for s in u.Infra.logical_statements(self._SOURCE)}

    def test_reports_real_statement_lines_not_target_module_lines(self) -> None:
        by_line = self._by_line()

        inline_import = by_line[10]

        tm.that(inline_import.category, eq=c.Infra.StatementCategory.IMPORT)
        tm.that(inline_import.text.strip(), eq="import os")

    def test_categorizes_pep695_type_alias(self) -> None:
        by_line = self._by_line()

        tm.that(by_line[5].category, eq=c.Infra.StatementCategory.TYPE_ALIAS)

    def test_categorizes_parenthesized_docstring_as_inert(self) -> None:
        source = (
            "class Wrapper:\n"
            '    """Facade (with parentheses) in the prose."""\n'
            "\n"
            "    Member: ClassVar[int] = 1\n"
        )
        statements = {s.line: s for s in u.Infra.logical_statements(source)}

        tm.that(statements[2].category, eq=c.Infra.StatementCategory.OTHER)
        tm.that(statements[4].category, eq=c.Infra.StatementCategory.ANN_ASSIGN)

    def test_categorizes_type_checking_guard(self) -> None:
        by_line = self._by_line()

        tm.that(by_line[3].category, eq=c.Infra.StatementCategory.IF_GUARD)

    def test_tracks_enclosing_class_for_classvar(self) -> None:
        by_line = self._by_line()

        classvar = by_line[7]

        tm.that(classvar.category, eq=c.Infra.StatementCategory.ANN_ASSIGN)
        tm.that(classvar.enclosing_kind, eq=c.Infra.RopeScopeKind.CLASS)
        tm.that(classvar.enclosing_name, eq="Widget")

    def test_tracks_enclosing_function_for_inline_import(self) -> None:
        by_line = self._by_line()

        inline_import = by_line[10]

        tm.that(inline_import.enclosing_kind, eq=c.Infra.RopeScopeKind.FUNCTION)
        tm.that(inline_import.enclosing_name, eq="method")

    def test_module_level_statement_has_module_encloser(self) -> None:
        by_line = self._by_line()

        tm.that(by_line[2].enclosing_kind, eq=c.Infra.RopeScopeKind.MODULE)

    def test_empty_source_returns_no_statements(self) -> None:
        tm.that(u.Infra.logical_statements(""), eq=())

    def test_preserves_newlines_in_multiline_statement(self) -> None:
        statements = u.Infra.logical_statements(self._MULTILINE_IMPORT)

        tm.that(statements[0].text, eq=self._MULTILINE_IMPORT.rstrip("\n"))
        tm.that(statements[0].category, eq=c.Infra.StatementCategory.FROM_IMPORT)
