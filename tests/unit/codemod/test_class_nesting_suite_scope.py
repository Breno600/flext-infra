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
from flext_infra.codemod import FlextInfraCodemodSemanticApply
from tests import c, m, u


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

    def test_nested_view_keeps_a_module_level_base_importable(
        self,
        tmp_path: Path,
    ) -> None:
        """A class already inside the owner does not pull its target's base in."""
        alias, _module_name, owner_name = self._models_owner()
        payload = f"{owner_name}Payload"
        holder = f"{owner_name}Holder"
        source = (
            '"""Models."""\n\n'
            "from __future__ import annotations\n\n"
            f'__all__: list[str] = ["{owner_name}", "{alias}"]\n\n'
            f"class {payload}:\n"
            '    """Payload."""\n\n'
            f"class {holder}({payload}):\n"
            '    """Holder."""\n\n'
            f"class {owner_name}:\n"
            '    """Owner."""\n\n'
            "    class View:\n"
            '        """View."""\n\n'
            f"        item = {holder}\n\n"
            f"{alias} = {owner_name}\n"
        )
        published = self._publish(tmp_path, source)
        loaded = self._load(published, tmp_path)
        owner = getattr(loaded, owner_name)
        holder_cls = getattr(loaded, holder)
        payload_cls = getattr(loaded, payload)
        tm.that(owner.View.item, eq=holder_cls)
        tm.that(holder_cls.__bases__, eq=(payload_cls,))
        tm.that(f"\nclass {holder}({payload}):" in published, eq=True)

    def test_nested_class_decorator_keeps_a_moved_helper_bare(
        self,
        tmp_path: Path,
    ) -> None:
        """A field specifier named by a nested model's decorator stays bare."""
        alias, _module_name, owner_name = self._models_owner()
        source = (
            '"""Models."""\n\n'
            "from __future__ import annotations\n\n"
            "from typing import dataclass_transform\n\n"
            f'__all__: list[str] = ["{owner_name}", "{alias}"]\n\n'
            "def _field(default: int = 0) -> int:\n"
            '    """Field."""\n'
            "    return default\n\n"
            f"class {owner_name}:\n"
            '    """Owner."""\n\n'
            "    @dataclass_transform(field_specifiers=(_field,))\n"
            "    class BaseModel:\n"
            '        """Model."""\n\n'
            f"{alias} = {owner_name}\n"
        )
        published = self._publish(tmp_path, source)
        tm.that(f"{owner_name}._field" in published, eq=False)
        tm.that(u.Infra.definition_time_name_errors(published), eq=())
        owner = getattr(self._load(published, tmp_path), owner_name)
        specifiers = owner.BaseModel.__dataclass_transform__["field_specifiers"]
        tm.that(len(specifiers), eq=1)
        tm.that(specifiers[0] is vars(owner)["_field"], eq=True)

    def test_method_decorator_reference_stays_at_module_level(
        self,
        tmp_path: Path,
    ) -> None:
        """A sibling suite whose method decorator reads a helper keeps both."""
        alias, _module_name, owner_name = self._models_owner()
        holder = f"{owner_name}Holder"
        source = (
            '"""Models."""\n\n'
            "from __future__ import annotations\n\n"
            "import functools\n\n"
            f'__all__: list[str] = ["{owner_name}", "{alias}"]\n\n'
            "def _size() -> int:\n"
            '    """Size."""\n'
            "    return 2\n\n"
            f"class {owner_name}:\n"
            '    """Owner."""\n\n'
            f"{alias} = {owner_name}\n\n"
            f"class {holder}:\n"
            '    """Holder."""\n\n'
            "    @staticmethod\n"
            "    @functools.lru_cache(maxsize=_size())\n"
            "    def value() -> int:\n"
            '        """Value."""\n'
            "        return 1\n"
        )
        published = self._publish(tmp_path, source)
        tm.that(u.Infra.definition_time_name_errors(published), eq=())
        loaded = self._load(published, tmp_path)
        tm.that(getattr(loaded, holder).value(), eq=1)
        tm.that(f"\nclass {holder}:" in published, eq=True)
        tm.that("\ndef _size() -> int:" in published, eq=True)

    def test_semantic_apply_refuses_a_plan_that_breaks_import(
        self,
        tmp_path: Path,
    ) -> None:
        """A moved default that reads a later module binding publishes nothing."""
        alias, module_name, owner_name = self._models_owner()
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        path = package / f"{module_name}.py"
        source = (
            '"""Models."""\n\n'
            "from __future__ import annotations\n\n"
            f'__all__: list[str] = ["{owner_name}", "{alias}"]\n\n'
            f"class {owner_name}:\n"
            '    """Owner."""\n\n'
            f"{alias} = {owner_name}\n\n"
            "LIMIT = len\n\n"
            "def _helper(measure: object = LIMIT) -> object:\n"
            '    """Helper."""\n'
            "    return measure\n"
        )
        path.write_text(source, encoding=c.Infra.ENCODING_DEFAULT)
        u.Tests.initialize_git_repo(root)
        report = m.Infra.ModScanReport(
            findings=0,
            actionable=0,
            detection_only=0,
            non_actionable_with_fix=0,
            files=frozenset(),
            entries=(),
        )
        with flext_infra.infra.rope_workspace(root) as rope:
            applied = FlextInfraCodemodSemanticApply.apply(root, report, rope)
        tm.fail(applied, has=f"{owner_name}: LIMIT")
        tm.that(path.read_text(encoding=c.Infra.ENCODING_DEFAULT), eq=source)

    @staticmethod
    def test_detector_reports_the_owner_named_inside_its_own_suite() -> None:
        """The NameError shape class nesting once published is reported."""
        source = (
            "from typing import dataclass_transform\n\n"
            "class Owner:\n"
            "    @staticmethod\n"
            "    def _field() -> int:\n"
            "        return 0\n\n"
            "    @dataclass_transform(field_specifiers=(Owner._field,))\n"
            "    class BaseModel:\n"
            "        pass\n"
        )
        tm.that(u.Infra.definition_time_name_errors(source), eq=("Owner: Owner",))

    @staticmethod
    def test_detector_reports_an_enclosing_class_binding() -> None:
        """A nested suite cannot read a binding of the class around it."""
        source = (
            "class Owner:\n"
            "    _CASES = (1, 2)\n\n"
            "    class Inner:\n"
            "        size = len(_CASES)\n"
        )
        tm.that(
            u.Infra.definition_time_name_errors(source),
            eq=("Owner.Inner: _CASES",),
        )

    @staticmethod
    def test_detector_accepts_deferred_and_module_bound_loads() -> None:
        """Function bodies, lambdas, type aliases and module globals resolve."""
        source = (
            "from typing import ClassVar\n\n"
            "LIMIT = 3\n\n"
            "class Owner[T]:\n"
            "    items: ClassVar[tuple[int, ...]] = tuple(range(LIMIT))\n"
            "    squares = {item: item * item for item in items}\n"
            "    type Alias = Owner[T]\n"
            "    factory = staticmethod(lambda: Owner)\n\n"
            "    def method(self) -> type[Owner[T]]:\n"
            "        return Owner\n\n"
            "    @staticmethod\n"
            "    def labels(names: tuple[str, ...] = tuple(n for n in 'ab')) -> int:\n"
            "        return len(names)\n\n"
            "    class Inner:\n"
            "        limit = LIMIT\n\n"
            "    class Box[V](list[V]):\n"
            "        pass\n"
        )
        tm.that(u.Infra.definition_time_name_errors(source), eq=())
