"""Conservative binding proof for canonical model-field boundary guards.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast

from flext_infra._utilities._semantic_cutover.bindings import (
    FlextInfraUtilitiesSemanticCutoverBindings,
)


class FlextInfraUtilitiesSemanticCutoverModelFieldsBindings(
    FlextInfraUtilitiesSemanticCutoverBindings,
):
    """Reject shadowed builtins and guard facades instead of guessing identity."""

    @classmethod
    def _require_unshadowed_guard(cls, tree: ast.Module) -> None:
        """Require every referenced builtin and the imported guard to be unbound.

        Raises:
            ValueError: If model-class narrowing conflicts with a local binding; or if
                model-class narrowing cannot resolve wildcard imports; or if model-class
                guard dependency has a different owner.

        """
        required = {"u", "isinstance", "type", "getattr", "object", "dict"}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) and required.intersection(
                cls.bound_identifiers(node),
            ):
                msg = "model-class narrowing conflicts with a local binding"
                raise ValueError(msg)
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        msg = "model-class narrowing cannot resolve wildcard imports"
                        raise ValueError(msg)
                    canonical = (
                        node.module == "flext_core"
                        and not node.level
                        and alias.name == "u"
                        and alias.asname is None
                    )
                    if (alias.asname or alias.name) in required and not canonical:
                        msg = "model-class guard dependency has a different owner"
                        raise ValueError(msg)


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverModelFieldsBindings"]
