"""Public runtime-base discovery from unpublished, authoritative planned bytes.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config, t, u


class TestsFlextInfraRuntimeEvaluatedBaseClasses:
    """Plan new packages without importing them or collapsing nested identities."""

    @staticmethod
    def _roots() -> t.StrTuple:
        return tuple(
            config.Infra.tooling.tools.ruff.lint.flake8_type_checking
            .runtime_evaluated_roots,
        )

    @classmethod
    def _root_import(cls) -> str:
        module, _, name = cls._roots()[0].rpartition(".")
        return f"from {module} import {name} as RuntimeRoot\n"

    def test_unpublished_project_is_not_imported_or_created(
        self, tmp_path: Path,
    ) -> None:
        root = tmp_path / "unpublished"
        package = root / "src" / "unpublished_contract"
        planned = {
            package / "__init__.py": "",
            package / "models.py": self._root_import() + (
                "class Contract(RuntimeRoot): pass\n"
                "class Derived(Contract): pass\n"
                "class Consumer(Derived): pass\n"
            ),
        }
        tm.that(
            u.Infra.runtime_evaluated_base_classes(root, planned, self._roots()),
            eq=tuple(sorted((
                *self._roots(), "unpublished_contract.models.Contract",
                "unpublished_contract.models.Derived",
            ))),
        )
        tm.that(root.exists(), eq=False)
        tm.that("unpublished_contract" in sys.modules, eq=False)

    def test_import_aliases_relative_generic_bases_and_planned_disk_convergence(
        self, tmp_path: Path,
    ) -> None:
        package = tmp_path / "src" / "planned_contract"
        package.mkdir(parents=True)
        (package / "models.py").write_text("class Contract: pass\n", encoding="utf-8")
        planned = {
            package / "__init__.py": "from .models import Facade as m\n",
            package / "models.py": self._root_import() + (
                "class Contract[T](RuntimeRoot): pass\n"
                "class Facade:\n"
                "    class Contract(Contract[int]): pass\n"
            ),
            package / "nested" / "__init__.py": "",
            package / "nested" / "consumer.py": (
                "from ..models import Contract as Alias\n"
                "from .. import m as models\n"
                "import planned_contract.models as module_alias\n"
                "class Direct(Alias[int]): pass\n"
                "class Nested(models.Contract): pass\n"
                "class Qualified(module_alias.Facade.Contract): pass\n"
            ),
        }
        expected = tuple(sorted((
            *self._roots(), "planned_contract.models.Contract",
            "planned_contract.m.Contract", "planned_contract.models.Facade.Contract",
        )))
        actual = u.Infra.runtime_evaluated_base_classes(tmp_path, planned, self._roots())
        tm.that(actual, eq=expected)
        for path, source in planned.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")
        tm.that(
            u.Infra.runtime_evaluated_base_classes(tmp_path, {}, self._roots()),
            eq=actual,
        )

    @pytest.mark.parametrize("model_on_right", [False, True])
    def test_nested_member_lookup_obeys_c3_not_depth_first(
        self, tmp_path: Path, *, model_on_right: bool,
    ) -> None:
        origin_base = "" if model_on_right else "(RuntimeRoot)"
        right_base = "(RuntimeRoot)" if model_on_right else ""
        source = self._root_import() + (
            "class Origin:\n"
            f"    class Contract{origin_base}: pass\n"
            "class Left(Origin): pass\n"
            "class Right(Origin):\n"
            f"    class Contract{right_base}: pass\n"
            "class Joint(Left, Right): pass\n"
            "class Consumer(Joint.Contract): pass\n"
        )
        expected = tuple(sorted((
            *self._roots(),
            *(("c3_contract.models.Joint.Contract",) if model_on_right else ()),
        )))
        tm.that(
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {tmp_path / "src" / "c3_contract" / "models.py": source},
                self._roots(),
            ),
            eq=expected,
        )

    def test_nested_bare_names_do_not_collide(self, tmp_path: Path) -> None:
        source = self._root_import() + (
            "class First:\n"
            "    class Contract(RuntimeRoot): pass\n"
            "    class Consumer(Contract): pass\n"
            "class Second:\n"
            "    class Contract: pass\n"
            "    class Consumer(Contract): pass\n"
            "class Positive(First.Contract): pass\n"
            "class Negative(Second.Contract): pass\n"
        )
        tm.that(
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {tmp_path / "src" / "collision_contract" / "models.py": source},
                self._roots(),
            ),
            eq=tuple(sorted((
                *self._roots(), "collision_contract.models.Contract",
                "collision_contract.models.First.Contract",
            ))),
        )

    def test_value_shadowing_is_a_visible_invalid_base(self, tmp_path: Path) -> None:
        source = self._root_import() + (
            "class Origin:\n"
            "    class Contract(RuntimeRoot): pass\n"
            "class Shadow(Origin): Contract = 0\n"
            "class Consumer(Shadow.Contract): pass\n"
        )
        with pytest.raises(ValueError, match="Non-class member shadows required base"):
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {tmp_path / "src" / "shadow_contract" / "models.py": source},
                self._roots(),
            )

    def test_inconsistent_mro_fails_visibly(self, tmp_path: Path) -> None:
        source = (
            "class Left: pass\nclass Right: pass\n"
            "class First(Left, Right): pass\nclass Second(Right, Left): pass\n"
            "class Invalid(First, Second): pass\n"
        )
        with pytest.raises(ValueError, match="Inconsistent class MRO"):
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {tmp_path / "src" / "invalid_contract" / "models.py": source},
                self._roots(),
            )
