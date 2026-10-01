"""Module, facade, and size rules for strict FLEXT namespaces."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, config, u

from .base import FlextInfraNamespaceRulesBase

if TYPE_CHECKING:
    from flext_infra import m, p, t


class FlextInfraNamespaceRulesStructure(FlextInfraNamespaceRulesBase):
    """Enforce one-class modules and explicit facade composition."""

    @classmethod
    def _is_functional_module(cls, tree: p.AttributeProbe) -> bool:
        """Return whether a module only re-exports symbols or runs an entry.

        Why: the operational ``r/e/x/h/d/s`` re-export modules
        and the ``python -m`` entrypoint stub carry no class by law. The shape
        is derived from the AST — imports, the export manifest, the ``__main__``
        guard and one exit call — so the exemption follows what the module IS,
        never a hardcoded list of file names.
        """
        statements = tuple(getattr(tree, "body", ()) or ())
        if cls.outer_classes(tree):
            return False
        entry_calls: list[str] = []
        has_export_manifest = False
        for statement in statements:
            kind = cls.kind(statement)
            if kind in {"Import", "ImportFrom"}:
                continue
            if cls._module_docstring(statement):
                continue
            if kind in {"Assign", "AnnAssign"} and cls._dunder_assignment(statement):
                has_export_manifest = True
                continue
            if kind == "Raise":
                continue
            if kind == "If":
                # The ``python -m`` guard holds the exit CALL (e.g.
                # ``raise SystemExit(main())``), not a function definition —
                # collect every call target so the entrypoint check sees it.
                entry_calls.extend(
                    cls.dotted_name(getattr(call, "func", None)).rsplit(".", 1)[-1]
                    for call in cls.walk(statement)
                    if cls.kind(call) == "Call"
                )
                continue
            if kind == "Expr" and cls.kind(getattr(statement, "value", None)) == "Call":
                called = cls.dotted_name(
                    getattr(getattr(statement, "value", None), "func", None),
                )
                entry_calls.append(called.rsplit(".", 1)[-1])
                continue
            # A non-dunder assignment, a type alias or any other statement is
            # loose data: the module is a data module and stays fully graded.
            return False
        # An ``__main__`` guard must terminate through the package
        # entrypoint (``...main()``); a pure re-export (operational
        # r/e/x/h/d/s) carries no call at all and is functional too.
        # Terminal wrappers (``SystemExit``/``sys.exit``/``builtins.exit``)
        # only forward the entrypoint's return code, so the real terminator is
        # the ``...main()`` call nested inside them.
        # Functional shape needs POSITIVE evidence: an entrypoint call chain
        # ending in ``...main()`` or an export manifest. A module that merely
        # lacks disqualifying statements (imports only, no class, no
        # ``__all__``) is incomplete data and stays fully graded — an empty
        # ``entry_calls`` never proves an entrypoint (``all([])`` is True).
        entrypoint_calls = [
            name for name in entry_calls if not name.lower().endswith("exit")
        ]
        if entrypoint_calls:
            return all(name.endswith("main") for name in entrypoint_calls)
        return has_export_manifest

    @classmethod
    def check_structure(
        cls,
        tree: p.AttributeProbe,
        filepath: Path,
        *,
        class_stem: str,
        policy: m.Infra.NamespaceModulePolicy,
        source: str,
    ) -> t.StrSequence:
        """Return structural and logical-size violations for one module.

        ``filepath`` is project-relative; a module under the project's
        ``tests/`` tree expects its facade class to carry the ``Tests`` prefix.
        """
        if filepath.name in {"__init__.py", "__version__.py"}:
            return ()
        if cls._is_functional_module(tree):
            return ()
        messages: list[str] = []
        classes = cls.outer_classes(tree)
        exports = u.Infra.public_export_names_source(source)
        if policy.expected_alias is not None and not any(
            cls._canonical_facade_alias(node, tree, policy=policy, exports=exports)
            for node in getattr(tree, "body", ()) or ()
        ):
            messages.append(
                f"{filepath}:1 — facade {policy.expected_alias!r} must bind and publish "
                f"its local owner {policy.expected_family!r} in __all__",
            )
        expected = (
            policy.expected_family
            if policy.expected_alias is not None and policy.expected_family is not None
            else f"Tests{class_stem}"
            if c.Infra.DIR_TESTS in filepath.parts
            else class_stem
        )
        if len(classes) < 1:
            messages.append(
                f"{filepath}:1 — module must declare at least one top-level class; "
                f"found {len(classes)}",
            )
        facade_classes = [
            node
            for node in classes
            if isinstance(getattr(node, "name", ""), str)
            and getattr(node, "name", "").startswith(expected)
        ]
        if not facade_classes:
            messages.append(
                f"{filepath}:1 — module must declare at least one class starting with "
                f"{expected!r} (the facade class)",
            )
        for node in facade_classes:
            name = getattr(node, "name", "")
            if expected and isinstance(name, str) and not name.startswith(expected):
                messages.append(
                    f"{filepath}:{cls.line(node)} — class {name!r} must start with "
                    f"{expected!r}",
                )
        # Secondary support classes at module level are allowed in facade modules;
        # only the facade class must satisfy the naming and nesting rules.
        for node in getattr(tree, "body", ()) or ():
            kind = cls.kind(node)
            if kind in {"FunctionDef", "AsyncFunctionDef"} and not (
                filepath.name == "cli.py" and cls.name_of(node) == "main"
            ):
                messages.append(
                    f"{filepath}:{cls.line(node)} — top-level function is forbidden; "
                    "nest behavior in the module class",
                )
            if kind in {"Assign", "AnnAssign"} and not (
                cls._dunder_assignment(node)
                or cls._canonical_facade_alias(
                    node,
                    tree,
                    policy=policy,
                    exports=exports,
                )
            ):
                messages.append(
                    f"{filepath}:{cls.line(node)} — module alias/data declaration is "
                    "forbidden; use the canonical facade class",
                )
            if kind == "Expr" and not cls._module_docstring(node):
                messages.append(
                    f"{filepath}:{cls.line(node)} — import-time expression is forbidden",
                )
        logical = sum(
            1
            for node in cls.walk(tree)
            if cls.kind(node) in c.Infra.NAMESPACE_LOGICAL_STATEMENT_KINDS
        )
        # The per-module ceiling is the gated config key loc_cap.max_lines;
        # this rule and the loc-cap gate share that one source.
        cap = config.Infra.codegen.loc_cap.max_lines
        if logical > cap:
            messages.append(
                f"{filepath}:1 — {logical} logical statements exceed the {cap} limit",
            )
        messages.extend(cls._facade_shape(tree, filepath, policy=policy))
        return cls.violations("NS-STRUCT", messages)

    @classmethod
    def _facade_shape(
        cls,
        tree: p.AttributeProbe,
        filepath: Path,
        *,
        policy: m.Infra.NamespaceModulePolicy,
    ) -> t.StrSequence:
        """Validate declared facade composition using real inherited namespaces."""
        if policy.expected_alias is None:
            return ()
        classes = cls.outer_classes(tree)
        if len(classes) != 1:
            return (f"{filepath}:1 — facade must declare exactly one outer class",)
        outer = classes[0]
        messages: list[str] = []
        if not (getattr(outer, "bases", ()) or ()):
            messages.append(
                f"{filepath}:{cls.line(outer)} — facade must extend its declared owner",
            )
        if policy.expected_alias not in c.Infra.FAMILY_DIRECTORIES:
            return tuple(messages)
        nested = tuple(
            node
            for node in (getattr(outer, "body", ()) or ())
            if cls.kind(node) == "ClassDef"
        )
        if len(nested) > 1:
            messages.append(
                f"{filepath}:{cls.line(outer)} — facade must compose one local namespace",
            )
        elif (
            not nested
            and not policy.inherited_namespaces
            and not (
                filepath.stem == policy.expected_alias
                and filepath.stem in c.Infra.NAMESPACE_SETTINGS_IMPORT_ALLOWED_OWNERS
            )
            and filepath.name != "base.py"
        ):
            messages.append(
                f"{filepath}:{cls.line(outer)} — facade must declare or inherit "
                "a nested namespace through its actual MRO",
            )
        elif nested:
            minimum_bases = (
                1 if policy.is_internal_namespace else c.Infra.FACADE_MINIMUM_BASES
            )
            if len(getattr(nested[0], "bases", ()) or ()) < minimum_bases:
                messages.append(
                    f"{filepath}:{cls.line(nested[0])} — local namespace must compose "
                    "its declared family bases",
                )
        return tuple(messages)

    @classmethod
    def _canonical_facade_alias(
        cls,
        node: p.AttributeProbe,
        tree: p.AttributeProbe,
        *,
        policy: m.Infra.NamespaceModulePolicy,
        exports: t.StrSequence,
    ) -> bool:
        """Accept the published binding selected by the shared semantic policy."""
        if cls.kind(node) not in {"Assign", "AnnAssign"}:
            return False
        value = getattr(node, "value", None)
        if value is None:
            return False
        alias = policy.expected_alias
        facade_class_name = policy.expected_family
        if facade_class_name is None:
            return False
        classes = cls.outer_classes(tree)
        facade_classes = [
            node for node in classes if getattr(node, "name", "") == facade_class_name
        ]
        if not facade_classes:
            return False
        facade = facade_classes[0]
        targets = getattr(node, "targets", ()) or (getattr(node, "target", None),)
        value_is_class = (
            cls.kind(value) == "Name" and cls.name_of(value) == facade_class_name
        )
        value_is_global_singleton = (
            cls.kind(value) == "Call"
            and cls.dotted_name(getattr(value, "func", None))
            == f"{facade_class_name}.fetch_global"
        )
        if alias is None and value_is_global_singleton and len(targets) == 1:
            # A declared singleton is a value, not a class facade alias. Its
            # existing factory binding remains owned by its local class.
            alias = cls.name_of(targets[0])
        if not (
            cls.kind(node) in {"Assign", "AnnAssign"}
            and len(targets) == 1
            and cls.kind(targets[0]) == "Name"
            and cls.name_of(targets[0]) == alias
            and alias in exports
            and (value_is_class or value_is_global_singleton)
            and cls.line(node) > cls.line(facade)
        ):
            return False
        return all(
            cls._dunder_assignment(statement) or cls._module_docstring(statement)
            for statement in (getattr(tree, "body", ()) or ())
            if cls.line(statement) > cls.line(node)
        )

    @classmethod
    def _dunder_assignment(cls, node: p.AttributeProbe) -> bool:
        """Allow only the export manifest at module level."""
        targets = (
            getattr(node, "targets", ())
            if cls.kind(node) == "Assign"
            else (getattr(node, "target", None),)
        )
        return any(cls.name_of(target) == "__all__" for target in targets)

    @classmethod
    def _module_docstring(cls, node: p.AttributeProbe) -> bool:
        """Return whether an expression is a module docstring."""
        value: p.AttributeProbe = getattr(node, "value", None)
        # Statements such as definitions and
        # ``pass`` have no expression value; keep node_kind strict for real nodes.
        if value is None:
            return False
        return cls.kind(value) == "Constant" and isinstance(
            getattr(value, "value", None),
            str,
        )


__all__: list[str] = ["FlextInfraNamespaceRulesStructure"]
