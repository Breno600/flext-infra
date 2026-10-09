"""Rope workspace indexing helpers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import operator
from collections.abc import MutableMapping
from functools import lru_cache
from pathlib import Path

from flext_infra import c, config, m, t
from flext_infra._utilities import (
    FlextInfraUtilitiesIterationWorkspace,
    FlextInfraUtilitiesProjectDiscovery,
    FlextInfraUtilitiesRopeCore,
    FlextInfraUtilitiesRopeSourceBases,
)


class FlextInfraUtilitiesRopeAnalysisWorkspace:
    """Rope-backed workspace indexing helpers."""

    @staticmethod
    def _excluded_parts() -> frozenset[str]:
        """Resolve analyzer exclusions from the generated artifact SSOT.

        Returns:
            The resulting ``frozenset[str]``.

        """
        ignored = frozenset[str](config.Infra.codegen.source_scan_ignored)
        return frozenset[str]((*c.Infra.ITERATION_EXCLUDED_PARTS, *ignored))

    @classmethod
    def package_name_for_dir(cls, package_dir: Path, *, project_root: Path) -> str:
        """Return the import package a directory declares inside a project.

        An empty string when the directory sits outside the project or under no
        recognised source root.

        Returns:
            The import package a directory declares inside a project.

        """
        if not package_dir.is_relative_to(project_root):
            return ""
        relative_parts = package_dir.relative_to(project_root).parts
        if not relative_parts:
            return ""
        root_name = relative_parts[0]
        if root_name == c.Infra.DEFAULT_SRC_DIR:
            package_parts = relative_parts[1:]
        elif root_name in c.Infra.ROOT_WRAPPER_SEGMENTS:
            package_parts = relative_parts
        else:
            package_parts = ()
        return ".".join(package_parts)

    @classmethod
    def generated_source_packages(cls, project_root: Path) -> t.StrTuple:
        """Return the import packages of a project's generated source trees.

        The tree names come from the codegen artifact key
        (``generated_source``); analyzers that take module names rather than
        path globs exclude exactly these packages.

        Returns:
            The sorted import packages of every generated source tree.

        """
        root = project_root.resolve()
        names = frozenset(config.Infra.codegen.generated_sources)
        ignored = cls._excluded_parts() - names
        packages: set[str] = set()
        for scan_root in config.Infra.source_scan.roots:
            base = root / scan_root
            if not base.is_dir():
                continue
            for name in names:
                for directory in base.rglob(name):
                    package = cls.package_name_for_dir(directory, project_root=root)
                    if (
                        directory.is_dir()
                        and package
                        and not ignored.intersection(directory.relative_to(root).parts)
                    ):
                        packages.add(package)
        return tuple(sorted(packages))

    @classmethod
    def module_name_for_file(cls, file_path: Path, *, project_root: Path) -> str:
        """Return the module name for a file.

        Returns:
            The module name for a file.

        """
        if file_path.name in {c.Infra.INIT_PY, c.Infra.INIT_PYI}:
            return cls.package_name_for_dir(file_path.parent, project_root=project_root)
        package_name = cls.package_name_for_dir(
            file_path.parent,
            project_root=project_root,
        )
        return f"{package_name}.{file_path.stem}" if package_name else ""

    @classmethod
    def facade_rebind_module(
        cls,
        file_path: Path,
        source: str,
        *,
        project_root: Path,
    ) -> str:
        """Return the module of one source written in the facade-rebind form.

        The form imports the parent letter, subclasses it and rebinds the
        letter to the subclass (``from flext_core import u`` /
        ``class FlextCliUtilities(u)`` / ``u = FlextCliUtilities``). Mypy
        rejects that rebind, so the checker configuration the operator
        authorized for it applies to exactly these modules
        (operator-ruling-2026-10-01-facade-rebind-mypy-scope).

        Returns:
            The module name, or the empty string when the source is not in
            that form or names no module.

        """
        tree = ast.parse(source)
        imported = {
            alias.asname or alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }

        def _base_names(node: ast.ClassDef) -> set[str]:
            """Resolve direct base names, seeing through ``Generic[T]`` subscripts.

            The canonical facade-rebind form subclasses the imported letter
            through a PEP 695 generic class, so the base reaches the AST as
            ``ast.Subscript(value=Name(letter))`` and a plain ``ast.Name``
            walk misses it.

            Returns:
                The resulting ``set[str]``.
            """
            names = set[str]()
            for base in node.bases:
                candidate = base.value if isinstance(base, ast.Subscript) else base
                if isinstance(candidate, ast.Name):
                    names.add(candidate.id)
            return names

        bases_by_class = {
            node.name: _base_names(node)
            for node in tree.body
            if isinstance(node, ast.ClassDef)
        }
        rebinds = any(
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Name)
            and any(
                isinstance(target, ast.Name)
                and target.id in imported
                and target.id in bases_by_class.get(node.value.id, set())
                for target in node.targets
            )
            for node in tree.body
        )
        if not rebinds:
            return ""
        return cls.module_name_for_file(file_path, project_root=project_root)

    @classmethod
    def facade_rebind_modules(
        cls,
        project_root: Path,
        planned_sources: t.MappingKV[Path, str],
    ) -> t.StrTuple:
        """Return the modules of a project written in the facade-rebind form.

        ``planned_sources`` maps each Python file the active plan publishes to
        its planned content: a scaffold renders the facades its own
        configuration must cover, so the planned bytes, not the tree before
        publication, decide those files. Every other source is read from disk.

        Returns:
            The modules written in the canonical facade-rebind form.

        """
        root = project_root.resolve()
        return tuple(
            sorted({
                module
                for file_path, source in cls._project_sources(
                    root,
                    planned_sources,
                ).items()
                if (
                    module := cls.facade_rebind_module(
                        file_path,
                        source,
                        project_root=root,
                    )
                )
            }),
        )

    @classmethod
    def runtime_evaluated_base_classes(
        cls,
        project_root: Path,
        planned_sources: t.MappingKV[Path, str],
        roots: t.StrSequence,
    ) -> t.StrTuple:
        """Return the class bases whose subclasses evaluate annotations at runtime.

        Captured source supplies declaration identities, while import bindings
        supply Ruff's qualified expressions. Planned bytes override disk and
        providers before aliases, members and ordered C3 parents are resolved.
        No project package is imported during generation.

        Returns:
            The declared roots and the derived bases, by qualified name.

        """
        root = project_root.resolve()
        sources = {
            cls.module_name_for_file(path, project_root=root): (path, source)
            for path, source in cls._project_sources(root, planned_sources).items()
            if cls.module_name_for_file(path, project_root=root)
        }
        if not sources:
            # No captured declaration (e.g. a scaffold planned before its
            # sources exist): nothing derives beyond the declared roots, so no
            # Rope project is opened and no workspace tree is walked.
            return tuple(sorted(roots))
        # Generated package inits are projections excluded from the class
        # inventory, yet their install_lazy_exports maps own the namespace
        # aliases (m, p, t and siblings) that facade-qualified bases resolve
        # through. Read those maps from disk so resolution can rewrite
        # ``<pkg>.<alias>`` targets to their provider modules.
        extra_module_aliases: dict[str, str] = {}
        owned = {path for path, _ in sources.values()}
        for init_path in sorted(root.rglob("__init__.py")):
            resolved = init_path.resolve()
            if resolved in owned or not init_path.is_file():
                continue
            init_module = cls.module_name_for_file(init_path, project_root=root)
            if not init_module:
                continue
            for (
                alias,
                absolute,
            ) in FlextInfraUtilitiesRopeSourceBases.lazy_module_aliases(
                init_module,
                init_path,
                init_path.read_text(encoding=c.Cli.ENCODING_DEFAULT),
            ).items():
                extra_module_aliases.setdefault(
                    f"{init_module}.{alias}",
                    absolute,
                )
        # The analysis root opens with the whole declared workspace's member
        # source roots on the resolution path: member sources legitimately
        # import sibling fleet packages (tests fixtures import flext_tests,
        # src modules import flext_core), and a member-only rope path raises
        # ModuleNotFoundError for every cross-member base resolution.
        # An unpublished project root (planned bytes only) is never created:
        # Rope parses from its nearest existing ancestor, which is always one
        # of the project roots so planned sources need no folder on disk.
        parse_root = next(path for path in (root, *root.parents) if path.is_dir())
        workspace_root = next(
            (
                parent
                for parent in (parse_root, *parse_root.parents)
                if (parent / "src").is_dir() and (parent / "flext-core").is_dir()
            ),
            parse_root,
        )
        project_roots = [
            parse_root,
            *(
                member
                for member in sorted(workspace_root.iterdir())
                if member.is_dir() and (member / "src").is_dir()
            ),
        ]
        with FlextInfraUtilitiesRopeCore.open_project(
            workspace_root,
            project_roots=project_roots,
        ) as project:
            return FlextInfraUtilitiesRopeSourceBases.runtime_bases(
                project,
                sources,
                roots,
                extra_module_aliases=extra_module_aliases,
            )

    @staticmethod
    def _project_sources(
        root: Path,
        planned_sources: t.MappingKV[Path, str],
    ) -> t.MappingKV[Path, str]:
        """Read the project's Python sources, the planned bytes overriding disk.

        Returns:
            Each source by resolved path.

        """
        sources: MutableMapping[Path, str] = {}
        if root.is_dir():
            files = FlextInfraUtilitiesIterationWorkspace.iter_python_files(
                m.Infra.SourceScanRequest(project_roots=(root,)),
            ).unwrap()
            for file_path in files:
                source = file_path.read_text(
                    encoding=c.Cli.ENCODING_DEFAULT,
                )
                sources[file_path.resolve()] = source
        for file_path, source in planned_sources.items():
            sources[file_path.resolve()] = source
        return sources

    @staticmethod
    def _is_generated_init_stub(file_path: Path) -> bool:
        """Return whether ``file_path`` is a codegen-owned package stub.

        Returns:
            Whether ``file_path`` is a codegen-owned package stub.

        """
        if file_path.name != c.Infra.INIT_PYI:
            return False
        return file_path.read_text(encoding=c.Cli.ENCODING_DEFAULT).startswith(
            c.Infra.AUTOGEN_HEADERS,
        )

    @classmethod
    def _governed_roots(cls, repository_root: Path) -> frozenset[Path]:
        """Return every declared governed project root, resolved.

        The authority is the same election the Rope opener uses
        (``discover_rope_project_roots``): a candidate the session indexes is
        governed by definition, so the index filter and the opened project set
        can never disagree about a sibling repository.

        Returns:
            Every declared governed project root, resolved.

        """
        return frozenset(
            FlextInfraUtilitiesProjectDiscovery.discover_rope_project_roots(
                repository_root,
            ),
        )

    @staticmethod
    @lru_cache(maxsize=c.Infra.DIRECTORY_CACHE_MAXSIZE)
    def _foreign_directory(
        directory: Path,
        repository_root: Path,
        governed_roots: frozenset[Path],
    ) -> bool:
        """Memoize Git boundaries by directory for one workspace index.

        Returns:
            The resulting ``bool``.

        """
        if directory == repository_root or not directory.is_relative_to(
            repository_root,
        ):
            return False
        return (
            ((directory / ".git").exists() or (directory / ".git").is_symlink())
            and directory not in governed_roots
        ) or FlextInfraUtilitiesRopeAnalysisWorkspace._foreign_directory(
            directory.parent,
            repository_root,
            governed_roots,
        )

    @classmethod
    def _inside_nested_repository(
        cls,
        path: Path,
        repository_root: Path,
        *,
        governed_roots: frozenset[Path],
    ) -> bool:
        """Exclude foreign nested Git checkouts, never declared governed members.

        A governed workspace member (a submodule declared in ``.gitmodules``,
        or scanned as a candidate project) carries its own ``.git`` root by
        design; that is not a foreign nested repository and must stay
        indexed. Only a ``.git`` boundary that is not one of the workspace's
        own governed roots — an unrelated clone, an ad hoc worktree — is
        excluded.

        Returns:
            The resulting ``bool``.

        """
        return cls._foreign_directory(path.parent, repository_root, governed_roots)

    @classmethod
    def _is_pruned_walk_dir(
        cls,
        directory: Path,
        resolved_root: Path,
        *,
        governed_roots: frozenset[Path],
    ) -> bool:
        """Return whether the pruned stub walk must not descend into ``directory``.

        Returns:
            Whether the pruned stub walk must not descend into ``directory``.

        """
        return (
            (
                ((directory / ".git").exists() or (directory / ".git").is_symlink())
                and directory not in governed_roots
            )
            or cls._inside_nested_repository(
                directory,
                resolved_root,
                governed_roots=governed_roots,
            )
            or bool(
                set(directory.relative_to(resolved_root).parts) & cls._excluded_parts(),
            )
            or any(
                c.Infra.TRANSIENT_PYTEST_SCRATCH_PART.match(part)
                for part in directory.relative_to(resolved_root).parts
            )
        )

    @classmethod
    def _pruned_stub_file_paths(cls, resolved_root: Path) -> set[Path]:
        """Collect ``*.pyi`` paths with a walk that prunes excluded subtrees.

        ``Path.rglob`` cannot prune, so it descends into every excluded
        subtree — a populated ``.venv`` or an embedded worktree makes the
        stat crawl cost whatever those directories contain. The walk applies
        the exclusion names and the nested-repository classification at every
        depth instead, and never follows symlinked directories.

        Returns:
            The resulting ``set[Path]``.

        """
        governed_roots = cls._governed_roots(resolved_root)
        stub_paths: set[Path] = set()
        for parent, dir_names, file_names in resolved_root.walk():
            dir_names[:] = [
                name
                for name in dir_names
                if not cls._is_pruned_walk_dir(
                    parent / name,
                    resolved_root,
                    governed_roots=governed_roots,
                )
            ]
            stub_paths.update(
                (parent / name).resolve()
                for name in file_names
                if name.endswith(".pyi") and (parent / name).is_file()
            )
        return stub_paths

    @classmethod
    def _python_and_stub_file_paths(
        cls,
        rope_project: t.Infra.RopeProject,
        resolved_root: Path,
    ) -> t.VariadicTuple[Path]:
        """Return Python and stub sources in the canonical declared source scope.

        Returns:
            Python and stub sources in the canonical declared source scope.

        """
        from flext_infra._utilities import FlextInfraUtilitiesProjectDiscovery

        rope_root = Path(rope_project.address).resolve()
        governed_roots = cls._governed_roots(resolved_root)
        source_paths = (
            (resolved_root / relative).resolve()
            for relative in (
                FlextInfraUtilitiesProjectDiscovery.ast_grep_scan_targets(resolved_root)
            )
        )
        return tuple(
            sorted(
                {
                    path
                    for path in source_paths
                    if path.is_relative_to(resolved_root)
                    and path.is_relative_to(rope_root)
                    and not set(path.relative_to(resolved_root).parts)
                    & cls._excluded_parts()
                    and not cls._inside_nested_repository(
                        path,
                        resolved_root,
                        governed_roots=governed_roots,
                    )
                },
                key=Path.as_posix,
            ),
        )

    @classmethod
    def _collect_modules(
        cls,
        rope_project: t.Infra.RopeProject,
        resolved_root: Path,
    ) -> tuple[
        MutableMapping[str, m.Infra.RopeModuleIndexEntry],
        MutableMapping[Path, list[m.Infra.RopeModuleIndexEntry]],
        MutableMapping[str, Path],
        MutableMapping[str, str],
        set[Path],
    ]:
        """Collect modules.

        Returns:
            The resulting ``tuple[MutableMapping[str, m.Infra.RopeModuleIndexEntry],
                MutableMapping[Path, list[m.Infra.RopeModuleIndexEntry]],
                MutableMapping[str, Path], MutableMapping[str, str], set[Path]]``.

        """
        modules_by_path: MutableMapping[str, m.Infra.RopeModuleIndexEntry] = {}
        modules_by_dir: MutableMapping[Path, list[m.Infra.RopeModuleIndexEntry]] = {}
        package_dir_by_name: MutableMapping[str, Path] = {}
        project_package_by_root: MutableMapping[str, str] = {}
        package_dirs: set[Path] = set()
        # Hermetic index: iterate the discovery output in sorted path order so
        # every derived structure (index, lazy maps, generated facades) is
        # byte-identical across environments regardless of fs enumeration.
        for file_path in sorted(
            cls._python_and_stub_file_paths(rope_project, resolved_root),
            key=str,
        ):
            resolved_file_path = file_path.resolve()
            if cls._is_generated_init_stub(resolved_file_path):
                continue
            if not resolved_file_path.is_relative_to(resolved_root):
                continue
            if cls._excluded_parts().intersection(
                resolved_file_path.relative_to(resolved_root).parts[:-1],
            ):
                # The scan-ignore SSOT owns source visibility everywhere: a
                # tool hook under an ignored resource (e.g. .claude, .agents)
                # is not a project module, and indexing it feeds the mod
                # planners a file they then crash on while moving helpers.
                continue
            resource_path = resolved_file_path.relative_to(resolved_root).as_posix()
            package_dir = resolved_file_path.parent
            is_package_init = resolved_file_path.name in {
                c.Infra.INIT_PY,
                c.Infra.INIT_PYI,
            }
            project_root = FlextInfraUtilitiesProjectDiscovery.nearest_project_root(
                resolved_root,
                resolved_file_path,
            )
            module_name = (
                cls.module_name_for_file(resolved_file_path, project_root=project_root)
                if project_root is not None
                else ""
            )
            package_name = (
                cls.package_name_for_dir(package_dir, project_root=project_root)
                if project_root is not None
                else module_name
                if is_package_init
                else module_name.rsplit(".", maxsplit=1)[0]
                if "." in module_name
                else ""
            )
            entry = m.Infra.RopeModuleIndexEntry(
                file_path=resolved_file_path,
                resource_path=resource_path,
                module_name=module_name,
                package_name=package_name,
                package_dir=package_dir,
                project_root=project_root,
                is_package_init=is_package_init,
            )
            modules_by_path[str(resolved_file_path)] = entry
            modules_by_dir.setdefault(package_dir, []).append(entry)
            package_dirs.add(package_dir)
            if package_name:
                package_dir_by_name[package_name] = package_dir
                if (
                    project_root is not None
                    and "." not in package_name
                    and package_dir.parent.name == c.Infra.DEFAULT_SRC_DIR
                ):
                    project_package_by_root[str(project_root)] = package_name
        return (
            modules_by_path,
            modules_by_dir,
            package_dir_by_name,
            project_package_by_root,
            package_dirs,
        )

    @staticmethod
    def _package_family_maps(
        sorted_package_dirs: t.VariadicTuple[Path],
    ) -> t.Pair[
        MutableMapping[Path, list[Path]],
        MutableMapping[Path, list[Path]],
    ]:
        """Map every package dir to its direct-child and descendant package dirs.

        Returns:
            The resulting ``(direct children, descendants)`` map pair.

        """
        package_dir_set = frozenset(sorted_package_dirs)
        direct_children_by_dir: MutableMapping[Path, list[Path]] = {
            package_dir: [] for package_dir in sorted_package_dirs
        }
        descendants_by_dir: MutableMapping[Path, list[Path]] = {
            package_dir: [] for package_dir in sorted_package_dirs
        }
        for package_dir in sorted_package_dirs:
            parent_dir = package_dir.parent
            if parent_dir in package_dir_set:
                direct_children_by_dir[parent_dir].append(package_dir)
            for ancestor_dir in package_dir.parents:
                if ancestor_dir == package_dir:
                    continue
                if ancestor_dir in package_dir_set:
                    descendants_by_dir[ancestor_dir].append(package_dir)
        return direct_children_by_dir, descendants_by_dir

    @classmethod
    def _package_identity(
        cls,
        package_dir: Path,
        modules_by_dir: t.MappingKV[Path, list[m.Infra.RopeModuleIndexEntry]],
        modules_by_path: t.MappingKV[str, m.Infra.RopeModuleIndexEntry],
    ) -> t.Quad[
        t.VariadicTuple[m.Infra.RopeModuleIndexEntry],
        Path,
        Path | None,
        str,
    ]:
        """Resolve one package's modules, init path, project root, and name.

        Returns:
            The resulting ``(sorted modules, init path, project root, name)``.

        """
        dir_modules = tuple(
            sorted(
                modules_by_dir.get(package_dir, ()),
                key=operator.attrgetter("file_path.name"),
            ),
        )
        init_path = (package_dir / c.Infra.INIT_PY).resolve()
        init_entry = modules_by_path.get(str(init_path))
        project_root = (
            init_entry.project_root
            if init_entry is not None
            else next(
                (
                    entry.project_root
                    for entry in dir_modules
                    if entry.project_root is not None
                ),
                None,
            )
        )
        package_name = (
            cls.package_name_for_dir(package_dir, project_root=project_root)
            if project_root is not None
            else init_entry.package_name
            if init_entry is not None
            else ""
        )
        return dir_modules, init_path, project_root, package_name

    @staticmethod
    def _register_package_identity(
        package_dir: Path,
        project_root: Path | None,
        package_name: str,
        package_dir_by_name: MutableMapping[str, Path],
        project_package_by_root: MutableMapping[str, str],
    ) -> None:
        """Record one package's name in the index maps when it is new."""
        if package_name and package_name not in package_dir_by_name:
            package_dir_by_name[package_name] = package_dir
        if (
            project_root is not None
            and "." not in package_name
            and package_dir.parent.name == c.Infra.DEFAULT_SRC_DIR
            and str(project_root) not in project_package_by_root
        ):
            project_package_by_root[str(project_root)] = package_name

    @classmethod
    def index_rope_workspace(
        cls,
        rope_project: t.Infra.RopeProject,
        repository_root: Path,
    ) -> m.Infra.RopeWorkspaceIndex:
        """Build a generic Rope workspace index for package-oriented planning.

        Returns:
            The resulting ``m.Infra.RopeWorkspaceIndex``.

        """
        cls._foreign_directory.cache_clear()
        resolved_root = repository_root.resolve()
        (
            modules_by_path,
            modules_by_dir,
            package_dir_by_name,
            project_package_by_root,
            package_dirs,
        ) = cls._collect_modules(rope_project, resolved_root)
        sorted_package_dirs = tuple(sorted(package_dirs))
        direct_children_by_dir, descendants_by_dir = cls._package_family_maps(
            sorted_package_dirs,
        )
        packages_by_dir: MutableMapping[str, m.Infra.RopePackageIndexEntry] = {}
        for package_dir in sorted_package_dirs:
            (
                dir_modules,
                init_path,
                project_root,
                package_name,
            ) = cls._package_identity(package_dir, modules_by_dir, modules_by_path)
            cls._register_package_identity(
                package_dir,
                project_root,
                package_name,
                package_dir_by_name,
                project_package_by_root,
            )
            packages_by_dir[str(package_dir)] = m.Infra.RopePackageIndexEntry(
                package_dir=package_dir,
                init_path=init_path,
                package_name=package_name,
                project_root=project_root,
                modules=dir_modules,
                direct_child_dirs=tuple(direct_children_by_dir.get(package_dir, ())),
                descendant_child_dirs=tuple(descendants_by_dir.get(package_dir, ())),
            )
        return m.Infra.RopeWorkspaceIndex(
            repository_root=resolved_root,
            package_dirs=sorted_package_dirs,
            packages_by_dir=packages_by_dir,
            modules_by_path=modules_by_path,
            package_dir_by_name=package_dir_by_name,
            project_package_by_root=project_package_by_root,
        )


__all__: list[str] = ["FlextInfraUtilitiesRopeAnalysisWorkspace"]
