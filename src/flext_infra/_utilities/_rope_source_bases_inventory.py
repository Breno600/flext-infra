"""Captured-source inventory feeding base resolution.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from importlib.util import resolve_name
from pathlib import Path

from flext_infra import m, t


class FlextInfraUtilitiesRopeSourceBasesInventory:
    """Captured-source inventory part of the source-bases composite."""

    @classmethod
    def _inventory(
        cls,
        project: t.Infra.RopeProject,
        module: str,
        path: Path,
        source: str,
        definitions: MutableMapping[str, m.Infra.SourceClassDefinition],
        *,
        required_line: int | None = None,
        allow_conditional: bool = False,
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
        from flext_infra._utilities import (
            FlextInfraUtilitiesRopeAnalysisSourceScan,
            FlextInfraUtilitiesRopeCore,
            FlextInfraUtilitiesRopeRuntime,
        )

        resource = (
            FlextInfraUtilitiesRopeCore.resolve_resource_from_path(project, path)
            if path.is_file()
            else None
        )
        parsed = FlextInfraUtilitiesRopeRuntime.build_string_module(
            project,
            source,
            resource=resource,
        ).get_ast()
        if not isinstance(parsed, ast.Module):
            message = f"Rope returned a non-module AST for {path}"
            raise TypeError(message)
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        globals_: MutableMapping[str, m.Infra.SourceClassReference | None] = {}

        def collect(
            statements: t.SequenceOf[ast.stmt],
            bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
            lexical: t.MappingKV[str, m.Infra.SourceClassReference | None],
            scope: str,
        ) -> None:
            for node in statements:
                if (
                    required_line is not None
                    and not scope
                    and node.lineno > required_line
                ):
                    break
                if isinstance(node, ast.ClassDef):
                    if (
                        required_line is not None
                        and not scope
                        and not (
                            node.lineno
                            <= required_line
                            <= (node.end_lineno or node.lineno)
                        )
                    ):
                        bindings[node.name] = m.Infra.SourceClassReference(
                            target=module,
                            attributes=tuple(f"{scope}{node.name}".split(".")),
                            qualified_base=f"{module}.{scope}{node.name}",
                        )
                        continue
                    visible = {**lexical, **bindings}
                    bases = tuple(
                        cls._reference(base, visible, module) for base in node.bases
                    )
                    if node.type_params:
                        bases = (
                            *bases,
                            m.Infra.SourceClassReference(
                                target="typing",
                                attributes=("Generic",),
                                qualified_base="typing.Generic",
                            ),
                        )
                    identity = f"{module}:{scope}{node.name}:{node.lineno}"
                    members: MutableMapping[
                        str,
                        m.Infra.SourceClassReference | None,
                    ] = {}
                    # Class locals are visible to a nested class's base expressions,
                    # but are not a closure for that nested class's own body.
                    collect(node.body, members, lexical, f"{scope}{node.name}.")
                    definitions[identity] = m.Infra.SourceClassDefinition(
                        identity=identity,
                        bases=bases,
                        members=members,
                    )
                    bindings[node.name] = m.Infra.SourceClassReference(
                        target=identity,
                        qualified_base=f"{module}.{node.name}",
                    )
                elif isinstance(node, ast.ImportFrom):
                    parts = package.split(".") if package else []
                    if node.level:
                        if node.level > len(parts):
                            message = f"Relative import escapes package in {module}"
                            raise ValueError(message)
                        prefix = ".".join(parts[: len(parts) - node.level + 1])
                        imported = ".".join(
                            part for part in (prefix, node.module) if part
                        )
                    else:
                        imported = node.module or ""
                    for alias in node.names:
                        if alias.name == "*":
                            if allow_conditional:
                                # External/installed modules re-export through
                                # star imports; the re-exported names resolve
                                # in the module's own runtime, not statically.
                                continue
                            message = (
                                f"Star import has no explicit class binding in {module}"
                            )
                            raise ValueError(message)
                        target = f"{imported}.{alias.name}"
                        binding = m.Infra.SourceClassReference(
                            target=imported,
                            attributes=(alias.name,),
                            qualified_base=target,
                        )
                        bindings[alias.asname or alias.name] = binding
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        target = (
                            alias.name if alias.asname else alias.name.partition(".")[0]
                        )
                        bindings[alias.asname or target] = m.Infra.SourceClassReference(
                            target=target,
                            qualified_base=target,
                        )
                elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = (
                        node.targets if isinstance(node, ast.Assign) else [node.target]
                    )
                    if any(not isinstance(target, ast.Name) for target in targets):
                        if allow_conditional and all(
                            isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id in bindings
                            and bindings[target.value.id] is None
                            for target in targets
                        ):
                            # Provider function metadata does not rebind a class.
                            continue
                        if allow_conditional and all(
                            isinstance(target, ast.Subscript)
                            and m.Infra.SubscriptRebind(
                                root_name=cls._subscript_root_name(target),
                            ).is_module_table_mutation
                            for target in targets
                        ):
                            # Standard-library alias re-registration (CPython's
                            # ``collections`` publishes ``sys.modules[
                            # 'collections.abc'] = _collections_abc``): an
                            # external runtime table mutation, never a class
                            # rebind — the touched names stay unknown.
                            continue
                        if (
                            len(targets) == 1
                            and isinstance(targets[0], ast.Attribute)
                            and isinstance(targets[0].value, ast.Name)
                            and targets[0].value.id in bindings
                            and bindings[targets[0].value.id] is not None
                            and isinstance(node.value, ast.Name)
                        ):
                            # Class-namespace completion rebind (``base.t = final``):
                            # a module completes a deferred base namespace and
                            # publishes the RHS class under the attribute name in
                            # its own exported namespace, so the binding map
                            # registers it exactly like a module-level alias.
                            visible = {**lexical, **bindings}
                            if (
                                node.value.id in visible
                                and visible[node.value.id] is not None
                            ):
                                reference = cls._reference(node.value, visible, module)
                                if reference is not None:
                                    bindings[targets[0].attr] = reference.model_copy(
                                        update={
                                            "qualified_base": (
                                                f"{module}.{targets[0].attr}"
                                            ),
                                        },
                                    )
                            continue
                        message = (
                            f"Unsupported class binding mutation in {module}: "
                            f"{ast.unparse(node)}"
                        )
                        raise ValueError(message)
                    value = node.value
                    if value is None:
                        continue
                    visible = {**lexical, **bindings}
                    head = value
                    while isinstance(head, (ast.Attribute, ast.Subscript)):
                        head = head.value
                    reference = (
                        cls._reference(value, visible, module)
                        if isinstance(head, ast.Name)
                        and isinstance(value, (ast.Name, ast.Attribute, ast.Subscript))
                        and not (head.id in visible and visible[head.id] is None)
                        else None
                    )
                    for target in targets:
                        if isinstance(target, ast.Name):
                            bindings[target.id] = (
                                reference.model_copy(
                                    update={"qualified_base": f"{module}.{target.id}"},
                                )
                                if reference is not None
                                else None
                            )
                elif (
                    isinstance(node, ast.AugAssign)
                    and allow_conditional
                    and isinstance(node.target, ast.Name)
                ):
                    bindings[node.target.id] = None
                elif (
                    isinstance(node, ast.Delete)
                    and allow_conditional
                    and all(isinstance(target, ast.Name) for target in node.targets)
                ):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            bindings.pop(target.id, None)
                elif isinstance(node, (ast.Delete, ast.AugAssign)):
                    # An augmented assignment or deletion mutates an existing
                    # object and never declares a class binding; a Name target
                    # reads as an unknown binding going forward.
                    if isinstance(node, ast.AugAssign) and isinstance(
                        node.target,
                        ast.Name,
                    ):
                        bindings.setdefault(node.target.id, None)
                    continue
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    bindings[node.name] = None
                elif isinstance(node, ast.If):
                    match node.test:
                        case ast.Compare(
                            left=ast.Name(id="__name__"),
                            ops=[ast.Eq()],
                            comparators=[ast.Constant(value="__main__")],
                        ):
                            collect(
                                node.body if module == "__main__" else node.orelse,
                                bindings,
                                lexical,
                                scope,
                            )
                            continue
                    if isinstance(node.test, ast.Constant) and isinstance(
                        node.test.value,
                        bool,
                    ):
                        collect(
                            node.body if node.test.value else node.orelse,
                            bindings,
                            lexical,
                            scope,
                        )
                        continue
                    if cls._is_type_checking_test(node.test):
                        # A TYPE_CHECKING gate never executes at runtime; its
                        # imports and assignments are the module's declared
                        # static binding surface, so they index directly.
                        collect(node.body, bindings, lexical, scope)
                        continue
                    # Non-constant conditions with class declarations
                    # (pydantic's own version-dependent models, read from
                    # the runtime environment) have no statically knowable
                    # class-ness: the conditional names bind as None so the
                    # base derivation degrades them exactly like any other
                    # non-class binding.
                    conditional = {
                        child.name
                        for statement in (*node.body, *node.orelse)
                        for child in ast.walk(statement)
                        if isinstance(child, ast.ClassDef)
                    }
                    left = dict(bindings)
                    right = dict(bindings)
                    for name in conditional:
                        left[name] = None
                        right[name] = None
                    collect(node.body, left, lexical, scope)
                    collect(node.orelse, right, lexical, scope)
                    for name in left.keys() | right.keys():
                        bindings[name] = (
                            left[name]
                            if name in left
                            and name in right
                            and left[name] == right[name]
                            else None
                        )
                elif isinstance(node, (ast.Try, ast.TryStar)):
                    if not allow_conditional:
                        message = (
                            f"Conditional exception-backed class bindings in {module}"
                        )
                        raise ValueError(message)
                    # External/installed modules may carry conditional imports:
                    # their bindings resolve at that module's own runtime, not
                    # statically, so the names read as unknown here while any
                    # nested declarations still join the definition inventory.
                    conditional: MutableMapping[
                        str,
                        m.Infra.SourceClassReference | None,
                    ] = {}
                    collect(node.body, conditional, lexical, scope)
                    collect(node.orelse, conditional, lexical, scope)
                    for handler in node.handlers:
                        collect(handler.body, conditional, lexical, scope)
                    for name in conditional:
                        bindings[name] = None

        collect(parsed.body, globals_, globals_, "")
        targets, references = (
            FlextInfraUtilitiesRopeAnalysisSourceScan.lazy_import_mapping_source(source)
        )
        if references and not module.startswith(("tests.", "tests.")):
            # Test and benchmark modules build installer maps at runtime from
            # the constants they exercise; the declared-mapping invariant
            # gates the production lazy-init modules only.
            message = (
                f"Unresolved declared lazy import mapping in {module}: {references}"
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
                    qualified_base=f"{module}.{name}",
                )
        return globals_
