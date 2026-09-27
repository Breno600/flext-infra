"""Typing, Pydantic, and dependency-injection namespace rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, u

from .base import FlextInfraNamespaceRulesBase

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraNamespaceRulesContracts(FlextInfraNamespaceRulesBase):
    """Reject untyped boundaries, legacy Pydantic, and concrete wiring."""

    @classmethod
    def check_contracts(
        cls, tree: p.AttributeProbe, filepath: Path, *, source: str
    ) -> t.StrSequence:
        """Return contract and clean-architecture violations."""
        posix = filepath.as_posix()
        if any(
            frag in posix for frag in c.Infra.NAMESPACE_STDLIB_ISLAND_PATH_FRAGMENTS
        ):
            # ADR-0018 stdlib island: no flext typing surface is importable.
            return []
        messages: list[str] = []
        imported_names = u.Infra.imported_callable_names(source)
        for node in cls.walk(tree):
            kind = cls.kind(node)
            if kind in {"FunctionDef", "AsyncFunctionDef"}:
                messages.extend(cls._function_contract(node, filepath))
                for decorator in getattr(node, "decorator_list", ()) or ():
                    if cls.kind(decorator) != "Call":
                        messages.extend(
                            cls._legacy_decorator(decorator, filepath, imported_names)
                        )
            if kind in {"AnnAssign", "arg", "FunctionDef", "AsyncFunctionDef"}:
                messages.extend(cls._annotation_contract(node, filepath))
            if kind == "Call":
                messages.extend(cls._call_contract(node, filepath, imported_names))
        messages.extend(cls._composition_root(tree, filepath))
        return cls.violations("NS-CONTRACT", messages)

    @classmethod
    def _function_contract(
        cls, node: p.AttributeProbe, filepath: Path
    ) -> t.StrSequence:
        """Require typed public input/output boundaries."""
        name = getattr(node, "name", "")
        if not isinstance(name, str) or (name.startswith("_") and name != "__init__"):
            return ()
        messages: list[str] = []
        arguments = getattr(node, "args", None)
        positional = (
            *(getattr(arguments, "posonlyargs", ()) or ()),
            *(getattr(arguments, "args", ()) or ()),
            *(getattr(arguments, "kwonlyargs", ()) or ()),
        )
        for argument in positional:
            argument_name = getattr(argument, "arg", "")
            if argument_name in {"self", "cls"}:
                continue
            if getattr(argument, "annotation", None) is None:
                messages.append(
                    f"{filepath}:{cls.line(argument)} — public input {argument_name!r} "
                    "must use a typed model contract"
                )
        if getattr(node, "returns", None) is None:
            messages.append(
                f"{filepath}:{cls.line(node)} — public operation {name!r} must declare "
                "a typed output"
            )
        if name != "__init__" or "services" not in filepath.parts:
            return tuple(messages)
        for argument in positional:
            annotation = getattr(argument, "annotation", None)
            annotation_name = cls.name_of(annotation)
            dotted = cls.dotted_name(annotation)
            if annotation_name.startswith("Flext") and not dotted.startswith("p."):
                messages.append(
                    f"{filepath}:{cls.line(argument)} — service dependency "
                    f"{annotation_name!r} must be injected through p"
                )
        return tuple(messages)

    @classmethod
    def _annotation_contract(
        cls, node: p.AttributeProbe, filepath: Path
    ) -> t.StrSequence:
        """Reject broad and legacy annotation vocabulary."""
        annotations: list[object] = []
        if cls.kind(node) == "AnnAssign" or cls.kind(node) == "arg":
            annotations.append(getattr(node, "annotation", None))
        else:
            annotations.append(getattr(node, "returns", None))
        messages: list[str] = []
        for annotation in annotations:
            if annotation is None:
                continue
            names = cls._annotation_type_names(annotation)
            banned = sorted(names & c.Infra.NAMESPACE_BANNED_ANNOTATIONS)
            if banned:
                messages.append(
                    f"{filepath}:{cls.line(node)} — banned annotation(s): "
                    + ", ".join(banned)
                )
        return tuple(messages)

    @classmethod
    def _annotation_type_names(cls, annotation: p.AttributeProbe) -> frozenset[str]:
        """Collect identifier names from an annotation, skipping call subtrees.

        Pydantic field metadata such as
        ``Annotated[t.MappingKV[str, str], m.Field(default_factory=dict)]``
        embeds a runtime value (the field factory) inside the annotation AST.
        Names living inside any ``Call`` (e.g. ``default_factory=dict``) are
        construction values, not type declarations, so they are excluded.
        Genuine ``dict``/``Any``/``object`` annotations are still reported for
        codemod migration (NS-CONTRACT codemod plan, handoff §1.4).
        """
        nodes = cls.walk(annotation)
        call_descendants: set[int] = set()
        for node in nodes:
            if cls.kind(node) == "Call":
                call_descendants.update(id(d) for d in cls.walk(node))
        return frozenset(
            cls.name_of(candidate)
            for candidate in nodes
            if cls.name_of(candidate) and id(candidate) not in call_descendants
        )

    @classmethod
    def _call_contract(
        cls,
        node: p.AttributeProbe,
        filepath: Path,
        imported_names: t.MappingKV[t.Pair[int, int], frozenset[str]],
    ) -> t.StrSequence:
        """Reject legacy Pydantic calls and service-locator access."""
        callable_node = getattr(node, "func", None)
        name = cls.name_of(callable_node)
        messages: list[str] = []
        if (
            name in c.Infra.NAMESPACE_PYDANTIC_V1_MEMBERS
            and name not in c.Infra.NAMESPACE_PYDANTIC_V1_DECORATORS
            and cls.kind(callable_node) == "Attribute"
        ):
            messages.append(
                f"{filepath}:{cls.line(node)} — legacy Pydantic member {name!r}; "
                "use Pydantic v2"
            )
        messages.extend(cls._legacy_decorator(callable_node, filepath, imported_names))
        if name in c.Infra.NAMESPACE_SERVICE_LOCATOR_NAMES:
            messages.append(
                f"{filepath}:{cls.line(node)} — service locator {name!r} is forbidden; "
                "inject p contracts"
            )
        return tuple(messages)

    @classmethod
    def _legacy_decorator(
        cls,
        node: p.AttributeProbe,
        filepath: Path,
        imported_names: t.MappingKV[t.Pair[int, int], frozenset[str]],
    ) -> t.StrSequence:
        """Reject imported Pydantic v1 decorators, never same-spelled local bindings."""
        if cls.kind(node) not in {"Name", "Attribute"}:
            return ()
        names = imported_names.get(
            (cls.line(node), getattr(node, "col_offset", 0)), frozenset()
        )
        return tuple(
            f"{filepath}:{cls.line(node)} — legacy Pydantic member {member!r}; "
            "use Pydantic v2"
            for member in sorted({
                name.rpartition(".")[2]
                for name in names
                if name.startswith("pydantic.")
                and name.rpartition(".")[2] in c.Infra.NAMESPACE_PYDANTIC_V1_DECORATORS
            })
        )

    @classmethod
    def _composition_root(cls, tree: p.AttributeProbe, filepath: Path) -> t.StrSequence:
        """Permit effectful construction only inside the public API class.

        Config/settings modules define canonical singletons at module level.
        """
        if filepath.name in {
            "api.py",
            "settings.py",
            "_settings.py",
            "config.py",
            "_config.py",
        }:
            return ()
        messages: list[str] = []
        for node in getattr(tree, "body", ()) or ():
            if cls.kind(node) not in {"Assign", "AnnAssign"}:
                continue
            value = getattr(node, "value", None)
            # A bare module annotation (AnnAssign without value) constructs nothing.
            if value is not None and cls.kind(value) == "Call":
                messages.append(
                    f"{filepath}:{cls.line(node)} — import-time wiring is forbidden; "
                    "compose dependencies in api.py"
                )
        return tuple(messages)


__all__: list[str] = ["FlextInfraNamespaceRulesContracts"]
