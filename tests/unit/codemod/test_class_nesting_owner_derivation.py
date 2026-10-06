"""Class nesting derives one owner for a module of loose members.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import infra
from tests import c, t, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraClassNestingOwnerDerivation:
    """A loose family module gains its derived owner; consumers follow it."""

    LOOSE_MODULE = '''"""Loose helpers of one family module."""

from __future__ import annotations

import os

# Owner-only permission bits.
_MODE = 0o600
LIMIT: int = 3


class _Marker:
    """Marker for callers without a precondition."""


_SENTINEL = _Marker()


def write(path: str, marker: _Marker = _SENTINEL) -> int:
    """Return a size derived from ``path`` for an unmarked call."""
    if isinstance(marker, _Marker):
        return _helper(path) + _MODE
    return LIMIT


def _helper(path: str) -> int:
    return len(os.fspath(path))


__all__: list[str] = ["LIMIT", "write"]
'''

    @staticmethod
    def _family_module(tmp_path: Path, stem: str, source: str) -> t.Pair[Path, Path]:
        """Write one module into the utilities family package of a workspace.

        Returns:
            The repository root and the written module path.

        """
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        family = (
            package / u.Infra.facade_family_declared_by(c.Infra.UTILITIES_PY).directory
        )
        tm.ok(u.Cli.ensure_dir(family))
        tm.ok(u.Cli.atomic_write_text_file(family / "__init__.py", ""))
        module = family / f"{stem}.py"
        tm.ok(u.Cli.atomic_write_text_file(module, source))
        return root, module

    @staticmethod
    def _derived_owner(root: Path, stem: str) -> str:
        """Return the owner the project class stem and family suffix derive.

        Returns:
            The derived owner class name.

        """
        family = u.Infra.facade_family_declared_by(c.Infra.UTILITIES_PY)
        return (
            f"{u.derive_class_stem(root.name)}{family.suffix}"
            f"{u.derive_class_stem(stem)}"
        )

    @staticmethod
    def _plan(
        root: Path,
        sources: t.MappingKV[Path, str],
    ) -> t.Pair[t.MappingKV[Path, str], t.MappingKV[Path, str] | str]:
        """Plan class nesting, then replan the planned sources.

        Returns:
            The planned sources and the replanned residue (or its failure).

        """
        with infra.rope_workspace(root) as rope:
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.CLASS_NESTING,
                rope_workspace=rope,
                sources=sources,
            )
            tm.ok(planned)
            updated = dict(sources)
            updated.update(
                (edit.file_path, edit.updated_source) for edit in planned.value
            )
            replanned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.CLASS_NESTING,
                rope_workspace=rope,
                sources=updated,
            )
        residue = (
            replanned.error or ""
            if replanned.failure
            else {edit.file_path: edit.updated_source for edit in replanned.value}
        )
        return updated, residue

    @staticmethod
    def _top_level(source: str) -> t.VariadicTuple[str]:
        """Return the names a module binds at top level, imports excluded.

        Returns:
            The class, function and assignment names in source order.

        """
        names: list[str] = []
        for node in ast.parse(source).body:
            if isinstance(node, ast.ClassDef | ast.FunctionDef):
                names.append(node.name)
            elif isinstance(node, ast.Assign | ast.AnnAssign):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                names.extend(
                    target.id for target in targets if isinstance(target, ast.Name)
                )
        return tuple(names)

    def test_zero_class_module_nests_under_the_derived_owner(
        self,
        tmp_path: Path,
    ) -> None:
        """Functions, constants and helper classes move under one owner."""
        root, module = self._family_module(tmp_path, "atomic_thing", self.LOOSE_MODULE)
        owner = self._derived_owner(root, "atomic_thing")

        updated, residue = self._plan(root, {module: self.LOOSE_MODULE})

        source = updated[module.resolve()]
        tm.that(self._top_level(source), eq=(owner, "__all__"))
        tm.that(source, has=f'__all__: list[str] = ["{owner}"]')
        tm.that(source, has="    @staticmethod\n    def write(")
        tm.that(source, has="    @staticmethod\n    def _helper(")
        tm.that(source, has="    class _Marker:")
        tm.that(source, has=f"return {owner}._helper(path) + {owner}._MODE")
        tm.that(source, has="    # Owner-only permission bits.")
        tm.that(residue, eq={})

    def test_module_constants_become_class_variables(self, tmp_path: Path) -> None:
        """A literal or annotated constant is a ``ClassVar`` of its owner."""
        root, module = self._family_module(tmp_path, "atomic_thing", self.LOOSE_MODULE)

        updated, _ = self._plan(root, {module: self.LOOSE_MODULE})

        source = updated[module.resolve()]
        tm.that(source, has="from typing import ClassVar")
        tm.that(source, has="    _MODE: ClassVar[int] = 0o600")
        tm.that(source, has="    LIMIT: ClassVar[int] = 3")
        tm.that(source, has="    _SENTINEL = _Marker()")
        compile(source, str(module), "exec")

    def test_private_classes_nest_under_the_derived_owner(
        self,
        tmp_path: Path,
    ) -> None:
        """Several private classes and no owner gain the derived owner."""
        source = (
            '"""Two private helpers."""\n\n'
            "from __future__ import annotations\n\n\n"
            "class _First:\n    pass\n\n\n"
            "class _Second(_First):\n    pass\n"
        )
        root, module = self._family_module(tmp_path, "pair_helpers", source)
        owner = self._derived_owner(root, "pair_helpers")

        updated, residue = self._plan(root, {module: source})

        nested = updated[module.resolve()]
        tm.that(self._top_level(nested), eq=(owner, "__all__"))
        tm.that(nested, has="    class _First:")
        tm.that(nested, has="    class _Second(_First):")
        tm.that(residue, eq={})
        compile(nested, str(module), "exec")

    def test_module_alias_consumers_read_the_owner(self, tmp_path: Path) -> None:
        """Module-alias and member imports are rewired to the owner."""
        root, module = self._family_module(tmp_path, "atomic_thing", self.LOOSE_MODULE)
        owner = self._derived_owner(root, "atomic_thing")
        package = module.parent
        consumer_owner = self._derived_owner(root, "consumer_thing")
        imported = ".".join(
            module.relative_to(root / c.Infra.DEFAULT_SRC_DIR).with_suffix("").parts,
        )
        consumer_source = (
            '"""Consumer of the loose module."""\n\n'
            "from __future__ import annotations\n\n"
            f"from {imported.rsplit('.', 1)[0]} import atomic_thing as thing\n"
            f"from {imported} import write\n\n\n"
            f"class {consumer_owner}:\n"
            '    """Consumer owner."""\n\n'
            "    @staticmethod\n"
            "    def run() -> int:\n"
            '        return thing.write("x") + write("y") + thing.LIMIT\n\n\n'
            f'__all__: list[str] = ["{consumer_owner}"]\n'
        )
        consumer = package / "consumer_thing.py"
        tm.ok(u.Cli.atomic_write_text_file(consumer, consumer_source))

        updated, residue = self._plan(
            root,
            {module: self.LOOSE_MODULE, consumer: consumer_source},
        )

        rewired = updated[consumer.resolve()]
        tm.that(rewired, has=f"from {imported} import {owner}")
        tm.that(rewired, lacks="import atomic_thing as thing")
        tm.that(rewired, lacks="import write")
        tm.that(
            rewired,
            has=f'{owner}.write("x") + {owner}.write("y") + {owner}.LIMIT',
        )
        tm.that(residue, eq={})

    def test_published_record_class_is_a_member(self, tmp_path: Path) -> None:
        """A published record class that is no family owner is a member."""
        root, module = self._family_module(tmp_path, "mode_helpers", "")
        owner = self._derived_owner(root, "mode_helpers")
        helper = f"{u.derive_class_stem(root.name)}NoPrecondition"
        source = (
            '"""Sentinel and helper."""\n\n'
            "from __future__ import annotations\n\n\n"
            f"class {helper}:\n    pass\n\n\n"
            f"NO_PRECONDITION = {helper}()\n\n\n"
            "def check(value: int) -> int:\n    return value\n\n\n"
            f'__all__: list[str] = ["{helper}", "NO_PRECONDITION", "check"]\n'
        )
        tm.ok(u.Cli.atomic_write_text_file(module, source))

        updated, residue = self._plan(root, {module: source})

        nested = updated[module.resolve()]
        tm.that(self._top_level(nested), eq=(owner, "__all__"))
        tm.that(nested, has=f"    class {helper}:")
        tm.that(residue, eq={})

    def test_rival_stem_classes_fail_naming_the_module(self, tmp_path: Path) -> None:
        """Two classes carrying the project stem leave the owner undecidable."""
        root, module = self._family_module(tmp_path, "rival_owners", "")
        owner = self._derived_owner(root, "rival_owners")
        source = (
            '"""Two candidate owners."""\n\n'
            "from __future__ import annotations\n\n\n"
            f"class {owner}Alpha:\n    pass\n\n\n"
            f"class {owner}Beta:\n    pass\n\n\n"
            f'__all__: list[str] = ["{owner}Alpha", "{owner}Beta"]\n'
        )
        tm.ok(u.Cli.atomic_write_text_file(module, source))

        with infra.rope_workspace(root) as rope:
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.CLASS_NESTING,
                rope_workspace=rope,
                sources={module: source},
            )

        tm.fail(planned, has="requires exactly one declared module owner")
        tm.fail(planned, has="rival_owners")

    def test_owner_creation_reads_stay_module_level(self, tmp_path: Path) -> None:
        """A metaclass factory, its builder and their sentinel never nest."""
        root, module = self._family_module(tmp_path, "lazy_helpers", "")
        owner = self._derived_owner(root, "lazy_helpers")
        source = (
            '"""Lazy assembly of one family facade."""\n\n'
            "from __future__ import annotations\n\n"
            "from typing import Any\n\n\n"
            "_SENTINEL: type | None = None\n\n\n"
            "def _build_tree() -> type:\n"
            '    """Assemble the tree on first access."""\n'
            "    global _SENTINEL\n"
            "    if _SENTINEL is not None:\n"
            "        return _SENTINEL\n\n"
            "    class Tree:\n"
            '        """Assembled tree."""\n\n'
            "    _SENTINEL = Tree\n"
            "    return _SENTINEL\n\n\n"
            "def _lazy_meta() -> type:\n"
            '    """Build the lazy metaclass."""\n\n'
            "    class _Meta(type):\n"
            '        """Assemble the tree on first class-level access."""\n\n'
            "        def __getattr__(cls, name: str) -> Any:\n"
            '            if name == "Tree":\n'
            "                tree = _build_tree()\n"
            "                cls.Tree = tree\n"
            "                return tree\n"
            '            msg = f"no attribute {name!r}"\n'
            "            raise AttributeError(msg)\n\n"
            "    return _Meta\n\n\n"
            f"class {owner}(metaclass=_lazy_meta()):\n"
            '    """The facade owner."""\n\n'
            f'__all__: list[str] = ["{owner}"]\n'
        )
        tm.ok(u.Cli.atomic_write_text_file(module, source))

        updated, residue = self._plan(root, {module: source})

        kept = updated[module.resolve()]
        tm.that(
            self._top_level(kept),
            eq=(
                "_SENTINEL",
                "_build_tree",
                "_lazy_meta",
                owner,
                "__all__",
            ),
        )
        tm.that(kept, has="def _lazy_meta() -> type:")
        tm.that(kept, has="tree = _build_tree()")
        tm.that(residue, eq={})
        compile(kept, str(module), "exec")

    def test_nested_class_annotations_keep_a_resolvable_name(
        self,
        tmp_path: Path,
    ) -> None:
        """Annotations inside a moved class name the owner, not a dropped bare name."""
        source = (
            '"""Registry annotations."""\n\n'
            "from __future__ import annotations\n\n"
            "from typing import ClassVar\n\n\n"
            "class _Handler:\n"
            "    @staticmethod\n"
            "    def current() -> _Registry:\n"
            "        return _Registry.current()\n\n\n"
            "class _Registry:\n"
            "    _current: ClassVar[_Registry | None] = None\n\n"
            "    @classmethod\n"
            "    def start(cls) -> _Registry:\n"
            "        return cls()\n\n"
            "    @classmethod\n"
            "    def current(cls) -> _Registry:\n"
            "        return cls()\n"
        )
        root, module = self._family_module(tmp_path, "registry_helpers", source)
        owner = self._derived_owner(root, "registry_helpers")

        updated, residue = self._plan(root, {module: source})

        nested = updated[module.resolve()]
        qualified = f"{owner}._Registry"
        tm.that(nested, has=f"def current() -> {qualified}:")
        tm.that(nested, has=f"return {qualified}.current()")
        tm.that(nested, has=f"_current: ClassVar[{qualified} | None] = None")
        tm.that(nested, has=f"def start(cls) -> {qualified}:")
        tm.that(nested, has=f"def current(cls) -> {qualified}:")
        tm.that(residue, eq={})
        compile(nested, str(module), "exec")
