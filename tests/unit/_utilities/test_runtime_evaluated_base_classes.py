"""Public runtime-base discovery from unpublished, authoritative planned bytes.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, t, u


class TestsFlextInfraRuntimeEvaluatedBaseClasses:
    """Plan new packages without importing them or collapsing nested identities."""

    @staticmethod
    def _roots() -> t.StrTuple:
        return tuple(
            dict.fromkeys(
                config.Infra.tooling.tools.ruff.lint.flake8_type_checking.runtime_evaluated_roots,
            ),
        )

    @classmethod
    def _root_import(cls) -> str:
        module, _, name = cls._roots()[0].rpartition(".")
        return f"from {module} import {name} as RuntimeRoot\n"

    @pytest.mark.parametrize(
        ("setup", "condition", "selects_model"),
        [
            ("from typing import TYPE_CHECKING", "TYPE_CHECKING", False),
            ("from typing import TYPE_CHECKING as checking", "checking", False),
            ("import typing as annotations", "annotations.TYPE_CHECKING", False),
            (
                "from typing_extensions import TYPE_CHECKING as checking",
                "checking",
                False,
            ),
            (
                "from typing import TYPE_CHECKING as original\nchecking = original",
                "checking",
                False,
            ),
            ("", "True", True),
            ("", "False", False),
            (
                "from typing import TYPE_CHECKING\nTYPE_CHECKING = True",
                "TYPE_CHECKING",
                True,
            ),
            ("checking: bool = False", "checking", False),
            ("original = True\nchecking = original", "checking", True),
        ],
    )
    def test_runtime_guard_uses_import_identity_and_boolean_rebindings(
        self,
        tmp_path: Path,
        setup: str,
        condition: str,
        *,
        selects_model: bool,
    ) -> None:
        """Only the proven runtime branch supplies the consumer's class alias."""
        source = self._root_import() + (
            f"{setup}\n"
            "class Model(RuntimeRoot): pass\n"
            "class Plain: pass\n"
            f"if {condition}:\n    Alias = Model\n"
            "else:\n    Alias = Plain\n"
            "class Consumer(Alias): pass\n"
        )
        expected = set(self._roots())
        if selects_model:
            expected.add("runtime_guard.models.Alias")
        tm.that(
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {tmp_path / "src" / "runtime_guard" / "models.py": source},
                self._roots(),
            ),
            eq=tuple(sorted(expected)),
        )

    @pytest.mark.parametrize(
        ("setup", "condition"),
        [
            (
                (
                    "from typing import TYPE_CHECKING\n"
                    "from os import getenv\n"
                    "TYPE_CHECKING = bool(getenv('COLLECTOR_GUARD'))"
                ),
                "TYPE_CHECKING",
            ),
            (
                (
                    "import typing\nfrom os import getenv\n"
                    "typing = getenv('COLLECTOR_GUARD')"
                ),
                "typing.TYPE_CHECKING",
            ),
            ("", "TYPE_CHECKING"),
        ],
    )
    def test_unknown_guard_cannot_borrow_standard_constant_semantics(
        self,
        tmp_path: Path,
        setup: str,
        condition: str,
    ) -> None:
        """Undecidable guards retain the original ambiguous-base failure."""
        source = self._root_import() + (
            f"{setup}\n"
            "class Model(RuntimeRoot): pass\n"
            "class Plain: pass\n"
            f"if {condition}:\n    Alias = Model\n"
            "else:\n    Alias = Plain\n"
            "class Consumer(Alias): pass\n"
        )
        with pytest.raises(ValueError, match="Non-class binding used as a base"):
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {tmp_path / "src" / "unknown_guard" / "models.py": source},
                self._roots(),
            )

    @pytest.mark.parametrize(
        ("setup", "mutation", "condition"),
        [
            (
                "import typing as ty",
                "ty.TYPE_CHECKING = enabled",
                "ty.TYPE_CHECKING",
            ),
            (
                "import typing as ty\nreflected = ty",
                "reflected.TYPE_CHECKING = enabled",
                "ty.TYPE_CHECKING",
            ),
            (
                "import typing",
                "typing.TYPE_CHECKING = enabled",
                "typing.TYPE_CHECKING",
            ),
        ],
    )
    def test_provider_guard_member_write_fails_before_stale_selection(
        self,
        tmp_path: Path,
        installed_dependency_path: Path,
        setup: str,
        mutation: str,
        condition: str,
    ) -> None:
        """Unsupported module stores cannot preserve stale constant provenance."""
        tm.ok(
            u.Cli.atomic_write_text_file(
                installed_dependency_path / "guard_provider.py",
                self._root_import() + f"{setup}\nenabled = True\n{mutation}\n"
                "class Model(RuntimeRoot): pass\n"
                "class Plain: pass\n"
                f"if {condition}:\n    Alias = Model\n"
                "else:\n    Alias = Plain\n"
                "class Derived(Alias): pass\n",
            ),
        )
        with pytest.raises(
            ValueError,
            match="Unsupported class binding mutation",
        ) as failure:
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {
                    tmp_path / "src" / "guard_consumer" / "models.py": (
                        "from guard_provider import Derived\n"
                        "class Consumer(Derived): pass\n"
                    ),
                },
                self._roots(),
            )
        tm.that(
            str(failure.value),
            eq=f"Unsupported class binding mutation in guard_provider: {mutation}",
        )
        tm.that("guard_provider" in sys.modules, eq=False)

    @pytest.mark.parametrize("replacement_model", [False, True])
    def test_provider_class_member_write_updates_exact_aliased_owner(
        self,
        tmp_path: Path,
        installed_dependency_path: Path,
        *,
        replacement_model: bool,
    ) -> None:
        """Member replacement neither retains old lineage nor changes bare names."""
        initial_base = "" if replacement_model else "(RuntimeRoot)"
        replacement = "Model" if replacement_model else "Plain"
        tm.ok(
            u.Cli.atomic_write_text_file(
                installed_dependency_path / "namespace_provider.py",
                self._root_import() + "class Facade:\n"
                "    class Contract(RuntimeRoot): pass\n"
                "    class Namespace:\n"
                f"        class Contract{initial_base}: pass\n"
                "        class Model(RuntimeRoot): pass\n"
                "        class Plain: pass\n"
                "    reflected = Namespace\n"
                f"    replacement = Namespace.{replacement}\n"
                "    reflected.Contract = replacement\n",
            ),
        )
        expected = {*self._roots(), "namespace_provider.Facade.Contract"}
        if replacement_model:
            expected.add("namespace_provider.Facade.Namespace.Contract")
        tm.that(
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {
                    tmp_path / "src" / "namespace_consumer" / "models.py": (
                        "from namespace_provider import Facade\n"
                        "class OuterConsumer(Facade.Contract): pass\n"
                        "class MemberConsumer(Facade.Namespace.Contract): pass\n"
                    ),
                },
                self._roots(),
            ),
            eq=tuple(sorted(expected)),
        )

    def test_provider_boolean_member_preserves_sdk_non_class_failure(
        self,
        tmp_path: Path,
        installed_dependency_path: Path,
    ) -> None:
        """A real Boolean member reaches the SDK's original non-class boundary."""
        tm.ok(
            u.Cli.atomic_write_text_file(
                installed_dependency_path / "boolean_member_provider.py",
                "class Facade:\n"
                "    class Namespace:\n"
                "        class Contract: pass\n"
                "    enabled = True\n"
                "    reflected = Namespace\n"
                "    reflected.Contract = enabled\n",
            ),
        )
        with pytest.raises(
            TypeError,
            match="Rope did not resolve a required base to a class",
        ):
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {
                    tmp_path / "src" / "boolean_member_consumer" / "models.py": (
                        "from boolean_member_provider import Facade\n"
                        "class Invalid(Facade.Namespace.Contract): pass\n"
                        "class Later(Missing): pass\n"
                    ),
                },
                self._roots(),
            )

    def test_unpublished_project_is_not_imported_or_created(
        self,
        tmp_path: Path,
    ) -> None:
        root = tmp_path / "unpublished"
        package = root / "src" / "unpublished_contract"
        planned = {
            package / "__init__.py": "",
            package / "models.py": self._root_import()
            + (
                "class Contract(RuntimeRoot): pass\n"
                "class Derived(Contract): pass\n"
                "class Consumer(Derived): pass\n"
            ),
        }
        tm.that(
            u.Infra.runtime_evaluated_base_classes(root, planned, self._roots()),
            eq=tuple(
                sorted((
                    *self._roots(),
                    "unpublished_contract.models.Contract",
                    "unpublished_contract.models.Derived",
                )),
            ),
        )
        tm.that(root.exists(), eq=False)
        tm.that("unpublished_contract" in sys.modules, eq=False)

    def test_import_aliases_relative_generic_bases_and_planned_disk_convergence(
        self,
        tmp_path: Path,
    ) -> None:
        package = tmp_path / "src" / "planned_contract"
        package.mkdir(parents=True)
        (package / "models.py").write_text("class Contract: pass\n", encoding="utf-8")
        planned = {
            package / "__init__.py": "from .models import Facade as m\n",
            package / "models.py": self._root_import()
            + (
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
        expected = tuple(
            sorted((
                *self._roots(),
                "planned_contract.models.Contract",
                "planned_contract.m.Contract",
                "planned_contract.models.Facade.Contract",
            )),
        )
        actual = u.Infra.runtime_evaluated_base_classes(
            tmp_path,
            planned,
            self._roots(),
        )
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
        self,
        tmp_path: Path,
        *,
        model_on_right: bool,
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
        expected = tuple(
            sorted((
                *self._roots(),
                *(("c3_contract.models.Joint.Contract",) if model_on_right else ()),
            )),
        )
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
            eq=tuple(
                sorted((
                    *self._roots(),
                    "collision_contract.models.Contract",
                    "collision_contract.models.First.Contract",
                )),
            ),
        )

    def test_generated_lazy_bindings_are_indexed_without_importing(
        self,
        tmp_path: Path,
    ) -> None:
        """Generated package exports bind the same source-defined model identity."""
        package = tmp_path / "src" / "generated_contract"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(
            c.Infra.AUTOGEN_HEADERS[0]
            + "\nfrom types import MappingProxyType\n"
            + "from typing import TYPE_CHECKING\n"
            + "from flext_core import install_lazy_exports\n"
            + "if TYPE_CHECKING:\n    from .models import m\n"
            + "install_lazy_exports(__name__, __file__, "
            'MappingProxyType({"m": ".models"}), public_exports=("m",))\n'
            + 'raise RuntimeError("This package must not be imported")\n',
            encoding="utf-8",
        )
        planned = {
            package / "models.py": self._root_import()
            + "class Contract(RuntimeRoot): pass\n"
            + "class Derived(Contract): pass\nm = Contract\n",
            package / "consumer.py": (
                "from generated_contract import m\nclass Consumer(m): pass\n"
            ),
        }
        tm.that(
            u.Infra.runtime_evaluated_base_classes(tmp_path, planned, self._roots()),
            eq=tuple(
                sorted((
                    *self._roots(),
                    "generated_contract.models.Contract",
                    "generated_contract.m",
                )),
            ),
        )
        tm.that("generated_contract" in sys.modules, eq=False)

    @pytest.mark.parametrize("qualified", [False, True])
    def test_generated_lazy_member_keeps_the_export_binding(
        self,
        tmp_path: Path,
        *,
        qualified: bool,
    ) -> None:
        """Provider members resolve through the exported class, not its module."""
        package = tmp_path / "src" / "flext"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(
            c.Infra.AUTOGEN_HEADERS[0]
            + "\nfrom types import MappingProxyType\n"
            + "from typing import TYPE_CHECKING\n"
            + "from flext_core import install_lazy_exports\n"
            + "if TYPE_CHECKING:\n    from .models import m\n"
            + "install_lazy_exports(__name__, __file__, "
            'MappingProxyType({"m": ".models"}), public_exports=("m",))\n'
            + 'raise RuntimeError("This package must not be imported")\n',
            encoding="utf-8",
        )
        source = (
            "import flext\nclass Consumer(flext.m.BaseModel): pass\n"
            if qualified
            else "from flext import m\nclass Consumer(m.BaseModel): pass\n"
        )
        planned = {
            package / "models.py": self._root_import()
            + "class Contract(RuntimeRoot): pass\n"
            + "class Facade:\n    BaseModel = Contract\nm = Facade\n",
            package / "consumer.py": source,
        }
        was_imported = "flext" in sys.modules
        tm.that(
            u.Infra.runtime_evaluated_base_classes(tmp_path, planned, self._roots()),
            eq=tuple(sorted({*self._roots(), "flext.m.BaseModel"})),
        )
        tm.that("flext" in sys.modules, eq=was_imported)

    def test_missing_direct_package_base_is_not_invented(self, tmp_path: Path) -> None:
        """An available provider class does not imply a package-level export."""
        package = tmp_path / "src" / "flext"
        planned = {
            package / "__init__.py": "",
            package / "models.py": self._root_import()
            + "class BaseModel(RuntimeRoot): pass\n",
            package / "consumer.py": (
                "import flext\nclass Invalid(flext.BaseModel): pass\n"
            ),
        }
        with pytest.raises(
            ValueError, match=r"Unresolved planned base: flext\.BaseModel"
        ):
            u.Infra.runtime_evaluated_base_classes(tmp_path, planned, self._roots())

    def test_native_stdlib_aliases_preserve_the_same_qualified_bases(
        self,
        tmp_path: Path,
    ) -> None:
        """A native stdlib provider has one identity through either import form."""
        path = tmp_path / "src" / "native_contract" / "models.py"
        direct = u.Infra.runtime_evaluated_base_classes(
            tmp_path,
            {
                path: (
                    "from collections.abc import Mapping\n"
                    "class Consumer(Mapping): pass\n"
                ),
            },
            self._roots(),
        )
        aliased = u.Infra.runtime_evaluated_base_classes(
            tmp_path,
            {
                path: (
                    "import collections.abc as provider\n"
                    "class Consumer(provider.Mapping): pass\n"
                ),
            },
            self._roots(),
        )
        tm.that(aliased, eq=direct)
        tm.that(set(self._roots()).issubset(aliased), eq=True)

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

    @pytest.mark.parametrize(
        "import_statement",
        [
            "from binding_contract.parts import document as part",
            "from .parts import document as part",
            "import binding_contract.parts.document as part",
        ],
    )
    def test_planned_submodule_import_resolves_its_declared_class(
        self,
        tmp_path: Path,
        import_statement: str,
    ) -> None:
        """An import-from submodule alias does not require an initializer export."""
        package = tmp_path / "src" / "binding_contract"
        planned = {
            package / "__init__.py": "",
            package / "parts" / "__init__.py": "",
            package / "parts" / "document.py": self._root_import()
            + "class Document(RuntimeRoot): pass\n",
            package / "facade.py": (
                f"{import_statement}\nclass Facade(part.Document): pass\n"
                "class Consumer(Facade): pass\n"
            ),
        }
        tm.that(
            u.Infra.runtime_evaluated_base_classes(tmp_path, planned, self._roots()),
            eq=tuple(
                sorted((
                    *self._roots(),
                    "binding_contract.parts.document.Document",
                    "binding_contract.facade.Facade",
                )),
            ),
        )
        tm.that(package.exists(), eq=False)
        tm.that("binding_contract" in sys.modules, eq=False)

    @pytest.mark.parametrize(
        ("shadow", "diagnostic"),
        [
            ("document = 0", r"Unresolved planned base: shadowed_submodule\.document"),
            ("class document: pass", "Missing inherited class member:"),
        ],
    )
    def test_planned_package_binding_is_not_replaced_by_a_submodule(
        self,
        tmp_path: Path,
        shadow: str,
        diagnostic: str,
    ) -> None:
        """Explicit package values/classes retain precedence over file names."""
        package = tmp_path / "src" / "shadowed_submodule"
        planned = {
            package / "__init__.py": shadow + "\n",
            package / "document.py": self._root_import()
            + "class Document(RuntimeRoot): pass\n",
            package / "consumer.py": (
                "from . import document as part\nclass Invalid(part.Document): pass\n"
            ),
        }
        with pytest.raises(ValueError, match=diagnostic):
            u.Infra.runtime_evaluated_base_classes(tmp_path, planned, self._roots())

    def test_planned_submodule_does_not_invent_a_missing_class(
        self,
        tmp_path: Path,
    ) -> None:
        """A captured submodule proves its location, not arbitrary class exports."""
        package = tmp_path / "src" / "missing_submodule_class"
        with pytest.raises(
            ValueError,
            match=(
                r"Unresolved planned base: missing_submodule_class\.parts"
                r"\.document\.Missing"
            ),
        ):
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {
                    package / "__init__.py": "",
                    package / "parts" / "__init__.py": "",
                    package / "parts" / "document.py": "class Document: pass\n",
                    package / "consumer.py": (
                        "from .parts import document as part\n"
                        "class Invalid(part.Missing): pass\n"
                    ),
                },
                self._roots(),
            )

    @pytest.mark.parametrize("name", ["Structure", "Union", "Array"])
    def test_ctypes_native_private_parents_do_not_require_module_exports(
        self,
        tmp_path: Path,
        name: str,
    ) -> None:
        """Real ctypes classes retain their private native ancestry."""
        body = (
            "    _length_ = 1\n    _type_ = ctypes.c_byte\n"
            if name == "Array"
            else "    _fields_ = ()\n"
        )
        source = (
            "import ctypes\n"
            f"class Consumer(ctypes.{name}):\n{body}"
            "class NativeParentConsumer(ctypes.Structure.__base__): pass\n"
        )
        tm.that(
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {tmp_path / "src" / "ctypes_contract" / "models.py": source},
                self._roots(),
            ),
            eq=tuple(sorted(self._roots())),
        )

    def test_ctypes_inherited_alias_obeys_c3_with_shared_native_identity(
        self,
        tmp_path: Path,
    ) -> None:
        """Native wrapper identity cannot split the shared diamond ancestor."""
        source = self._root_import() + (
            "from ctypes import Structure\n"
            "class Origin(Structure):\n    class Contract: pass\n"
            "class Left(Origin): pass\n"
            "class Right(Origin):\n    class Contract(RuntimeRoot): pass\n"
            "class Joint(Left, Right): pass\n"
            "class Consumer(Joint.Contract): pass\n"
        )
        tm.that(
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {tmp_path / "src" / "native_diamond" / "models.py": source},
                self._roots(),
            ),
            eq=tuple(sorted((*self._roots(), "native_diamond.models.Joint.Contract"))),
        )

    def test_shared_private_native_parent_is_still_a_duplicate_base(
        self,
        tmp_path: Path,
    ) -> None:
        """Separate provider wrappers cannot invent distinct native classes."""
        with pytest.raises(ValueError, match="Duplicate class base"):
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {
                    tmp_path / "src" / "duplicate_native" / "models.py": (
                        "from ctypes import Structure as First\n"
                        "import ctypes as provider\n"
                        "class Invalid(First.__base__, provider.Union.__base__): pass\n"
                    ),
                },
                self._roots(),
            )

    @pytest.mark.parametrize(
        ("module", "name"),
        [("_ctypes", "_CData"), ("ctypes", "MissingNativeClass")],
    )
    def test_missing_native_export_keeps_its_original_failure(
        self,
        tmp_path: Path,
        module: str,
        name: str,
    ) -> None:
        """An observed private parent is not an invented module-level export."""
        with pytest.raises(u.Infra.rope_attribute_not_found_error_types()) as failure:
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {
                    tmp_path / "src" / "missing_native" / "models.py": (
                        f"import {module}\nclass Invalid({module}.{name}): pass\n"
                    ),
                },
                self._roots(),
            )
        tm.that(str(failure.value), eq=f"Attribute {name} not found")

    @pytest.mark.parametrize("name", ["ABC", "ABCMeta"])
    def test_native_abc_provider_metadata_preserves_class_bases(
        self,
        tmp_path: Path,
        name: str,
    ) -> None:
        """CPython's ABCMeta metadata assignment is not a lineage mutation."""
        tm.that(
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {
                    tmp_path / "src" / "abc_contract" / "models.py": (
                        f"from abc import {name}\nclass Consumer({name}): pass\n"
                    ),
                },
                self._roots(),
            ),
            eq=tuple(sorted(self._roots())),
        )

    @pytest.mark.parametrize("declared", [False, True])
    @pytest.mark.parametrize(
        "metadata",
        [
            "Contract.__module__ = __name__",
            "Contract.__module__: str = 'published_metadata'",
            "Contract.__name__ = 'PublishedContract'",
            "Contract.__qualname__ = 'Published.Contract'",
            "Contract.__doc__ = 'Published documentation'",
        ],
    )
    def test_provider_class_metadata_preserves_imported_and_declared_lineage(
        self,
        tmp_path: Path,
        installed_dependency_path: Path,
        metadata: str,
        *,
        declared: bool,
    ) -> None:
        """Metadata neither changes lexical class bindings nor publishes aliases."""
        provider = installed_dependency_path / "metadata_provider.py"
        declaration = (
            self._root_import() + "class Contract(RuntimeRoot): pass\n"
            if declared
            else self._root_import() + "Contract = RuntimeRoot\n"
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                provider,
                declaration + f"{metadata}\nclass Derived(Contract): pass\n"
                "raise RuntimeError('provider must not be imported')\n",
            ),
        )
        tm.that(
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {
                    tmp_path / "src" / "metadata_contract" / "models.py": (
                        "from metadata_provider import Derived\n"
                        "class Consumer(Derived): pass\n"
                    ),
                },
                self._roots(),
            ),
            eq=tuple(sorted((*self._roots(), "metadata_provider.Derived"))),
        )
        tm.that("metadata_provider" in sys.modules, eq=False)

    @pytest.mark.parametrize(
        "mutation",
        [
            "Contract.__bases__ = (Plain,)",
            "Contract.__bases__ = replacement",
            "Contract.__class__ = Plain",
            "Namespace.Contract = 0",
            "Contract.__module__ = Namespace.Contract = 'metadata'",
        ],
    )
    def test_provider_metadata_never_masks_the_first_binding_mutation(
        self,
        tmp_path: Path,
        installed_dependency_path: Path,
        mutation: str,
    ) -> None:
        """The first unsupported store escapes before a later invalid base."""
        tm.ok(
            u.Cli.atomic_write_text_file(
                installed_dependency_path / "mutating_provider.py",
                self._root_import()
                + "class Contract(RuntimeRoot): pass\nclass Plain: pass\n"
                "class Namespace:\n    Contract = Contract\n"
                "replacement = (Plain,)\n"
                "Contract.__module__ = __name__\n"
                f"{mutation}\nclass Derived(Contract): pass\n",
            ),
        )
        with pytest.raises(
            ValueError,
            match="Unsupported class binding mutation",
        ) as failure:
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {
                    tmp_path / "src" / "mutation_consumer" / "models.py": (
                        "from mutating_provider import Derived\n"
                        "class Consumer(Derived): pass\n"
                        "class Later(Missing): pass\n"
                    ),
                },
                self._roots(),
            )
        tm.that(
            str(failure.value),
            eq=f"Unsupported class binding mutation in mutating_provider: {mutation}",
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

    @pytest.mark.parametrize("aliased", [False, True])
    def test_qualified_provider_import_keeps_its_class_attributes(
        self,
        tmp_path: Path,
        *,
        aliased: bool,
    ) -> None:
        """A module binding is resolved with its attributes, never as a class."""
        root = self._roots()[0]
        module, _, name = root.rpartition(".")
        source = (
            f"import {module} as provider\nclass Contract(provider.{name}): pass\n"
            if aliased
            else f"import {module}\nclass Contract({root}): pass\n"
        )
        source += "class Consumer(Contract): pass\n"
        tm.that(
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {tmp_path / "src" / "qualified_contract" / "models.py": source},
                self._roots(),
            ),
            eq=tuple(sorted((*self._roots(), "qualified_contract.models.Contract"))),
        )

    def test_libcst_module_alias_resolves_the_published_class(
        self,
        tmp_path: Path,
    ) -> None:
        """The original real-consumer base has a complete installed source identity."""
        source = "import libcst as cst\nclass Transformer(cst.CSTTransformer): pass\n"
        tm.that(
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {tmp_path / "src" / "transformer_contract" / "visitor.py": source},
                self._roots(),
            ),
            eq=tuple(sorted(self._roots())),
        )

    def test_provider_reexports_and_inherited_aliases_use_declared_source(
        self,
        tmp_path: Path,
        installed_dependency_path: Path,
    ) -> None:
        """Static provider provenance supplies lazy exports without importing them."""
        provider = installed_dependency_path / "declared_provider"
        provider.mkdir()
        tm.ok(
            u.Cli.atomic_write_text_file(
                provider / "__init__.py",
                "from .models import Facade as exports\n"
                "raise RuntimeError('provider must not be imported during planning')\n",
            ),
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                provider / "models.py",
                self._root_import()
                + "class Contracts:\n    class Payload(RuntimeRoot): pass\n"
                "class Parent(Contracts): pass\n"
                "class Facade(Parent): Alias = Parent.Payload\n",
            ),
        )
        source = (
            "from declared_provider import exports as schemas\n"
            "class Consumer(schemas.Alias): pass\n"
        )
        tm.that(
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {tmp_path / "src" / "provider_contract" / "models.py": source},
                self._roots(),
            ),
            eq=tuple(sorted((*self._roots(), "declared_provider.exports.Alias"))),
        )
        tm.that("declared_provider" in sys.modules, eq=False)

    def test_planned_reexport_overrides_an_installed_provider(
        self,
        tmp_path: Path,
        installed_dependency_path: Path,
    ) -> None:
        """A same-name installed distribution cannot override the captured plan."""
        provider = installed_dependency_path / "planned_provider"
        provider.mkdir()
        tm.ok(
            u.Cli.atomic_write_text_file(
                provider / "__init__.py",
                "from .models import Contract\n",
            ),
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                provider / "models.py",
                "class Contract: pass\n",
            ),
        )
        bridge = installed_dependency_path / "declared_bridge"
        bridge.mkdir()
        tm.ok(
            u.Cli.atomic_write_text_file(
                bridge / "__init__.py",
                "from planned_provider.models import Contract\nFacade = Contract\n",
            ),
        )
        package = tmp_path / "src" / "planned_provider"
        planned = {
            package / "__init__.py": "from .models import Contract\n",
            package / "models.py": self._root_import()
            + "class Contract(RuntimeRoot): pass\n",
            package / "consumer.py": (
                "from planned_provider import Contract\n"
                "from declared_bridge import Facade\n"
                "class Consumer(Contract): pass\n"
                "class BridgedConsumer(Facade): pass\n"
            ),
        }
        tm.that(
            u.Infra.runtime_evaluated_base_classes(tmp_path, planned, self._roots()),
            eq=tuple(
                sorted((
                    *self._roots(),
                    "planned_provider.Contract",
                    "declared_bridge.Facade",
                )),
            ),
        )

    def test_configured_root_can_be_an_unpublished_planned_class(
        self,
        tmp_path: Path,
    ) -> None:
        package = tmp_path / "src" / "unpublished_root"
        roots = ("unpublished_root.Contract",)
        planned = {
            package / "__init__.py": "from .models import Contract\n",
            package / "models.py": self._root_import()
            + "class Contract(RuntimeRoot): pass\n",
            package / "consumer.py": (
                "from unpublished_root import Contract\n"
                "class Consumer(Contract): pass\n"
            ),
        }
        tm.that(
            u.Infra.runtime_evaluated_base_classes(tmp_path, planned, roots),
            eq=roots,
        )

    @pytest.mark.parametrize("value", ["0", "RuntimeRoot()"])
    def test_field_or_call_value_cannot_be_a_class_alias(
        self,
        tmp_path: Path,
        value: str,
    ) -> None:
        """A shadowing value fails instead of borrowing the ancestor's class."""
        source = self._root_import() + (
            "class Parent:\n    class Contract(RuntimeRoot): pass\n"
            f"class Shadow(Parent): Contract = {value}\n"
            "class Consumer(Shadow.Contract): pass\n"
        )
        with pytest.raises(ValueError, match="Non-class member shadows required base"):
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {tmp_path / "src" / "value_contract" / "models.py": source},
                self._roots(),
            )

    def test_missing_explicit_external_base_is_not_deselected(
        self,
        tmp_path: Path,
    ) -> None:
        source = self._root_import() + (
            "import absent_provider_contract as missing\n"
            "class Invalid(RuntimeRoot, missing.Required): pass\n"
        )
        with pytest.raises(u.Infra.rope_module_not_found_error_types()):
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {tmp_path / "src" / "missing_contract" / "models.py": source},
                self._roots(),
            )

    def test_imported_module_is_not_a_class_identity(self, tmp_path: Path) -> None:
        source = "import libcst as cst\nclass Invalid(cst): pass\n"
        with pytest.raises(ValueError, match="Module used as a class base"):
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {tmp_path / "src" / "module_contract" / "models.py": source},
                self._roots(),
            )

    def test_duplicate_class_identity_through_alias_fails(
        self,
        tmp_path: Path,
    ) -> None:
        source = self._root_import() + (
            "Alias = RuntimeRoot\nclass Invalid(RuntimeRoot, Alias): pass\n"
        )
        with pytest.raises(ValueError, match="Duplicate class base"):
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {tmp_path / "src" / "duplicate_contract" / "models.py": source},
                self._roots(),
            )

    def test_conditional_required_alias_is_not_chosen_from_one_branch(
        self,
        tmp_path: Path,
    ) -> None:
        source = self._root_import() + (
            "class Model(RuntimeRoot): pass\nclass Plain: pass\n"
            "if unknown_condition:\n    Alias = Model\n"
            "else:\n    Alias = Plain\n"
            "class Consumer(Alias): pass\n"
        )
        with pytest.raises(ValueError, match="Non-class binding used as a base"):
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {tmp_path / "src" / "conditional_contract" / "models.py": source},
                self._roots(),
            )

    @pytest.mark.parametrize(
        "mutation",
        [
            "del Contract",
            "Contract, other = (0, 1)",
            "[Contract] = [0]",
            "Namespace.Contract = Plain",
            "Namespace.Contract += Plain",
        ],
    )
    def test_unsupported_mutation_never_preserves_a_previous_class(
        self,
        tmp_path: Path,
        mutation: str,
    ) -> None:
        source = self._root_import() + (
            "class Contract(RuntimeRoot): pass\nclass Plain: pass\n"
            "class Namespace:\n    Contract = Contract\n"
            f"{mutation}\nclass Consumer(Contract): pass\n"
        )
        with pytest.raises(ValueError, match="Unsupported class binding mutation"):
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {tmp_path / "src" / "mutation_contract" / "models.py": source},
                self._roots(),
            )

    def test_provider_reexport_enters_a_planned_class_once(
        self,
        tmp_path: Path,
        installed_dependency_path: Path,
    ) -> None:
        provider = installed_dependency_path / "planned_bridge"
        provider.mkdir()
        tm.ok(
            u.Cli.atomic_write_text_file(
                provider / "__init__.py",
                "from planned_destination.models import Contract\n"
                "raise RuntimeError('provider must not be imported')\n",
            ),
        )
        package = tmp_path / "src" / "planned_destination"
        planned = {
            package / "__init__.py": "",
            package / "models.py": self._root_import()
            + "class Contract(RuntimeRoot): pass\n",
            package / "consumer.py": (
                "from planned_bridge import Contract\nclass Consumer(Contract): pass\n"
            ),
        }
        tm.that(
            u.Infra.runtime_evaluated_base_classes(tmp_path, planned, self._roots()),
            eq=tuple(sorted((*self._roots(), "planned_bridge.Contract"))),
        )
        tm.that(package.exists(), eq=False)
        tm.that("planned_bridge" in sys.modules, eq=False)

    def test_true_planned_reexport_cycle_fails_at_its_binding(
        self,
        tmp_path: Path,
    ) -> None:
        package = tmp_path / "src" / "cycle_contract"
        planned = {
            package / "__init__.py": "",
            package / "left.py": "from .right import Contract\n",
            package / "right.py": "from .left import Contract\n",
            package / "consumer.py": (
                "from .left import Contract\nclass Consumer(Contract): pass\n"
            ),
        }
        with pytest.raises(ValueError, match="Cyclic class alias"):
            u.Infra.runtime_evaluated_base_classes(tmp_path, planned, self._roots())

    def test_missing_inherited_member_cannot_be_deselected(
        self,
        tmp_path: Path,
    ) -> None:
        source = "class Namespace: pass\nclass Invalid(Namespace.Missing): pass\n"
        with pytest.raises(ValueError, match="Missing inherited class member"):
            u.Infra.runtime_evaluated_base_classes(
                tmp_path,
                {tmp_path / "src" / "member_contract" / "models.py": source},
                self._roots(),
            )
