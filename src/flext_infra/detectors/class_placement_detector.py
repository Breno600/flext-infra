"""Detect classes declared outside their canonical family locations via rope.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, m, u

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraClassPlacementDetector:
    """Detect misplaced class declarations across the five FLEXT families."""

    @staticmethod
    def detect_file(
        ctx: m.Infra.DetectorContext,
    ) -> t.SequenceOf[m.Infra.ClassPlacementViolation]:
        """Detect classes and class-level constants outside canonical families."""
        res = u.Infra.fetch_python_resource(
            ctx.rope_project, ctx.file_path, skip_protected=True, skip_settings=True
        )
        if res is None:
            return []
        file_path = ctx.file_path
        if "ai_hub/hook_client" in file_path.as_posix():
            # ADR-0018 stdlib island: class-level constants are mandated to
            # stay inside the standalone native client.
            return []
        parts = file_path.parts
        violations: list[m.Infra.ClassPlacementViolation] = []
        governed_classes = (
            FlextInfraClassPlacementDetector._governed_classes_with_family(
                ctx.rope_project, res
            )
        )

        # 1. Misplaced governed classes → family relocation action.
        for ci, family in governed_classes:
            if FlextInfraClassPlacementDetector._in_canonical_location(
                family, parts, file_path.name
            ):
                continue
            violations.append(
                FlextInfraClassPlacementDetector._violation_for_class(
                    ctx=ctx, ci=ci, family=family
                )
            )

        # 2. Class-level constants outside _constants → classvar_relocation action.
        #    Covers explicit ClassVar annotations AND implicit UPPER_CASE
        #    constant-like assignments (no ClassVar annotation).
        if not FlextInfraClassPlacementDetector._in_canonical_location(
            "c", parts, file_path.name
        ):
            classvar_violations: list[m.Infra.ClassPlacementViolation] = []
            for ci in FlextInfraClassPlacementDetector._public_classes(
                ctx.rope_project, res
            ):
                classvar_violations.extend(
                    m.Infra.ClassPlacementViolation(
                        file=str(file_path),
                        line=constant.line,
                        name=constant.name,
                        base_class=ci.name,
                        suggestion=(
                            f"Move constant {constant.name} "
                            f"from {ci.name} to _constants"
                        ),
                        action="classvar_relocation",
                        fixable=True,
                        target_facade=FlextInfraClassPlacementDetector._target_facade(
                            ctx, "c"
                        ),
                        family="c",
                    )
                    for constant in FlextInfraClassPlacementDetector._class_constants(
                        ctx.rope_project, res, class_name=ci.name
                    )
                )
            violations.extend(classvar_violations)

        # 3. Misplaced type aliases → deep_namespace_refactor action.
        for alias_name, alias_line in FlextInfraClassPlacementDetector._type_aliases(
            ctx.rope_project, res
        ):
            if FlextInfraClassPlacementDetector._in_canonical_location(
                "t", parts, file_path.name
            ):
                continue
            violations.append(
                m.Infra.ClassPlacementViolation(
                    file=str(file_path),
                    line=alias_line,
                    name=alias_name,
                    base_class="TypeAlias",
                    suggestion=(
                        f"Move type alias {alias_name} to typings.py or _typings/"
                    ),
                    action="deep_namespace_refactor",
                    fixable=False,
                    target_facade=FlextInfraClassPlacementDetector._target_facade(
                        ctx, "t"
                    ),
                    family="t",
                )
            )

        return violations

    @staticmethod
    def _governed_classes_with_family(
        rope_project: t.Infra.RopeProject, resource: t.Infra.RopeResource
    ) -> t.VariadicTuple[t.Pair[m.Infra.ClassInfo, str]]:
        """Return public governed classes with their family letters."""
        results: list[t.Pair[m.Infra.ClassInfo, str]] = []
        for ci in u.Infra.get_class_info(rope_project, resource):
            if ci.name.startswith("_"):
                continue
            family = u.Infra.class_family(ci)
            if not family:
                continue
            results.append((ci, family))
        return tuple(results)

    @staticmethod
    def _violation_for_class(
        *, ctx: m.Infra.DetectorContext, ci: m.Infra.ClassInfo, family: str
    ) -> m.Infra.ClassPlacementViolation:
        """Build a ClassPlacementViolation for a misplaced class."""
        return m.Infra.ClassPlacementViolation(
            file=str(ctx.file_path),
            line=ci.line,
            name=ci.name,
            base_class=ci.bases[0] if ci.bases else "object",
            suggestion=FlextInfraClassPlacementDetector._suggestion_for_family(family),
            action="relocate_facade_class",
            fixable=True,
            target_facade=FlextInfraClassPlacementDetector._target_facade(ctx, family),
            family=family,
        )

    @staticmethod
    def _in_canonical_location(
        family: str, parts: t.VariadicTuple[str], file_name: str
    ) -> bool:
        """Return True when the file already lives in the canonical family area."""
        dir_sets = {
            "m": c.Infra.PLACEMENT_CANONICAL_MODEL_DIRS,
            "p": c.Infra.PLACEMENT_CANONICAL_PROTOCOL_DIRS,
            "c": c.Infra.PLACEMENT_CANONICAL_CONSTANTS_DIRS,
            "u": c.Infra.PLACEMENT_CANONICAL_UTILITY_DIRS,
            "t": c.Infra.PLACEMENT_CANONICAL_TYPING_DIRS,
        }
        file_sets = {
            "m": c.Infra.PLACEMENT_CANONICAL_MODEL_FILES,
            "p": c.Infra.PLACEMENT_CANONICAL_PROTOCOL_FILES,
            "c": c.Infra.PLACEMENT_CANONICAL_CONSTANTS_FILES,
            "u": c.Infra.PLACEMENT_CANONICAL_UTILITY_FILES,
            "t": c.Infra.PLACEMENT_CANONICAL_TYPING_FILES,
        }
        if file_name in file_sets.get(family, frozenset()):
            return True
        return bool(set(parts) & dir_sets.get(family, frozenset()))

    @staticmethod
    def _suggestion_for_family(family: str) -> str:
        """Return a human-readable relocation suggestion for a family."""
        return {
            "m": "Move Pydantic model class to models.py or _models/",
            "p": "Move Protocol class to protocols.py or _protocols/",
            "c": "Move Enum constant class to constants.py or _constants/",
            "u": "Move utility class to utilities.py or _utilities/",
            "t": "Move type alias to typings.py or _typings/",
        }.get(family, "Move class to canonical family location")

    @staticmethod
    def _target_facade(ctx: m.Infra.DetectorContext, family: str) -> str:
        """Return the canonical facade class name for a family and project."""
        stem = u.derive_class_stem(ctx.project_name) if ctx.project_name else ""
        suffix = c.Infra.FAMILY_SUFFIXES.get(family, "")
        return f"{stem}{suffix}" if stem and suffix else ""

    @staticmethod
    def _public_classes(
        rope_project: t.Infra.RopeProject, resource: t.Infra.RopeResource
    ) -> t.SequenceOf[m.Infra.ClassInfo]:
        """Return public top-level classes from the current Rope AST."""
        tree = u.Infra.get_pymodule(rope_project, resource).get_ast()
        classes: list[m.Infra.ClassInfo] = []
        for node in getattr(tree, "body", ()) or ():
            if u.Infra.node_kind(u.Infra.ensure_ast_node(node)) != "ClassDef":
                continue
            name = getattr(node, "name", "")
            if not isinstance(name, str) or not name or name.startswith("_"):
                continue
            line = getattr(node, "lineno", 1)
            classes.append(
                m.Infra.ClassInfo(
                    name=name,
                    line=line if isinstance(line, int) and line > 0 else 1,
                    bases=(),
                )
            )
        return tuple(classes)

    @staticmethod
    def _class_body_nodes(
        tree: t.Infra.RopeAstNode, *, class_name: str
    ) -> t.SequenceOf[t.Infra.RopeAstNode]:
        """Return direct body nodes for the top-level class named ``class_name``."""
        module_body = getattr(tree, "body", None) or ()
        if not isinstance(module_body, (list, tuple)):
            return ()
        for node in module_body:
            if u.Infra.node_kind(u.Infra.ensure_ast_node(node)) != "ClassDef":
                continue
            if getattr(node, "name", "") == class_name:
                class_body = getattr(node, "body", None) or ()
                if not isinstance(class_body, (list, tuple)):
                    return ()
                return tuple(
                    body_node
                    for body_node in class_body
                    if u.Infra.is_ast_node(body_node)
                )
        return ()

    @staticmethod
    def _class_constants(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        *,
        class_name: str,
    ) -> t.SequenceOf[m.Infra.ConstantInfo]:
        """Return class-level constants declared in ``class_name``'s body.

        Includes explicit ``ClassVar[...]`` annotations and implicit
        UPPER_CASE assignments whose value looks like a canonical constant.
        """
        pymodule = u.Infra.get_pymodule(rope_project, resource)
        tree = pymodule.get_ast()
        body = FlextInfraClassPlacementDetector._class_body_nodes(
            tree, class_name=class_name
        )
        constants: list[m.Infra.ConstantInfo] = []
        for node in body:
            node_kind = u.Infra.node_kind(u.Infra.ensure_ast_node(node))
            if node_kind == "AnnAssign":
                constant = FlextInfraClassPlacementDetector._annassign_constant(node)
            elif node_kind == "Assign":
                constant = FlextInfraClassPlacementDetector._assign_constant(node)
            else:
                continue
            if constant is not None:
                constants.append(constant)
        return tuple(constants)

    @staticmethod
    def _namespace_constant_name(target: p.AttributeProbe) -> str | None:
        """Return the public namespace-constant name bound by ``target``.

        ``None`` for a private, exempt, or non-constant binding.
        """
        if not u.Infra.is_ast_node(target):
            return None
        target_name = u.Infra.name_of(target)
        if not target_name or target_name.startswith("_"):
            return None
        if target_name in c.Infra.CLASSVAR_EXEMPT_NAMES:
            return None
        if not c.Infra.NAMESPACE_CONSTANT_PATTERN.match(target_name):
            return None
        return target_name

    @staticmethod
    def _constant_info(
        node: p.AttributeProbe, target_name: str
    ) -> m.Infra.ConstantInfo:
        """Return one constant record placed at the node's line, defaulting to 1."""
        line = getattr(node, "lineno", 1)
        return m.Infra.ConstantInfo(
            name=target_name, line=line if isinstance(line, int) and line > 0 else 1
        )

    @staticmethod
    def _annassign_constant(node: t.Infra.RopeAstNode) -> m.Infra.ConstantInfo | None:
        """Return ConstantInfo for an AnnAssign node, or None if not a violation."""
        target_name = FlextInfraClassPlacementDetector._namespace_constant_name(
            getattr(node, "target", None)
        )
        if target_name is None:
            return None
        annotation = getattr(node, "annotation", None)
        has_classvar = FlextInfraClassPlacementDetector._annotation_contains(
            annotation, "ClassVar"
        )
        value = getattr(node, "value", None)
        if (
            not has_classvar
            and not FlextInfraClassPlacementDetector._classvar_value_permitted(value)
        ):
            return None
        return FlextInfraClassPlacementDetector._constant_info(node, target_name)

    @staticmethod
    def _assign_constant(node: t.Infra.RopeAstNode) -> m.Infra.ConstantInfo | None:
        """Return ConstantInfo for an implicit Assign node, or None if not a violation."""
        targets = getattr(node, "targets", None)
        if not isinstance(targets, (list, tuple)) or len(targets) != 1:
            return None
        target_name = FlextInfraClassPlacementDetector._namespace_constant_name(
            targets[0]
        )
        if target_name is None:
            return None
        value = getattr(node, "value", None)
        if not FlextInfraClassPlacementDetector._classvar_value_permitted(value):
            return None
        return FlextInfraClassPlacementDetector._constant_info(node, target_name)

    @staticmethod
    def _type_aliases(
        rope_project: t.Infra.RopeProject, resource: t.Infra.RopeResource
    ) -> t.SequenceOf[t.Pair[str, int]]:
        """Return module-level type aliases as (name, line) pairs."""
        pymodule = u.Infra.get_pymodule(rope_project, resource)
        tree = pymodule.get_ast()
        aliases: list[t.Pair[str, int]] = []
        for node in getattr(tree, "body", []) or []:
            kind = u.Infra.node_kind(u.Infra.ensure_ast_node(node))
            if kind == "TypeAlias":
                name = getattr(node, "name", None)
                name_str = getattr(name, "id", str(name)) if name else ""
                line = getattr(node, "lineno", 1)
                if name_str:
                    aliases.append((name_str, line))
                continue
            if kind == "AnnAssign":
                annotation = getattr(node, "annotation", None)
                if not FlextInfraClassPlacementDetector._annotation_contains(
                    annotation, "TypeAlias"
                ):
                    continue
                target = getattr(node, "target", None)
                if not u.Infra.is_ast_node(target):
                    continue
                target_name = u.Infra.name_of(target)
                line = getattr(node, "lineno", 1)
                if target_name:
                    aliases.append((target_name, line))
        return tuple(aliases)

    @staticmethod
    def _annotation_contains(annotation: t.Infra.RopeAstNode | None, name: str) -> bool:
        """Return True when ``name`` appears in any sub-node identifier."""
        if annotation is None:
            return False
        for sub in u.Infra.walk_ast_nodes(u.Infra.ensure_ast_node(annotation)):
            if u.Infra.name_of(sub) == name:
                return True
        return False

    @staticmethod
    def _classvar_value_permitted(value: t.Infra.RopeAstNode | None) -> bool:
        """Return True when a ClassVar default is a literal/canonical constant."""
        if value is None:
            return True
        kind = u.Infra.node_kind(u.Infra.ensure_ast_node(value))
        if kind in {"Constant", "Name", "Attribute", "Tuple", "List", "Set", "Dict"}:
            return True
        if kind == "Call":
            func = getattr(value, "func", None)
            if not u.Infra.is_ast_node(func):
                return False
            func_name = u.Infra.name_of(func)
            if func_name in c.Infra.CLASSVAR_ALLOWED_CALLS:
                return True
            if u.Infra.node_kind(u.Infra.ensure_ast_node(func)) == "Attribute":
                base = getattr(func, "value", None)
                base_name = getattr(base, "id", "")
                return base_name in c.Infra.CLASSVAR_ALLOWED_CALLS
        return False


__all__: list[str] = ["FlextInfraClassPlacementDetector"]
