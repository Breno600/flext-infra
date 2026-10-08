"""Public immutable nested payload relocation contracts.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import infra
from tests import c, u


class TestsFlextInfraDeclarationRelocation:
    """Exercise real Rope bindings and preserve the original source inventory."""

    @staticmethod
    def _seed(tmp_path: Path, *, body: str = "value: str = Field(default='payload')",
              base: str = "PayloadBase", cycle: bool = False) -> tuple[Path, dict[Path, str]]:
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        stem = u.derive_class_stem(root.name)
        models = package / u.Infra.facade_family_declared_by(c.Infra.MODELS_PY).directory
        utilities = package / u.Infra.facade_family_declared_by(c.Infra.UTILITIES_PY).directory
        models.mkdir()
        utilities.mkdir()
        (models / "__init__.py").write_text("", encoding="utf-8")
        (utilities / "__init__.py").write_text("", encoding="utf-8")
        owner = f"{stem}ModelsPayload"
        source_owner = f"{stem}UtilitiesPayload"
        facade = f"{stem}Models"
        sources = {
            models / "payload.py": (
                (f"from {package.name}._utilities.payload import {source_owner}\n" if cycle else "")
                + f"class {owner}:\n    pass\n\n__all__ = ['{owner}']\n"
            ),
            package / "models.py": (
                f"from {package.name}._models.payload import {owner}\n"
                f"class {facade}({owner}):\n    pass\nm = {facade}\n"
            ),
            utilities / "payload.py": (
                "from pydantic import BaseModel as PayloadBase, Field\n"
                "from pydantic_settings import BaseSettings\n"
                f"class {source_owner}:\n"
                f"    class Payload({base}):\n        {body}\n"
                f"\ndef local():\n    return {source_owner}.Payload()\n"
                f"\n__all__ = ['{source_owner}']\n"
            ),
            package / "consumer.py": (
                "from __future__ import annotations\n"
                "from typing import Annotated, Literal\n"
                f"from {package.name}._utilities.payload import {source_owner} as Original\n"
                "def build() -> 'Original.Payload':\n    return Original.Payload()\n"
                "text = 'Original.Payload'\n"
                "literal: Literal['Original.Payload']\n"
                "metadata: Annotated[str, 'Original.Payload']\n"
            ),
            package / "homonym.py": (
                "class Original:\n    class Payload:\n        pass\n"
                "value = Original.Payload()\n"
            ),
        }
        for path, source in sources.items():
            path.write_text(source, encoding="utf-8")
        tm.that(u.Tests.run_lazy_init(root), eq=0)
        return root, sources

    @staticmethod
    def test_move_preserves_payloads_and_is_immutable_idempotent(tmp_path: Path) -> None:
        root, sources = TestsFlextInfraDeclarationRelocation._seed(tmp_path)
        with infra.rope_workspace(root) as rope:
            planned = u.Infra.plan_semantic_cutover(c.Infra.SemanticCutoverPhase.DECLARATION_RELOCATION,
                                                   rope_workspace=rope, sources=sources)
            tm.ok(planned)
            tm.that(len(planned.value), eq=3)
            proposed = dict(sources)
            proposed.update({edit.file_path: edit.updated_source for edit in planned.value})
            trees = {path.name + path.parent.name: ast.parse(source) for path, source in proposed.items()}
            consumer = next(tree for name, tree in trees.items() if name.startswith("consumer.py"))
            constants = [node.value for node in ast.walk(consumer) if isinstance(node, ast.Constant)]
            tm.that(constants.count("Original.Payload"), eq=3)
            remaining = u.Infra.plan_semantic_cutover(c.Infra.SemanticCutoverPhase.DECLARATION_RELOCATION,
                                                     rope_workspace=rope, sources=proposed)
            tm.ok(remaining)
            tm.that(remaining.value, empty=True)
        for path, source in sources.items():
            tm.that(path.read_text(encoding="utf-8"), eq=source)

    @staticmethod
    @pytest.mark.parametrize("body,base", [
        ("value: str = 'data'\n        def run(self):\n            return self.value", "PayloadBase"),
        ("value: str = 'data'", "BaseSettings"),
    ])
    def test_behavior_and_settings_are_not_payload_movers(tmp_path: Path, body: str, base: str) -> None:
        root, sources = TestsFlextInfraDeclarationRelocation._seed(tmp_path, body=body, base=base)
        with infra.rope_workspace(root) as rope:
            planned = u.Infra.plan_semantic_cutover(c.Infra.SemanticCutoverPhase.DECLARATION_RELOCATION,
                                                   rope_workspace=rope, sources=sources)
        tm.ok(planned)
        tm.that(planned.value, empty=True)

    @staticmethod
    def test_cycle_refuses_without_mutation(tmp_path: Path) -> None:
        root, sources = TestsFlextInfraDeclarationRelocation._seed(tmp_path, cycle=True)
        with infra.rope_workspace(root) as rope:
            with pytest.raises(ValueError, match="runtime import cycle"):
                u.Infra.plan_semantic_cutover(c.Infra.SemanticCutoverPhase.DECLARATION_RELOCATION,
                                              rope_workspace=rope, sources=sources)
        for path, source in sources.items():
            tm.that(path.read_text(encoding="utf-8"), eq=source)
