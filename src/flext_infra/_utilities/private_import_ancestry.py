"""Static lexical inheritance discovery for public facade cutover.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast

from flext_infra import t
from flext_infra._utilities._private_import_ancestry_collector import (
    _ClassBaseCollector,
)


class FlextInfraUtilitiesPrivateImportAncestry:
    """Resolve bases using bindings present when each class is declared."""

    @staticmethod
    def class_bases(
        sources: t.MappingKV[str, t.Pair[str, bool]],
    ) -> t.MappingKV[str, t.VariadicTuple[str]]:
        """Index static class ancestry, including private intermediate owners.

        Returns:
            The resulting ``t.MappingKV[str, t.VariadicTuple[str]]``.

        """
        bases: t.MutableMappingKV[str, t.VariadicTuple[str]] = {}
        for module, (source, is_package) in sources.items():
            tree = ast.parse(source, filename=module)
            package = module if is_package else module.rpartition(".")[0]
            collector = _ClassBaseCollector(
                module=module,
                package=package,
            )
            collector.collect_root(tree.body)
            bases.update(collector.bases)
        return bases


__all__: list[str] = ["FlextInfraUtilitiesPrivateImportAncestry"]
