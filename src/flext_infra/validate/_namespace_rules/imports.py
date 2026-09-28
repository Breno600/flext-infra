"""Import-order and public-boundary rules for strict FLEXT namespaces."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c

from .base import FlextInfraNamespaceRulesBase

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraNamespaceRulesImports(FlextInfraNamespaceRulesBase):
    """Enforce the forward layer chain and facade-only local imports."""

    @classmethod
    def check_imports(
        cls, tree: p.AttributeProbe, filepath: Path, *, package_name: str
    ) -> t.StrSequence:
        """Return import-boundary violations for one module."""
        owner = cls.layer_of_path(filepath)
        messages: list[str] = []
        for node, type_only in cls.imports_with_context(tree):
            if cls.kind(node) == "Import":
                messages.extend(
                    cls._check_plain_import(
                        node,
                        filepath,
                        package_name=package_name,
                        owner=owner,
                        type_only=type_only,
                    )
                )
                continue
            messages.extend(
                cls._check_from_import(
                    node,
                    filepath,
                    package_name=package_name,
                    owner=owner,
                    type_only=type_only,
                )
            )
        return cls.violations("NS-IMPORT", messages)

    @classmethod
    def _check_plain_import(
        cls,
        node: p.AttributeProbe,
        filepath: Path,
        *,
        package_name: str,
        owner: str | None,
        type_only: bool,
    ) -> t.StrSequence:
        """Validate local ``import module`` declarations."""
        messages: list[str] = []
        for alias in getattr(node, "names", ()) or ():
            module = getattr(alias, "name", "")
            if not isinstance(module, str) or not module.startswith(package_name):
                continue
            if getattr(alias, "asname", None):
                messages.append(
                    f"{filepath}:{cls.line(node)} — local import aliases are forbidden"
                )
            imported = cls.layer_of_module(module, package_name)
            violation = cls._reverse_import(owner, imported, type_only=type_only)
            if violation:
                messages.append(f"{filepath}:{cls.line(node)} — {violation}: {module}")
            if cls._private_bypass(module, filepath):
                messages.append(
                    f"{filepath}:{cls.line(node)} — import through the public facade, "
                    f"not {module!r}"
                )
        return tuple(messages)

    @classmethod
    def _check_from_import(
        cls,
        node: p.AttributeProbe,
        filepath: Path,
        *,
        package_name: str,
        owner: str | None,
        type_only: bool,
    ) -> t.StrSequence:
        """Validate local ``from module import symbol`` declarations."""
        module = getattr(node, "module", "")
        if not isinstance(module, str) or not module.startswith(package_name):
            return ()
        messages: list[str] = [
            f"{filepath}:{cls.line(node)} — local import aliases are forbidden"
            for alias in (getattr(node, "names", ()) or ())
            if getattr(alias, "asname", None)
        ]
        imported = cls.layer_of_module(module, package_name)
        if module == package_name:
            imported_aliases = tuple(
                getattr(alias, "name", "")
                for alias in (getattr(node, "names", ()) or ())
            )
            ranks = {
                name: name
                for name in (
                    *c.Infra.NAMESPACE_LAYER_ORDER,
                    *c.Infra.NAMESPACE_OPERATION_FACADES,
                )
                if name in imported_aliases
            }
            for imported_name in ranks:
                violation = cls._reverse_import(
                    owner, imported_name, type_only=type_only
                )
                if violation:
                    messages.append(
                        f"{filepath}:{cls.line(node)} — {violation}: {imported_name}"
                    )
        else:
            violation = cls._reverse_import(owner, imported, type_only=type_only)
            if violation:
                messages.append(f"{filepath}:{cls.line(node)} — {violation}: {module}")
        if cls._private_bypass(module, filepath):
            messages.append(
                f"{filepath}:{cls.line(node)} — import through the public facade, "
                f"not {module!r}"
            )
        return tuple(messages)

    @staticmethod
    def _private_bypass(module: str, filepath: Path) -> bool:
        """Return whether a local private family is imported outside its facade."""
        for family, layer in c.Infra.NAMESPACE_LAYER_BY_FAMILY.items():
            if not family.startswith("_") or f".{family}" not in module:
                continue
            facade_file = next(
                (
                    filename
                    for filename, candidate in c.Infra.NAMESPACE_LAYER_BY_FILE.items()
                    if candidate == layer and not filename.startswith("_")
                ),
                "",
            )
            return filepath.name != facade_file and family not in filepath.parts
        return False

    @staticmethod
    def _reverse_import(
        owner: str | None, imported: str | None, *, type_only: bool
    ) -> str | None:
        """Describe a backward runtime edge, allowing it only for type checking.

        Settings/config owners legitimately declare nested Pydantic namespace
        models and so require the declaration facades ``m``/``t``/``u`` at
        runtime (BaseModel, Field, MappingKV, model_validator, JsonValue).
        Operator ruling 2026-09-19: settings defaults also read declared
        constants — ``AlgarOudMigSettings``-style layers bind
        ``= c.<Namespace>.CONSTANT`` as Pydantic field defaults — so ``c`` is
        allowed at runtime in settings owners exactly like the declaration
        facades; constants are the layer whose purpose is to be consumed.
        Direct ``pydantic`` remains prohibited (ENFORCE-070); only the project
        facades are permitted. The forward chain still applies to ``p`` and to
        every operational facade ``r/e/x/h/d/s``.
        """
        if owner is None or imported is None or type_only:
            return None
        if owner in c.Infra.NAMESPACE_SETTINGS_IMPORT_ALLOWED_OWNERS and (
            imported in _DECLARATION_FACADES_RUNTIME or imported == "c"
        ):
            return None
        order = c.Infra.NAMESPACE_LAYER_ORDER
        owner_rank = order.index(owner) if owner in order else len(order)
        imported_rank = order.index(imported) if imported in order else len(order)
        if imported in c.Infra.NAMESPACE_OPERATION_FACADES:
            imported_rank = order.index("base")
        if imported_rank > owner_rank:
            return "reverse runtime import; later layers are TYPE_CHECKING-only"
        return None


# Why (cosmos-3flk9): settings/config are Pydantic declaration layers —
# their field and factory surface (BaseModel, Field, ConfigDict,
# model_validator, JsonValue, resolve_env_file) legitimately lives on the
# class/types/utility facades. ``c`` and ``p`` stay forward-chain-only and
# the operational r/e/x/h/d/s keep their base-layer rank (below).
# Derived from the canonical chain law (NAMESPACE_LAYER_ORDER): the
# declaration facades sit between c and base, and p is excluded because the
# protocols facade is TYPE_CHECKING-only — never a runtime import.
_DECLARATION_FACADES_RUNTIME: frozenset[str] = frozenset(
    layer
    for layer in c.Infra.NAMESPACE_LAYER_ORDER[
        c.Infra.NAMESPACE_LAYER_ORDER.index("c")
        + 1 : c.Infra.NAMESPACE_LAYER_ORDER.index("base")
    ]
    if layer != "p"
)


__all__: list[str] = ["FlextInfraNamespaceRulesImports"]
