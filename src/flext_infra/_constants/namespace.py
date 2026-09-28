"""Bootstrap-safe namespace constants."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsNamespace:
    """Namespace constants shared by bootstrap-sensitive utilities."""

    NAMESPACE_SETTINGS_FILE_NAMES: ClassVar[frozenset[str]] = frozenset({
        "settings.py",
        "_settings.py",
    })
    NAMESPACE_PROTECTED_FILES: ClassVar[frozenset[str]] = frozenset({
        "settings.py",
        "_settings.py",
        "typings.py",
        "_typings.py",
        "__init__.py",
        "__main__.py",
        "__version__.py",
        "conftest.py",
        "py.typed",
    })
    NAMESPACE_LAYER_ORDER: ClassVar[t.VariadicTuple[str]] = (
        "settings",
        "config",
        "c",
        "t",
        "p",
        "m",
        "u",
        "base",
        "services",
        "api",
        "cli",
    )
    NAMESPACE_OPERATION_FACADES: ClassVar[t.VariadicTuple[str]] = (
        "r",
        "e",
        "x",
        "h",
        "d",
        "s",
    )
    # Carve-out D1 (decision A, handoff §1.3): settings/config owners (the only
    # rank-0/1 layers that declare nested Pydantic namespace-models) may import
    # the declaration facades m/t/u at runtime — BaseModel/Field/typings/
    # MappingKV/JSON/JsonValue and model_validator — exactly the canonical
    # Flext<X>Settings pattern (e.g. flext-auth/_settings.py, flext-api/_settings).
    # Direct ``pydantic`` stays prohibited (ENFORCE-070): flext-core is the sole
    # owner of pydantic. c/p and the operational facades r/e/x/h/d/s are NOT
    # covered by this carve-out and remain forward-only (TYPE_CHECKING).
    NAMESPACE_SETTINGS_IMPORT_ALLOWED_OWNERS: ClassVar[t.VariadicTuple[str]] = (
        "settings",
        "config",
    )
    # Platform service-facade singletons emitted by codegen (api.py.j2:20
    # ``{{ alias }} = {{ class_stem }}.fetch_global()``) and the canonical
    # base/services/config/settings layers. These expose a bottom singleton
    # ``alias = Class.fetch_global()`` (plain Assign or typed AnnAssign) which
    # the structure rule must recognize as canonical, not a banned module alias.
    # Handoff §1.2 layer order: ...base->services->api->cli; settings/config are
    # the rank-0/1 layers (rank-0/1 layers that declare the Flext<X>Settings).
    NAMESPACE_PLATFORM_FACADE_SINGLETONS: ClassVar[t.MappingKV[str, t.StrPair]] = (
        MappingProxyType({
            "api.py": ("api", ""),
            "base.py": ("s", "ServiceBase"),
            "_config.py": ("config", "Config"),
            "config.py": ("config", "Config"),
            "_settings.py": ("settings", "Settings"),
            "settings.py": ("settings", "Settings"),
        })
    )
    "Canonical platform facade file name -> (alias, class-name suffix)."
    NAMESPACE_LAYER_BY_FILE: ClassVar[MappingProxyType[str, str]] = MappingProxyType({
        "settings.py": "settings",
        "_settings.py": "settings",
        "config.py": "config",
        "_config.py": "config",
        "constants.py": "c",
        "typings.py": "t",
        "protocols.py": "p",
        "models.py": "m",
        "utilities.py": "u",
        "base.py": "base",
        "api.py": "api",
        "cli.py": "cli",
    })
    NAMESPACE_LAYER_BY_FAMILY: ClassVar[MappingProxyType[str, str]] = MappingProxyType({
        "_constants": "c",
        "_typings": "t",
        "_protocols": "p",
        "_models": "m",
        "_utilities": "u",
        "services": "services",
    })
    # ADR-0018 stdlib island: the native hook client runs as `python3 -I -S`
    # and cannot consume the flext typing surface; its annotations stay stdlib.
    NAMESPACE_STDLIB_ISLAND_PATH_FRAGMENTS: ClassVar[t.StrSequence] = (
        "/ai_hub/hook_client",
    )
    NAMESPACE_BANNED_ANNOTATIONS: ClassVar[frozenset[str]] = frozenset({
        "Any",
        "Optional",
        "dict",
        "object",
    })
    NAMESPACE_PYDANTIC_V1_MEMBERS: ClassVar[frozenset[str]] = frozenset({
        "parse_obj",
        "parse_raw",
        "validator",
        "root_validator",
    })
    # Attribute syntax alone cannot prove the receiver type. Ambiguous names
    # such as ``dict`` and ``json`` are intentionally absent; only Pydantic-v1-
    # exclusive members are detected without qualified import provenance.
    NAMESPACE_PYDANTIC_V1_DECORATORS: ClassVar[frozenset[str]] = frozenset({
        "validator",
        "root_validator",
    })
    NAMESPACE_SERVICE_LOCATOR_NAMES: ClassVar[frozenset[str]] = frozenset({
        "container",
        "get_service",
        "locator",
        "resolve_service",
        "service_locator",
    })
    NAMESPACE_LOGICAL_STATEMENT_KINDS: ClassVar[frozenset[str]] = frozenset({
        "AnnAssign",
        "Assert",
        "Assign",
        "AsyncFor",
        "AsyncFunctionDef",
        "AsyncWith",
        "AugAssign",
        "ClassDef",
        "Delete",
        "For",
        "FunctionDef",
        "If",
        "Match",
        "Raise",
        "Return",
        "Try",
        "TypeAlias",
        "While",
        "With",
        "Yield",
        "YieldFrom",
    })


__all__: list[str] = ["FlextInfraConstantsNamespace"]
