"""Rope-backed import and rename operations.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections import defaultdict
from collections.abc import Callable, MutableMapping
from pathlib import Path

from flext_cli import u
from rope.base import exceptions

from flext_infra import c, m, p, r, t
from flext_infra._utilities import (
    FlextInfraUtilitiesPyproject,
    FlextInfraUtilitiesRopeAnalysis,
    FlextInfraUtilitiesRopeCore,
    FlextInfraUtilitiesRopeRuntime,
)


class FlextInfraUtilitiesRopeImports:
    """Rope-backed import organization and rename helpers."""

    @staticmethod
    def import_statements(
        module_imports: t.Infra.RopeModuleImports,
    ) -> t.SequenceOf[t.Infra.RopeImportStatement]:
        """Return validated Rope import statements from one module import collection.

        Returns:
            Validated Rope import statements from one module import collection.

        """
        return tuple(module_imports.imports)

    @staticmethod
    def import_statement_module_name(
        import_statement: t.Infra.RopeImportStatement,
    ) -> str | None:
        """Return the declared module name, preserving relative import depth.

        Returns:
            The declared module name, preserving relative import depth.

        """
        import_info = import_statement.import_info
        if not FlextInfraUtilitiesRopeRuntime.from_import_info(import_info):
            return None
        module_name = f"{'.' * import_info.level}{import_info.module_name}"
        return module_name or None

    @staticmethod
    def import_statement_names_and_aliases(
        import_statement: t.Infra.RopeImportStatement,
    ) -> t.SequenceOf[t.Pair[str, str | None]]:
        """Return validated imported-name pairs from one Rope import statement.

        Returns:
            Validated imported-name pairs from one Rope import statement.

        """
        import_info = import_statement.import_info
        if not (
            FlextInfraUtilitiesRopeRuntime.from_import_info(import_info)
            or FlextInfraUtilitiesRopeRuntime.normal_import_info(import_info)
        ):
            return ()
        return tuple(import_info.names_and_aliases)

    @classmethod
    def imported_module_paths(
        cls,
        module_imports: t.Infra.RopeModuleImports,
        *,
        current_package: str = "",
    ) -> t.StrSequence:
        """Return runtime import targets represented by a Rope module import set.

        Returns:
            Runtime import targets represented by a Rope module import set.

        """
        imported_paths: list[str] = []
        for import_statement in cls.import_statements(module_imports):
            declared_name = (
                getattr(import_statement.import_info, "module_name", "") or ""
            )
            level = getattr(import_statement.import_info, "level", 0) or 0
            module_name = cls.import_statement_module_name(import_statement)
            names_and_aliases = cls.import_statement_names_and_aliases(import_statement)
            if current_package and level > 0:
                resolved = FlextInfraUtilitiesRopeAnalysis.resolve_import_module(
                    current_package=current_package,
                    module_name=declared_name,
                    level=level,
                )
                if not resolved:
                    resolved = current_package
                if resolved != declared_name:
                    module_name = resolved
            if module_name is not None:
                imported_paths.append(module_name)
                imported_paths.extend(
                    f"{module_name}.{name}" for name, _alias in names_and_aliases
                )
                continue
            imported_paths.extend(name for name, _alias in names_and_aliases)
        return tuple(imported_paths)

    @staticmethod
    def find_occurrences(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        offset: int,
        *,
        resources: t.SequenceOf[t.Infra.RopeResource] | None = None,
        in_hierarchy: bool = False,
    ) -> t.SequenceOf[t.Infra.RopeLocation]:
        """Find all occurrences of the symbol at offset across the project.

        Returns:
            The resulting ``t.SequenceOf[t.Infra.RopeLocation]``.

        Raises:
            RuntimeError: If rope find_occurrences failed for.

        """
        try:
            return FlextInfraUtilitiesRopeRuntime.runtime_find_occurrences(
                rope_project,
                resource,
                offset,
                resources=resources,
                in_hierarchy=in_hierarchy,
            )
        except (
            exceptions.RefactoringError,
            exceptions.ResourceNotFoundError,
            exceptions.ModuleNotFoundError,
            AttributeError,
            TypeError,
            RecursionError,
        ) as exc:
            msg = (
                "rope find_occurrences failed for "
                f"{resource.path}@{offset}: {type(exc).__name__}: {exc!s}"
            )
            raise RuntimeError(msg) from exc

    @staticmethod
    def location_file_path(location: t.Infra.RopeLocation) -> Path | None:
        """Resolve one Rope occurrence back to an absolute file path.

        Returns:
            The resulting ``Path | None``.

        """
        resource = getattr(location, "resource", None)
        real_path = getattr(resource, "real_path", None)
        if isinstance(real_path, str) and real_path:
            return Path(real_path).resolve()
        path = getattr(resource, "path", None)
        if isinstance(path, str) and path:
            return Path(path)
        return None

    @staticmethod
    def indexed_search_resources(
        rope_workspace: p.Infra.RopeWorkspaceDsl,
        *,
        resource: t.Infra.RopeResource,
        name: str,
        definition_path: Path,
        dependent_import_targets: t.StrSequence = (),
    ) -> t.VariadicTuple[t.Infra.RopeResource]:
        """Build the reachability resource set for semantic occurrence searches.

        The workspace name index already narrows the candidate module set to
        files that contain ``name`` textually. This helper converts that cheap
        index into concrete Rope resources so callers can still rely on Rope's
        semantic identity checks without scanning the full project, keeping the
        removal-planning resource set: package reexports stay excluded and the
        candidates narrow to the import dependents when targets are given.

        Returns:
            The resulting ``t.VariadicTuple[t.Infra.RopeResource]``.

        """
        resolved_definition = definition_path.resolve()
        dependent_paths: frozenset[str] | None = None
        if dependent_import_targets:
            dependent_candidates: set[Path] = {resolved_definition}
            for import_target in dependent_import_targets:
                dependent_candidates.update(
                    path.resolve()
                    for path in rope_workspace.import_dependents(import_target)
                )
            dependent_paths = frozenset(str(path) for path in dependent_candidates)

        def admitted(resolved_path: Path) -> bool:
            return (
                resolved_path != resolved_definition
                and resolved_path.name != c.Infra.INIT_PY
                and (dependent_paths is None or str(resolved_path) in dependent_paths)
            )

        return FlextInfraUtilitiesRopeImports._indexed_search_resources(
            rope_workspace,
            resource=resource,
            name=name,
            definition_path=resolved_definition,
            occurrence_admitted=admitted,
        )

    @staticmethod
    def indexed_surface_search_resources(
        rope_workspace: p.Infra.RopeWorkspaceDsl,
        *,
        resource: t.Infra.RopeResource,
        name: str,
        definition_path: Path,
    ) -> t.VariadicTuple[t.Infra.RopeResource]:
        """Build the report-only resource set that spans package reexports.

        Report-only callers index every surface, so ``__init__`` reexports stay
        admissible and the candidate set is not narrowed to import dependents.

        Returns:
            The resulting ``t.VariadicTuple[t.Infra.RopeResource]``.

        """
        resolved_definition = definition_path.resolve()

        def admitted(resolved_path: Path) -> bool:
            return resolved_path != resolved_definition

        return FlextInfraUtilitiesRopeImports._indexed_search_resources(
            rope_workspace,
            resource=resource,
            name=name,
            definition_path=resolved_definition,
            occurrence_admitted=admitted,
        )

    @staticmethod
    def _indexed_search_resources(
        rope_workspace: p.Infra.RopeWorkspaceDsl,
        *,
        resource: t.Infra.RopeResource,
        name: str,
        definition_path: Path,
        occurrence_admitted: Callable[[Path], bool],
    ) -> t.VariadicTuple[t.Infra.RopeResource]:
        """Collect deduplicated Rope resources from the workspace name index.

        Returns:
            The resulting ``t.VariadicTuple[t.Infra.RopeResource]``.

        Raises:
            RuntimeError: If rope search resource unavailable for indexed path.

        """
        occurrences = rope_workspace.name_index().get(name, ())
        seen_paths = {str(definition_path)}
        resources: list[t.Infra.RopeResource] = [resource]
        for path, _surface, _lines in occurrences:
            resolved_path = path.resolve()
            if not occurrence_admitted(resolved_path):
                continue
            cache_key = str(resolved_path)
            if cache_key in seen_paths:
                continue
            candidate_resource = rope_workspace.resource(resolved_path)
            if candidate_resource is None:
                msg = (
                    "rope search resource unavailable for indexed path "
                    f"{resolved_path} while resolving '{name}'"
                )
                raise RuntimeError(msg)
            seen_paths.add(cache_key)
            resources.append(candidate_resource)
        return tuple(resources)

    @staticmethod
    def organize_imports(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeFile,
        *,
        apply: bool,
    ) -> p.Result[bool]:
        """Organize imports for one rope resource using rope's import tools.

        ``r.ok(True)`` when rope produced a non-empty change set; the
        change is applied when ``apply`` is set. ``r.ok(False)`` when
        rope produced no changes (already organised). ``r.fail(reason)``
        when rope raised a refactoring/resource/type error.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        try:
            original_source = resource.read()
            organizer = FlextInfraUtilitiesRopeRuntime.import_organizer(rope_project)
            changes = organizer.organize_imports(resource)
        except (
            SyntaxError,
            exceptions.ModuleSyntaxError,
            exceptions.RefactoringError,
            exceptions.ResourceNotFoundError,
            exceptions.ModuleNotFoundError,
            AttributeError,
            TypeError,
        ) as exc:
            return r[bool].fail(f"rope organize_imports raised: {exc!s}", exception=exc)
        if changes is None:
            return r[bool].ok(value=False)
        change_list_raw = getattr(changes, "changes", None)
        if not isinstance(change_list_raw, list):
            return r[bool].fail(
                "unexpected rope organize_imports result type: "
                f"{type(changes).__name__}",
            )
        change_list = tuple(change_list_raw)
        if not change_list:
            return r[bool].ok(value=False)
        changed = any(
            getattr(change, "new_contents", None) is not None
            and getattr(change, "new_contents", None) != original_source
            for change in change_list
        )
        if changed and apply:
            rope_project.do(changes)
        return r[bool].ok(changed)

    @classmethod
    def normalize_imports(
        cls,
        rope_project: t.Infra.RopeProject,
        *,
        file_paths: t.SequenceOf[Path],
        preserve_canonical_aliases: bool = False,
    ) -> p.Result[bool]:
        """Normalize imports with Ruff and preserve semantic facade references.

        Ruff owns removal and ordering because it understands quoted typing
        expressions, including cast arguments. Rope's unused-import pass drops
        imports used only in those expressions before Ruff can inspect them.
        Rope still resolves canonical aliases when their preservation is requested.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        existing_paths = tuple(path.resolve() for path in file_paths if path.is_file())
        if not existing_paths:
            return r[bool].ok(value=False)
        canonical_imports: MutableMapping[
            Path,
            list[t.Pair[str, t.VariadicTuple[str]]],
        ] = {}
        if preserve_canonical_aliases:
            try:
                canonical_imports = cls._collect_canonical_alias_imports(
                    rope_project,
                    existing_paths,
                )
            except ValueError as exc:
                return r[bool].fail(str(exc), exception=exc)
        before = {path: path.read_bytes() for path in existing_paths}
        normalized_paths = tuple(str(path) for path in existing_paths)
        check_result = u.Cli.run_checked(
            ["ruff", "check", "--fix", "--select", "I,F401", *normalized_paths],
            timeout=c.Infra.TIMEOUT_SHORT,
        )
        if check_result.failure:
            return r[bool].from_failure(check_result)
        if preserve_canonical_aliases:
            restore_result = cls._ensure_canonical_alias_imports(
                rope_project,
                canonical_imports,
            )
            if restore_result.failure:
                return r[bool].from_failure(restore_result)
        format_result = u.Cli.run_checked(
            ["ruff", "format", *normalized_paths],
            timeout=c.Infra.TIMEOUT_SHORT,
        )
        if format_result.failure:
            return r[bool].from_failure(format_result)
        return r[bool].ok(
            any(path.read_bytes() != before[path] for path in existing_paths),
        )

    @classmethod
    def _collect_canonical_alias_imports(
        cls,
        rope_project: t.Infra.RopeProject,
        file_paths: t.SequenceOf[Path],
    ) -> MutableMapping[Path, list[t.Pair[str, t.VariadicTuple[str]]]]:
        """Collect canonical runtime-alias imports eligible for semantic restore.

        Returns:
            The resulting ``MutableMapping[Path, list[t.Pair[str,
                t.VariadicTuple[str]]]]``.

        Raises:
            ValueError: If ``referenced_result.failure``.

        """
        runtime_aliases = u.runtime_alias_names(c.Infra.PKG_INFRA_UNDERSCORE)
        canonical_modules = frozenset({
            c.Infra.PKG_CORE_UNDERSCORE,
            c.Infra.PKG_INFRA_UNDERSCORE,
        })
        collected: MutableMapping[Path, list[t.Pair[str, t.VariadicTuple[str]]]] = {}
        for file_path in file_paths:
            resource = FlextInfraUtilitiesRopeCore.resolve_resource_from_path(
                rope_project,
                file_path,
            )
            if resource is None:
                continue
            module_imports = FlextInfraUtilitiesRopeCore.resolve_module_imports(
                rope_project,
                resource,
            )
            entries: list[t.Pair[str, t.VariadicTuple[str]]] = []
            for import_stmt in cls.import_statements(module_imports):
                import_info = import_stmt.import_info
                if (
                    not FlextInfraUtilitiesRopeRuntime.from_import_info(import_info)
                    or import_info.level != 0
                ):
                    continue
                if import_info.module_name not in canonical_modules:
                    continue
                plain_names = [
                    (name, alias)
                    for name, alias in import_info.names_and_aliases
                    if alias is None
                ]
                if not plain_names or not all(
                    name in runtime_aliases for name, _alias in plain_names
                ):
                    continue
                referenced_result = cls._referenced_runtime_aliases(
                    resource.read(),
                    tuple(name for name, _alias in plain_names),
                )
                if referenced_result.failure:
                    msg = referenced_result.error or "alias reference scan failed"
                    raise ValueError(msg)
                referenced_aliases = referenced_result.unwrap()
                alias_names = tuple(
                    name for name, _alias in plain_names if name in referenced_aliases
                )
                if not alias_names:
                    continue
                entries.append((import_info.module_name, alias_names))
            if entries:
                collected[file_path] = entries
        return collected

    @staticmethod
    def _referenced_runtime_aliases(
        source: str,
        aliases: t.SequenceOf[str],
    ) -> p.Result[frozenset[str]]:
        """Return runtime aliases referenced after Ruff cleanup.

        Returns:
            Runtime aliases referenced after Ruff cleanup.

        """
        alias_set = frozenset(aliases)
        referenced: set[str] = set()
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return r[frozenset[str]].fail(
                f"source is not parseable after import cleanup: {exc!s}",
                exception=exc,
            )
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in alias_set:
                referenced.add(node.id)
                continue
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                literal = node.value
                referenced.update(
                    alias for alias in alias_set if f"{alias}." in literal
                )
        return r[frozenset[str]].ok(frozenset(referenced))

    @classmethod
    def _ensure_canonical_alias_imports(
        cls,
        rope_project: t.Infra.RopeProject,
        collected: MutableMapping[Path, list[t.Pair[str, t.VariadicTuple[str]]]],
    ) -> p.Result[bool]:
        """Re-add canonical runtime-alias imports removed by Ruff F401 cleanup.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        changed_any = False
        for file_path, entries in collected.items():
            restore_result = cls._restore_alias_imports(
                rope_project,
                file_path,
                entries,
            )
            if restore_result.failure:
                return r[bool].from_failure(restore_result)
            changed_any = changed_any or restore_result.unwrap()
        return r[bool].ok(changed_any)

    @classmethod
    def _restore_alias_imports(
        cls,
        rope_project: t.Infra.RopeProject,
        file_path: Path,
        entries: t.SequenceOf[t.Pair[str, t.VariadicTuple[str]]],
    ) -> p.Result[bool]:
        """Restore one file's referenced canonical aliases Rope removed.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        resource = FlextInfraUtilitiesRopeCore.resolve_resource_from_path(
            rope_project,
            file_path,
        )
        if resource is None:
            return r[bool].ok(value=False)
        module_imports = FlextInfraUtilitiesRopeCore.resolve_module_imports(
            rope_project,
            resource,
        )
        referenced_aliases_result = cls._referenced_runtime_aliases(
            resource.read(),
            tuple(alias for _module_name, aliases in entries for alias in aliases),
        )
        if referenced_aliases_result.failure:
            return r[bool].from_failure(referenced_aliases_result)
        referenced_aliases = referenced_aliases_result.unwrap()
        current = cls._current_plain_aliases(module_imports)
        changed = False
        for module_name, alias_names in entries:
            missing = sorted(
                (frozenset(alias_names) & referenced_aliases)
                - current.get(module_name, set()),
            )
            if not missing:
                continue
            existing = current.get(module_name, set())
            if existing:
                # Merge into the existing from-import via rope mutation.
                changed = (
                    cls._merge_missing_into_statement(
                        module_imports,
                        module_name,
                        missing,
                    )
                    or changed
                )
            else:
                module_imports.add_import(
                    FlextInfraUtilitiesRopeRuntime.from_import(
                        module_name,
                        0,
                        [(name, None) for name in missing],
                    ),
                )
                changed = True
        if not changed:
            return r[bool].ok(value=False)
        module_imports.remove_duplicates()
        module_imports.sort_imports()
        updated_source = module_imports.get_changed_source()
        if updated_source == resource.read():
            return r[bool].ok(value=False)
        resource.write(updated_source)
        return r[bool].ok(value=True)

    @staticmethod
    def _current_plain_aliases(
        module_imports: t.Infra.RopeModuleImports,
    ) -> MutableMapping[str, set[str]]:
        """Map each absolute from-import's module to its unaliased names.

        Returns:
            The module name to unaliased imported names.

        """
        current: MutableMapping[str, set[str]] = defaultdict(set)
        for import_stmt in FlextInfraUtilitiesRopeImports.import_statements(
            module_imports,
        ):
            import_info = import_stmt.import_info
            if (
                not FlextInfraUtilitiesRopeRuntime.from_import_info(import_info)
                or import_info.level != 0
            ):
                continue
            current[import_info.module_name].update(
                name for name, alias in import_info.names_and_aliases if alias is None
            )
        return current

    @staticmethod
    def _merge_missing_into_statement(
        module_imports: t.Infra.RopeModuleImports,
        module_name: str,
        missing: t.StrSequence,
    ) -> bool:
        """Merge missing names into the module's existing absolute from-import.

        Returns:
            True when a matching statement was found and mutated.

        """
        for import_stmt in FlextInfraUtilitiesRopeImports.import_statements(
            module_imports,
        ):
            import_info = import_stmt.import_info
            if (
                not FlextInfraUtilitiesRopeRuntime.from_import_info(import_info)
                or import_info.level != 0
                or import_info.module_name != module_name
            ):
                continue
            merged = list(import_info.names_and_aliases)
            present = {name for name, alias in merged if alias is None}
            merged.extend(
                (name, None) for name in sorted(missing) if name not in present
            )
            import_stmt.import_info = FlextInfraUtilitiesRopeRuntime.from_import(
                module_name,
                0,
                merged,
            )
            return True
        return False

    @classmethod
    def relocate_from_import_aliases(
        cls,
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeFile,
        *,
        source_module: str,
        target_module: str,
        aliases: t.StrSequence,
    ) -> str | None:
        """Move unaliased names from one absolute import to another using Rope.

        The relocated source is written to ``resource`` and returned; ``None``
        means no import changed.

        Returns:
            The resulting ``str | None``.

        """
        updated = cls._planned_from_import_aliases(
            rope_project,
            resource,
            source_module=source_module,
            target_module=target_module,
            aliases=aliases,
        )
        if updated is not None:
            resource.write(updated)
        return updated

    @classmethod
    def package_root_import_owner(
        cls, project_root: Path, source_module: str
    ) -> str | None:
        """Resolve an own-package target; foreign-package findings stay residue.

        Returns:
            The declared project package or no owned relocation target.
        """
        own = FlextInfraUtilitiesPyproject.project_package_name(project_root)
        return own if source_module.split(".", maxsplit=1)[0] == own else None

    @classmethod
    def plan_package_root_import(
        cls,
        rope_workspace: p.Infra.RopeWorkspaceDsl,
        file_path: Path,
        *,
        source_module: str,
        aliases: t.StrSequence,
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Plan an own-package import without publishing or rebinding foreign names.

        The project declaration owns the target. Rope owns import bindings and
        aliases; foreign-package findings remain unmodified residue.

        Returns:
            A typed source edit, no-op, or an explicit resource/ownership failure.
        """
        entry = rope_workspace.module(file_path)
        root = entry.project_root if entry is not None else None
        if root is None:
            return r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]].fail(
                f"import owner has no declared project: {file_path}",
            )
        own = cls.package_root_import_owner(root, source_module)
        if own is None:
            return r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]].ok(())
        resource = rope_workspace.resource(file_path)
        if resource is None:
            return r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]].fail(
                f"import owner is not a Rope resource: {file_path}",
            )
        original = resource.read()
        updated = cls._planned_from_import_aliases(
            rope_workspace.rope_project,
            resource,
            source_module=source_module,
            target_module=own,
            aliases=aliases,
        )
        if updated is None:
            return r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]].ok(())
        return r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]].ok((
            m.Infra.SemanticMigrationEdit(
                file_path=file_path.resolve(),
                original_source=original,
                updated_source=updated,
                changes=(f"bound import to declared package {own}",),
            ),
        ))

    @classmethod
    def _planned_from_import_aliases(
        cls,
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeFile,
        *,
        source_module: str,
        target_module: str,
        aliases: t.StrSequence,
    ) -> str | None:
        aliases_to_move = frozenset(aliases)
        if not aliases_to_move:
            return None
        module_imports = FlextInfraUtilitiesRopeCore.resolve_module_imports(
            rope_project,
            resource,
        )
        original_source: str = resource.read()
        target_import_stmt, moved_aliases = cls._strip_aliases_from_source_imports(
            module_imports,
            source_module=source_module,
            target_module=target_module,
            aliases_to_move=aliases_to_move,
        )
        if not moved_aliases:
            return None
        merged_target_pairs = cls._merge_aliases_into_target(
            module_imports,
            target_import_stmt=target_import_stmt,
            target_module=target_module,
            moved_aliases=moved_aliases,
        )
        updated_source: str = module_imports.get_changed_source()
        if merged_target_pairs and cls._uses_parenthesized_from_import(
            source=original_source,
            module_name=target_module,
        ):
            updated_source = cls._format_parenthesized_from_import(
                source=updated_source,
                module_name=target_module,
                names_and_aliases=merged_target_pairs,
            )
        if updated_source == original_source:
            return None
        return updated_source

    @staticmethod
    def _strip_aliases_from_source_imports(
        module_imports: t.Infra.RopeModuleImports,
        *,
        source_module: str,
        target_module: str,
        aliases_to_move: frozenset[str],
    ) -> t.Pair[t.Infra.RopeImportStatement | None, t.Infra.StrSet]:
        """Remove ``aliases_to_move`` from each ``from source_module`` statement.

        Returns ``(target_import_stmt_or_None, moved_aliases_set)``. Mutates
        the source-module statements in place via ``import_info`` reassignment;
        the caller still owns the merge into the target.

        Returns:
            The resulting ``t.Pair[t.Infra.RopeImportStatement | None,
                t.Infra.StrSet]``.

        """
        target_import_stmt: t.Infra.RopeImportStatement | None = None
        moved_aliases: t.Infra.StrSet = set()
        import_statements = module_imports.imports
        if not import_statements:
            return target_import_stmt, moved_aliases
        for import_stmt in import_statements:
            import_info = import_stmt.import_info
            if not (
                FlextInfraUtilitiesRopeRuntime.from_import_info(import_info)
                and import_info.level == 0
            ):
                continue
            if import_info.module_name == target_module:
                target_import_stmt = import_stmt
            if import_info.module_name != source_module:
                continue
            kept_pairs: list[t.Pair[str, str | None]] = []
            for name, alias in import_info.names_and_aliases:
                if alias is None and name in aliases_to_move:
                    moved_aliases.add(name)
                    continue
                kept_pairs.append((name, alias))
            if len(kept_pairs) == len(import_info.names_and_aliases):
                continue
            import_stmt.import_info = FlextInfraUtilitiesRopeRuntime.from_import(
                source_module,
                0,
                kept_pairs,
            )
        return target_import_stmt, moved_aliases

    @staticmethod
    def _merge_aliases_into_target(
        module_imports: t.Infra.RopeModuleImports,
        *,
        target_import_stmt: t.Infra.RopeImportStatement | None,
        target_module: str,
        moved_aliases: t.Infra.StrSet,
    ) -> t.SequenceOf[t.Pair[str, str | None]]:
        """Merge ``moved_aliases`` into the target import; create one if missing.

        Returns:
            The resulting ``t.SequenceOf[t.Pair[str, str | None]]``.

        Raises:
            RuntimeError: If rope target import mismatch for.

        """
        sorted_moved = sorted(moved_aliases)
        if target_import_stmt is None:
            module_imports.add_import(
                FlextInfraUtilitiesRopeRuntime.from_import(
                    target_module,
                    0,
                    [(name, None) for name in sorted_moved],
                ),
            )
            module_imports.sort_imports()
            return tuple((name, None) for name in sorted_moved)
        import_info = target_import_stmt.import_info
        if not (
            FlextInfraUtilitiesRopeRuntime.from_import_info(import_info)
            and import_info.level == 0
            and import_info.module_name == target_module
        ):
            msg = (
                "rope target import mismatch for "
                f"{target_module}: {type(import_info).__name__}"
            )
            raise RuntimeError(msg)
        merged_pairs = list(import_info.names_and_aliases)
        existing_plain_names = {name for name, alias in merged_pairs if alias is None}
        merged_pairs.extend(
            (name, None) for name in sorted_moved if name not in existing_plain_names
        )
        target_import_stmt.import_info = FlextInfraUtilitiesRopeRuntime.from_import(
            target_module,
            0,
            list(merged_pairs),
        )
        return tuple(merged_pairs)

    @staticmethod
    def _uses_parenthesized_from_import(*, source: str, module_name: str) -> bool:
        """Check whether source uses a parenthesized from import.

        Returns:
            The resulting ``bool``.

        """
        pattern = c.Infra.compile_from_module_paren_open(module_name)
        return any(pattern.match(line) for line in source.splitlines())

    @staticmethod
    def _format_parenthesized_from_import(
        *,
        source: str,
        module_name: str,
        names_and_aliases: t.SequenceOf[t.Pair[str, str | None]],
    ) -> str:
        """Format parenthesized from import.

        Returns:
            The resulting ``str``.

        """
        entries = [
            (f"{name} as {alias}" if alias else name)
            for name, alias in names_and_aliases
        ]
        replacement = "\n".join([
            f"from {module_name} import (",
            *[f"    {entry}," for entry in entries],
            ")",
        ])
        pattern = c.Infra.compile_from_module_import_line(module_name)
        rewritten_source: str = pattern.sub(replacement, source, count=1)
        if rewritten_source == source:
            return source
        return rewritten_source

    @staticmethod
    def _persisted_import_block(
        module_imports: t.Infra.RopeModuleImports,
        resource: t.Infra.RopeFile,
        *,
        apply: bool,
    ) -> str | None:
        """Normalize, render, and optionally write one module's import block.

        ``None`` when the rendered block already matches the file on disk.

        Returns:
            The resulting ``str | None``.

        """
        module_imports.remove_duplicates()
        module_imports.sort_imports()
        updated: str = module_imports.get_changed_source()
        if updated == resource.read():
            return None
        if apply:
            resource.write(updated)
        return updated

    @staticmethod
    def add_import(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeFile,
        from_module: str,
        names: t.StrSequence,
        *,
        apply: bool = True,
    ) -> str | None:
        """Add ``from <module> import <names>`` using rope's ImportOrganizer.

        Returns:
            The resulting ``str | None``.

        """
        module_imports = FlextInfraUtilitiesRopeCore.resolve_module_imports(
            rope_project,
            resource,
        )
        module_imports.add_import(
            FlextInfraUtilitiesRopeRuntime.from_import(
                from_module,
                0,
                [(name, None) for name in sorted(names)],
            ),
        )
        return FlextInfraUtilitiesRopeImports._persisted_import_block(
            module_imports,
            resource,
            apply=apply,
        )

    @staticmethod
    def remove_import_names(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeFile,
        from_module: str,
        names: t.StrSequence,
        *,
        apply: bool = True,
    ) -> str | None:
        """Remove specific names from ``from <module> import ...``.

        Returns:
            The resulting ``str | None``.

        """
        names_to_remove = frozenset(names)
        module_imports = FlextInfraUtilitiesRopeCore.resolve_module_imports(
            rope_project,
            resource,
        )
        changed = False
        import_statements = FlextInfraUtilitiesRopeImports.import_statements(
            module_imports,
        )
        for import_stmt in import_statements:
            import_info = import_stmt.import_info
            from_import = (
                import_info
                if FlextInfraUtilitiesRopeRuntime.from_import_info(import_info)
                and import_info.level == 0
                and import_info.module_name == from_module
                else None
            )
            if from_import is None:
                continue
            kept = [
                (name, alias)
                for name, alias in from_import.names_and_aliases
                if name not in names_to_remove
            ]
            if len(kept) < len(from_import.names_and_aliases):
                import_stmt.import_info = FlextInfraUtilitiesRopeRuntime.from_import(
                    from_module,
                    0,
                    kept,
                )
                changed = True
        if not changed:
            return None
        return FlextInfraUtilitiesRopeImports._persisted_import_block(
            module_imports,
            resource,
            apply=apply,
        )

    # ------------------------------------------------------------------
    # Import alignment: every relative from-import takes its absolute form
    # ------------------------------------------------------------------

    @staticmethod
    def _absolute_from_import(source_module: str, module_name: str, level: int) -> str:
        """Resolve one relative from-import target to its absolute module name.

        Python resolves ``level`` dots from the module's own package, so a
        module ``a.b.c`` with ``level=1`` imports from ``a.b``.

        Returns:
            The resulting ``str``.

        """
        parts = source_module.split(".")
        base = parts[: max(len(parts) - level, 0)]
        return ".".join(part for part in (*base, module_name) if part)

    @classmethod
    def align_module_imports(
        cls,
        *,
        rope_project: t.Infra.RopeProject,
        repository_root: Path,
        index: m.Infra.RopeWorkspaceIndex,
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenFilePlan]]:
        """Plan absolute-form rewrites for every relative from-import.

        Package initializers are generated and render their own imports, so
        only authored modules are planned.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.CodegenFilePlan]]``.

        """
        file_plans: list[m.Infra.CodegenFilePlan] = []
        for entry in sorted(
            index.modules_by_path.values(),
            key=lambda item: str(item.file_path),
        ):
            if entry.is_package_init or not entry.module_name:
                continue
            plan_result = cls._align_entry_imports(
                rope_project,
                repository_root,
                entry,
            )
            if plan_result.failure:
                return r[t.VariadicTuple[m.Infra.CodegenFilePlan]].from_failure(
                    plan_result,
                )
            plan_value, plan_present = plan_result.value
            if plan_present and plan_value is not None:
                file_plans.append(plan_value)
        return r[t.VariadicTuple[m.Infra.CodegenFilePlan]].ok(tuple(file_plans))

    @classmethod
    def _align_entry_imports(
        cls,
        rope_project: t.Infra.RopeProject,
        repository_root: Path,
        entry: m.Infra.RopeModuleIndexEntry,
    ) -> p.Result[t.Pair[m.Infra.CodegenFilePlan | None, bool]]:
        """Plan the absolute-form rewrite of one indexed module's imports.

        Returns:
            One file plan when the module's imports change; otherwise None.

        """
        file_path = entry.file_path
        if not file_path.is_file():
            return r[t.Pair[m.Infra.CodegenFilePlan, bool]].ok((None, False))
        resource = FlextInfraUtilitiesRopeCore.resolve_resource_from_path(
            rope_project,
            file_path,
        )
        if resource is None:
            return r[t.Pair[m.Infra.CodegenFilePlan, bool]].ok((None, False))
        module_imports = FlextInfraUtilitiesRopeCore.resolve_module_imports(
            rope_project,
            resource,
        )
        changed = cls._rewrite_relative_from_imports(
            module_imports,
            entry.module_name,
        )
        if not changed:
            return r[t.Pair[m.Infra.CodegenFilePlan, bool]].ok((None, False))
        updated_source = module_imports.get_changed_source()
        original_source = resource.read()
        if updated_source == original_source:
            return r[t.Pair[m.Infra.CodegenFilePlan, bool]].ok((None, False))
        before = u.Cli.atomic_read_binary_file_state(file_path, required=False)
        if before.failure:
            return r[t.Pair[m.Infra.CodegenFilePlan | None, bool]].from_failure(before)
        return r[t.Pair[m.Infra.CodegenFilePlan, bool]].ok(
            (
                m.Infra.CodegenFilePlan(
                    project=repository_root,
                    path=file_path.resolve(),
                    before=before.value,
                    desired_content=updated_source.encode("utf-8"),
                    desired_mode=0o644,
                ),
                True,
            ),
        )

    @classmethod
    def _rewrite_relative_from_imports(
        cls,
        module_imports: t.Infra.RopeModuleImports,
        source_module: str,
    ) -> bool:
        """Rewrite every relative from-import of one module to absolute form.

        Returns:
            True when any import statement changed.

        Raises:
            ValueError: If a relative import level escapes the package.

        """
        changed = False
        for import_stmt in cls.import_statements(module_imports):
            import_info = import_stmt.import_info
            if not FlextInfraUtilitiesRopeRuntime.from_import_info(import_info):
                continue
            level = import_info.level or 0
            if level == 0:
                continue
            absolute = cls._absolute_from_import(
                source_module,
                import_info.module_name or "",
                level,
            )
            if not absolute:
                msg = (
                    f"relative import level {level} escapes the package of "
                    f"{source_module}"
                )
                raise ValueError(msg)
            import_stmt.import_info = FlextInfraUtilitiesRopeRuntime.from_import(
                absolute,
                0,
                list(import_info.names_and_aliases),
            )
            changed = True
        return changed


__all__: list[str] = ["FlextInfraUtilitiesRopeImports"]
