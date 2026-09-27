"""Behavior tests for the canonical typing unifier transformer."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import c
from flext_infra.transformers.typing_unifier import FlextInfraRefactorTypingUnifier

if TYPE_CHECKING:
    from tests import t


class FlextInfraRefactorTypingUnificationRule:
    """Adapter for canonical typing-unifier behavior tests."""

    def __init__(self, settings: t.JsonMapping) -> None:
        """Initialize the unification rule with typed settings."""
        self._settings = settings

    def apply(
        self, source: str, _file_path: Path | None = None
    ) -> t.Infra.TransformResult:
        """Apply canonical typing unification to source text."""
        _ = self._settings
        return FlextInfraRefactorTypingUnifier(
            canonical_map=c.Infra.TYPING_INLINE_UNION_CANONICAL_MAP,
            file_path=_file_path,
        ).apply_to_source(source)


class TestsFlextInfraRefactorInfraRefactorTypingUnifier:
    """Behavior contract for test_infra_refactor_typing_unifier."""

    def test_builtin_dict_keeps_mutable_field_and_return_contracts(self) -> None:
        """The callable's consumers retain item-assignment capability."""
        source = (
            "class Store:\n"
            "    values: dict[str, str] = {}\n"
            "    def contents(self) -> dict[str, str]:\n"
            "        return self.values\n"
        )
        updated, _ = FlextInfraRefactorTypingUnifier(canonical_map={}).apply_to_source(
            source
        )
        tm.that(updated, has="values: dict[str, str]")
        tm.that(updated, has="-> dict[str, str]")

    def test_converts_typealias_to_pep695(self) -> None:
        """Verify converts typealias to pep695."""
        source = (
            "from __future__ import annotations\n"
            "from typing import TypeAlias\n\n"
            "MyType: TypeAlias = str\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source)
        tm.that(updated, has="type MyType = str")
        tm.that(changes, has="Converted legacy TypeAlias assignment: MyType")

    def test_converts_multiple_aliases(self) -> None:
        """Verify converts multiple aliases."""
        source = (
            "from typing import TypeAlias\n\n"
            "AliasA: TypeAlias = str\n"
            "AliasB: TypeAlias = int\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source)
        tm.that(updated, has="type AliasA = str")
        tm.that(updated, has="type AliasB = int")
        tm.that(changes, has="Converted legacy TypeAlias assignment: AliasA")
        tm.that(changes, has="Converted legacy TypeAlias assignment: AliasB")

    def test_removes_dead_typealias_import(self) -> None:
        """Verify removes dead typealias import."""
        source = "from typing import TypeAlias\nMyType: TypeAlias = str\n"
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, _changes = rule.apply(source)
        tm.that(updated, has="type MyType = str")

    def test_removes_all_unused_typing_imports(self) -> None:
        """Verify removes all unused typing imports."""
        source = (
            "x: Final[str] = ''\n"
            "from typing import Final, TypeAlias, ClassVar, override\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, _changes = rule.apply(source)
        tm.that(updated, has="from typing import Final")

    def test_preserves_used_typing_imports(self) -> None:
        """Verify preserves used typing imports."""
        source = (
            "x: Final[str] = ''\n"
            "y: ClassVar[int] = 0\n"
            "from typing import Final, ClassVar\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source)
        tm.that(updated, has="from typing import Final, ClassVar")
        tm.that(updated, eq=source)
        tm.that(changes, eq=[])

    def test_replaces_primitives_union(self) -> None:
        """Verify replaces primitives union."""
        source = (
            "from __future__ import annotations\n\n"
            "def foo(x: str | int | float | bool) -> None:\n"
            "    pass\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source)
        tm.that(updated, has="t.Primitives")
        tm.that(updated, lacks="str | int | float | bool")
        tm.that(
            changes,
            has="Canonicalized inline union str | int | float | bool -> t.Primitives",
        )

    def test_replaces_numeric_union(self) -> None:
        """Verify replaces numeric union."""
        source = "def foo(x: int | float) -> None:\n    pass\n"
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source)
        tm.that(updated, has="x: t.Numeric")
        tm.that(updated, lacks="int | float")
        tm.that(changes, has="Canonicalized inline union int | float -> t.Numeric")

    def test_replaces_scalar_union(self) -> None:
        """Verify replaces scalar union."""
        source = (
            "from datetime import datetime\n"
            "def foo(x: str | int | float | bool | datetime) -> None:\n    pass\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source)
        tm.that(updated, has="x: t.Scalar")
        tm.that(updated, lacks="str | int | float | bool | datetime")
        tm.that(
            changes,
            has=(
                "Canonicalized inline union str | int | float | bool | datetime "
                "-> t.Scalar"
            ),
        )

    def test_preserves_non_json_members_of_union(self) -> None:
        """Datetime and Path do not acquire a JSON-only consumer contract."""
        source = (
            "from datetime import datetime\n"
            "from pathlib import Path\n"
            "def foo(x: str | int | float | bool | datetime | Path) -> None:\n"
            "    pass\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, _changes = rule.apply(source)
        tm.that(updated, has="t.Scalar | Path")
        tm.that(updated, lacks="t.JsonValue")

    def test_injects_t_import_when_needed(self) -> None:
        """Verify injects t import when needed."""
        source = "def foo(x: int | float) -> None:\n    pass\n"
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, _changes = rule.apply(source)
        tm.that(updated, has="x: t.Numeric")

    def test_replaces_subset_union_with_none(self) -> None:
        """Verify replaces subset union with none."""
        source = "def foo(x: int | float | None) -> None:\n    pass\n"
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, _changes = rule.apply(source)
        tm.that(updated, has="t.Numeric | None")
        tm.that(updated, lacks="int | float | None")

    def test_skips_definition_files(self) -> None:
        """Verify skips definition files."""
        source = "def foo(x: int | float) -> None:\n    pass\n"
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source, _file_path=Path("typings.py"))
        tm.that(updated, has="int | float")
        tm.that(updated, lacks="t.Numeric")
        tm.that(updated, lacks="from flext_core import t")
        tm.that(changes, eq=[])

    def test_preserves_non_matching_unions(self) -> None:
        """Verify preserves non matching unions."""
        source = "def foo(x: str | bytes) -> None:\n    pass\n"
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source)
        tm.that(updated, has="str | bytes")
        tm.that(updated, lacks="from flext_core import t")
        tm.that(changes, eq=[])

    def test_noop_clean_module(self) -> None:
        """Verify noop clean module."""
        source = (
            "from __future__ import annotations\n\ndef foo(x: str) -> None:\n    pass\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source)
        tm.that(updated, eq=source)
        tm.that(changes, eq=[])

    def test_preserves_used_imports_when_import_precedes_usage(self) -> None:
        """Verify preserves used imports when import precedes usage."""
        source = (
            "from __future__ import annotations\n"
            "from typing import ClassVar, Final\n\n"
            "class Foo:\n"
            "    X: ClassVar[str] = 'hello'\n"
            "    Y: Final[int] = 42\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source)
        tm.that(updated, has="from typing import ClassVar, Final")
        tm.that(updated, eq=source)
        tm.that(changes, eq=[])

    def test_unifier_preserves_used_names_when_import_precedes_usage(self) -> None:
        """Used typing names survive the unification of the import header."""
        source = (
            "from __future__ import annotations\n"
            "from typing import ClassVar, Final, Literal, override\n\n"
            "class Config:\n"
            "    NAME: Final[str] = 'app'\n"
            "    ITEMS: ClassVar[t.StrSequence] = []\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, _changes = rule.apply(source)
        tm.that(updated, has="NAME: Final[str] = 'app'")
        tm.that(updated, has="ITEMS: ClassVar[t.StrSequence]")

    def test_unifier_leaves_fully_unused_import_line_untouched(self) -> None:
        """The unifier unifies used names; unused-only imports stay as-is.

        Unused-import removal belongs to the dead-import owner, not the
        typing unifier — this test pins that boundary.
        """
        source = (
            "from typing import Literal, override\n\ndef foo() -> None:\n    pass\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source)
        tm.that(updated, eq=source)
        tm.that(changes, eq=[])

    def test_typealias_conversion_preserves_used_typing_siblings(self) -> None:
        """Verify typealias conversion preserves used typing siblings."""
        source = (
            "from __future__ import annotations\n"
            "from typing import Final, TypeAlias\n\n"
            "MyType: TypeAlias = str\n"
            "TIMEOUT: Final[int] = 30\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source)
        tm.that(updated, has="type MyType = str")
        tm.that(updated, has="from typing import Final")
        tm.that(changes, has="Converted legacy TypeAlias assignment: MyType")

    def test_preserves_type_checking_import(self) -> None:
        """Verify preserves type checking import."""
        source = (
            "from __future__ import annotations\n"
            "from typing import TYPE_CHECKING\n\n"
            "if TYPE_CHECKING:\n"
            "    from pathlib import Path\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source)
        tm.that(updated, has="from typing import TYPE_CHECKING")
        tm.that(updated, eq=source)
        tm.that(changes, eq=[])

    def test_preserves_protocol_and_runtime_checkable(self) -> None:
        """Verify preserves protocol and runtime checkable."""
        source = (
            "from __future__ import annotations\n"
            "from typing import Protocol, runtime_checkable\n\n"
            "@runtime_checkable\n"
            "class Connectable(Protocol):\n"
            "    def connect(self) -> None: ...\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source)
        tm.that(updated, has="from typing import Protocol, runtime_checkable")
        tm.that(updated, eq=source)
        tm.that(changes, eq=[])

    def test_preserves_annotated_in_function_params(self) -> None:
        """Verify preserves annotated in function params."""
        source = (
            "from __future__ import annotations\n"
            "from typing import Annotated\n"
            "from flext_core import m\n\n"
            "def create(name: Annotated[str, m.Field(min_length=1)]) -> None:\n"
            "    pass\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source)
        tm.that(updated, has="from typing import Annotated")
        tm.that(updated, eq=source)
        tm.that(changes, eq=[])

    def test_rewrites_only_annotated_type_and_preserves_metadata(self) -> None:
        """Treat metadata and Literal values as payloads rather than type syntax."""
        source = (
            "from __future__ import annotations\n"
            "from typing import Annotated, Literal\n\n"
            "from flext_core import m\n"
            "def consume(value: Annotated[list[object], m.Field(description='object list')]) -> None:\n"
            "    pass\n"
            "kind: Literal['object']\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, _changes = rule.apply(source)
        tm.that(
            updated,
            has="Annotated[t.SequenceOf[object], m.Field(description='object list')]",
        )
        tm.that(updated, has="Literal['object']")

    def test_preserves_override_in_method(self) -> None:
        """Verify preserves override in method."""
        source = (
            "from __future__ import annotations\n"
            "from typing import override\n\n"
            "class Child:\n"
            "    @override\n"
            "    def run(self) -> None:\n"
            "        pass\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source)
        tm.that(updated, has="from typing import override")
        tm.that(updated, eq=source)
        tm.that(changes, eq=[])

    def test_all_three_capabilities_in_one_pass(self) -> None:
        """Verify all three capabilities in one pass."""
        source = (
            "from __future__ import annotations\n"
            "from typing import TypeAlias, Final\n\n"
            "MyType: TypeAlias = str\n\n"
            "def foo(x: str | int | float | bool) -> Final[str]:\n"
            "    pass\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source)
        tm.that(updated, has="type MyType = str")
        tm.that(updated, has="Final")
        tm.that(updated, has="t.Primitives")
        tm.that(changes, has="Converted legacy TypeAlias assignment: MyType")
        # Import removal remains disabled, so this contract only verifies
        # the emitted change record.
        tm.that(
            changes,
            has="Canonicalized inline union str | int | float | bool -> t.Primitives",
        )

    def test_no_duplicate_t_import_when_t_from_project_package(self) -> None:
        """Verify no duplicate t import when t from project package."""
        source = (
            "from __future__ import annotations\n"
            "from flext_infra import c, m, t\n\n"
            "def foo(x: int | float) -> None:\n"
            "    pass\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source)
        tm.that(updated, has="t.Numeric")
        tm.that(updated, has="from flext_infra import c, m, t")
        tm.that(changes, has="Canonicalized inline union int | float -> t.Numeric")

    def test_preserves_typealias_import_when_class_level_usage_exists(self) -> None:
        """Verify preserves typealias import when class level usage exists."""
        source = (
            "from __future__ import annotations\n"
            "from typing import TypeAlias\n"
            "from collections.abc import Callable, Mapping, "
            "MutableMapping, MutableSequence, Sequence, Callable\n\n"
            "class MyTypes:\n"
            "    Handler: TypeAlias = Callable[[], None]\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, changes = rule.apply(source)
        tm.that(updated, has="from typing import TypeAlias")
        tm.that(updated, has="Handler: TypeAlias = Callable[[], None]")
        tm.that(updated, eq=source)
        tm.that(changes, eq=[])

    def test_removes_typealias_import_only_when_all_usages_converted(self) -> None:
        """Verify removes typealias import only when all usages converted."""
        source = (
            "from __future__ import annotations\n"
            "from typing import TypeAlias\n\n"
            "MyType: TypeAlias = str\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, _changes = rule.apply(source)
        tm.that(updated, has="type MyType = str")

    def test_rewrites_builtin_containers_to_canonical_t_aliases(
        self, tmp_path: Path
    ) -> None:
        """Verify rewrites builtin containers to canonical t aliases."""
        source = (
            "from __future__ import annotations\n"
            "from flext_core import t\n\n"
            "def build(data: dict[str, list[object]]) -> tuple[str, int]:\n"
            "    return ('ok', len(data))\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        file_path = tmp_path / "demo/src/flext_demo/sample.py"
        file_path.parent.mkdir(parents=True)
        file_path.write_text(source, encoding="utf-8")
        updated, changes = rule.apply(source, _file_path=file_path)
        tm.that(updated, has="from flext_core import t")
        tm.that(updated, has="data: t.MappingKV[str, t.SequenceOf[object]]")
        tm.that(updated, has="-> t.Pair[str, int]")
        tm.that(
            "\n".join(changes),
            has="Canonicalized built-in annotation dict[str, list[object]]",
        )

    def test_rewrites_tuple_variadics_preserving_any(self, tmp_path: Path) -> None:
        """Tuple shape does not prove a narrower contract for its elements."""
        source = (
            "from __future__ import annotations\n"
            "from flext_core import t\n"
            "from typing import Any\n\nvalue: tuple[Any, ...]\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        file_path = tmp_path / "demo/tests/test_sample.py"
        file_path.parent.mkdir(parents=True)
        file_path.write_text(source, encoding="utf-8")
        updated, _changes = rule.apply(source, _file_path=file_path)
        tm.that(updated, has="from flext_core import t")
        tm.that(updated, has="value: t.VariadicTuple[Any]")

    def test_rewrites_fixed_arity_four_tuple_to_quad(self, tmp_path: Path) -> None:
        """Verify rewrites fixed arity four tuple to quad."""
        source = (
            "from __future__ import annotations\n\n"
            "value: tuple[str, int, float, bool]\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, _changes = rule.apply(
            source, _file_path=tmp_path / "demo/src/flext_demo/sample.py"
        )
        tm.that(updated, has="from flext_core import t")
        tm.that(updated, has="value: t.Quad[str, int, float, bool]")

    def test_inserts_t_import_after_parenthesized_import_block(self) -> None:
        """Verify inserts t import after parenthesized import block."""
        source = (
            "from __future__ import annotations\n"
            "from flext_core import (\n"
            "    c,\n"
            "    m,\n"
            ")\n\n"
            "def consume(value: list[object]) -> None:\n    pass\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, _changes = rule.apply(source)
        tm.that(updated, has="from flext_core import (\n    c,\n    m,\n)")
        tm.that(updated, has="from flext_core import t")
        tm.that(updated.index("from flext_core import t"), gt=updated.index("    m,"))
        tm.that(updated, has="value: t.SequenceOf[object]")

    def test_skips_duplicate_t_import_in_parenthesized_import_block(
        self, tmp_path: Path
    ) -> None:
        """Verify skips duplicate t import in parenthesized import block."""
        source = (
            "from __future__ import annotations\n"
            "from flext_infra import (\n"
            "    c,\n"
            "    m,\n"
            "    t,\n"
            ")\n\n"
            "def consume(value: list[object]) -> None:\n    pass\n"
        )
        rule = FlextInfraRefactorTypingUnificationRule({
            "id": "unify-typings",
            "fix_action": "unify_typings",
        })
        updated, _changes = rule.apply(
            source, _file_path=tmp_path / "demo/src/flext_demo/sample.py"
        )
        tm.that(updated, has="from flext_infra import (\n    c,\n    m,\n    t,\n)")
        tm.that(updated.count("from flext_infra import t"), eq=0)
        tm.that(updated, has="value: t.SequenceOf[object]")
