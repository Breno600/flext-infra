"""Class nesting leaves an immediate suite reference importable.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from flext_tests import tm

import flext_infra
from tests import c, u


class TestsFlextInfraClassNestingSuiteScope:
    """A nested class suite cannot see a sibling while the owner is building."""

    @staticmethod
    def _models_owner() -> tuple[str, str, str]:
        """Return the models alias, module file name, and owner class.

        Returns:
            The alias, the module stem, and the owner class name.

        """
        alias = next(
            letter
            for letter, family in u.Infra.facade_families().items()
            if family.module == "models"
        )
        module_name = u.Tests.family_public_module(alias)
        owner_name = (
            f"{u.derive_class_stem('flext-test-project')}"
            f"{u.Infra.facade_families()[alias].suffix}"
        )
        return alias, module_name, owner_name

    @classmethod
    def _publish(cls, tmp_path: Path, source: str) -> str:
        """Plan class nesting and return the source a later publish would write.

        Returns:
            The updated source, or ``source`` when the plan moves nothing.

        """
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        _alias, module_name, _owner_name = cls._models_owner()
        module_path = package_root / f"{module_name}.py"
        module_path.write_text(source, encoding=c.Infra.ENCODING_DEFAULT)
        with flext_infra.infra.rope_workspace(repository_root) as rope:
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.CLASS_NESTING,
                rope_workspace=rope,
                sources={module_path: source},
            )
        edits = tm.ok(planned)
        return edits[0].updated_source if edits else source

    @staticmethod
    def _load(published: str, tmp_path: Path) -> ModuleType:
        """Import published source as a module so a NameError fails the test.

        Returns:
            The loaded module.

        Raises:
            RuntimeError: If the published module has no loader.

        """
        module_path = tmp_path / "published_models.py"
        module_path.write_text(published, encoding=c.Infra.ENCODING_DEFAULT)
        spec = importlib.util.spec_from_file_location("published_models", module_path)
        if spec is None or spec.loader is None:
            msg = "published models module did not load"
            raise RuntimeError(msg)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_immediate_suite_reference_stays_at_module_level(
        self,
        tmp_path: Path,
    ) -> None:
        """A default factory that names a sibling stays a module global."""
        alias, _module_name, owner_name = self._models_owner()
        payload = f"{owner_name}Payload"
        holder = f"{owner_name}Holder"
        source = (
            '"""Models."""\n\n'
            "from __future__ import annotations\n\n"
            f'__all__: list[str] = ["{owner_name}", "{alias}"]\n\n'
            f"class {owner_name}:\n"
            '    """Owner."""\n\n'
            f"{alias} = {owner_name}\n\n"
            f"class {payload}:\n"
            '    """Payload."""\n\n'
            f"class {holder}:\n"
            '    """Holder."""\n\n'
            f"    payload = {payload}\n"
        )
        published = self._publish(tmp_path, source)
        loaded = self._load(published, tmp_path)
        holder_cls = getattr(loaded, holder)
        payload_cls = getattr(loaded, payload)
        tm.that(isinstance(holder_cls, type), eq=True)
        tm.that(isinstance(payload_cls, type), eq=True)
        tm.that(holder_cls.payload, eq=payload_cls)
        tm.that(f"\nclass {holder}:" in published, eq=True)
        tm.that(f"\nclass {payload}:" in published, eq=True)

    def test_inherited_siblings_still_nest_and_import(
        self,
        tmp_path: Path,
    ) -> None:
        """A base in the class header still moves under the owner."""
        alias, _module_name, owner_name = self._models_owner()
        base = f"{owner_name}Base"
        child = f"{owner_name}Child"
        source = (
            '"""Models."""\n\n'
            "from __future__ import annotations\n\n"
            f'__all__: list[str] = ["{owner_name}", "{alias}"]\n\n'
            f"class {owner_name}:\n"
            '    """Owner."""\n\n'
            f"{alias} = {owner_name}\n\n"
            f"class {base}:\n"
            '    """Base."""\n\n'
            f"class {child}({base}):\n"
            '    """Child."""\n'
        )
        published = self._publish(tmp_path, source)
        loaded = self._load(published, tmp_path)
        owner = getattr(loaded, owner_name)
        tm.that(isinstance(owner, type), eq=True)
        nested_child = getattr(owner, child)
        nested_base = getattr(owner, base)
        tm.that(nested_child.__bases__, eq=(nested_base,))
