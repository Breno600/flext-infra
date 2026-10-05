"""Public planning contracts for immutable Rope family flattening.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import infra
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraFamilyFlatten:
    """Exercise the real module graph, not mocked semantic identities."""

    @staticmethod
    @pytest.mark.parametrize("collision", [False, True])
    def test_snapshot_rewrites_alias_and_inherited_consumers_without_effects(
        tmp_path: Path,
        *,
        collision: bool,
    ) -> None:
        """Test snapshot rewrites alias and inherited consumers without effects."""
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        directory = u.Infra.facade_family_declared_by(c.Infra.MODELS_PY).directory
        family = package / directory
        family.mkdir()
        (family / "__init__.py").write_text("", encoding="utf-8")
        path = family / "payload.py"
        owner = f"{u.derive_class_stem(root.name)}ModelsPayload"
        parent = package / "entities.py"
        parent.write_text("class Parent:\n    Entity = 'inherited'\n", encoding="utf-8")
        inheritance = "(Parent)" if collision else ""
        source = (
            "from enum import Enum\n"
            f"from {package.name}.entities import Parent\n\n"
            f"class {owner}{inheritance}:\n"
            "    class Wrapper:\n"
            "        class Entity(Enum):\n"
            "            VALUE = 'member'\n"
            "        TEXT = '''first\n        literal indentation\n        last'''\n"
            f"\n__all__ = ['{owner}']\n"
        )
        path.write_text(source, encoding="utf-8")
        consumer = package / "consumer.py"
        references = (
            f"from {package.name}.{directory}.payload import {owner} as Part\n\n"
            "class Public(Part):\n    pass\n\n"
            "VALUE = Public.Wrapper.Entity.VALUE\n"
            "TEXT = Part.Wrapper.TEXT\n"
        )
        consumer.write_text(references, encoding="utf-8")
        homonym = package / "unrelated.py"
        unrelated = (
            "class Other:\n    class Wrapper:\n        TEXT = 'unrelated'\n"
            "VALUE = Other.Wrapper.TEXT\n"
        )
        homonym.write_text(unrelated, encoding="utf-8")
        sources = {path: source, consumer: references, homonym: unrelated}
        # Imports and MRO must resolve the proposed wrapper, not its disk name.
        sources[path] = source.replace("class Wrapper:", "class Grouping:")
        sources[consumer] = references.replace(".Wrapper.", ".Grouping.")
        with infra.rope_workspace(root) as rope:
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.CLASS_NESTING,
                rope_workspace=rope,
                sources=sources,
            )
            tm.ok(planned)
            proposed = dict(sources)
            proposed.update({
                edit.file_path: edit.updated_source for edit in planned.value
            })
            expected_member = "GroupingEntity"
            tm.that(proposed[path], has=f"    class {expected_member}(Enum):")
            tm.that(
                proposed[path],
                has="'''first\n        literal indentation\n        last'''",
            )
            tm.that(proposed[consumer], has=f"VALUE = Public.{expected_member}.VALUE")
            tm.that(proposed[consumer], has="TEXT = Part.GroupingTEXT")
            tm.that(proposed[homonym], eq=unrelated)
            remaining = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.CLASS_NESTING,
                rope_workspace=rope,
                sources=proposed,
            )
            tm.ok(remaining)
            tm.that(remaining.value, empty=True)
        for file_path, original in {
            path: source,
            consumer: references,
            homonym: unrelated,
        }.items():
            tm.that(file_path.read_text(encoding="utf-8"), eq=original)

    @staticmethod
    @pytest.mark.parametrize(
        "entity",
        [
            "class Entity(Enum):\n        VALUE = 'one'",
            "class Entity:\n        def value(self) -> int:\n            return 1",
        ],
    )
    def test_entity_classes_are_not_namespace_wrappers(
        tmp_path: Path,
        entity: str,
    ) -> None:
        """Test entity classes are not namespace wrappers."""
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        family = (
            package / u.Infra.facade_family_declared_by(c.Infra.MODELS_PY).directory
        )
        family.mkdir()
        (family / "__init__.py").write_text("", encoding="utf-8")
        path = family / "payload.py"
        owner = f"{u.derive_class_stem(root.name)}ModelsPayload"
        source = (
            f"from enum import Enum\nclass {owner}:\n    {entity}\n\n"
            f"__all__ = ['{owner}']\n"
        )
        path.write_text(source, encoding="utf-8")
        with infra.rope_workspace(root) as rope:
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.CLASS_NESTING,
                rope_workspace=rope,
                sources={path: source},
            )
        tm.ok(planned)
        tm.that(planned.value, empty=True)

    @staticmethod
    @pytest.mark.parametrize(
        "reference",
        ["ALIAS = {owner}.Wrapper", 'alias: "{owner}.Wrapper"'],
    )
    def test_wrapper_used_as_an_entity_is_preserved_without_edits(
        tmp_path: Path,
        reference: str,
    ) -> None:
        """Test wrapper used as an entity is preserved without edits."""
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        directory = u.Infra.facade_family_declared_by(c.Infra.CONSTANTS_PY).directory
        family = package / directory
        family.mkdir()
        (family / "__init__.py").write_text("", encoding="utf-8")
        path = family / "payload.py"
        owner = f"{u.derive_class_stem(root.name)}ConstantsPayload"
        source = (
            f"class {owner}:\n    class Wrapper:\n        VALUE = 1\n\n"
            f"{reference.format(owner=owner)}\n\n__all__ = ['{owner}']\n"
        )
        path.write_text(source, encoding="utf-8")
        with infra.rope_workspace(root) as rope:
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.CLASS_NESTING,
                rope_workspace=rope,
                sources={path: source},
            )
        tm.ok(planned)
        tm.that(planned.value, empty=True)
        tm.that(path.read_text(encoding="utf-8"), eq=source)

    @staticmethod
    def test_flatten_removes_wrapper_docstring_and_promotes_alias_member(
        tmp_path: Path,
    ) -> None:
        """Test flatten removes wrapper docstring and promotes alias member."""
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        directory = u.Infra.facade_family_declared_by(c.Infra.MODELS_PY).directory
        family = package / directory
        family.mkdir()
        (family / c.Infra.INIT_PY).write_text("", encoding="utf-8")
        path = family / "payload.py"
        owner = f"{u.derive_class_stem(root.name)}ModelsPayload"
        source = (
            "from enum import Enum\n\n"
            f"class {owner}:\n"
            '    """Owner doc."""\n'
            "    class Wrapper:\n"
            '        """Wrapper doc."""\n'
            "        class Entity(Enum):\n"
            "            VALUE = 'member'\n"
            "        type Grouped = Entity\n"
            f"\n__all__ = ['{owner}']\n"
        )
        path.write_text(source, encoding="utf-8")
        consumer = package / "consumer.py"
        references = (
            f"from {package.name}.{directory}.payload import "
            f"{owner} as Part\n\nmember: Part.Wrapper.Grouped\n"
        )
        consumer.write_text(references, encoding="utf-8")
        with infra.rope_workspace(root) as rope:
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.CLASS_NESTING,
                rope_workspace=rope,
                sources={path: source, consumer: references},
            )
        tm.ok(planned)
        flattened = {path: source, consumer: references}
        flattened.update({
            edit.file_path: edit.updated_source for edit in planned.value
        })
        tm.that(flattened[path], has='"""Owner doc."""')
        tm.that(flattened[path], has="type WrapperGrouped = WrapperEntity")
        tm.that(flattened[consumer], has="member: Part.WrapperGrouped")
        assert '"""Wrapper doc."""' not in flattened[path], flattened[path]

    @staticmethod
    def test_composed_facade_keeps_the_wrapper_callers_still_use(
        tmp_path: Path,
    ) -> None:
        """A facade alias that still names the wrapper is not flattened away."""
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        directory = u.Infra.facade_family_declared_by(c.Infra.MODELS_PY).directory
        family = package / directory
        family.mkdir()
        (family / "__init__.py").write_text("", encoding="utf-8")
        path = family / "payload.py"
        owner = f"{u.derive_class_stem(root.name)}ModelsPayload"
        source = (
            f"class {owner}:\n"
            "    class VerbReceipt:\n"
            "        class Stage:\n"
            "            pass\n"
            "        class Report:\n"
            "            pass\n"
            f"\n__all__ = ['{owner}']\n"
        )
        path.write_text(source, encoding="utf-8")
        facade_name = f"{u.derive_class_stem(root.name)}Models"
        project = u.derive_class_stem(root.name)
        facade = (
            f"from {package.name}.{directory}.payload import {owner}\n\n"
            f"class {facade_name}:\n"
            f"    class {project}({owner}):\n"
            "        pass\n\n"
            f"m = {facade_name}\n"
        )
        facade_path = package / "models.py"
        facade_path.write_text(facade, encoding="utf-8")
        consumer = package / "consumer.py"
        references = (
            "from __future__ import annotations\n"
            f"from {package.name} import m\n\n"
            f"def render() -> m.{project}.VerbReceipt.Stage:\n"
            f"    return m.{project}.VerbReceipt.Stage()\n"
        )
        consumer.write_text(references, encoding="utf-8")
        sources = {path: source, facade_path: facade, consumer: references}
        with infra.rope_workspace(root) as rope:
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.CLASS_NESTING,
                rope_workspace=rope,
                sources=sources,
            )
        tm.ok(planned)
        updated = dict(sources)
        updated.update({edit.file_path: edit.updated_source for edit in planned.value})
        tm.that(updated[path], has="class VerbReceipt:")
        tm.that(updated[consumer], has=f"m.{project}.VerbReceipt.Stage")
        tm.that(consumer.read_text(encoding="utf-8"), eq=references)
