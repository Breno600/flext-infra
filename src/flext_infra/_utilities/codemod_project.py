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
)
from flext_infra._utilities.base import FlextInfraUtilitiesBase
from flext_infra._utilities.codemod_rules import FlextInfraUtilitiesCodemodRules
from flext_infra._utilities.namespace import FlextInfraUtilitiesCodegenNamespace
from flext_infra._utilities.pyproject import FlextInfraUtilitiesPyproject
from flext_infra._utilities.rope_core import FlextInfraUtilitiesRopeCore
from flext_infra._utilities.rope_imports import FlextInfraUtilitiesRopeImports


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
                msg = f"source module is absent from the project import graph: {file_path}"
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

        ``captures`` maps each metavariable of the finding to its ast-grep
        single capture (``{"text": ...}``) or transformed value (a string). A
        declared variable the finding did not capture is a rule defect and
        raises; the syntactic match alone never stands in for it.

        ``facts`` is the admission pass's project snapshot; it must have been
        built for every predicate the rule names.

        Returns:
            Whether one finding satisfies its rule's project context.

        Raises:
            ValueError: If the facts were not built for a predicate of the rule.

        """
        missing = {condition.predicate for condition in rule.context} - facts.predicates
        if missing:
            msg = (
                f"{rule.id}: project facts were not built for predicates "
                f"{sorted(missing)}"
            )
            raise ValueError(msg)
        source = (file_path if file_path.is_absolute() else root / file_path).resolve()
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
                msg = f"namespace violation does not follow the report format: {violation}"
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
