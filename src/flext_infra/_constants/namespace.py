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


__all__: list[str] = ["FlextInfraConstantsNamespace"]
