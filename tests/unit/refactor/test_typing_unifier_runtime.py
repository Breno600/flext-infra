"""Public runtime checks for lexical typing rewrites and preserved data."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, infra, u
from flext_infra.transformers.typing_unifier import FlextInfraRefactorTypingUnifier

if TYPE_CHECKING:
    from pathlib import Path


class TestsTypingUnifierRuntime:
    """Validate transformed consumers through imports and get_type_hints."""

    def test_unknown_uses_keep_contract_and_iteration_keeps_mutable_elements(
        self, tmp_path: Path
    ) -> None:
        source = f"""from {c.Infra.PKG_CORE_UNDERSCORE} import t

def destructure(values: dict[str, int]) -> int:
    (selected,) = (values,)
    selected.update(count=3)
    return values["count"]

def mutate(values: dict[str, int]) -> None:
    values.update(count=4)

def escape(values: dict[str, int]) -> int:
    mutate(values)
    return values["count"]

def copy_only(values: dict[str, int]) -> int:
    copied = values.copy()
    copied.update(count=5)
    return copied["count"]

def nested(values: list[dict[str, int]]) -> int:
    [entry.update(count=6) for entry in values]
    return sum(entry["count"] for entry in values)

def count_nested(values: dict[str, list[int]]) -> int:
    return len(values)
"""
        transformer = FlextInfraRefactorTypingUnifier(
            canonical_map=c.Infra.TYPING_INLINE_UNION_CANONICAL_MAP
        )
        updated, _changes = transformer.apply_to_source(source)
        (tmp_path / "contract_consumer.py").write_text(updated, encoding="utf-8")
        probe = f"""from types import MappingProxyType
from typing import get_type_hints
from {c.Infra.PKG_CORE_UNDERSCORE} import t
from contract_consumer import destructure, escape, copy_only, nested, count_nested
print(get_type_hints(destructure)["values"] == dict[str, int])
print(get_type_hints(escape)["values"] == dict[str, int])
print(get_type_hints(copy_only)["values"] == dict[str, int])
print(get_type_hints(nested)["values"] == t.SequenceOf[dict[str, int]])
print(get_type_hints(count_nested)["values"] == t.MappingKV[str, list[int]])
for operation in (destructure, escape, copy_only):
    values = {{"count": 1}}
    print(operation(values), values["count"])
entries = ({{"count": 1}}, {{"count": 2}})
print(nested(entries), entries[0]["count"], entries[1]["count"])
print(count_nested(MappingProxyType({{"items": [1]}})))
"""
        outcome = tm.ok(u.Cli.run([sys.executable, "-c", probe], cwd=tmp_path))
        tm.that(
            outcome.stdout.splitlines(),
            eq=["True", "True", "True", "True", "True", "3 3", "4 4", "5 1", "12 6 6", "1"],
        )
        stable, repeat_changes = transformer.apply_to_source(updated)
        tm.that(stable, eq=updated)
        tm.that(repeat_changes, eq=[])

    def test_mutation_tracks_lexical_bindings_closures_and_aliases(
        self, tmp_path: Path
    ) -> None:
        source = f"""from {c.Infra.PKG_CORE_UNDERSCORE} import t

def read(values: dict[str, int]) -> int:
    return values["count"]

def write(values: dict[str, int]) -> int:
    values["count"] += 1
    return values["count"]

def closure(values: dict[str, int]) -> int:
    def update() -> None:
        values.update(count=3)
    update()
    return values["count"]

def shadow(values: dict[str, int]) -> int:
    def update(values: dict[str, int]) -> None:
        values.update(count=4)
    update({{}})
    return values["count"]

def aliases(first: dict[str, int], second: dict[str, int]) -> int:
    selected = first
    selected = second
    selected.update(count=5)
    return first["count"] + second["count"]
"""
        transformer = FlextInfraRefactorTypingUnifier(
            canonical_map=c.Infra.TYPING_INLINE_UNION_CANONICAL_MAP
        )
        updated, changes = transformer.apply_to_source(source)
        tm.that(bool(changes), eq=True)
        (tmp_path / "lexical_consumer.py").write_text(updated, encoding="utf-8")
        probe = f"""from types import MappingProxyType
from typing import get_type_hints
from {c.Infra.PKG_CORE_UNDERSCORE} import t
from lexical_consumer import read, write, closure, shadow, aliases
print(get_type_hints(read)["values"] == t.MappingKV[str, int])
print(get_type_hints(shadow)["values"] == t.MappingKV[str, int])
print(get_type_hints(write)["values"] == dict[str, int])
print(get_type_hints(closure)["values"] == dict[str, int])
print(get_type_hints(aliases)["first"] == dict[str, int])
print(get_type_hints(aliases)["second"] == dict[str, int])
immutable = MappingProxyType({{"count": 2}})
print(read(immutable), shadow(immutable))
payload = {{"count": 1}}
print(write(payload), closure(payload), payload["count"])
first, second = {{"count": 2}}, {{"count": 1}}
print(aliases(first, second), first["count"], second["count"])
"""
        outcome = tm.ok(u.Cli.run([sys.executable, "-c", probe], cwd=tmp_path))
        tm.that(
            outcome.stdout.splitlines(),
            eq=["True", "True", "True", "True", "True", "True", "2 2", "2 3 3", "7 2 5"],
        )
        stable, repeat_changes = transformer.apply_to_source(updated)
        tm.that(stable, eq=updated)
        tm.that(repeat_changes, eq=[])

    def test_aliased_typing_preserves_metadata_and_broad_types(
        self, tmp_path: Path
    ) -> None:
        """Brackets, commas and Unicode in metadata remain data at runtime."""
        source = f"""from {c.Infra.PKG_CORE_UNDERSCORE} import t
from typing import Annotated as A, Literal as L, Any as Payload
import typing as typing_module

TEXT = "str | int | float | bool; object; typing.Any; ] café, ☃"

def consume(entrée: A[list[object], "] object, café ☃"], kind: L["] object, café ☃"], payload: Payload) -> object:
    return payload

def quoted(value: 'A[list[object], "] object, café ☃"]') -> typing_module.Any:
    return value
"""
        transformer = FlextInfraRefactorTypingUnifier(
            canonical_map=c.Infra.TYPING_INLINE_UNION_CANONICAL_MAP
        )
        updated, changes = transformer.apply_to_source(source)
        tm.that(bool(changes), eq=True)
        (tmp_path / "typing_consumer.py").write_text(updated, encoding="utf-8")
        probe = """from typing import Any, get_args, get_type_hints
from pydantic import TypeAdapter
from typing_consumer import TEXT, consume, quoted
hints = get_type_hints(consume, include_extras=True)
quoted_hints = get_type_hints(quoted, include_extras=True)
sentinel = object()
values = TypeAdapter(get_args(hints["entrée"])[0]).validate_python([sentinel])
print(values[0] is sentinel)
print(get_args(hints["entrée"])[1])
print(get_args(hints["kind"])[0])
print(hints["payload"] is Any, hints["return"] is object, quoted_hints["return"] is Any)
print(get_args(quoted_hints["value"])[1])
print(TEXT)
"""
        outcome = tm.ok(u.Cli.run([sys.executable, "-c", probe], cwd=tmp_path))
        tm.that(
            outcome.stdout.splitlines(),
            eq=[
                "True",
                "] object, café ☃",
                "] object, café ☃",
                "True True True",
                "] object, café ☃",
                "str | int | float | bool; object; typing.Any; ] café, ☃",
            ],
        )
        stable, repeat_changes = transformer.apply_to_source(updated)
        tm.that(stable, eq=updated)
        tm.that(repeat_changes, eq=[])

    def test_shadowed_builtin_keeps_its_runtime_identity(self, tmp_path: Path) -> None:
        """A local class named list is not the builtin container."""
        source = """from typing import Any

class list[T]:
    pass

def consume(value: list[object], payload: Any) -> object:
    return payload
"""
        transformer = FlextInfraRefactorTypingUnifier(
            canonical_map=c.Infra.TYPING_INLINE_UNION_CANONICAL_MAP
        )
        updated, changes = transformer.apply_to_source(source)
        tm.that(updated, eq=source)
        tm.that(changes, eq=[])
        (tmp_path / "typing_homonym.py").write_text(updated, encoding="utf-8")
        probe = """from typing import Any, get_origin, get_type_hints
from typing_homonym import consume, list
hints = get_type_hints(consume)
print(get_origin(hints["value"]) is list, hints["payload"] is Any, hints["return"] is object)
"""
        outcome = tm.ok(u.Cli.run([sys.executable, "-c", probe], cwd=tmp_path))
        tm.that(outcome.stdout.strip(), eq="True True True")

    @pytest.mark.parametrize(
        ("declaration", "probe", "expected"),
        [
            (
                "type Number = int | float\n",
                "from pydantic import TypeAdapter\nfrom deferred_consumer import Number\nprint(TypeAdapter(Number).validate_json('1.25'))\n",
                "1.25",
            ),
            (
                f"from {c.Infra.PKG_CORE_UNDERSCORE} import m\nclass Number(m.BaseModel):\n    value: int | float\n",
                "from deferred_consumer import Number\nprint(Number.model_validate_json('{\"value\": 1.25}').value)\n",
                "1.25",
            ),
            (
                "def consume(value: int | float) -> None:\n    pass\n",
                "from typing import get_type_hints\nfrom deferred_consumer import consume\nprint(get_type_hints(consume)['value'] == (int | float))\n",
                "True",
            ),
        ],
    )
    def test_deferred_import_cannot_replace_a_runtime_union(
        self, tmp_path: Path, declaration: str, probe: str, expected: str
    ) -> None:
        """PEP 695 and Pydantic consumers keep their valid contract on refusal."""
        source = (
            "from __future__ import annotations\nfrom typing import TYPE_CHECKING\n"
            f"if TYPE_CHECKING:\n    from {c.Infra.PKG_CORE_UNDERSCORE} import t\n"
            + declaration
        )
        path = tmp_path / "deferred_consumer.py"
        path.write_text(source, encoding="utf-8")
        transformer = FlextInfraRefactorTypingUnifier(
            canonical_map=c.Infra.TYPING_INLINE_UNION_CANONICAL_MAP
        )
        with infra.rope_workspace(tmp_path) as rope:
            resource = rope.resource(path)
            assert resource is not None
            project = rope.rope_project
            with pytest.raises(ValueError, match="requires a runtime binding"):
                transformer.transform(project, resource)
        tm.that(path.read_text(encoding="utf-8"), eq=source)
        outcome = tm.ok(u.Cli.run([sys.executable, "-c", probe], cwd=tmp_path))
        tm.that(outcome.stdout.strip(), eq=expected)

    def test_late_alias_import_does_not_prove_runtime_availability(
        self, tmp_path: Path
    ) -> None:
        """A class may execute before a later module import becomes available."""
        source = f"""from __future__ import annotations
from {c.Infra.PKG_CORE_UNDERSCORE} import m
class Number(m.BaseModel):
    value: int | float
from {c.Infra.PKG_CORE_UNDERSCORE} import t
"""
        path = tmp_path / "late_consumer.py"
        path.write_text(source, encoding="utf-8")
        transformer = FlextInfraRefactorTypingUnifier(
            canonical_map=c.Infra.TYPING_INLINE_UNION_CANONICAL_MAP
        )
        with infra.rope_workspace(tmp_path) as rope:
            resource = rope.resource(path)
            assert resource is not None
            project = rope.rope_project
            with pytest.raises(ValueError, match="requires a runtime binding"):
                transformer.transform(project, resource)
        tm.that(path.read_text(encoding="utf-8"), eq=source)
        probe = "from late_consumer import Number\nprint(Number.model_validate_json('{\"value\": 1.25}').value)\n"
        outcome = tm.ok(u.Cli.run([sys.executable, "-c", probe], cwd=tmp_path))
        tm.that(outcome.stdout.strip(), eq="1.25")

    def test_owning_package_import_is_not_injected_during_initialization(
        self, tmp_path: Path
    ) -> None:
        """Package initialization keeps the valid pre-facade consumer executable."""
        package = tmp_path / "src" / "initialization_demo"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(
            "from .__version__ import consume\n"
            f"from {c.Infra.PKG_CORE_UNDERSCORE} import t\n",
            encoding="utf-8",
        )
        source = "from __future__ import annotations\ndef consume(value: int | float) -> int | float:\n    return value\n"
        path = package / "__version__.py"
        path.write_text(source, encoding="utf-8")
        transformer = FlextInfraRefactorTypingUnifier(
            canonical_map=c.Infra.TYPING_INLINE_UNION_CANONICAL_MAP, file_path=path
        )
        with infra.rope_workspace(tmp_path) as rope:
            resource = rope.resource(path)
            assert resource is not None
            project = rope.rope_project
            with pytest.raises(ValueError, match="owning package facade"):
                transformer.transform(project, resource)
        tm.that(path.read_text(encoding="utf-8"), eq=source)
        probe = "from typing import get_type_hints\nfrom initialization_demo import consume\nprint(consume(1.25), get_type_hints(consume)['value'] == (int | float))\n"
        outcome = tm.ok(u.Cli.run([sys.executable, "-c", probe], cwd=package.parent))
        tm.that(outcome.stdout.strip(), eq="1.25 True")

    def test_new_external_alias_keeps_get_type_hints_available(
        self, tmp_path: Path
    ) -> None:
        """An unassociated consumer may import its declared external type owner."""
        source = "from __future__ import annotations\ndef consume(value: int | float) -> None:\n    pass\n"
        transformer = FlextInfraRefactorTypingUnifier(
            canonical_map=c.Infra.TYPING_INLINE_UNION_CANONICAL_MAP
        )
        updated, _changes = transformer.apply_to_source(source)
        (tmp_path / "external_consumer.py").write_text(updated, encoding="utf-8")
        probe = (
            "from typing import get_type_hints\n"
            "from pydantic import TypeAdapter\n"
            "from external_consumer import consume\n"
            "print(TypeAdapter(get_type_hints(consume)['value']).validate_json('1.25'))\n"
        )
        outcome = tm.ok(u.Cli.run([sys.executable, "-c", probe], cwd=tmp_path))
        tm.that(outcome.stdout.strip(), eq="1.25")
