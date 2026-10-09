"""Public utility evidence for the facade-base semantic cutover.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, infra, m, p, t, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraFacadeBaseCutover:
    """Exercise the facade-base phase only through ``u.Infra``."""

    PARENT_CLASS = "ParentDeclaredModelFacade"
    OTHER_CLASS = "OtherDeclaredModelFacade"

    @staticmethod
    def _lazy_publication(submodule: str, *names: str) -> str:
        """Render the lazy publication a generated package ``__init__`` carries.

        Generated initializers publish every name through one
        ``install_lazy_exports(__name__, globals(), MappingProxyType({...}))``
        call mapping each name to its provider submodule.

        Returns:
            The publication statements for ``names``.

        """
        entries = "".join(f'        "{name}": "{submodule}",\n' for name in names)
        return (
            "from types import MappingProxyType\n"
            "from flext_core.lazy import install_lazy_exports\n"
            "install_lazy_exports(\n"
            "    __name__,\n"
            "    globals(),\n"
            "    MappingProxyType({\n"
            f"{entries}"
            "    }),\n"
            ")\n"
        )

    @pytest.mark.parametrize(
        ("statement", "base", "rebind"),
        [
            ("from parent_pkg import m", "m", "m = ChildModels"),
            (
                "from parent_pkg import m as _parent_m",
                "_parent_m",
                "m: type[ChildModels] = ChildModels",
            ),
        ],
    )
    def test_rebound_letter_base_extends_the_declared_class(
        self,
        tmp_path: Path,
        statement: str,
        base: str,
        rebind: str,
    ) -> None:
        """Test rebound letter base extends the declared class."""
        child, sources = self._workspace(
            tmp_path,
            f"{statement}\n\n\nclass ChildModels({base}):\n    pass\n\n\n{rebind}\n",
        )
        edits = self._edits(tmp_path, sources, child)
        tm.that(tuple(edit.file_path for edit in edits), eq=(child.resolve(),))
        updated = edits[0].updated_source
        tm.that(updated, has=f"from parent_pkg import {self.PARENT_CLASS}\n")
        tm.that(updated, has=f"class ChildModels({self.PARENT_CLASS}):")
        tm.that(updated, has="\nm = ChildModels\n")
        tm.that(updated, lacks="import m")
        tm.that(updated, lacks="type[ChildModels]")
        replanned = self._edits(tmp_path, {**sources, child: updated}, child)
        tm.that(replanned, empty=True)

    def test_eager_letter_reads_spell_the_parent_class(self, tmp_path: Path) -> None:
        """Test eager letter reads spell the parent class."""
        child, sources = self._workspace(
            tmp_path,
            "from parent_pkg import m\n\n\nclass ChildModels(m):\n"
            "    base = m.BaseModel\n\n"
            "    def later(self) -> object:\n        return m.BaseModel\n\n\n"
            "m = ChildModels\n",
        )
        updated = self._edits(tmp_path, sources, child)[0].updated_source
        tm.that(updated, has=f"    base = {self.PARENT_CLASS}.BaseModel\n")
        tm.that(updated, has="        return m.BaseModel\n")

    def test_every_letter_base_of_a_composed_facade_extends_its_own_parent(
        self,
        tmp_path: Path,
    ) -> None:
        """A facade composing two parents by letter rewires each to its class."""
        child, sources = self._workspace(
            tmp_path,
            "from other_pkg import m as other_m\nfrom parent_pkg import m\n\n\n"
            "class ChildModels(m, other_m):\n    base = m.BaseModel\n"
            "    other = other_m.BaseModel\n\n\nm = ChildModels\n",
        )
        other = tmp_path / "other/src/other_pkg"
        sources[other / "__init__.py"] = (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            f"    from .models import {self.OTHER_CLASS}, m\n"
            f"{self._lazy_publication('.models', self.OTHER_CLASS, 'm')}"
            f"__all__ = [{self.OTHER_CLASS!r}, 'm']\n"
        )
        sources[other / "models.py"] = (
            "from base_pkg import m\n"
            f"class {self.OTHER_CLASS}(m):\n    pass\n"
            f"m = {self.OTHER_CLASS}\n"
            f"__all__ = [{self.OTHER_CLASS!r}, 'm']\n"
        )
        edits = self._edits(tmp_path, sources, child)
        tm.that(tuple(edit.file_path for edit in edits), eq=(child.resolve(),))
        updated = edits[0].updated_source
        tm.that(updated, has=f"from other_pkg import {self.OTHER_CLASS}\n")
        tm.that(updated, has=f"from parent_pkg import {self.PARENT_CLASS}\n")
        tm.that(
            updated,
            has=f"class ChildModels({self.PARENT_CLASS}, {self.OTHER_CLASS}):",
        )
        tm.that(updated, has=f"    base = {self.PARENT_CLASS}.BaseModel\n")
        tm.that(updated, has=f"    other = {self.OTHER_CLASS}.BaseModel\n")
        tm.that(updated, has="\nm = ChildModels\n")
        tm.that(updated, lacks="other_m")
        tm.that(updated, lacks="import m\n")
        tm.that(
            edits[0].changes,
            eq=(
                f"extended other_pkg.{self.OTHER_CLASS} in ChildModels",
                f"extended parent_pkg.{self.PARENT_CLASS} in ChildModels",
            ),
        )
        replanned = self._edits(tmp_path, {**sources, child: updated}, child)
        tm.that(replanned, empty=True)

    def test_letter_base_without_rebind_is_untouched(self, tmp_path: Path) -> None:
        """Test letter base without rebind is untouched."""
        child, sources = self._workspace(
            tmp_path,
            "from parent_pkg import m\n\n\nclass ChildService(m):\n    pass\n",
        )
        tm.that(self._edits(tmp_path, sources, child), empty=True)

    def test_undeclared_letter_owner_fails_the_plan(self, tmp_path: Path) -> None:
        """Test undeclared letter owner fails the plan."""
        child, sources = self._workspace(
            tmp_path,
            "from parent_pkg import m\n\n\nclass ChildModels(m):\n    pass\n\n\n"
            "m = ChildModels\n",
            parent_exports=(self.PARENT_CLASS,),
        )
        tm.fail(self._plan(tmp_path, sources, child), has="is not declared")

    def test_facade_classes_derive_every_published_letter(
        self,
        tmp_path: Path,
        installed_dependency_path: Path,
    ) -> None:
        """Test facade classes derive every published letter."""
        _child, sources = self._workspace(tmp_path, "")
        for path, source in sources.items():
            if "parent_pkg" in path.parts:
                relative = path.relative_to(tmp_path / "parent/src")
                target = installed_dependency_path / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source, encoding="utf-8")
        tm.that(u.Infra.facade_classes("parent_pkg"), eq={"m": self.PARENT_CLASS})

    def test_composite_facade_cuts_over_every_letter(self, tmp_path: Path) -> None:
        """A facade binding several parent letters cuts over all of them."""
        parent = tmp_path / "parent/src/parent_pkg"
        second = tmp_path / "second/src/second_pkg"
        child = tmp_path / "child/src/child_pkg/protocols.py"
        second_publication = self._lazy_publication(
            ".protocols",
            "SecondDeclaredProtocols",
            "p",
        )
        sources = {
            parent / "__init__.py": (
                "from typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n"
                f"    from .models import {self.PARENT_CLASS}, m\n"
                f"{self._lazy_publication('.models', self.PARENT_CLASS, 'm')}"
                f"__all__ = [{self.PARENT_CLASS!r}, 'm']\n"
            ),
            parent / "models.py": (
                "from base_pkg import m\n"
                f"class {self.PARENT_CLASS}(m):\n    pass\n"
                f"m = {self.PARENT_CLASS}\n"
                f"__all__ = [{self.PARENT_CLASS!r}, 'm']\n"
            ),
            second / "__init__.py": (
                "from typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n"
                "    from .protocols import SecondDeclaredProtocols, p\n"
                f"{second_publication}"
                "__all__ = ['SecondDeclaredProtocols', 'p']\n"
            ),
            second / "protocols.py": (
                "class SecondDeclaredProtocols:\n    pass\n"
                "p = SecondDeclaredProtocols\n"
                "__all__ = ['SecondDeclaredProtocols', 'p']\n"
            ),
            child: (
                "from parent_pkg import m\n"
                "from second_pkg import p\n\n\n"
                "class ChildProtocols(m, p):\n    pass\n\n\n"
                "m = ChildProtocols\n"
                "p = ChildProtocols\n"
                "__all__ = ['ChildProtocols', 'm', 'p']\n"
            ),
        }

        updated = self._edits(tmp_path, sources, child)[0].updated_source

        tm.that(
            updated,
            has=f"class ChildProtocols({self.PARENT_CLASS}, SecondDeclaredProtocols):",
        )
        tm.that(updated, has=f"from parent_pkg import {self.PARENT_CLASS}\n")
        tm.that(updated, has="from second_pkg import SecondDeclaredProtocols\n")

    def test_lazy_published_letter_resolves_the_declared_class(
        self,
        tmp_path: Path,
    ) -> None:
        """A letter published only through the generated lazy map resolves.

        The package binds the letter nowhere else (no TYPE_CHECKING import):
        the ``install_lazy_exports`` publication alone names its provider.
        """
        parent = tmp_path / "parent/src/parent_pkg"
        child = tmp_path / "child/src/child_pkg/models.py"
        sources = {
            parent / "__init__.py": (
                f"__all__ = [{self.PARENT_CLASS!r}, 'm']\n"
                f"{self._lazy_publication('.models', self.PARENT_CLASS, 'm')}"
            ),
            parent / "models.py": (
                "from base_pkg import m\n"
                f"class {self.PARENT_CLASS}(m):\n    pass\n"
                f"m = {self.PARENT_CLASS}\n"
                f"__all__ = [{self.PARENT_CLASS!r}, 'm']\n"
            ),
            child: (
                "from parent_pkg import m\n\n\n"
                "class ChildModels(m):\n    pass\n\n\n"
                "m = ChildModels\n"
            ),
        }

        updated = self._edits(tmp_path, sources, child)[0].updated_source

        tm.that(updated, has=f"class ChildModels({self.PARENT_CLASS}):")

    def test_annotation_without_value_preserves_the_bound_facade(
        self,
        tmp_path: Path,
    ) -> None:
        """A later annotation leaves an existing Python name binding intact."""
        child, sources = self._workspace(
            tmp_path,
            "from parent_pkg import m\n\nclass ChildModels(m):\n    pass\n"
            "m = ChildModels\n",
        )
        parent = tmp_path / "parent/src/parent_pkg/models.py"
        sources[parent] += f"m: type[{self.PARENT_CLASS}]\n"

        updated = self._edits(tmp_path, sources, child)[0].updated_source

        tm.that(updated, has=f"class ChildModels({self.PARENT_CLASS}):")

    @pytest.mark.parametrize(
        ("guard_import", "guard"),
        [
            ("from typing import TYPE_CHECKING", "TYPE_CHECKING"),
            ("import typing", "typing.TYPE_CHECKING"),
            ("import typing_extensions", "typing_extensions.TYPE_CHECKING"),
        ],
    )
    def test_type_only_self_import_does_not_override_lazy_publication(
        self,
        tmp_path: Path,
        installed_dependency_path: Path,
        guard_import: str,
        guard: str,
    ) -> None:
        """Static self-imports do not create runtime facade binding cycles."""
        _child, sources = self._workspace(tmp_path, "")
        parent = tmp_path / "parent/src/parent_pkg"
        sources[parent / "__init__.py"] = (
            f"{guard_import}\n"
            f"{self._lazy_publication('.models', self.PARENT_CLASS, 'm')}"
            f"if {guard}:\n"
            f"    from parent_pkg import {self.PARENT_CLASS}, m\n"
            f"__all__ = [{self.PARENT_CLASS!r}, 'm']\n"
        )
        for path, source in sources.items():
            if "parent_pkg" in path.parts:
                target = installed_dependency_path / path.relative_to(
                    tmp_path / "parent/src",
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source, encoding="utf-8")

        tm.that(u.Infra.facade_classes("parent_pkg"), eq={"m": self.PARENT_CLASS})

    @pytest.mark.parametrize(
        "runtime_binding",
        [
            "from .models import {owner}, m\n",
            "class {owner}:\n    pass\nm = {owner}\n",
            "from .models import {owner}\nm: type[{owner}] = {owner}\n",
        ],
    )
    def test_type_checking_else_preserves_runtime_class_bindings(
        self,
        tmp_path: Path,
        runtime_binding: str,
    ) -> None:
        """Only the runtime else arm supplies imports, classes, and aliases."""
        child, sources = self._workspace(
            tmp_path,
            "from parent_pkg import m\nclass ChildModels(m):\n    pass\n"
            "m = ChildModels\n",
        )
        runtime = runtime_binding.format(owner=self.PARENT_CLASS)
        sources[tmp_path / "parent/src/parent_pkg/__init__.py"] = (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            f"    from parent_pkg import {self.PARENT_CLASS}, m\n"
            "else:\n"
            + "".join(f"    {line}\n" for line in runtime.splitlines())
            + f"__all__ = [{self.PARENT_CLASS!r}, 'm']\n"
        )

        updated = self._edits(tmp_path, sources, child)[0].updated_source

        tm.that(updated, has=f"class ChildModels({self.PARENT_CLASS}):")

    @pytest.mark.parametrize("after_lazy_map", [False, True])
    def test_runtime_self_import_still_fails_with_lazy_publication(
        self,
        tmp_path: Path,
        *,
        after_lazy_map: bool,
    ) -> None:
        """A lazy entry never hides a real module-scope circular binding."""
        child, sources = self._workspace(
            tmp_path,
            "from parent_pkg import m\nclass ChildModels(m):\n    pass\n"
            "m = ChildModels\n",
        )
        init = tmp_path / "parent/src/parent_pkg/__init__.py"
        binding = f"from parent_pkg import {self.PARENT_CLASS}, m\n"
        sources[init] = (
            sources[init] + binding if after_lazy_map else binding + sources[init]
        )

        tm.fail(self._plan(tmp_path, sources, child), has="cyclic facade binding")

    @pytest.mark.parametrize(
        "last_binding",
        [
            "m = {owner}\n",
            "m: type[{owner}] = {owner}\n",
            "if runtime_condition:\n    m = {owner}\n",
        ],
    )
    def test_last_runtime_binding_wins_over_earlier_binding(
        self,
        tmp_path: Path,
        last_binding: str,
    ) -> None:
        """Imports, classes, aliases, and ordinary guards keep their ordering."""
        child, sources = self._workspace(
            tmp_path,
            "from parent_pkg import m\nclass ChildModels(m):\n    pass\n"
            "m = ChildModels\n",
        )
        sources[tmp_path / "parent/src/parent_pkg/__init__.py"] = (
            "from typing import TYPE_CHECKING\n"
            "from parent_pkg import m\n"
            f"class {self.PARENT_CLASS}:\n    pass\n"
            f"class {self.OTHER_CLASS}:\n    pass\n"
            f"m = {self.PARENT_CLASS}\n"
            + last_binding.format(owner=self.OTHER_CLASS)
            + "if TYPE_CHECKING:\n"
            f"    m = {self.PARENT_CLASS}\n"
            f"__all__ = [{self.PARENT_CLASS!r}, {self.OTHER_CLASS!r}, 'm']\n"
        )

        updated = self._edits(tmp_path, sources, child)[0].updated_source

        tm.that(updated, has=f"class ChildModels({self.OTHER_CLASS}):")

    def test_type_only_publication_without_runtime_owner_fails(
        self,
        tmp_path: Path,
    ) -> None:
        """Static declarations alone cannot publish a runtime facade owner."""
        child, sources = self._workspace(
            tmp_path,
            "from parent_pkg import m\nclass ChildModels(m):\n    pass\n"
            "m = ChildModels\n",
        )
        sources[tmp_path / "parent/src/parent_pkg/__init__.py"] = (
            "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n"
            f"    from .models import {self.PARENT_CLASS}, m\n"
            f"__all__ = [{self.PARENT_CLASS!r}, 'm']\n"
        )

        tm.fail(self._plan(tmp_path, sources, child), has="is not declared")

    def _workspace(
        self,
        tmp_path: Path,
        child_source: str,
        *,
        parent_exports: t.StrSequence = (),
    ) -> t.Pair[Path, t.MutableMappingKV[Path, str]]:
        """Declare a parent whose class name no package naming could infer.

        Returns:
            The resulting ``t.Pair[Path, t.MutableMappingKV[Path, str]]``.

        """
        exports = parent_exports or (self.PARENT_CLASS, "m")
        parent = tmp_path / "parent/src/parent_pkg"
        child = tmp_path / "child/src/child_pkg/models.py"
        return child, {
            parent / "__init__.py": (
                "from typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n"
                f"    from .models import {self.PARENT_CLASS}, m\n"
                f"{self._lazy_publication('.models', self.PARENT_CLASS, 'm')}"
                f"__all__ = [{self.PARENT_CLASS!r}, 'm']\n"
            ),
            parent / "models.py": (
                "from base_pkg import m\n"
                f"class {self.PARENT_CLASS}(m):\n    pass\n"
                f"m = {self.PARENT_CLASS}\n"
                f"__all__ = {list(exports)!r}\n"
            ),
            child: child_source,
        }

    @staticmethod
    def _finding(file_path: Path) -> m.Infra.ModScanFinding:
        """Build one detector finding for the facade module.

        Returns:
            The resulting ``m.Infra.ModScanFinding``.

        """
        return m.Infra.ModScanFinding(
            rule_file="facade-base-by-class-name.yml",
            rule_id="facade-base-by-class-name",
            repository="child",
            file=file_path,
            range={},
            text="m = ChildModels",
            actionable=False,
            classification=c.Infra.ModScanFindingClass.DETECTION_ONLY,
            payload={},
        )

    @classmethod
    def _plan(
        cls,
        tmp_path: Path,
        sources: t.MappingKV[Path, str],
        child: Path,
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Plan the facade-base phase for the detector finding in ``child``.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]``.

        """
        with infra.rope_workspace(tmp_path) as rope:
            return u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.FACADE_BASE,
                rope_workspace=rope,
                sources=sources,
                findings=(cls._finding(child.relative_to(tmp_path)),),
            )

    @classmethod
    def _edits(
        cls,
        tmp_path: Path,
        sources: t.MappingKV[Path, str],
        child: Path,
    ) -> t.VariadicTuple[m.Infra.SemanticMigrationEdit]:
        """Return the successful plan's edits.

        Returns:
            The successful plan's edits.

        """
        planned = cls._plan(tmp_path, sources, child)
        tm.ok(planned)
        return planned.value
