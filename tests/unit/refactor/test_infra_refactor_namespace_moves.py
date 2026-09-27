"""Tests for refactor namespace-move rewriting."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from tests import m, u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraRefactorInfraRefactorNamespaceMoves:
    """Behavior contract for test_infra_refactor_namespace_moves."""

    @staticmethod
    def _write_file(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

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
            package_root / "__init__.py", "from __future__ import annotations\n"
        )
        return (project_root, package_root)

    def test_rewrite_manual_protocol_violations_uses_public_runtime_api(
        self, tmp_path: Path
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
            violations=[
                m.Infra.ManualProtocolViolation(
                    file=str(source_file), line=5, name="External"
                )
            ],
        )

        tm.that(
            source_file.read_text(encoding="utf-8"), lacks="class External(Protocol):"
        )
        tm.that(
            consumer_file.read_text(encoding="utf-8"),
            has="from demo_pkg.protocols import External",
        )
        protocols_text = protocols_file.read_text(encoding="utf-8")
        tm.that(protocols_text, has="from typing import Protocol")
        tm.that(protocols_text, has="class External(Protocol):")
        tm.that(source_file.with_suffix(".py.bak").exists(), eq=True)
        tm.that(consumer_file.with_suffix(".py.bak").exists(), eq=True)
        tm.that(protocols_file.with_suffix(".py.bak").exists(), eq=True)

    def test_rewrite_manual_typing_alias_violations_uses_public_runtime_api(
        self, tmp_path: Path
    ) -> None:
        project_root, package_root = self._build_project(tmp_path)
        typings_file = package_root / "typings.py"
        source_file = package_root / "service.py"
        self._write_file(
            typings_file, "from __future__ import annotations\n\nTYPE_READY = True\n"
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
            project_root=project_root,
            violations=[
                m.Infra.ManualTypingAliasViolation(
                    file=str(source_file), line=6, name="PayloadMap"
                )
            ],
            parse_failures=[],
        )

        source_text = source_file.read_text(encoding="utf-8")
        typings_text = typings_file.read_text(encoding="utf-8")
        tm.that(source_text, lacks="PayloadMap: TypeAlias = t.StrMapping")
        tm.that(typings_text, has="type PayloadMap = t.StrMapping")
        tm.that(typings_text, lacks="from typing import TypeAlias")
        tm.that(typings_text, has="from flext_core import t")
        tm.that(source_file.with_suffix(".py.bak").exists(), eq=True)
        tm.that(typings_file.with_suffix(".py.bak").exists(), eq=True)

    def test_rewrite_compatibility_alias_violations_uses_public_runtime_api(
        self, tmp_path: Path
    ) -> None:
        _, package_root = self._build_project(tmp_path)
        source_file = package_root / "models.py"
        self._write_file(
            source_file,
            (
                "from __future__ import annotations\n\n"
                "class NewThing:\n"
                "    pass\n\n"
                "LegacyThing = NewThing\n"
                "REGISTRY = [LegacyThing]\n"
            ),
        )

        u.Infra.rewrite_compatibility_alias_violations(
            violations=[
                m.Infra.CompatibilityAliasViolation(
                    file=str(source_file),
                    line=6,
                    alias_name="LegacyThing",
                    target_name="NewThing",
                )
            ],
            parse_failures=[],
        )

        source_text = source_file.read_text(encoding="utf-8")
        tm.that(source_text, lacks="LegacyThing = NewThing")
        tm.that(source_text, has="REGISTRY = [NewThing]")
        tm.that(source_file.with_suffix(".py.bak").exists(), eq=True)

    def test_rewrite_compatibility_alias_violations_migrates_foreign_canonical_alias(
        self, tmp_path: Path
    ) -> None:
        _project_root, package_root = self._build_project(tmp_path)
        source_file = package_root / "service.py"
        self._write_file(
            source_file,
            (
                "from __future__ import annotations\n\n"
                "from flext_core import c, t, r\n\n"
                "VALUE = c.MAX_SIZE\n"
                "def fn(x: t.StrSequence) -> r.Result[str]:\n"
                "    return r.ok(x[0])\n"
            ),
        )

        u.Infra.rewrite_compatibility_alias_violations(
            violations=[
                m.Infra.CompatibilityAliasViolation(
                    file=str(source_file),
                    line=4,
                    alias_name="c",
                    target_name="c",
                    module_name="flext_infra",
                ),
                m.Infra.CompatibilityAliasViolation(
                    file=str(source_file),
                    line=4,
                    alias_name="t",
                    target_name="t",
                    module_name="flext_infra",
                ),
            ],
            parse_failures=[],
        )

        source_text = source_file.read_text(encoding="utf-8")
        tm.that(source_text, lacks="from flext_core import c, t, r")
        tm.that(source_text, has="from flext_infra.constants import c")
        tm.that(source_text, has="from flext_infra.typings import t")
        tm.that(source_text, has="from flext_core import r")
