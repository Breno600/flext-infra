"""Source-bases composite facade over the inventory and runtime parts.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path

from flext_infra import m, t
from flext_infra._utilities import (
    FlextInfraUtilitiesRopeSourceBasesInventory,
    FlextInfraUtilitiesRopeSourceBasesRuntime,
)


class FlextInfraUtilitiesRopeSourceBases:
    """Source-bases composite facade over the inventory and runtime parts."""

    @classmethod
    def inventory(
        cls,
        request: m.Infra.SourceBindingInventoryRequest,
        definitions: MutableMapping[str, m.Infra.SourceClassDefinition],
    ) -> t.MappingKV[str, m.Infra.SourceClassReference | None]:
        """Index lexical bindings without installing a cross-module Rope overlay.

        Returns:
            The module's explicit lexical bindings, including value shadowing.

        """
        return FlextInfraUtilitiesRopeSourceBasesInventory.inventory(
            request,
            definitions,
        )

    @classmethod
    def runtime_bases(
        cls,
        project: t.Infra.RopeProject,
        sources: t.MappingKV[str, t.Pair[Path, str]],
        roots: t.StrSequence,
        extra_module_aliases: t.MappingKV[str, str] | None = None,
    ) -> t.StrTuple:
        """Resolve owned classes in C3 order and external classes through Rope.

        Only configured roots mark model evaluation boundaries. No first-party
        module is imported or resolved from disk when its planned source exists.
        Provider reexports follow Rope's declared import provenance. Their source
        declarations, not Rope's possibly incomplete superclass inference, supply
        the ordered bases. Missing references and invalid inheritance fail
        loudly.

        Returns:
            Sorted configured roots and derived Ruff-qualified base expressions.

        """
        return FlextInfraUtilitiesRopeSourceBasesRuntime.runtime_bases(
            project,
            sources,
            roots,
            extra_module_aliases,
        )


# The flat module-level re-export: the package lazy map and the
# internal from-import contract resolve this name at module scope
# (the S6 nesting moved the class inside the family facade).

__all__: list[str] = ["FlextInfraUtilitiesRopeSourceBases"]
