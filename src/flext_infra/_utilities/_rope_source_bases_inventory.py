"""Captured-source inventory feeding base resolution.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from importlib.util import resolve_name

from flext_infra import m, t


class FlextInfraUtilitiesRopeSourceBasesInventory:
    """Captured-source inventory part of the source-bases composite."""

    @classmethod
    def inventory(
        cls,
        request: m.Infra.SourceBindingInventoryRequest,
        definitions: MutableMapping[str, m.Infra.SourceClassDefinition],
    ) -> t.MappingKV[str, m.Infra.SourceClassReference | None]:
        """Index lexical bindings without installing a cross-module Rope overlay.

        A provider class is indexed at its native declaration line. Unreferenced
        module-level provider classes remain qualified declarations, not fabricated
        lineages. A captured class owns its nested declaration identities.

        Returns:
            The module's explicit lexical bindings, including value shadowing.

        Raises:
            TypeError: If Rope does not return a module AST.
            ValueError: If a required binding has unsupported source semantics.

        """
        from flext_infra._utilities import FlextInfraUtilitiesRopeAnalysisSourceScan, FlextInfraUtilitiesRopeCore, FlextInfraUtilitiesRopeRuntime, FlextInfraUtilitiesRopeSourceBindingCollector
        resource = (
            FlextInfraUtilitiesRopeCore.resolve_resource_from_path(
                request.project,
                request.path,
            )
            if request.path.is_file()
            else None
        )
        parsed = FlextInfraUtilitiesRopeRuntime.build_string_module(
            request.project,
            request.source,
            resource=resource,
        ).get_ast()
        if not isinstance(parsed, ast.Module):
            message = f"Rope returned a non-module AST for {request.path}"
            raise TypeError(message)
        package = (
            request.module
            if request.path.name == "__init__.py"
            else request.module.rpartition(".")[0]
        )
        globals_: MutableMapping[str, m.Infra.SourceClassReference | None] = {}
        spec = m.Infra.SourceBindingCollectorSpec(
            module=request.module,
            package=package,
            required_line=request.required_line,
            allow_conditional=request.allow_conditional,
            definitions=definitions,
            lexical=globals_,
        )
        FlextInfraUtilitiesRopeSourceBindingCollector.collect(
            spec,
            parsed.body,
            globals_,
            "",
        )
        targets, references = (
            FlextInfraUtilitiesRopeAnalysisSourceScan.lazy_import_mapping_source(
                request.source,
            )
        )
        if references and not request.module.startswith(("tests.", "tests.")):
            # Test and benchmark modules build installer maps at runtime from
            # the constants they exercise; the declared-mapping invariant
            # gates the production lazy-init modules only.
            message = (
                f"Unresolved declared lazy import mapping in {request.module}: "
                f"{references}"
            )
            raise ValueError(message)
        for target, exports in targets:
            destination = (
                resolve_name(target, package) if target.startswith(".") else target
            )
            for name in exports:
                globals_[name] = m.Infra.SourceClassReference(
                    target=destination,
                    attributes=(name,),
                    qualified_base=f"{request.module}.{name}",
                )
        return globals_
