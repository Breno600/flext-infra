"""Runtime behavior of the generated structural protocol assembly."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import get_type_hints

import pytest

from flext_infra import t
from flext_infra.codegen.protocol_models import FlextInfraCodegenProtocolModels

MEMBER = "demo_member"

PYPROJECT = '[project]\nname = "demo-member"\nversion = "0.1.0"\n'

MODELS = '''\
"""Demo member models."""


from flext_core import m, t


type Permuted[First, Second] = tuple[Second, First]
type Repeated[Value] = tuple[Value, Value]
type Unused[Value, Ignored] = tuple[Value, ...]
type Identity[Value] = Value
type Nested[Value] = Permuted[Value, list[Value]]


class Order(m.FrozenModel):
    """A validated order."""

    sku: str = m.Field(description="Stock keeping unit of the ordered item.")
    quantity: int = m.Field(default=1, description="Number of units ordered.")
    tags: t.VariadicTuple[str] = m.Field(default=(), description="Order labels.")
    permuted: Permuted[int, str] = m.Field(
        default=("tag", 1), description="Order type parameter permutation."
    )
    repeated: Repeated[int] = m.Field(
        default=(1, 2), description="Order type parameter repetition."
    )
    unused: Unused[str, int] = m.Field(
        default=(), description="Order type parameter tail."
    )
    identity: Identity[str] = m.Field(
        default="identity", description="Order type parameter identity."
    )
    nested: Nested[int] = m.Field(
        default=([1], 1), description="Order type parameter nesting."
    )
    factory: type[str] = m.Field(default=str, description="Order factory type.")


class Shipment(m.FrozenModel):
    """A validated shipment referencing its order."""

    order: Order | None = m.Field(default=None, description="Shipped order.")


type Payload = Order | Shipment


class DemoMemberModels:
    """Member models container."""

    Order = Order
    Shipment = Shipment
    Payload = Payload
'''

PROTOCOLS = '''\
"""Demo member protocols container."""

from demo_member._protocols.manual_ports import ManualPort

__all__ = ["DemoMemberProtocols", "ManualPort"]


class DemoMemberProtocols:
    """Member protocols container."""

    ManualPort = ManualPort
'''

MANUAL_PORTS = '''\
"""Hand-declared ports; the generator never regenerates these."""

from typing import Protocol


class ManualPort(Protocol):
    """A hand-owned structural port."""

    def bind(self) -> bool:
        """Bind the port."""
        ...
'''

CONSUMER = '''\
"""Consumer referencing the member protocols facade."""

from demo_member import p


def ship(order: p.DemoMember.Order) -> p.DemoMember.Payload:
    """Consume the structural contracts."""
    raise NotImplementedError
'''

TYPINGS = '''\
"""Demo member typings container."""


from flext_core import t


class DemoMemberTypes:
    """Member typings container."""

    VariadicTuple = t.VariadicTuple
'''


def _write_member(root: Path) -> None:
    """Materialize the demo member on disk."""
    package = root / "src" / MEMBER
    (package / "_protocols").mkdir(parents=True)
    (root / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "models.py").write_text(MODELS, encoding="utf-8")
    (package / "protocols.py").write_text(PROTOCOLS, encoding="utf-8")
    (package / "typings.py").write_text(TYPINGS, encoding="utf-8")
    (package / "consumer.py").write_text(CONSUMER, encoding="utf-8")
    (package / "_protocols" / "manual_ports.py").write_text(
        MANUAL_PORTS, encoding="utf-8"
    )


def _load_module(path: Path) -> ModuleType:
    """Import one real module from its file path."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        msg = f"cannot import {path}"
        raise RuntimeError(msg)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def member_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Provide a real importable demo member for the generator."""
    _purge_member_modules()
    _write_member(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path / "src"))
    yield tmp_path
    _purge_member_modules()


def _purge_member_modules() -> None:
    """Drop cached demo-member modules so imports re-read the member on disk."""
    for key in [key for key in sys.modules if key.startswith(MEMBER)]:
        del sys.modules[key]
    importlib.invalidate_caches()


def _service(root: Path, *, apply: bool) -> FlextInfraCodegenProtocolModels:
    """Build the generator service against the member root."""
    return FlextInfraCodegenProtocolModels(repository_root=root, apply_changes=apply)


def test_apply_generates_runtime_checkable_contracts(member_root: Path) -> None:
    """Applying assembles generated modules whose protocols hold at runtime."""
    result = _service(member_root, apply=True).execute()
    assert result.success, result.error
    generated_dir = member_root / "src" / MEMBER / "_protocols"
    part = generated_dir / "generated_models_models_01.py"
    assert part.is_file()
    content = part.read_text(encoding="utf-8")
    assert content.startswith("# AUTO-GENERATED FILE")
    assert "@runtime_checkable" in content
    assert "class Order(Protocol):" in content
    assert "def quantity(self) -> int:" in content
    assert "p.DemoMember.Order | None" in content
    assert "p.DemoMember.Order" in content
    assert "ManualPort" not in content
    aggregate = generated_dir / "generated_models.py"
    assert "class DemoMemberProtocolsGeneratedModels:" in aggregate.read_text(
        encoding="utf-8"
    )
    module = _load_module(part)
    models = importlib.import_module("demo_member.models")

    generated = module.ModelsProtocolsGeneratedPart01
    assert isinstance(models.Order(sku="a"), generated.Order)


@pytest.mark.parametrize(
    ("field_name", "expected"),
    [
        ("tags", tuple[str, ...]),
        ("permuted", tuple[str, int]),
        ("repeated", tuple[int, int]),
        ("unused", tuple[str, ...]),
        ("identity", str),
        ("nested", tuple[list[int], int]),
        ("factory", type[str]),
    ],
)
def test_generated_annotations_resolve_specialized_aliases(
    member_root: Path, field_name: str, expected: t.TypeHintSpecifier
) -> None:
    """Real consumers resolve specialized aliases without free parameters."""
    result = _service(member_root, apply=True).execute()
    assert result.success, result.error
    part = member_root / "src" / MEMBER / "_protocols" / "generated_models_models_01.py"
    module = _load_module(part)
    generated = module.ModelsProtocolsGeneratedPart01.Order
    accessor = getattr(generated, field_name)

    assert get_type_hints(accessor.fget)["return"] == expected
    models = importlib.import_module("demo_member.models")
    assert isinstance(models.Order(sku="alias consumer"), generated)


def test_apply_is_idempotent(member_root: Path) -> None:
    """A second apply rewrites nothing; check-only passes on fresh output."""
    assert _service(member_root, apply=True).execute().success
    part = member_root / "src" / MEMBER / "_protocols" / "generated_models_models_01.py"
    before = part.read_bytes()
    assert _service(member_root, apply=True).execute().success
    assert part.read_bytes() == before
    assert _service(member_root, apply=False).execute().success


def test_check_only_reports_drift(member_root: Path) -> None:
    """Check-only fails naming the drifted module after a model change."""
    assert _service(member_root, apply=True).execute().success
    models_path = member_root / "src" / MEMBER / "models.py"
    models_path.write_text(
        MODELS.replace(
            'sku: str = m.Field(description="Stock keeping unit of the ordered item.")',
            'sku: str = m.Field(description="Stock keeping unit of the ordered item.")\n'
            '    weight: float = m.Field(default=1.0, description="Drift probe weight.")',
        ),
        encoding="utf-8",
    )
    for name in [key for key in sys.modules if key.startswith(MEMBER)]:
        del sys.modules[name]
    importlib.invalidate_caches()
    result = _service(member_root, apply=False).execute()
    assert not result.success
    assert result.error is not None
    assert "drifted" in result.error


def test_unresolved_reference_fails_typed(member_root: Path) -> None:
    """A referenced protocol without a model fails with the exact name."""
    consumer = member_root / "src" / MEMBER / "consumer.py"
    consumer.write_text(
        CONSUMER + "\n\ndef ghost(port: p.DemoMember.Ghost) -> None:\n    ...\n",
        encoding="utf-8",
    )
    result = _service(member_root, apply=True).execute()
    assert not result.success
    assert result.error is not None
    assert "Ghost" in result.error
