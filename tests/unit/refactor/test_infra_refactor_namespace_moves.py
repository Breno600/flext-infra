"""Tests for refactor namespace-move rewriting."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from tests import u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


@pytest.mark.slow
class TestsFlextInfraRefactorInfraRefactorNamespaceMoves:
    """Behavior contract for test_infra_refactor_namespace_moves."""

    @staticmethod
    def _write_file(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    @staticmethod
    def _non_module_files(package_root: Path) -> t.VariadicTuple[str]:
        """Return files the rewrite left beside the package modules."""
        return tuple(
            sorted(
                path.name
                for path in package_root.iterdir()
                if path.is_file() and path.suffix != ".py"
            ),
        )

    @classmethod
    def _build_project(cls, tmp_path: Path) -> t.Pair[Path, Path]:
        project_root = tmp_path / "flext-demo"
        package_root = project_root / "src" / "demo_pkg"
        cls._write_file(
            project_root / "pyproject.toml",
            '[project]\nname = "flext-demo"\nversion = "0.1.0"\n',
        )
        cls._write_file(project_root / "Makefile", "check:\n\t@true\n")
        cls._write_file(
            package_root / "__init__.py", "from __future__ import annotations\n",
        )
        u.Tests.provision_checkout(project_root)
        return (project_root, package_root)

    def test_rewrite_manual_protocol_violations_uses_public_runtime_api(
        self, tmp_path: Path,
    ) -> None:
        project_root, package_root = self._build_project(tmp_path)
        protocols_file = package_root / "protocols.py"
        source_file = package_root / "service.py"
        consumer_file = package_root / "consumer.py"
        self._write_file(
            protocols_file,
            "from __future__ import annotations\n\nclass ExistingProtocol:\n    pass\n",
        )
        self._write_file(
            source_file,
            (
                "from __future__ import annotations\n\n"
                "from typing import Protocol\n\n"
                "class External(Protocol):\n"
                "    def call(self) -> str:\n"
                '        """Return the external value."""\n'
                "        ...\n"
            ),
        )
        self._write_file(
            consumer_file,
            (
                "from __future__ import annotations\n\n"
                "from demo_pkg.service import External\n\n"
                "def use(dep: External) -> External:\n"
                "    return dep\n"
            ),
        )

        u.Infra.rewrite_manual_protocol_violations(
            project_root=project_root,
            py_files=[source_file, consumer_file],
            names_by_file={source_file: {"External"}},
        )

        tm.that(
            source_file.read_text(encoding="utf-8"), lacks="class External(Protocol):",
        )
        tm.that(
            consumer_file.read_text(encoding="utf-8"),
            has="from demo_pkg.protocols import External",
        )
        protocols_text = protocols_file.read_text(encoding="utf-8")
        tm.that(protocols_text, has="from typing import Protocol")
        tm.that(protocols_text, has="class External(Protocol):")
        tm.that(self._non_module_files(package_root), eq=())

    def test_rewrite_manual_typing_alias_violations_uses_public_runtime_api(
        self, tmp_path: Path,
    ) -> None:
        project_root, package_root = self._build_project(tmp_path)
        typings_file = package_root / "typings.py"
        source_file = package_root / "service.py"
        self._write_file(
            typings_file, "from __future__ import annotations\n\nTYPE_READY = True\n",
        )
        self._write_file(
            source_file,
            (
                "from __future__ import annotations\n\n"
                "from collections.abc import Mapping\n"
                "from typing import TypeAlias\n\n"
                "PayloadMap: TypeAlias = t.StrMapping\n"
                "value = 1\n"
            ),
        )

        u.Infra.rewrite_manual_typing_alias_violations(
            project_root=project_root, names_by_file={source_file: {"PayloadMap"}},
        )

        source_text = source_file.read_text(encoding="utf-8")
        typings_text = typings_file.read_text(encoding="utf-8")
        tm.that(source_text, lacks="PayloadMap: TypeAlias = t.StrMapping")
        tm.that(typings_text, has="type PayloadMap = t.StrMapping")
        tm.that(typings_text, lacks="from typing import TypeAlias")
        tm.that(typings_text, has="from flext_core import t")
        tm.that(self._non_module_files(package_root), eq=())
