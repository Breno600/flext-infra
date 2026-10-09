"""Qualified runtime-base discovery over captured, unpublished source.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path

from flext_infra import m, t
from flext_infra._utilities._rope_source_bases_aliases import (
    FlextInfraUtilitiesRopeSourceBasesAliases,
)
from flext_infra._utilities._rope_source_bases_inventory import (
    FlextInfraUtilitiesRopeSourceBasesInventory,
)
from flext_infra._utilities._rope_source_bases_runtime import (
    FlextInfraUtilitiesRopeSourceBasesRuntime,
)


class FlextInfraUtilitiesRopeSourceBases:
    """Source-bases composite facade over the inventory, aliases, and runtime parts."""

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
    def lazy_module_aliases(
        cls,
        module: str,
        path: Path,
        source: str,
    ) -> t.StrMapping:
        """Read the ``install_lazy_exports`` namespace alias map of one module.

        Returns:
            The module's facade alias names routed to their lazy module paths.

        """
        return FlextInfraUtilitiesRopeSourceBasesAliases.lazy_module_aliases(
            module,
            path,
            source,
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


__all__: list[str] = ["FlextInfraUtilitiesRopeSourceBases"]
