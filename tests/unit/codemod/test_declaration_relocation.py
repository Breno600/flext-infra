"""Public immutable nested payload relocation contracts.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import infra
from flext_infra.codemod.batch_gates import FlextInfraModGateEngine
from tests import c, u


class TestsFlextInfraDeclarationRelocation:
    """Exercise real Rope bindings and preserve the original source inventory."""

    @staticmethod
    def _seed(
        tmp_path: Path,
        *,
        body: str = "value: str = Field(default='payload')",
        base: str = "PayloadBase",
        cycle: bool = False,
        existing_imports: bool = False,
    ) -> tuple[Path, dict[Path, str]]:
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        stem = u.derive_class_stem(root.name)
        models = (
            package / u.Infra.facade_family_declared_by(c.Infra.MODELS_PY).directory
        )
        utilities = (
            package / u.Infra.facade_family_declared_by(c.Infra.UTILITIES_PY).directory
        )
        models.mkdir()
        utilities.mkdir()
        (models / "__init__.py").write_text("", encoding="utf-8")
        (utilities / "__init__.py").write_text("", encoding="utf-8")
        owner = f"{stem}ModelsPayload"
        source_owner = f"{stem}UtilitiesPayload"
        facade = f"{stem}Models"
        sources = {
            models / "payload.py": (
                '"""Authored payload family."""\nfrom __future__ import annotations\n'
                + (
                    "from pydantic import BaseModel as PayloadBase, Field\n"
                    if existing_imports
                    else ""
                )
                + (
                    f"from {package.name}._utilities.payload import {source_owner}\n"
                    if cycle
                    else ""
                )
                + f"class {owner}:\n    pass\n\n__all__ = ['{owner}']\n"
            ),
            package / "models.py": (
                f"from {package.name}._models.payload import {owner}\n"
                f"class {facade}({owner}):\n    pass\nm = {facade}\n"
                f"__all__ = ['{facade}', 'm']\n"
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
                f"from {package.name}._utilities.payload "
                f"import {source_owner} as Original\n"
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
    @pytest.mark.parametrize("existing_imports", [False, True])
    def test_move_preserves_payloads_and_is_immutable_idempotent(
        tmp_path: Path,
        *,
        existing_imports: bool,
    ) -> None:
        """Test move preserves payloads and is immutable idempotent.

        Raises:
            RuntimeError: If Published payload module has no loader.
        """
        root, sources = TestsFlextInfraDeclarationRelocation._seed(
            tmp_path,
            existing_imports=existing_imports,
        )
        with infra.rope_workspace(root) as rope:
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.DECLARATION_RELOCATION,
                rope_workspace=rope,
                sources=sources,
            )
            tm.ok(planned)
            tm.that(len(planned.value), eq=3)
            proposed = dict(sources)
            proposed.update({
                edit.file_path: edit.updated_source for edit in planned.value
            })
            trees = {
                path.name + path.parent.name: ast.parse(source)
                for path, source in proposed.items()
            }
            consumer = next(
                tree for name, tree in trees.items() if name.startswith("consumer.py")
            )
            constants = [
                node.value
                for node in ast.walk(consumer)
                if isinstance(node, ast.Constant)
            ]
            tm.that(constants.count("Original.Payload"), eq=3)
            remaining = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.DECLARATION_RELOCATION,
                rope_workspace=rope,
                sources=proposed,
            )
            tm.ok(remaining)
            tm.that(remaining.value, empty=True)
        for path, source in sources.items():
            tm.that(path.read_text(encoding="utf-8"), eq=source)
        target = next(
            path
            for path in sources
            if path.parent.name
            == u.Infra.facade_family_declared_by(c.Infra.MODELS_PY).directory
        )
        published = tmp_path / "published_payload.py"
        published.write_text(proposed[target], encoding="utf-8")
        spec = importlib.util.spec_from_file_location("published_payload", published)
        if spec is None or spec.loader is None:
            msg = "Published payload module has no loader"
            raise RuntimeError(msg)
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
        owner = next(
            node.name
            for node in ast.parse(sources[target]).body
            if isinstance(node, ast.ClassDef)
        )
        payload = getattr(loaded, owner).Payload
        tm.that(
            payload.model_validate({"value": "consumer"}).model_dump(),
            eq={"value": "consumer"},
        )
        tm.that(payload.model_validate({}).model_dump(), eq={"value": "payload"})

    @staticmethod
    @pytest.mark.parametrize(
        ("body", "base"),
        [
            (
                (
                    "value: str = 'data'\n        def run(self):\n"
                    "            return self.value"
                ),
                "PayloadBase",
            ),
            ("value: str = 'data'", "BaseSettings"),
        ],
    )
    def test_behavior_and_settings_are_not_payload_movers(
        tmp_path: Path,
        body: str,
        base: str,
    ) -> None:
        """Test behavior and settings are not payload movers."""
        root, sources = TestsFlextInfraDeclarationRelocation._seed(
            tmp_path,
            body=body,
            base=base,
        )
        with infra.rope_workspace(root) as rope:
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.DECLARATION_RELOCATION,
                rope_workspace=rope,
                sources=sources,
            )
        tm.ok(planned)
        tm.that(planned.value, empty=True)

    @staticmethod
    def test_cycle_refuses_without_mutation(tmp_path: Path) -> None:
        """Test cycle refuses without mutation."""
        root, sources = TestsFlextInfraDeclarationRelocation._seed(tmp_path, cycle=True)
        with (
            infra.rope_workspace(root) as rope,
            pytest.raises(ValueError, match="runtime import cycle"),
        ):
            u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.DECLARATION_RELOCATION,
                rope_workspace=rope,
                sources=sources,
            )
        for path, source in sources.items():
            tm.that(path.read_text(encoding="utf-8"), eq=source)

    @staticmethod
    def test_proposed_sources_not_disk_own_the_identity_snapshot(
        tmp_path: Path,
    ) -> None:
        """Test proposed sources not disk own the identity snapshot."""
        root, disk = TestsFlextInfraDeclarationRelocation._seed(tmp_path)
        sources = {
            path: source.replace("class Payload(", "class Revised(").replace(
                ".Payload",
                ".Revised",
            )
            for path, source in disk.items()
            if path.name != "homonym.py"
        }
        sources.update({
            path: source for path, source in disk.items() if path.name == "homonym.py"
        })
        with infra.rope_workspace(root) as rope:
            result = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.DECLARATION_RELOCATION,
                rope_workspace=rope,
                sources=sources,
            )
            tm.ok(result)
            tm.that(len(result.value), eq=3)
            sources.update({
                edit.file_path: edit.updated_source for edit in result.value
            })
            repeated = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.DECLARATION_RELOCATION,
                rope_workspace=rope,
                sources=sources,
            )
            tm.ok(repeated)
            tm.that(repeated.value, empty=True)
        for path, source in disk.items():
            tm.that(path.read_text(encoding="utf-8"), eq=source)

    @staticmethod
    def test_local_destination_capture_refuses_without_mutation(tmp_path: Path) -> None:
        """Test local destination capture refuses without mutation."""
        root, sources = TestsFlextInfraDeclarationRelocation._seed(tmp_path)
        consumer = next(path for path in sources if path.name == "consumer.py")
        sources[consumer] = sources[consumer].replace("def build()", "def build(m)")
        consumer.write_text(sources[consumer], encoding="utf-8")
        with (
            infra.rope_workspace(root) as rope,
            pytest.raises(ValueError, match="shadowed quoted type destination"),
        ):
            u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.DECLARATION_RELOCATION,
                rope_workspace=rope,
                sources=sources,
            )
        for path, source in sources.items():
            tm.that(path.read_text(encoding="utf-8"), eq=source)

    @staticmethod
    def test_quoted_field_dependency_is_transferred(tmp_path: Path) -> None:
        """Test quoted field dependency is transferred.

        Raises:
            RuntimeError: If Published decimal payload has no loader.
        """
        root, sources = TestsFlextInfraDeclarationRelocation._seed(
            tmp_path,
            body="amount: 'Decimal'",
        )
        origin = next(
            path
            for path in sources
            if path.parent.name
            == u.Infra.facade_family_declared_by(c.Infra.UTILITIES_PY).directory
        )
        sources[origin] = "from decimal import Decimal\n" + sources[origin]
        origin.write_text(sources[origin], encoding="utf-8")
        with infra.rope_workspace(root) as rope:
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.DECLARATION_RELOCATION,
                rope_workspace=rope,
                sources=sources,
            )
            tm.ok(planned)
            target = next(
                edit
                for edit in planned.value
                if edit.file_path.parent.name
                == u.Infra.facade_family_declared_by(c.Infra.MODELS_PY).directory
            )
        published = tmp_path / "published_decimal.py"
        published.write_text(target.updated_source, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("published_decimal", published)
        if spec is None or spec.loader is None:
            msg = "Published decimal payload has no loader"
            raise RuntimeError(msg)
        loaded = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = loaded
        try:
            spec.loader.exec_module(loaded)
            owner = next(
                node.name
                for node in ast.parse(target.original_source).body
                if isinstance(node, ast.ClassDef)
            )
            payload = getattr(loaded, owner).Payload
            tm.that(
                payload.model_validate({"amount": "2.5"}).model_dump_json(),
                eq='{"amount":"2.5"}',
            )
        finally:
            del sys.modules[spec.name]

    @staticmethod
    def test_real_scan_selects_the_immutable_declaration_phase(tmp_path: Path) -> None:
        """Test real scan selects the immutable declaration phase."""
        root, sources = TestsFlextInfraDeclarationRelocation._seed(tmp_path)
        preflight = FlextInfraModGateEngine.scan(root, fix=False).unwrap()
        phase = c.Infra.SemanticCutoverPhase.DECLARATION_RELOCATION
        rule_id = c.Infra.SEMANTIC_CUTOVER_RULE_IDS[phase]
        tm.that(
            any(finding.rule_id == rule_id for finding in preflight.entries),
            eq=True,
        )
        with infra.rope_workspace(root) as rope:
            planned = u.Infra.plan_semantic_cutover(
                phase,
                rope_workspace=rope,
                sources=sources,
                findings=preflight.entries,
            )
            tm.ok(planned)
            tm.that(len(planned.value), eq=3)
        for path, source in sources.items():
            tm.that(path.read_text(encoding="utf-8"), eq=source)

    @staticmethod
    def test_validator_and_computed_field_runtime_preserved(tmp_path: Path) -> None:
        """Test validator and computed field runtime preserved.

        Raises:
            RuntimeError: If Published validator has no loader.
        """
        root, sources = TestsFlextInfraDeclarationRelocation._seed(
            tmp_path,
            body=(
                "value: int = 1\n"
                "        @field_validator('value')\n"
                "        @classmethod\n"
                "        def normalize(cls, value: int) -> int:\n"
                "            return value * 2\n"
                "        @computed_field\n"
                "        @property\n"
                "        def derived(self) -> int:\n"
                "            return self.value + 1"
            ),
        )
        origin = next(
            path
            for path in sources
            if path.parent.name
            == u.Infra.facade_family_declared_by(c.Infra.UTILITIES_PY).directory
        )
        sources[origin] = (
            "from pydantic import field_validator, computed_field\n" + sources[origin]
        )
        origin.write_text(sources[origin], encoding="utf-8")
        with infra.rope_workspace(root) as rope:
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.DECLARATION_RELOCATION,
                rope_workspace=rope,
                sources=sources,
            )
            tm.ok(planned)
            target = next(
                edit
                for edit in planned.value
                if edit.file_path.parent.name
                == u.Infra.facade_family_declared_by(c.Infra.MODELS_PY).directory
            )
        published = tmp_path / "published_validator.py"
        published.write_text(target.updated_source, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("published_validator", published)
        if spec is None or spec.loader is None:
            msg = "Published validator has no loader"
            raise RuntimeError(msg)
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
        owner = next(
            node.name
            for node in ast.parse(target.original_source).body
            if isinstance(node, ast.ClassDef)
        )
        tm.that(
            getattr(loaded, owner).Payload.model_validate({"value": 3}).model_dump(),
            eq={"value": 6, "derived": 7},
        )

    @staticmethod
    @pytest.mark.parametrize("guard", ["generated", "nested-validator"])
    def test_unsafe_sources_refuse_the_whole_plan(tmp_path: Path, guard: str) -> None:
        """Test unsafe sources refuse the whole plan."""
        root, sources = TestsFlextInfraDeclarationRelocation._seed(tmp_path)
        if guard == "generated":
            path = next(path for path in sources if path.name == "consumer.py")
            sources[path] = c.Infra.AUTOGEN_HEADERS[0] + "\n" + sources[path]
            expected = "generated consumer"
        else:
            path = next(
                path
                for path in sources
                if path.parent.name
                == u.Infra.facade_family_declared_by(c.Infra.UTILITIES_PY).directory
            )
            sources[path] = sources[path].replace(
                "value: str = Field(default='payload')",
                (
                    "value: str = Field(default='payload')\n"
                    "        @field_validator('value')\n"
                    "        @classmethod\n"
                    "        def normalize(cls, value: str) -> str:\n"
                    "            scratch = [value for value in ()]\n"
                    "            return value"
                ),
            )
            sources[path] = "from pydantic import field_validator\n" + sources[path]
            expected = "unproven nested validator scope"
        path.write_text(sources[path], encoding="utf-8")
        with (
            infra.rope_workspace(root) as rope,
            pytest.raises(ValueError, match=expected),
        ):
            u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.DECLARATION_RELOCATION,
                rope_workspace=rope,
                sources=sources,
            )
        for path, source in sources.items():
            tm.that(path.read_text(encoding="utf-8"), eq=source)
