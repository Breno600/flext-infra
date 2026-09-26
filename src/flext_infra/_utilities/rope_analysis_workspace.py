"""Rope workspace indexing helpers."""

from __future__ import annotations

import operator
from collections.abc import MutableMapping
from pathlib import Path

from flext_infra import c, config, m, t

from .project_discovery import FlextInfraUtilitiesProjectDiscovery
from .rope_core import FlextInfraUtilitiesRopeCore


class FlextInfraUtilitiesRopeAnalysisWorkspace:
    """Rope-backed workspace indexing helpers."""

    @staticmethod
    def _excluded_parts() -> frozenset[str]:
        """Resolve analyzer exclusions from the generated artifact SSOT."""
        ignored = frozenset[str](config.Infra.codegen.source_scan_ignored)
        return frozenset[str]((*c.Infra.ITERATION_EXCLUDED_PARTS, *ignored))

    @staticmethod
    def _project_root_for_file(repository_root: Path, file_path: Path) -> Path | None:
        """Project root for file."""
        for parent in file_path.parents:
            if (parent / "pyproject.toml").is_file():
                return parent.resolve()
            if parent == repository_root:
                return repository_root
        return None

    @classmethod
    def package_name_for_dir(cls, package_dir: Path, *, project_root: Path) -> str:
        """Return the import package a directory declares inside a project.

        An empty string when the directory sits outside the project or under no
        recognised source root.
        """
        try:
            relative_parts = package_dir.relative_to(project_root).parts
        except ValueError:
            return ""
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
    def _module_name_for_file(cls, file_path: Path, *, project_root: Path) -> str:
        """Return the module name for a file."""
        if file_path.name in {c.Infra.INIT_PY, c.Infra.INIT_PYI}:
            return cls.package_name_for_dir(file_path.parent, project_root=project_root)
        package_name = cls.package_name_for_dir(
            file_path.parent, project_root=project_root
        )
        return f"{package_name}.{file_path.stem}" if package_name else ""

    @staticmethod
    def _is_generated_init_stub(file_path: Path) -> bool:
        """Return whether ``file_path`` is a codegen-owned package stub."""
        if file_path.name != c.Infra.INIT_PYI:
            return False
        return file_path.read_text(encoding=c.Cli.ENCODING_DEFAULT).startswith(
            c.Infra.AUTOGEN_HEADERS
        )

    @classmethod
    def _governed_roots(cls, repository_root: Path) -> frozenset[Path]:
        """Return every declared governed project root, resolved.

        The authority is the same election the Rope opener uses
        (``discover_rope_project_roots``): a candidate the session indexes is
        governed by definition, so the index filter and the opened project set
        can never disagree about a sibling repository.
        """
        return frozenset(
            FlextInfraUtilitiesProjectDiscovery.discover_rope_project_roots(
                repository_root
            )
        )

    @staticmethod
    def _inside_nested_repository(
        path: Path, repository_root: Path, *, governed_roots: frozenset[Path]
    ) -> bool:
        """Exclude foreign nested Git checkouts, never declared governed members.

        A governed workspace member (a submodule declared in ``.gitmodules``,
        or scanned as a candidate project) carries its own ``.git`` root by
        design; that is not a foreign nested repository and must stay
        indexed. Only a ``.git`` boundary that is not one of the workspace's
        own governed roots — an unrelated clone, an ad hoc worktree — is
        excluded.
        """
        return any(
            ((parent / ".git").exists() or (parent / ".git").is_symlink())
            and parent not in governed_roots
            for parent in path.parents
            if parent != repository_root and parent.is_relative_to(repository_root)
        )

    @classmethod
    def _is_pruned_walk_dir(
        cls, directory: Path, resolved_root: Path, *, governed_roots: frozenset[Path]
    ) -> bool:
        """Return whether the pruned stub walk must not descend into ``directory``."""
        return (
            (
                ((directory / ".git").exists() or (directory / ".git").is_symlink())
                and directory not in governed_roots
            )
            or cls._inside_nested_repository(
                directory, resolved_root, governed_roots=governed_roots
            )
            or bool(
                set(directory.relative_to(resolved_root).parts) & cls._excluded_parts()
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
        """
        governed_roots = cls._governed_roots(resolved_root)
        stub_paths: set[Path] = set()
        for parent, dir_names, file_names in resolved_root.walk():
            dir_names[:] = [
                name
                for name in dir_names
                if not cls._is_pruned_walk_dir(
                    parent / name, resolved_root, governed_roots=governed_roots
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
        cls, rope_project: t.Infra.RopeProject, resolved_root: Path
    ) -> t.VariadicTuple[Path]:
        """Return indexed sources, declared wrapper modules, and typing stubs."""
        governed_roots = cls._governed_roots(resolved_root)
        python_paths = {
            path.resolve()
            for path in FlextInfraUtilitiesRopeCore.python_file_paths(rope_project)
            if not set(path.relative_to(resolved_root).parts) & cls._excluded_parts()
            and not cls._inside_nested_repository(
                path, resolved_root, governed_roots=governed_roots
            )
        }
        # flext-pulj (codex): Rope's source roots omit tests/examples/scripts;
        # index those declared wrapper surfaces so explicitly targeted codegen
        # can update their generated initializers without textual fallbacks.
        wrapper_paths = {
            path.resolve()
            for wrapper_name in c.Infra.ROOT_WRAPPER_SEGMENTS
            for wrapper_root in (resolved_root / wrapper_name,)
            if wrapper_root.is_dir()
            for path in wrapper_root.rglob("*.py")
            if path.is_file()
            and not set(path.relative_to(resolved_root).parts) & cls._excluded_parts()
            and not cls._inside_nested_repository(
                path, resolved_root, governed_roots=governed_roots
            )
        }
        stub_paths = cls._pruned_stub_file_paths(resolved_root)
        return tuple(
            sorted(python_paths | wrapper_paths | stub_paths, key=Path.as_posix)
        )

    @classmethod
    def _collect_modules(
        cls, rope_project: t.Infra.RopeProject, resolved_root: Path
    ) -> tuple[
        MutableMapping[str, m.Infra.RopeModuleIndexEntry],
        MutableMapping[Path, list[m.Infra.RopeModuleIndexEntry]],
        MutableMapping[str, Path],
        MutableMapping[str, str],
        set[Path],
    ]:
        """Collect modules."""
        modules_by_path: MutableMapping[str, m.Infra.RopeModuleIndexEntry] = {}
        modules_by_dir: MutableMapping[Path, list[m.Infra.RopeModuleIndexEntry]] = {}
        package_dir_by_name: MutableMapping[str, Path] = {}
        project_package_by_root: MutableMapping[str, str] = {}
        package_dirs: set[Path] = set()
        # Hermetic index: iterate the discovery output in sorted path order so
        # every derived structure (index, lazy maps, generated facades) is
        # byte-identical across environments regardless of fs enumeration.
        for file_path in sorted(
            cls._python_and_stub_file_paths(rope_project, resolved_root), key=str
        ):
            resolved_file_path = file_path.resolve()
            if cls._is_generated_init_stub(resolved_file_path):
                continue
            if not resolved_file_path.is_relative_to(resolved_root):
                continue
            resource_path = resolved_file_path.relative_to(resolved_root).as_posix()
            package_dir = resolved_file_path.parent
            is_package_init = resolved_file_path.name in {
                c.Infra.INIT_PY,
                c.Infra.INIT_PYI,
            }
            project_root = cls._project_root_for_file(resolved_root, resolved_file_path)
            module_name = (
                cls._module_name_for_file(resolved_file_path, project_root=project_root)
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

    @classmethod
    def index_rope_workspace(
        cls, rope_project: t.Infra.RopeProject, repository_root: Path
    ) -> m.Infra.RopeWorkspaceIndex:
        """Build a generic Rope workspace index for package-oriented planning."""
        resolved_root = repository_root.resolve()
        (
            modules_by_path,
            modules_by_dir,
            package_dir_by_name,
            project_package_by_root,
            package_dirs,
        ) = cls._collect_modules(rope_project, resolved_root)
        sorted_package_dirs = tuple(sorted(package_dirs))
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
        packages_by_dir: MutableMapping[str, m.Infra.RopePackageIndexEntry] = {}
        for package_dir in sorted_package_dirs:
            dir_modules = tuple(
                sorted(
                    modules_by_dir.get(package_dir, ()),
                    key=operator.attrgetter("file_path.name"),
                )
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
            if package_name and package_name not in package_dir_by_name:
                package_dir_by_name[package_name] = package_dir
            if (
                project_root is not None
                and "." not in package_name
                and package_dir.parent.name == c.Infra.DEFAULT_SRC_DIR
                and str(project_root) not in project_package_by_root
            ):
                project_package_by_root[str(project_root)] = package_name
            direct_child_dirs = tuple(direct_children_by_dir.get(package_dir, ()))
            descendant_child_dirs = tuple(descendants_by_dir.get(package_dir, ()))
            packages_by_dir[str(package_dir)] = m.Infra.RopePackageIndexEntry(
                package_dir=package_dir,
                init_path=init_path,
                package_name=package_name,
                project_root=project_root,
                modules=dir_modules,
                direct_child_dirs=direct_child_dirs,
                descendant_child_dirs=descendant_child_dirs,
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
