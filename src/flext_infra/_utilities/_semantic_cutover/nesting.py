"""Automatic class-nesting plans derived from the public Rope workspace.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from typing import TYPE_CHECKING

from flext_infra import m, r, t
from flext_infra._utilities._semantic_cutover.edits import (
    FlextInfraUtilitiesSemanticCutoverEdits,
)
from flext_infra._utilities._semantic_cutover.family_flatten import (
    FlextInfraUtilitiesSemanticFamilyFlatten,
)
from flext_infra._utilities._semantic_cutover.nesting_cst import (
    FlextInfraUtilitiesSemanticCutoverNestingCst,
)
from flext_infra._utilities._semantic_cutover.nesting_owner import (
    FlextInfraUtilitiesSemanticCutoverNestingOwner,
)
from flext_infra._utilities._semantic_cutover.test_helpers import (
    FlextInfraUtilitiesSemanticTestHelpers,
)
from flext_infra._utilities.namespace import FlextInfraUtilitiesCodegenNamespace
from flext_infra._utilities.rope_runtime_modules import (
    FlextInfraUtilitiesRopeRuntimeModules,
)

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraUtilitiesSemanticCutoverNesting(
    FlextInfraUtilitiesSemanticTestHelpers,
    FlextInfraUtilitiesSemanticFamilyFlatten,
    FlextInfraUtilitiesSemanticCutoverNestingCst,
    FlextInfraUtilitiesSemanticCutoverNestingOwner,
    FlextInfraUtilitiesSemanticCutoverEdits,
):
    """Plan class nesting from semantic module ownership instead of record lists."""

    @staticmethod
    def _inheritance_bound_to_owner(
        classes: t.MappingKV[str, ast.ClassDef],
        owner_name: str,
    ) -> frozenset[str]:
        """Return top-level classes an owner cannot contain.

        Nesting is a definition-time move, so it fails in both directions of an
        inheritance edge. A class that inherits from the owner cannot live in
        the owner's body, because a class body cannot reference the class being
        defined around it. An owner that inherits from the class cannot contain
        it either, because the owner's base list is evaluated before its body
        exists. Either move produces a NameError at import, so both are excluded
        from the plan and stay at module level.

        Returns:
            Top-level classes an owner cannot contain.

        """

        def ancestors(name: str) -> frozenset[str]:
            found: set[str] = set()
            pending = [name]
            while pending:
                for base in classes[pending.pop()].bases:
                    current: ast.expr = base
                    while isinstance(current, ast.Attribute):
                        current = current.value
                    if (
                        isinstance(current, ast.Name)
                        and current.id in classes
                        and current.id not in found
                    ):
                        found.add(current.id)
                        pending.append(current.id)
            return frozenset(found)

        return ancestors(owner_name) | {
            name for name in classes if owner_name in ancestors(name)
        }

    @classmethod
    def _class_nesting_definitions(
        cls,
        rope_workspace: p.Infra.RopeWorkspaceDsl,
        file_path: Path,
        source: str,
    ) -> p.Result[t.StrMapping]:
        """Map each loose top-level class to the owner Rope's module policy elects.

        Returns:
            The resulting ``p.Result[t.StrMapping]``.

        """
        planned = r[t.StrMapping]
        family = FlextInfraUtilitiesCodegenNamespace.facade_family_of_file(
            file_path.name,
        ) or FlextInfraUtilitiesCodegenNamespace.facade_family_of_directory(
            file_path.parent.name,
        )
        # A dunder module (``__main__``, ``__version__``, a package init) is
        # never a facade module, whatever family directory holds it.
        if family is None or file_path.stem.startswith("__"):
            return planned.ok({})
        tree = ast.parse(source, filename=str(file_path))
        classes = {
            node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
        }
        convention = rope_workspace.convention(file_path)
        loose = cls._loose_members(
            tree,
            values=not convention.module_policy.allow_type_alias,
        )
        if len(classes) <= 1 and not loose:
            return planned.ok({})
        owned = cls._module_owner(
            convention,
            file_path,
            classes,
            cls._declared_names(tree),
        )
        if owned.failure:
            return planned.from_failure(owned)
        owner = owned.value
        movable = cls._movable_members(
            tree,
            loose,
            owner=owner,
            module_name=convention.module_name,
        )
        if movable.failure:
            return planned.from_failure(movable)
        bound: frozenset[str] = (
            cls._inheritance_bound_to_owner(classes, owner)
            if owner in classes
            else frozenset()
        )
        definitions = {
            name: owner for name in classes if name != owner and name not in bound
        }
        definitions.update((name, owner) for name in movable.value)
        return planned.ok(definitions)

    @classmethod
    def _plan_class_nesting(
        cls,
        rope_workspace: p.Infra.RopeWorkspaceDsl,
        sources: t.MappingKV[Path, str],
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Compose helper promotion, family flattening, and orphan nesting.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]``.

        """
        planned = r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]
        # The planner contract keeps every failure in the Result (see
        # plan_semantic_cutover); helper promotion raises per rejected move.
        # A promotion ValueError IS the rejected move's loud contract (one
        # utilities facade, unshadowed destination, unchanged bindings), so it
        # propagates instead of demoting to a Result the caller would retry.
        promotion = planned.create_from_callable(
            lambda: cls._test_helper_edits(rope_workspace, sources),
        )
        if promotion.failure:
            error = promotion.exception
            if isinstance(error, ValueError):
                raise error
            return promotion
        promoted = promotion.value
        proposed = dict(sources)
        merged = {edit.file_path: edit for edit in promoted}
        for edit in promoted:
            proposed[edit.file_path] = edit.updated_source
        flattened = cls._family_flatten_edits(rope_workspace, proposed)
        for edit in flattened:
            proposed[edit.file_path] = edit.updated_source
        nested = cls._plan_orphan_nesting(rope_workspace, proposed)
        if nested.failure:
            return planned.from_failure(nested)
        for edit in (*flattened, *nested.value):
            previous = merged.get(edit.file_path)
            merged[edit.file_path] = m.Infra.SemanticMigrationEdit(
                file_path=edit.file_path,
                original_source=(
                    previous.original_source if previous else edit.original_source
                ),
                updated_source=edit.updated_source,
                changes=(*previous.changes, *edit.changes)
                if previous
                else edit.changes,
            )
        return planned.ok(tuple(merged[path] for path in sorted(merged)))

    @classmethod
    def _plan_orphan_nesting(
        cls,
        rope_workspace: p.Infra.RopeWorkspaceDsl,
        sources: t.MappingKV[Path, str],
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Plan all structural nesting and consumer rewrites without effects.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]``.

        """
        planned_edits = r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]
        modules = {
            entry.file_path.resolve(): entry for entry in rope_workspace.modules()
        }
        editable = cls._editable_sources(sources)
        owned = tuple(item for item in editable if item[0] in modules)

        def definitions_for(item: t.Pair[Path, str]) -> p.Result[t.StrMapping]:
            return cls._class_nesting_definitions(rope_workspace, *item)

        planned = r[t.StrMapping].traverse(owned, definitions_for, fail_fast=False)
        if planned.failure:
            return planned_edits.from_failure(planned)
        definitions_by_file = {
            path: definitions
            for (path, _source), definitions in zip(owned, planned.value, strict=True)
            if definitions
        }
        bindings_by_module: MutableMapping[str, MutableMapping[str, str]] = {}
        for path, definitions in definitions_by_file.items():
            module_name = modules[path].module_name
            bindings = bindings_by_module.setdefault(module_name, {})
            for name, owner in definitions.items():
                if bindings.setdefault(name, owner) != owner:
                    return planned_edits.fail(
                        f"ambiguous class-nesting owner for {module_name}.{name}: "
                        f"{bindings[name]}, {owner}",
                    )
        nested_names = frozenset(
            name for bindings in bindings_by_module.values() for name in bindings
        )
        if not nested_names:
            return planned_edits.ok(())
        project = FlextInfraUtilitiesRopeRuntimeModules.snapshot_project(
            rope_workspace.rope_project,
            sources,
        )
        try:
            quoted = cls._nesting_quoted_sources(
                project,
                dict(editable),
                definitions_by_file,
            )
        finally:
            project.close()

        def rewrite(path: Path, source: str) -> t.Infra.TransformResult:
            module = modules.get(path)
            definitions = definitions_by_file.get(path, {})
            updated = cls._rewrite_class_nesting_source(
                quoted[path],
                module_name=module.module_name if module is not None else "",
                is_package_init=module.is_package_init if module is not None else False,
                bindings_by_module=bindings_by_module,
                definitions=definitions,
            )
            if definitions and updated == source:
                msg = "class-nesting owner produced no structural edit"
                raise ValueError(msg)
            return updated, tuple(
                f"nested {name} under {owner}" for name, owner in definitions.items()
            ) or ("rewired nested-class consumer",)

        return cls._semantic_edits(
            tuple(
                (path, source)
                for path, source in editable
                if path in definitions_by_file
                or quoted[path] != source
                or any(name in source for name in nested_names)
            ),
            rewrite,
        )


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverNesting"]
