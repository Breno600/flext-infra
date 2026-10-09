"""Project-scope analyses the rule engine evaluates for rule data.

ast-grep matches one file's syntax. Some laws are verdicts over the whole
project: whether a module takes part in an import cycle, whether a facade's
namespace composes every class its family package declares. The engine owns
building those project facts once per admission pass, from the tree as it is
then (a pass after a rewrite reads the rewritten project); rule
documents name the verdict they need through ``metadata.context`` predicates.
No rule lives here: the rule data decides where a fact is asked and what it
means.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, MutableMapping
from functools import cache, lru_cache
from importlib.metadata import packages_distributions
from importlib.util import find_spec
from pathlib import Path
from types import MappingProxyType

from flext_cli import u
from packaging.utils import canonicalize_name

from flext_infra import c, config, m, p, r, t
from flext_infra._utilities._rope_analysis.asthelpers import (
    FlextInfraUtilitiesRopeAnalysisAstHelpers,
)
from flext_infra._utilities._rope_analysis.exports import (
    FlextInfraUtilitiesRopeAnalysisExports,
)
from flext_infra._utilities._rope_analysis.importstate import (
    FlextInfraUtilitiesRopeAnalysisImportState,
    FlextInfraUtilitiesRopeCore,
    FlextInfraUtilitiesRopeImports,
    FlextInfraUtilitiesRopeRuntime,
    FlextInfraUtilitiesRopeRuntimeModules,
    FlextInfraUtilitiesRopeSourceBases,
    FlextInfraUtilitiesSemanticCutoverBindings,
    FlextInfraUtilitiesSemanticFamilyTypeReferences,
)

_RESOLVED_SYMBOL_OPERAND_COUNT = 2


class FlextInfraUtilitiesCodemodProject(FlextInfraUtilitiesCodemodRules):
    """Evaluate rule context over project facts: packages, layers, graphs."""

    @classmethod
    def project_import_graph(
        cls,
        root: Path,
    ) -> t.Pair[t.MappingKV[str, frozenset[str]], t.MappingKV[Path, str]]:
        """Return the runtime import graph and the module name of each file.

        Edges come from Rope's module-level import table, which leaves
        ``if TYPE_CHECKING:`` imports and function-local imports out: only
        imports that run when the module loads can form a cycle. Each target
        is truncated to the longest module the project defines.

        Returns:
            The runtime import graph and the module name of each file.

        Raises:
            ValueError: If rope could not name module.

        """
        raw: MutableMapping[str, set[str]] = {}
        modules: MutableMapping[Path, str] = {}
        with FlextInfraUtilitiesRopeCore.open_project(root) as project:
            for resource in FlextInfraUtilitiesRopeCore.python_resources(project):
                pymodule = FlextInfraUtilitiesRopeCore.resolve_pymodule(
                    project,
                    resource,
                )
                name = pymodule.get_name()
                if not name:
                    msg = f"rope could not name module {resource.path}"
                    raise ValueError(msg)
                path = Path(resource.real_path).resolve()
                modules[path] = name
                package = (
                    name if path.name == c.Infra.INIT_PY else name.rpartition(".")[0]
                )
                raw[name] = set(
                    FlextInfraUtilitiesRopeImports.imported_module_paths(
                        FlextInfraUtilitiesRopeCore.resolve_module_imports(
                            project,
                            resource,
                        ),
                        current_package=package,
                    ),
                )
        known = frozenset(raw)
        graph = {
            name: frozenset(
                target
                for imported in targets
                if (target := cls._known_prefix(imported, known)) is not None
                and target != name
            )
            for name, targets in raw.items()
        }
        return graph, modules

    @staticmethod
    def project_import_cycles(
        graph: t.MappingKV[str, frozenset[str]],
    ) -> t.MappingKV[str, frozenset[str]]:
        """Map each module in a runtime import cycle to its cycle's members.

        Returns:
            The resulting ``t.MappingKV[str, frozenset[str]]``.

        """
        cycles: MutableMapping[str, frozenset[str]] = {}
        for component in FlextInfraUtilitiesBase.strongly_connected_components({
            name: set(targets) for name, targets in graph.items()
        }):
            members = frozenset(component)
            if len(members) > 1:
                cycles.update(dict.fromkeys(members, members))
        return cycles

    @classmethod
    def import_closes_cycle(
        cls,
        root: Path,
        file_path: Path,
        imported: str,
        name: str | None,
        facts: m.Infra.CodemodProjectFacts,
    ) -> bool:
        """Return whether one import of ``file_path`` is an edge of a cycle.

        ``imported`` is the import's module as written (relative dots
        included); ``name`` is the imported name of a from-import, which is
        itself a module when the statement imports a submodule.

        Returns:
            Whether one import of ``file_path`` is an edge of a cycle.

        Raises:
            ValueError: If source module is absent from the project import graph.

        """
        graph, modules = facts.import_graph, facts.import_modules
        source = modules.get(file_path.resolve())
        if source is None:
            layout = FlextInfraUtilitiesCodegenNamespace.layout(root)
            if layout is not None and file_path.is_relative_to(layout.src_dir):
                msg = (
                    f"source module is absent from the project import graph: "
                    f"{file_path}"
                )
                raise ValueError(msg)
            # Project-level files are scanned by ast-grep but have no package
            # import graph node, so none of their imports can close a cycle.
            return False
        package = (
            source if file_path.name == c.Infra.INIT_PY else source.rpartition(".")[0]
        )
        level = len(imported) - len(imported.lstrip("."))
        absolute = (
            FlextInfraUtilitiesRopeAnalysisImportState.resolve_import_module(
                current_package=package,
                module_name=imported.lstrip("."),
                level=level,
            )
            if level
            else imported
        ) or package
        known = frozenset(graph)
        candidates = (f"{absolute}.{name}", absolute) if name else (absolute,)
        target = next(
            (
                found
                for candidate in candidates
                if (found := cls._known_prefix(candidate, known)) is not None
            ),
            None,
        )
        members = facts.import_cycles.get(source, frozenset())
        return target is not None and target != source and target in members

    @classmethod
    def composes_family_package(cls, facade_file: Path, namespace: str) -> bool:
        """Return whether ``namespace`` in a facade module composes its family.

        The family package of ``<pkg>/<stem>.py`` is ``<pkg>/_<stem>/``. Every
        class a module of that package declares in its ``__all__`` must be
        reachable through the bases of the facade's ``namespace`` class,
        following the bases each package class declares. A facade without a
        family package composes nothing and holds.

        Returns:
            Whether ``namespace`` in a facade module composes its family.

        """
        package = facade_file.parent / f"_{facade_file.stem}"
        if not package.is_dir():
            return True
        bases_by_class: MutableMapping[str, t.StrSequence] = {}
        exported: set[str] = set()
        for module in sorted(package.rglob(f"*{c.Infra.EXT_PYTHON}")):
            if module.name == c.Infra.INIT_PY:
                continue
            source = module.read_text(encoding=c.Cli.ENCODING_DEFAULT)
            declared = frozenset(
                FlextInfraUtilitiesRopeAnalysisExports.public_export_names_source(
                    source,
                ),
            )
            for (
                info
            ) in FlextInfraUtilitiesRopeAnalysisAstHelpers.class_info_from_source(
                source,
            ):
                bases_by_class[info.name] = tuple(info.bases)
                if info.name in declared:
                    exported.add(info.name)
        pending = list(cls._nested_class_bases(facade_file, namespace))
        reached: set[str] = set()
        while pending:
            name = pending.pop()
            if name in reached:
                continue
            reached.add(name)
            pending.extend(bases_by_class.get(name, ()))
        return exported <= reached

    @staticmethod
    def _nested_class_bases(facade_file: Path, namespace: str) -> t.StrSequence:
        """Return the base names of class ``namespace`` nested in the facade.

        Returns:
            The base names of class ``namespace`` nested in the facade.

        Raises:
            ValueError: If class.

        """
        tree = FlextInfraUtilitiesRopeAnalysisAstHelpers.parse_string_module(
            facade_file.read_text(encoding=c.Cli.ENCODING_DEFAULT),
        ).get_ast()
        for node in FlextInfraUtilitiesRopeAnalysisAstHelpers.walk_ast_nodes(tree):
            if (
                FlextInfraUtilitiesRopeAnalysisAstHelpers.node_kind(node) == "ClassDef"
                and getattr(node, "name", "") == namespace
            ):
                return tuple(
                    name
                    for base in getattr(node, "bases", ()) or ()
                    if (
                        name
                        := FlextInfraUtilitiesRopeAnalysisAstHelpers.class_base_name(
                            base,
                        )
                    )
                )
        msg = f"class {namespace} is not declared in {facade_file}"
        raise ValueError(msg)

    @classmethod
    def codemod_project_facts(
        cls,
        root: Path,
        rules: t.SequenceOf[m.Infra.CodemodRule],
    ) -> m.Infra.CodemodProjectFacts:
        """Build the project facts one admission pass needs, from the tree now.

        Only the facts the rules' predicates ask for are built: the import
        graph and cycles for ``import-cycle``, the runtime closure for the
        runtime and facade package predicates.

        Returns:
            The project facts for the predicates of ``rules``.

        """
        predicates = frozenset(
            condition.predicate for rule in rules for condition in rule.context
        )
        resolved = root.resolve()
        graph: t.MappingKV[str, frozenset[str]] = {}
        modules: t.MappingKV[Path, str] = {}
        if c.Infra.CodemodContextPredicate.IMPORT_CYCLE in predicates:
            graph, modules = cls.project_import_graph(resolved)
        return m.Infra.CodemodProjectFacts(
            predicates=predicates,
            import_graph=graph,
            import_modules=modules,
            import_cycles=cls.project_import_cycles(graph),
            runtime_modules=(
                cls._runtime_modules(resolved)
                if predicates & c.Infra.CODEMOD_RUNTIME_CLOSURE_PREDICATES
                else frozenset()
            ),
        )

    @staticmethod
    def codemod_source_path(root: Path, file_path: Path) -> Path:
        """Resolve one finding file path against its project root.

        Returns:
            The absolute source path of the finding.

        """
        return (file_path if file_path.is_absolute() else root / file_path).resolve()

    @classmethod
    def codemod_context_admits(
        cls,
        root: Path,
        rule: m.Infra.CodemodRule,
        file_path: Path,
        captures: t.JsonMapping,
        facts: m.Infra.CodemodProjectFacts,
    ) -> bool:
        """Return whether one finding satisfies its rule's project context.

        ``admission.captures`` maps each metavariable of the finding to its
        ast-grep single capture (``{"text": ...}``) or transformed value (a
        string). A declared variable the finding did not capture is a rule
        defect and raises; the syntactic match alone never stands in for it.

        ``admission.facts`` is the admission pass's project snapshot; it must
        have been built for every predicate the rule names.

        Returns:
            Whether one finding satisfies its rule's project context.

        Raises:
            ValueError: If the facts were not built for a predicate of the rule.

        """
        root = admission.root
        rule = admission.rule
        captures = admission.captures
        facts = admission.facts
        snapshot = admission.snapshot
        missing = {condition.predicate for condition in rule.context} - facts.predicates
        if missing:
            msg = (
                f"{rule.id}: project facts were not built for predicates "
                f"{sorted(missing)}"
            )
            raise ValueError(msg)
        source = cls.codemod_source_path(root, admission.file_path)
        for condition in rule.context:
            # A condition binds the capture of the branch that matched: a rule
            # variable the matching branch does not capture leaves it vacuous.
            # The plan proved every context variable occurs in the rule.
            if condition.variable not in captures:
                continue
            value = cls._captured_text(rule, condition.variable, captures, source)
            of = (
                cls._captured_text(rule, condition.of, captures, source)
                if condition.of is not None and condition.of in captures
                else None
            )
            holds = cls._context_holds(
                root.resolve(),
                condition,
                (value, of),
                source,
                facts,
            )
            if holds is not condition.holds:
                return False
        return True

    @classmethod
    def codemod_binding_snapshot(
        cls,
        root: Path,
        source_states: tuple[m.Cli.AtomicFileState, ...] = (),
        modules: t.StrSequence = (),
    ) -> m.Infra.CodemodBindingSnapshot:
        """Capture Python owners and their static import closure before inference.

        Returns:
            The resulting ``m.Infra.CodemodBindingSnapshot``.

        Raises:
            ValueError: If binding source snapshots disagree.
        """
        states: t.MutableMappingKV[Path, m.Cli.AtomicFileState] = {}
        for state in source_states:
            if states.setdefault(state.path.resolve(), state) != state:
                msg = f"binding source snapshots disagree: {state.path}"
                raise ValueError(msg)
        with FlextInfraUtilitiesRopeCore.open_project(root) as project:
            pending = [
                project.get_resource(path.relative_to(root.resolve()).as_posix())
                for path in states
            ]
            pending.extend(
                resource
                for name in modules
                if (resource := project.find_module(name)) is not None
            )
            visited: set[Path] = set()
            while pending:
                fetched = cls._snapshot_module_tree(
                    states,
                    visited,
                    pending.pop(),
                )
                if fetched is None:
                    continue
                path, resource, tree = fetched
                visited.add(path)
                pending.extend(cls._snapshot_import_resources(project, resource, tree))
        return m.Infra.CodemodBindingSnapshot(states=tuple(states.values()))

    @staticmethod
    def _snapshot_module_tree(
        states: t.MutableMappingKV[Path, m.Cli.AtomicFileState],
        visited: set[Path],
        resource: t.Infra.RopeResource,
    ) -> t.Triple[Path, t.Infra.RopeResource, ast.Module] | None:
        """Authenticate one pending module and parse its snapshot source.

        Returns:
            The resolved path, live resource, and parsed tree, or ``None``
            when the resource carries no governable Python source.

        Raises:
            TypeError: If binding package has no source resource contract.
            ValueError: If binding source is absent.

        """
        path = Path(resource.real_path).resolve()
        if path.is_dir():
            if not isinstance(resource, p.Infra.RopeRoot):
                msg = f"binding package has no source resource contract: {path}"
                raise TypeError(msg)
            # A directory without an initializer (a namespace package or
            # a compiled extension's stub folder) carries no module
            # source, so the static import closure has nothing to read.
            if not resource.has_child(c.Infra.INIT_PY):
                return None
            resource = resource.get_child(c.Infra.INIT_PY)
            path = Path(resource.real_path).resolve()
        if path in visited or not path.is_file() or path.suffix != ".py":
            return None
        state = states.get(path)
        if state is None:
            state = u.Cli.atomic_read_binary_file_state(path, required=True).unwrap()
            states[path] = state
        if state.content is None:
            msg = f"binding source is absent: {path}"
            raise ValueError(msg)
        return (
            path,
            resource,
            ast.parse(state.content.decode("utf-8"), filename=str(path)),
        )

    @classmethod
    def _snapshot_import_resources(
        cls,
        project: p.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        tree: ast.Module,
    ) -> list[t.Infra.RopeResource]:
        """Collect the Rope resources of every import inside one module tree.

        Returns:
            The pending resources named by the module's import statements.

        """
        found: list[t.Infra.RopeResource] = []
        for node in ast.walk(tree):
            found.extend(cls._snapshot_node_import_resources(project, resource, node))
        return found

    @classmethod
    def _snapshot_node_import_resources(
        cls,
        project: p.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        node: ast.AST,
    ) -> list[t.Infra.RopeResource]:
        """Collect the Rope resources of one import statement's targets.

        Returns:
            The pending resources named by the statement, possibly empty.

        """
        found: list[t.Infra.RopeResource] = []
        imports = (
            tuple(alias.name for alias in node.names)
            if isinstance(node, ast.Import)
            else (node.module or "",)
            if isinstance(node, ast.ImportFrom)
            else ()
        )
        level = node.level if isinstance(node, ast.ImportFrom) else 0
        for name in imports:
            imported = cls._snapshot_imported_resource(
                project,
                resource,
                name,
                level=level,
            )
            if imported is not None:
                found.append(imported)
        if not isinstance(node, ast.ImportFrom):
            return found
        for alias in node.names:
            if alias.name == "*":
                continue
            qualified = f"{node.module}.{alias.name}" if node.module else alias.name
            child = cls._snapshot_imported_resource(
                project,
                resource,
                qualified,
                level=level,
            )
            if child is not None:
                found.append(child)
        return found

    @staticmethod
    def _snapshot_imported_resource(
        project: p.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        name: str,
        *,
        level: int,
    ) -> t.Infra.RopeResource | None:
        """Resolve one imported module name relative to the importing package.

        Returns:
            The imported module resource, or ``None`` when Rope cannot find it.

        """
        return (
            project.find_relative_module(name, resource.parent, level)
            if level
            else project.find_module(name, resource.parent)
        )

    @classmethod
    def _occurrence_binding_holds(
        cls,
        root: Path,
        source: Path,
        condition: m.Infra.CodemodContextCondition,
        captures: t.JsonMapping,
        snapshot: m.Infra.CodemodBindingSnapshot,
    ) -> bool:
        """Resolve the exact captured expression, never another same-spelling use.

        A resolved-symbol operand names a module and its expression; same-binding
        names an expression in the occurrence's lexical scope. Annotation payloads
        are not executable migration candidates. Missing coordinates are a rule
        defect, not permission to resolve at module scope.

        Returns:
            The resulting ``bool``.
        """
        capture = m.Infra.AstGrepCapture.model_validate(captures[condition.variable])
        sources = {
            state.path.resolve(): state.content.decode("utf-8")
            for state in snapshot.states
            if state.content is not None
        }
        content = sources[source].encode("utf-8")
        text, start, end = cls._validated_capture_span(source, capture, content)
        tree = ast.parse(text, filename=str(source))
        if not any(
            isinstance(node, ast.expr | ast.Import | ast.ImportFrom)
            and FlextInfraUtilitiesRopeRuntimeModules.source_offset(text, node) == start
            and ast.get_source_segment(text, node) == capture.text
            for node in ast.walk(tree)
        ):
            return False
        if condition.predicate is c.Infra.CodemodContextPredicate.UNREFERENCED_IMPORT:
            return cls._unreferenced_import_holds(tree, capture.text)
        with FlextInfraUtilitiesRopeCore.open_project(root) as live:
            project = FlextInfraUtilitiesRopeRuntimeModules.snapshot_project(
                live,
                sources,
                captured=snapshot,
            )
            try:
                resource = project.get_resource(
                    source.relative_to(root.resolve()).as_posix(),
                )
                module = project.get_pymodule(resource)
                scope = FlextInfraUtilitiesRopeRuntimeModules.scope_at(module, start)
                if cls._type_payload_occurrence(project, module, text, start, end):
                    return False
                if condition.predicate in {
                    c.Infra.CodemodContextPredicate.SAME_BINDING,
                    c.Infra.CodemodContextPredicate.EXECUTABLE_OCCURRENCE,
                } and not cls._subscript_bindings_stable(
                    project,
                    module,
                    text,
                    (start, end),
                    sources,
                ):
                    return False
                if (
                    condition.predicate
                    is c.Infra.CodemodContextPredicate.EXECUTABLE_OCCURRENCE
                ):
                    return True
                return cls._resolved_expression_holds(
                    (project, module, scope),
                    condition,
                    capture.text,
                    start,
                    sources,
                )
            finally:
                project.close()

    @staticmethod
    def _validated_capture_span(
        source: Path,
        capture: m.Infra.AstGrepCapture,
        content: bytes,
    ) -> t.Triple[str, int, int]:
        """Validate the capture bytes against the snapshot content.

        Returns:
            The decoded source text and the capture start/end character
            offsets.

        Raises:
            ValueError: If binding capture differs from source.

        """
        if not (0 <= capture.start_byte < capture.end_byte <= len(content)) or (
            content[capture.start_byte : capture.end_byte]
            != capture.text.encode("utf-8")
        ):
            msg = f"binding capture differs from source: {source}"
            raise ValueError(msg)
        text = content.decode("utf-8")
        start = len(content[: capture.start_byte].decode("utf-8"))
        end = len(content[: capture.end_byte].decode("utf-8"))
        return text, start, end

    @staticmethod
    def _unreferenced_import_holds(tree: ast.Module, capture_text: str) -> bool:
        """Report whether an import capture has no load references anywhere.

        Returns:
            Whether the single captured import stays unreferenced.

        """
        declarations = ast.parse(capture_text).body
        if len(declarations) != 1 or not isinstance(
            declarations[0],
            ast.Import | ast.ImportFrom,
        ):
            return False
        names = FlextInfraUtilitiesSemanticCutoverBindings.bound_identifiers(
            declarations[0],
        )
        return not any(
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in names
            for node in ast.walk(tree)
        )

    @staticmethod
    def _type_payload_occurrence(
        project: p.Infra.RopeProject,
        module: p.Infra.RopePyModule,
        text: str,
        start: int,
        end: int,
    ) -> bool:
        """Report whether the occurrence lands inside a type payload range.

        Returns:
            Whether the capture start sits inside an annotation payload.

        """
        payload_ranges = (
            FlextInfraUtilitiesSemanticFamilyTypeReferences.type_payload_ranges
        )
        return any(
            left <= start < end <= right
            for left, right in payload_ranges(text, project, module)
        )

    @classmethod
    def _subscript_bindings_stable(
        cls,
        project: p.Infra.RopeProject,
        module: p.Infra.RopePyModule,
        text: str,
        span: t.Pair[int, int],
        sources: t.MappingKV[Path, str],
    ) -> bool:
        """Hold every enclosing subscript receiver on a stable binding chain.

        Returns:
            Whether no enclosing subscript hides a rebound or opaque wrapper.

        """
        start, end = span
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.Subscript):
                continue
            left, right = (
                FlextInfraUtilitiesSemanticFamilyTypeReferences.expression_range(
                    text,
                    node,
                )
            )
            if left <= start < end <= right and not cls._stable_binding_chain(
                (
                    project,
                    module,
                    FlextInfraUtilitiesRopeRuntimeModules.scope_at(module, left),
                ),
                node.value,
                left,
                sources,
            ):
                # A rebound/opaque wrapper can be a typing payload even
                # when scope-wide inference currently calls it something
                # else. Refuse the fixer rather than reinterpret its data.
                return False
        return True

    @classmethod
    def _resolved_expression_holds(
        cls,
        frame: t.Triple[p.Infra.RopeProject, p.Infra.RopePyModule, p.Infra.RopeScope],
        condition: m.Infra.CodemodContextCondition,
        capture_text: str,
        start: int,
        sources: t.MappingKV[Path, str],
    ) -> bool:
        """Resolve the captured expression against its predicate's target.

        Returns:
            Whether the resolved symbol matches the predicate's expectation.

        Raises:
            ValueError: If resolved-symbol requires a module and an expression; or
                if same-binding requires one lexical expression.

        """
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        project, scope = frame[0], frame[2]
        expression = ast.parse(capture_text, mode="eval").body
        if not isinstance(expression, ast.Name | ast.Attribute):
            return False
        actual = runtime.resolve_symbol(scope, expression)
        if condition.predicate is c.Infra.CodemodContextPredicate.RESOLVED_SYMBOL:
            return cls._resolved_symbol_matches(project, condition, actual)
        if len(condition.arg) != 1:
            msg = "same-binding requires one lexical expression"
            raise ValueError(msg)
        target = condition.arg[0]
        target_expression = ast.parse(target, mode="eval").body
        if not (
            cls._stable_binding_chain(frame, expression, start, sources)
            and cls._stable_binding_chain(frame, target_expression, start, sources)
        ):
            return False
        primary = target_expression
        while isinstance(primary, ast.Attribute):
            primary = primary.value
        if not isinstance(primary, ast.Name):
            return False
        if (
            scope.get_kind() != c.Infra.RopeScopeKind.MODULE
            and primary.id in scope.get_defined_names()
        ):
            # A local assignment/import/parameter can capture the emitted
            # facade even when Rope infers its current value as a class.
            return False
        expected = runtime.resolve_symbol(scope, target_expression)
        return cls._binding_symbols_match(expected, actual)

    @classmethod
    def _resolved_symbol_matches(
        cls,
        project: p.Infra.RopeProject,
        condition: m.Infra.CodemodContextCondition,
        actual: p.Infra.RopePyName | None,
    ) -> bool:
        """Resolve the predicate's module-qualified target symbol.

        Returns:
            Whether the module target resolves to the actual occurrence symbol.

        Raises:
            ValueError: If resolved-symbol requires a module and an expression.

        """
        if len(condition.arg) != _RESOLVED_SYMBOL_OPERAND_COUNT:
            msg = "resolved-symbol requires a module and an expression"
            raise ValueError(msg)
        target_module, target = condition.arg
        scope = project.get_module(target_module).get_scope()
        if scope is None:
            return False
        expected = FlextInfraUtilitiesRopeRuntimeModules.resolve_symbol(
            scope,
            ast.parse(target, mode="eval").body,
        )
        return cls._binding_symbols_match(expected, actual)

    @staticmethod
    def _binding_symbols_match(
        expected: p.Infra.RopePyName | None,
        actual: p.Infra.RopePyName | None,
    ) -> bool:
        """Compare the resolved expectation against the actual occurrence.

        Returns:
            Whether both sides resolve to the same symbol or facade alias.

        """
        if expected is None or actual is None:
            return False
        if (
            isinstance(expected, p.Infra.RopeAssignedName)
            and len(expected.assignments) != 1
        ):
            return False
        if FlextInfraUtilitiesRopeRuntimeModules.same_name(expected, actual):
            return True
        # A facade alias is an assignment of the identical class, not a
        # duplicate declaration. Scalar/unknown object inference is never proof.
        owner = expected.get_object()
        return (
            FlextInfraUtilitiesRopeRuntime.abstract_class(owner)
            and owner is actual.get_object()
        )

    @classmethod
    def _stable_binding_chain(
        cls,
        frame: t.Triple[p.Infra.RopeProject, p.Infra.RopePyModule, p.Infra.RopeScope],
        expression: ast.expr,
        offset: int,
        sources: t.MappingKV[Path, str],
        *,
        visited: frozenset[t.Pair[str, str]] = frozenset(),
    ) -> bool:
        """Reject rebound receivers, intermediate owners, and imported alias chains.

        ``frame`` carries the Rope project, the module owning the expression,
        and the lexical scope the expression resolves in.

        Returns:
            The resulting ``bool``.
        """
        project, module, scope = frame
        binding = cls._chain_base_binding(
            frame,
            expression,
            offset,
            sources,
            visited=visited,
        )
        if binding is None:
            return False
        chain = cls._chain_module_text(project, module, sources)
        if chain is None:
            return False
        path, text = chain
        routes = FlextInfraUtilitiesRopeSourceBases.lazy_module_aliases(
            module.get_name(),
            path,
            text,
        )
        if not cls._single_reaching_binding(text, scope, expression, offset, routes):
            return False
        if not cls._chain_alias_and_assignment_proven(
            project,
            binding,
            expression,
            routes,
        ):
            return False
        if isinstance(binding, p.Infra.RopeImportedName):
            return cls._chain_imported_binding(
                project,
                binding,
                sources,
                visited=visited,
            )
        return cls._chain_declaration_stable(
            project,
            binding,
            expression,
            sources,
            visited=visited,
        )

    @classmethod
    def _chain_base_binding(
        cls,
        frame: t.Triple[p.Infra.RopeProject, p.Infra.RopePyModule, p.Infra.RopeScope],
        expression: ast.expr,
        offset: int,
        sources: t.MappingKV[Path, str],
        *,
        visited: frozenset[t.Pair[str, str]],
    ) -> p.Infra.RopePyName | None:
        """Resolve the chain's base binding for one attribute or name expression.

        Returns:
            The resolved base binding, or ``None`` when the receiver chain is
            rebound, opaque, or the expression is neither attribute nor name.

        """
        scope = frame[2]
        if isinstance(expression, ast.Attribute):
            if not cls._stable_binding_chain(
                frame,
                expression.value,
                offset,
                sources,
                visited=visited,
            ):
                return None
        elif not isinstance(expression, ast.Name):
            return None
        return FlextInfraUtilitiesRopeRuntimeModules.resolve_symbol(scope, expression)

    @staticmethod
    def _chain_module_text(
        project: p.Infra.RopeProject,
        module: p.Infra.RopePyModule,
        sources: t.MappingKV[Path, str],
    ) -> t.Pair[Path, str] | None:
        """Locate the module source text inside the closed project.

        Returns:
            The module path and snapshot text, or ``None`` when unavailable.

        """
        resource = module.get_resource()
        if resource is None:
            return None
        path = Path(resource.real_path).resolve()
        if path.is_dir():
            path /= c.Infra.INIT_PY
        if not path.is_relative_to(Path(project.root.real_path).resolve()):
            # NoProject-backed foreign modules can read disk outside the closed
            # project's filesystem commands. Their receipts guard publication,
            # but cannot establish an immutable inference graph: refuse a fixer.
            return None
        text = sources.get(path)
        if text is None:
            return None
        return path, text

    @staticmethod
    def _chain_alias_and_assignment_proven(
        project: p.Infra.RopeProject,
        binding: p.Infra.RopePyName,
        expression: ast.expr,
        routes: t.StrMapping,
    ) -> bool:
        """Hold the lazy alias route and the single-assignment contract.

        Returns:
            Whether the alias route agrees with the binding and the binding is
            assigned exactly once.

        """
        if isinstance(expression, ast.Name) and expression.id in routes:
            route = project.get_module(routes[expression.id])
            target = route.get_attribute(expression.id)
            if not FlextInfraUtilitiesRopeRuntimeModules.same_name(
                target,
                binding,
            ) and (
                not FlextInfraUtilitiesRopeRuntime.abstract_class(target.get_object())
                or target.get_object() is not binding.get_object()
            ):
                return False
        return not (
            isinstance(binding, p.Infra.RopeAssignedName)
            and len(binding.assignments) != 1
        )

    @classmethod
    def _chain_imported_binding(
        cls,
        project: p.Infra.RopeProject,
        binding: p.Infra.RopeImportedName,
        sources: t.MappingKV[Path, str],
        *,
        visited: frozenset[t.Pair[str, str]],
    ) -> bool:
        """Follow an imported name to its defining module and continue there.

        Returns:
            Whether the imported binding chain stays stable at its origin.

        """
        imported = binding.imported_module.get_object()
        if not isinstance(imported, p.Infra.RopePyModule):
            return False
        key = (imported.get_name(), binding.imported_name)
        if key in visited:
            return False
        imported_scope = imported.get_scope()
        imported_resource = imported.get_resource()
        if imported_scope is None or imported_resource is None:
            return False
        imported_path = Path(imported_resource.real_path).resolve()
        if imported_path.is_dir():
            imported_path /= c.Infra.INIT_PY
        imported_text = sources.get(imported_path)
        if imported_text is None:
            return False
        value = binding.get_object()
        if isinstance(value, p.Infra.RopePyModule) and (
            value.get_name() == f"{imported.get_name()}.{binding.imported_name}"
        ):
            # A from-import may publish a submodule without a declaration in
            # its package initializer. Any package-level rebind makes that
            # implicit route unproven.
            rebound = any(
                binding.imported_name
                in FlextInfraUtilitiesSemanticCutoverBindings.bound_identifiers(node)
                for node in ast.walk(ast.parse(imported_text))
            )
            value_resource = None if rebound else value.get_resource()
            return (
                not rebound
                and value_resource is not None
                and Path(value_resource.real_path).resolve() in sources
            )
        return cls._stable_binding_chain(
            (project, imported, imported_scope),
            ast.Name(id=binding.imported_name, ctx=ast.Load()),
            len(imported_text),
            sources,
            visited=visited | {key},
        )

    @classmethod
    def _chain_declaration_stable(
        cls,
        project: p.Infra.RopeProject,
        binding: p.Infra.RopePyName,
        expression: ast.expr,
        sources: t.MappingKV[Path, str],
        *,
        visited: frozenset[t.Pair[str, str]],
    ) -> bool:
        """Hold the definition site of the resolved binding against rebinds.

        Returns:
            Whether the binding's single declaration stays stable at its owner.

        """
        holder_context = cls._chain_holder_context(binding, project, sources)
        if holder_context is None:
            return False
        if isinstance(binding, p.Infra.RopeImportedModule):
            return True
        holder, line, holder_text = holder_context
        name = (
            expression.attr
            if isinstance(expression, ast.Attribute)
            else expression.id
            if isinstance(expression, ast.Name)
            else ""
        )
        chased = cls._chain_holder_declaration(holder, holder_text, line, name)
        if chased is None:
            return False
        declaration, holder_offset, holder_scope = chased
        if not (
            isinstance(binding, p.Infra.RopeAssignedName)
            and isinstance(declaration, ast.Assign | ast.AnnAssign)
        ):
            return True
        value = declaration.value
        if not isinstance(value, ast.Name | ast.Attribute):
            return isinstance(value, ast.Constant)
        key = (holder.get_name(), name)
        return key not in visited and cls._stable_binding_chain(
            (project, holder, holder_scope),
            value,
            holder_offset,
            sources,
            visited=visited | {key},
        )

    @staticmethod
    def _chain_holder_context(
        binding: p.Infra.RopePyName,
        project: p.Infra.RopeProject,
        sources: t.MappingKV[Path, str],
    ) -> t.Triple[p.Infra.RopePyModule, int | None, str] | None:
        """Locate the definition site text of one binding inside the project.

        Returns:
            The defining module, its line, and the snapshot text, or ``None``
            when the definition site is unavailable or foreign.

        """
        holder, line = binding.get_definition_location()
        holder_resource = None if holder is None else holder.get_resource()
        if holder_resource is None or holder is None:
            return None
        holder_path = Path(holder_resource.real_path).resolve()
        if holder_path.is_dir():
            holder_path /= c.Infra.INIT_PY
        if not holder_path.is_relative_to(Path(project.root.real_path).resolve()):
            return None
        holder_text = sources.get(holder_path)
        if holder_text is None:
            return None
        return holder, line, holder_text

    @classmethod
    def _chain_holder_declaration(
        cls,
        holder: p.Infra.RopePyModule,
        holder_text: str,
        line: int | None,
        name: str,
    ) -> t.Triple[ast.stmt, int, p.Infra.RopeScope] | None:
        """Prove the holder's declaration is the single reaching definition.

        Returns:
            The declaration, its offset, and the holder lexical scope, or
            ``None`` when the declaration is absent or ambiguous.

        """
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        declaration = next(
            (
                node
                for node in ast.walk(ast.parse(holder_text))
                if isinstance(node, ast.stmt) and node.lineno == line
            ),
            None,
        )
        if declaration is None:
            return None
        holder_offset = runtime.source_offset(holder_text, declaration)
        holder_scope = runtime.scope_at(holder, holder_offset, declaration_line=line)
        if not cls._single_reaching_binding(
            holder_text,
            holder_scope,
            ast.Name(id=name, ctx=ast.Load()),
            len(holder_text),
        ):
            return None
        return declaration, holder_offset, holder_scope

    @staticmethod
    def _single_reaching_binding(
        source: str,
        scope: p.Infra.RopeScope,
        expression: ast.expr,
        offset: int,
        declared_routes: t.StrMapping | None = None,
    ) -> bool:
        """Prove one unconditional declaration instead of Rope's last assignment.

        Returns:
            The resulting ``bool``.
        """
        declarations = FlextInfraUtilitiesCodemodProject._single_reaching_declarations(
            source,
            scope,
            expression,
        )
        if isinstance(expression, ast.Attribute):
            return not declarations
        if len(declarations) != 1:
            return False
        declaration = declarations[0]
        if isinstance(declaration, ast.arg):
            return False
        start = FlextInfraUtilitiesRopeRuntimeModules.source_offset(source, declaration)
        if start >= offset:
            return False
        return FlextInfraUtilitiesCodemodProject._declaration_reaches_unconditionally(
            source,
            declaration,
            expression,
            declared_routes,
        )

    @staticmethod
    def _single_reaching_declarations(
        source: str,
        scope: p.Infra.RopeScope,
        expression: ast.expr,
    ) -> list[ast.AST]:
        """Collect the frame-local declarations competing with the expression.

        Returns:
            The declarations of the expression's spelling at the scope frame.

        """
        tree = ast.parse(source)
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        frames = (
            ast.Module,
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef,
            ast.Lambda,
        )
        spelling = ast.unparse(expression)
        declarations: list[ast.AST] = []
        for node in ast.walk(tree):
            names = FlextInfraUtilitiesSemanticCutoverBindings.bound_identifiers(node)
            attribute = isinstance(node, ast.Attribute) and isinstance(
                node.ctx,
                ast.Store | ast.Del,
            )
            if spelling not in names and not (
                attribute and ast.unparse(node) == spelling
            ):
                continue
            parent = parents.get(node)
            while parent is not None and not isinstance(parent, frames):
                parent = parents.get(parent)
            if parent is not None and (
                isinstance(parent, ast.Module) or parent.lineno == scope.get_start()
            ):
                declarations.append(node)
        return declarations

    @staticmethod
    def _declaration_reaches_unconditionally(
        source: str,
        declaration: ast.AST,
        expression: ast.expr,
        declared_routes: t.StrMapping | None,
    ) -> bool:
        """Report whether the declaration dominates the queried offset.

        Returns:
            Whether no conditional frame guards the declaration, allowing the
            declared lazy-module routes.

        """
        parents = {
            child: parent
            for parent in ast.walk(ast.parse(source))
            for child in ast.iter_child_nodes(parent)
        }
        frames = (
            ast.Module,
            ast.FunctionDef,
            ast.AsyncFunctionDef,
            ast.ClassDef,
            ast.Lambda,
        )
        spelling = ast.unparse(expression)
        parent = parents.get(declaration)
        while parent is not None and not isinstance(parent, frames):
            conditional = isinstance(
                parent,
                ast.If | ast.Try | ast.For | ast.While | ast.With,
            )
            if conditional and not (
                isinstance(parent, ast.If)
                and declared_routes is not None
                and spelling in declared_routes
            ):
                return False
            parent = parents.get(parent)
        return True

    @staticmethod
    def _captured_text(
        rule: m.Infra.CodemodRule,
        variable: str,
        captures: t.JsonMapping,
        source: Path,
    ) -> str:
        capture = captures.get(variable)
        text = capture.get("text") if isinstance(capture, Mapping) else capture
        if not isinstance(text, str) or not text.strip():
            msg = (
                f"{rule.id}: context variable ${variable} was not captured in {source}"
            )
            raise ValueError(msg)
        return text.strip()

    @staticmethod
    def _codemod_runtime_aliases(root: Path, package: str, own: str) -> frozenset[str]:
        """Read local aliases from source and dependency aliases from runtime.

        Returns:
            The resulting ``frozenset[str]``.

        Raises:
            ValueError: If project layout is unresolved.

        """
        if package == own:
            layout = FlextInfraUtilitiesCodegenNamespace.layout(root)
            if layout is None:
                msg = f"project layout is unresolved: {root}"
                raise ValueError(msg)
            return frozenset(layout.runtime_aliases)
        return frozenset(u.runtime_alias_names(package))

    @classmethod
    def _context_holds(
        cls,
        root: Path,
        condition: m.Infra.CodemodContextCondition,
        captured: t.Pair[str, str | None],
        file_path: Path,
        facts: m.Infra.CodemodProjectFacts,
    ) -> bool:
        """Evaluate one predicate against the project SSOT it names.

        Returns:
            The resulting ``bool``.

        Raises:
            ValueError: If project layout is unresolved; or if predicate.

        """
        value, of = captured
        predicate = condition.predicate
        module = cls._top_module(value)
        own = FlextInfraUtilitiesPyproject.project_package_name(root)
        match predicate:
            case c.Infra.CodemodContextPredicate.STDLIB_MODULE:
                return module in sys.stdlib_module_names
            case c.Infra.CodemodContextPredicate.OWN_PACKAGE:
                # The project owns its public package and its internal tiers
                # (tests, examples, scripts); an absolute import between them
                # never crosses a package boundary.
                return module == own or module in c.Infra.NON_PUBLIC_LAZY_ROOTS
            case c.Infra.CodemodContextPredicate.RUNTIME_PACKAGE:
                return module in facts.runtime_modules
            case c.Infra.CodemodContextPredicate.FACADE_PACKAGE:
                return module in facts.runtime_modules and bool(
                    cls._codemod_runtime_aliases(root, module, own),
                )
            case c.Infra.CodemodContextPredicate.RUNTIME_ALIAS:
                return value in cls._codemod_runtime_aliases(
                    root,
                    own if of is None else cls._top_module(of),
                    own,
                )
            case c.Infra.CodemodContextPredicate.LOCAL_ALIAS:
                layout = FlextInfraUtilitiesCodegenNamespace.layout(root)
                if layout is None:
                    msg = f"project layout is unresolved: {root}"
                    raise ValueError(msg)
                return value in layout.runtime_aliases
            case c.Infra.CodemodContextPredicate.MODULE_EXPORT:
                return value in cls._module_exports(file_path)
            case c.Infra.CodemodContextPredicate.FILE_FAMILY:
                return value in cls._file_families(file_path)
            case c.Infra.CodemodContextPredicate.PACKAGE_EXPORT:
                if of is None:
                    msg = f"predicate {predicate} requires an 'of' capture"
                    raise ValueError(msg)
                return value in cls._package_exports(of)
            case c.Infra.CodemodContextPredicate.FACADE_MODULE:
                return bool(
                    frozenset(config.Infra.tooling.lazy_init.import_layer_order)
                    & cls._module_exports(file_path),
                )
            case c.Infra.CodemodContextPredicate.LATER_LAYER:
                return cls._later_layer(root, file_path, value, condition)
            case c.Infra.CodemodContextPredicate.CLASS_STEM:
                return cls._has_class_stem(root, file_path, value)
            case c.Infra.CodemodContextPredicate.PACKAGE_LAYERS:
                return cls._package_has_layers(file_path.parent, condition.arg)
            case c.Infra.CodemodContextPredicate.PACKAGE_ROOT_INIT:
                layout = FlextInfraUtilitiesCodegenNamespace.layout(root)
                if layout is None:
                    msg = f"project layout is unresolved: {root}"
                    raise ValueError(msg)
                return file_path.resolve() == layout.init_path.resolve()
            case c.Infra.CodemodContextPredicate.FAMILY_BASE:
                return cls._family_package_has_base(file_path)
            case c.Infra.CodemodContextPredicate.IMPORT_CYCLE:
                return cls.import_closes_cycle(root, file_path, value, of, facts)
            case c.Infra.CodemodContextPredicate.COMPOSES_FAMILY:
                return cls.composes_family_package(file_path, value)

    @staticmethod
    def _top_module(value: str) -> str:
        """Return the top-level package of a captured dotted module.

        Returns:
            The top-level package of a captured dotted module.

        """
        return value.split(maxsplit=1)[0].split(".", maxsplit=1)[0]

    @classmethod
    def _runtime_modules(cls, root: Path) -> frozenset[str]:
        """Top-level import names provided by the project's runtime closure.

        Returns:
            The resulting ``frozenset[str]``.

        """
        project = FlextInfraUtilitiesCodemodRules.codemod_project_requirements(
            root,
        ).unwrap()
        closure = FlextInfraUtilitiesCodemodRules.codemod_runtime_closure(
            project[1],
            FlextInfraUtilitiesCodemodRules.codemod_distributions(),
        )
        return frozenset(
            module
            for module, providers in cls._installed_import_packages().items()
            if providers & closure
        )

    @staticmethod
    @cache
    def _installed_import_packages() -> t.MappingKV[str, frozenset[str]]:
        """Map each installed import package to its canonical distributions.

        Installed metadata is a fact of the interpreter environment, fixed for
        the life of the process, so it is read once; a project's runtime
        closure over it is still computed per admission pass.

        Returns:
            The resulting ``t.MappingKV[str, frozenset[str]]``.

        """
        return MappingProxyType({
            module: frozenset(canonicalize_name(name) for name in providers)
            for module, providers in packages_distributions().items()
        })

    @staticmethod
    def _module_exports(file_path: Path) -> frozenset[str]:
        """Names one module source declares in its own ``__all__``.

        Returns:
            The resulting ``frozenset[str]``.

        """
        return frozenset(
            FlextInfraUtilitiesRopeAnalysisExports.public_export_names_source(
                file_path.read_text(encoding=c.Cli.ENCODING_DEFAULT),
            ),
        )

    @classmethod
    def _file_families(cls, file_path: Path) -> frozenset[str]:
        """Facade letters of the family a module belongs to.

        A module belongs to the letters its own ``__all__`` declares and to
        those of the facade module of each private family package it lives
        in (``<pkg>/_models/x.py`` belongs to what ``<pkg>/models.py``
        declares). The letter vocabulary is the tooling import-layer order;
        no file name is mapped to a letter.

        Returns:
            The resulting ``frozenset[str]``.

        """
        letters = frozenset(config.Infra.tooling.lazy_init.import_layer_order)
        facades = (
            file_path,
            *(
                directory.parent / f"{directory.name.removeprefix('_')}.py"
                for directory in file_path.parents
                if directory.name.startswith("_")
                and not directory.name.startswith("__")
            ),
        )
        return frozenset(
            letter
            for facade in facades
            if facade.is_file()
            for letter in letters.intersection(cls._module_exports(facade))
        )

    @classmethod
    @lru_cache(maxsize=256)
    def _package_exports(cls, module: str) -> frozenset[str]:
        """Names an installed module declares in its ``__all__`` (not imported).

        Returns:
            The resulting ``frozenset[str]``.

        Raises:
            ValueError: If module is not importable for its exports.

        """
        spec = find_spec(module)
        if spec is None or spec.origin is None:
            msg = f"module is not importable for its exports: {module}"
            raise ValueError(msg)
        return cls._module_exports(Path(spec.origin))

    @classmethod
    def _later_layer(
        cls,
        root: Path,
        file_path: Path,
        imported: str,
        condition: m.Infra.CodemodContextCondition,
    ) -> bool:
        """Return whether an import reaches a later layer than its module's.

        Layers and their order are the tooling import-layer order. A
        module's layer is a family it belongs to (its own ``__all__`` or its
        family package's facade) or the layer its stem names (``settings``,
        ``base``, ``api``); an imported letter is its own layer. A rule may
        name the layer to compare with (``arg``) instead of the module's, and
        the layer an imported name that is no layer stands for (``as``).

        Returns:
            Whether an import reaches a later layer than its module's.

        """
        order = tuple(config.Infra.tooling.lazy_init.import_layer_order)
        owner = cls._layer_rank(
            order,
            frozenset(condition.arg) if condition.arg else cls._path_layers(file_path),
        )
        if owner is None:
            return False
        if imported in order:
            target_layers: frozenset[str] = frozenset({imported})
        elif imported.isidentifier() and condition.as_:
            target_layers = frozenset(condition.as_)
        else:
            target = cls._own_module_path(root, file_path, imported)
            if target is None:
                return False
            target_layers = cls._path_layers(target)
        target_rank = cls._layer_rank(order, target_layers)
        return target_rank is not None and target_rank > owner

    @staticmethod
    def _has_class_stem(root: Path, file_path: Path, name: str) -> bool:
        """Return whether a class name carries the project's class stem.

        The stem is derived from the project name; a module of the project's
        tests tree prefixes it with ``Tests``.

        Returns:
            Whether a class name carries the project's class stem.

        Raises:
            ValueError: If project layout is unresolved.

        """
        layout = FlextInfraUtilitiesCodegenNamespace.layout(root)
        if layout is None:
            msg = f"project layout is unresolved: {root}"
            raise ValueError(msg)
        tests = file_path.is_relative_to(root / c.Infra.DIR_TESTS)
        prefix = f"Tests{layout.class_stem}" if tests else layout.class_stem
        return name.startswith(prefix)

    @classmethod
    def _package_has_layers(cls, package: Path, layers: t.StrSequence) -> bool:
        """Return whether a package provides every named layer.

        A layer is provided by a runtime alias the package's modules declare
        (a facade letter), by a module or private module named for it, or by
        a subpackage of that name.

        Returns:
            Whether a package provides every named layer.

        """
        aliases = frozenset(
            alias
            for module in package.glob(f"*{c.Infra.EXT_PYTHON}")
            if module.name != c.Infra.INIT_PY
            for alias in cls._module_exports(module)
        )
        return all(
            layer in aliases
            or (package / f"{layer}{c.Infra.EXT_PYTHON}").is_file()
            or (package / f"_{layer}{c.Infra.EXT_PYTHON}").is_file()
            or (package / layer / c.Infra.INIT_PY).is_file()
            for layer in layers
        )

    @classmethod
    def _family_package_has_base(cls, file_path: Path) -> bool:
        """Return whether the family package holding a module has ``base.py``.

        A family package is a private directory ``_<stem>`` beside a facade
        module ``<stem>.py`` that declares a facade letter.

        Returns:
            Whether the family package holding a module has ``base.py``.

        """
        letters = frozenset(config.Infra.tooling.lazy_init.import_layer_order)
        for directory in file_path.parents:
            facade = directory.parent / f"{directory.name.removeprefix('_')}.py"
            if (
                directory.name.startswith("_")
                and not directory.name.startswith("__")
                and facade.is_file()
                and letters & cls._module_exports(facade)
            ):
                return (directory / f"base{c.Infra.EXT_PYTHON}").is_file()
        return True

    @classmethod
    def _path_layers(cls, path: Path) -> frozenset[str]:
        order = frozenset(config.Infra.tooling.lazy_init.import_layer_order)
        stems = {
            part.removeprefix("_").removesuffix(c.Infra.EXT_PYTHON)
            for part in (path.name, *(parent.name for parent in path.parents))
        }
        families = cls._file_families(path) if path.is_file() else frozenset()
        return families | (order & stems)

    @staticmethod
    def _layer_rank(order: t.StrSequence, layers: frozenset[str]) -> int | None:
        ranks = [order.index(layer) for layer in layers if layer in order]
        return min(ranks) if ranks else None

    @staticmethod
    def _own_module_path(root: Path, file_path: Path, imported: str) -> Path | None:
        """Resolve an import of the own package to its module file or package.

        Returns:
            The resulting ``Path | None``.

        """
        layout = FlextInfraUtilitiesCodegenNamespace.layout(root)
        if layout is None or not file_path.is_relative_to(layout.src_dir):
            return None
        level = len(imported) - len(imported.lstrip("."))
        parts = [part for part in imported.lstrip(".").split(".") if part]
        if level:
            base = file_path.parent
            for _ in range(level - 1):
                base = base.parent
        else:
            if not parts or parts[0] != layout.package_name:
                return None
            base = layout.src_dir
        target = base.joinpath(*parts)
        module = target.with_suffix(c.Infra.EXT_PYTHON)
        return module if module.is_file() else target

    @classmethod
    def parse_namespace_validation(
        cls,
        validation: p.Result[m.Infra.ValidationReport],
        root: Path,
    ) -> p.Result[t.VariadicTuple[m.Infra.CensusViolation]]:
        """Convert the engine-backed namespace report into census violations.

        A violation is fixable when its rule declares a token fix or a rope
        relocation in the project's rule plan.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.CensusViolation]]``.

        Raises:
            ValueError: If namespace violation does not follow the report format.

        """
        if validation.failure:
            return r[t.VariadicTuple[m.Infra.CensusViolation]].from_failure(validation)
        planned = cls.codemod_rule_plan(root)
        if planned.failure:
            return r[t.VariadicTuple[m.Infra.CensusViolation]].from_failure(planned)
        repairable = frozenset(
            rule.id
            for rule in planned.value.rules
            if rule.fixable
            or rule.relocation is not None
            or rule.id in c.Infra.SEMANTIC_CUTOVER_RULE_IDS.values()
        )
        parsed: list[m.Infra.CensusViolation] = []
        for violation in validation.value.violations:
            match = c.Infra.VIOLATION_PATTERN.match(violation)
            if match is None:
                msg = (
                    f"namespace violation does not follow the report format: "
                    f"{violation}"
                )
                raise ValueError(msg)
            parsed.append(
                m.Infra.CensusViolation(
                    module=match.group("module"),
                    rule=match.group("rule"),
                    line=int(match.group("line")),
                    message=match.group("message"),
                    fixable=match.group("rule") in repairable,
                ),
            )
        return r[t.VariadicTuple[m.Infra.CensusViolation]].ok(tuple(parsed))

    @staticmethod
    def _known_prefix(module: str, known: frozenset[str]) -> str | None:
        """Return the longest dotted prefix of ``module`` the project defines.

        Returns:
            The longest dotted prefix of ``module`` the project defines.

        """
        parts = module.split(".")
        for size in range(len(parts), 0, -1):
            candidate = ".".join(parts[:size])
            if candidate in known:
                return candidate
        return None


__all__: list[str] = ["FlextInfraUtilitiesCodemodProject"]
