"""Public family cutovers preserve quoted type identities and literal payloads."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import infra
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraFamilyTypeReferences:
    """Exercise the real Rope graph for generic bases and deferred annotations."""

    def test_quoted_types_follow_symbols_without_rewriting_literal_homonyms(
        self, tmp_path: Path
    ) -> None:
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        directory = c.Infra.FAMILY_DIRECTORIES["m"]
        family = package / directory
        family.mkdir()
        (family / c.Infra.INIT_PY).write_text("", encoding="utf-8")
        (package / "entities.py").write_text(
            "class Container[T]:\n    pass\n\n"
            "class Other:\n    class Domain:\n        class Item:\n            pass\n",
            encoding="utf-8",
        )
        owner = f"{u.derive_class_stem(root.name)}ModelsPayload"
        path = family / "payload.py"
        source = (
            f"from {package.name}.entities import Container\n\n"
            f"class {owner}:\n"
            "    class Domain:\n"
            "        class Item:\n            pass\n"
            f'        class Builder(Container["{owner}.Domain.Item"]):\n'
            "            pass\n"
            f"\n__all__ = ['{owner}']\n"
        )
        path.write_text(source, encoding="utf-8")
        consumer = package / "consumer.py"
        references = (
            "from __future__ import annotations\n"
            "from typing import Annotated as Meta, Literal as Choice\n"
            f"from {package.name}.{directory}.payload import {owner} as Part\n"
            f"from {package.name}.entities import Container, Other\n\n"
            "class Public(Part):\n    pass\n\n"
            'class Specialized(Container["Part.Domain.Item"]):\n    pass\n\n'
            "LABEL = 'é'; item: \"Public.Domain.Item\"\n"
            'items: list["Part.Domain.Item"]\n'
            'meta: Meta["Part.Domain.Item", "Part.Domain.Item"]\n'
            'choice: Choice["Part.Domain.Item"]\n'
            'unrelated: "Other.Domain.Item"\n'
            'type Items = list["Part.Domain.Item"]\n'
            'TEXT = "Part.Domain.Item"\n\n'
            'def convert(value: "Part.Domain.Item") -> "Part.Domain.Item":\n'
            "    Part = Other\n"
            '    local: "Part.Domain.Item"\n'
            "    return Part.Domain.Item()\n"
        )
        consumer.write_text(references, encoding="utf-8")
        sources = {path: source, consumer: references}
        with infra.rope_workspace(root) as rope:
            planned = tm.ok(
                u.Infra.plan_semantic_cutover(
                    c.Infra.SemanticCutoverPhase.CLASS_NESTING,
                    rope_workspace=rope,
                    sources=sources,
                )
            )
            proposed = dict(sources)
            proposed.update({edit.file_path: edit.updated_source for edit in planned})
            tm.that(proposed[path], has=f"Container['{owner}.DomainItem']")
            for preserved in (
                'choice: Choice["Part.Domain.Item"]',
                'unrelated: "Other.Domain.Item"',
                'TEXT = "Part.Domain.Item"',
                '    local: "Part.Domain.Item"',
            ):
                tm.that(proposed[consumer], has=preserved)
            for rewritten in (
                "Container['Part.DomainItem']",
                "LABEL = 'é'; item: 'Public.DomainItem'",
                "items: list['Part.DomainItem']",
                "meta: Meta['Part.DomainItem', \"Part.Domain.Item\"]",
                "type Items = list['Part.DomainItem']",
                "def convert(value: 'Part.DomainItem') -> 'Part.DomainItem':",
            ):
                tm.that(proposed[consumer], has=rewritten)
            remaining = tm.ok(
                u.Infra.plan_semantic_cutover(
                    c.Infra.SemanticCutoverPhase.CLASS_NESTING,
                    rope_workspace=rope,
                    sources=proposed,
                )
            )
            tm.that(remaining, empty=True)
        tm.that(path.read_text(encoding="utf-8"), eq=source)
        tm.that(consumer.read_text(encoding="utf-8"), eq=references)
