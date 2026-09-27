"""Import migration preserves live bindings and embedded source payloads."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, infra, u
from flext_infra.transformers.import_modernizer import (
    FlextInfraRefactorImportModernizer,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestsImportModernizerRuntime:
    """Exercise migrated Pydantic consumers through their public runtime."""

    @pytest.mark.parametrize(
        ("declaration", "base", "field"),
        [
            (
                "from pydantic import BaseModel as Parent, Field as declare",
                "Parent",
                "declare",
            ),
            ("import pydantic as pd", "pd.BaseModel", "pd.Field"),
        ],
    )
    def test_import_aliases_keep_models_and_quoted_annotations_importable(
        self, tmp_path: Path, declaration: str, base: str, field: str
    ) -> None:
        """Alias changes preserve schema metadata, homonyms and multiline data."""
        payload = 'from pydantic import BaseModel, Field\nclass Row(BaseModel):\n    value = Field(description="BaseModel ] café, ☃")\nprint("BaseModel ] café, ☃")\n'
        source = f'''from typing import Annotated as A, Literal as L
{declaration}
from pydantic import RootModel

PAYLOAD = """{payload}"""

def local(BaseModel):
    return BaseModel

class Row({base}):
    value: A[str, {field}(description="BaseModel ] café, ☃")]
    kind: L["BaseModel ] café, ☃"] = "BaseModel ] café, ☃"

def describe(value: "{base}") -> 'A[{base}, "BaseModel ] café, ☃"]':
    return value

type RowBase = A["{base}", "BaseModel ] café, ☃"]

class Rows(RootModel[list["{base}"]]):
    pass
'''
        transformer = FlextInfraRefactorImportModernizer(
            imports_to_remove=["pydantic"],
            symbols_to_replace={"BaseModel": "m.BaseModel", "Field": "m.Field"},
            runtime_aliases={"m"},
            blocked_aliases=set(),
        )
        path = tmp_path / "import_consumer.py"
        path.write_text(source, encoding="utf-8")
        with infra.rope_workspace(tmp_path) as rope:
            resource = rope.resource(path)
            assert resource is not None
            _updated, changes = transformer.transform(rope.rope_project, resource)
        tm.that(bool(changes), eq=True)
        probe = f"""from typing import get_args, get_type_hints
from flext_core import cli
from pydantic import TypeAdapter
from {c.Infra.PKG_CORE_UNDERSCORE} import m
from import_consumer import PAYLOAD, Row, RowBase, Rows, describe, local
row = Row.model_validate_json('{{"value": "live"}}')
hints = get_type_hints(describe, include_extras=True)
cli.print(row.value, local("kept"))
cli.print(Row.model_fields["value"].description)
cli.print(hints["value"] is m.BaseModel, get_args(hints["return"])[0] is m.BaseModel)
cli.print(get_args(hints["return"])[1])
cli.print(PAYLOAD == {payload!r})
cli.print(TypeAdapter(RowBase).validate_python(row) is row)
cli.print(Rows.model_validate([row]).root[0] is row)
"""
        outcome = tm.ok(u.Cli.run([sys.executable, "-c", probe], cwd=tmp_path))
        tm.that(
            outcome.stdout.splitlines(),
            eq=[
                "live kept",
                "BaseModel ] café, ☃",
                "True True",
                "BaseModel ] café, ☃",
                "True",
                "True",
                "True",
            ],
        )

    def test_embedded_source_does_not_create_outer_imports(self) -> None:
        """Ordinary strings are not import declarations or symbol consumers."""
        source = '''PAYLOAD = """from pydantic import BaseModel, Field
class Row(BaseModel):
    value = Field(description="Field ] café, ☃")
"""
'''
        transformer = FlextInfraRefactorImportModernizer(
            imports_to_remove=["pydantic"],
            symbols_to_replace={"BaseModel": "m.BaseModel", "Field": "m.Field"},
            runtime_aliases={"m"},
            blocked_aliases=set(),
        )
        updated, changes = transformer.apply_to_source(source)
        tm.that(updated, eq=source)
        tm.that(changes, eq=[])

    @pytest.mark.parametrize(
        "collision",
        [
            "import pathlib as m\nclass Row(BaseModel):\n    pass\n",
            "m = 1\nclass Row(BaseModel):\n    pass\n",
            "def build(m):\n    class Row(BaseModel):\n        pass\n    return Row\n",
            "class Host:\n    m = 1\n    class Row(BaseModel):\n        pass\n",
        ],
    )
    def test_competing_destination_binding_rejects_the_complete_rewrite(
        self, collision: str
    ) -> None:
        """An unrelated import or local binding cannot capture a facade path."""
        source = f"from pydantic import BaseModel\n{collision}"
        transformer = FlextInfraRefactorImportModernizer(
            imports_to_remove=["pydantic"],
            symbols_to_replace={"BaseModel": "m.BaseModel"},
            runtime_aliases={"m"},
            blocked_aliases=set(),
        )
        with pytest.raises(ValueError, match=r"capture|declared facade"):
            transformer.apply_to_source(source)

    def test_existing_derived_facade_is_preserved(self, tmp_path: Path) -> None:
        """The declared project facade remains the consumer's runtime owner."""
        source = """from flext_infra import m
from pydantic import BaseModel
class Row(BaseModel):
    value: str
"""
        transformer = FlextInfraRefactorImportModernizer(
            imports_to_remove=["pydantic"],
            symbols_to_replace={"BaseModel": "m.BaseModel"},
            runtime_aliases={"m"},
            blocked_aliases=set(),
        )
        updated, _changes = transformer.apply_to_source(source)
        (tmp_path / "derived_consumer.py").write_text(updated, encoding="utf-8")
        probe = """from flext_core import cli
from flext_infra import m
from derived_consumer import Row, m as owner
cli.print(owner is m, Row.model_validate_json('{"value": "live"}').value)
"""
        outcome = tm.ok(u.Cli.run([sys.executable, "-c", probe], cwd=tmp_path))
        tm.that(outcome.stdout.strip(), eq="True live")

    def test_exported_binding_requires_its_consumer_cutover(self) -> None:
        """A public re-export cannot disappear from an import-only source rewrite."""
        source = "from pydantic import BaseModel\n__all__ = ['BaseModel']\n"
        transformer = FlextInfraRefactorImportModernizer(
            imports_to_remove=["pydantic"],
            symbols_to_replace={"BaseModel": "m.BaseModel"},
            runtime_aliases={"m"},
            blocked_aliases=set(),
        )
        with pytest.raises(ValueError, match="re-export consumers"):
            transformer.apply_to_source(source)

    def test_conditional_imports_execute_on_each_original_route(
        self, tmp_path: Path
    ) -> None:
        """Each branch and a runtime consumer of TYPE_CHECKING retain imports."""
        source = f"""from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from {c.Infra.PKG_CORE_UNDERSCORE} import m

def build(flag):
    if flag:
        from pydantic import BaseModel
        class Row(BaseModel):
            value: str
        return Row.model_validate_json('{{"value": "branch"}}').value
    else:
        from pydantic import Field
        return Field(description="other branch").description

from pydantic import BaseModel
class RuntimeRow(BaseModel):
    value: str
"""
        transformer = FlextInfraRefactorImportModernizer(
            imports_to_remove=["pydantic"],
            symbols_to_replace={"BaseModel": "m.BaseModel", "Field": "m.Field"},
            runtime_aliases={"m"},
            blocked_aliases=set(),
        )
        updated, _changes = transformer.apply_to_source(source)
        (tmp_path / "conditional_consumer.py").write_text(updated, encoding="utf-8")
        probe = """from flext_core import cli
from conditional_consumer import build, RuntimeRow
cli.print(build(True), build(False))
cli.print(RuntimeRow.model_validate_json('{"value": "runtime"}').value)
"""
        outcome = tm.ok(u.Cli.run([sys.executable, "-c", probe], cwd=tmp_path))
        tm.that(outcome.stdout.splitlines(), eq=["branch other branch", "runtime"])

    @pytest.mark.parametrize(
        "expression",
        [
            "TypeVar('T', bound='BaseModel')",
            "NewType('N', 'BaseModel')",
            "cast('BaseModel', None)",
        ],
    )
    def test_deferred_typing_calls_reject_incomplete_import_migration(
        self, expression: str
    ) -> None:
        """Unsupported deferred call consumers retain their complete source contract."""
        source = f"from typing import TypeVar, NewType, cast\nfrom pydantic import BaseModel\nvalue = {expression}\n"
        transformer = FlextInfraRefactorImportModernizer(
            imports_to_remove=["pydantic"],
            symbols_to_replace={"BaseModel": "m.BaseModel"},
            runtime_aliases={"m"},
            blocked_aliases=set(),
        )
        with pytest.raises(ValueError, match="deferred typing-call consumer"):
            transformer.apply_to_source(source)

    @pytest.mark.parametrize(
        "access",
        [
            "    before = m.BaseModel\n",
            "    def read():\n        return m.BaseModel\n    before = read()\n",
        ],
    )
    def test_local_import_rejects_capture_of_existing_ancestor_reads(
        self, tmp_path: Path, access: str
    ) -> None:
        """The rejected rewrite leaves direct reads and closure reads executable."""
        source = f"from {c.Infra.PKG_CORE_UNDERSCORE} import m\ndef build():\n{access}    from pydantic import BaseModel\n    return before is BaseModel\n"
        path = tmp_path / "ancestral_consumer.py"
        path.write_text(source, encoding="utf-8")
        transformer = FlextInfraRefactorImportModernizer(
            imports_to_remove=["pydantic"],
            symbols_to_replace={"BaseModel": "m.BaseModel"},
            runtime_aliases={"m"},
            blocked_aliases=set(),
        )
        with infra.rope_workspace(tmp_path) as rope:
            resource = rope.resource(path)
            assert resource is not None
            project = rope.rope_project
            with pytest.raises(ValueError, match="capture ancestral binding"):
                transformer.transform(project, resource)
        tm.that(path.read_text(encoding="utf-8"), eq=source)
        probe = "from ancestral_consumer import build\nprint(build())\n"
        outcome = tm.ok(u.Cli.run([sys.executable, "-c", probe], cwd=tmp_path))
        tm.that(outcome.stdout.strip(), eq="True")
