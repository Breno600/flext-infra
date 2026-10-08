"""Project discovery utilities for package and workspace resolution.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from importlib import util as importlib_util
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from flext_infra import c, r, t
from flext_infra._utilities import (
    FlextInfraUtilitiesNamespaceConfig,
    FlextInfraUtilitiesProjectDiscovery,
    FlextInfraUtilitiesPyproject,
    FlextInfraUtilitiesRopeAnalysis,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from flext_infra import p


class FlextInfraUtilitiesDiscovery(
    FlextInfraUtilitiesNamespaceConfig,
    FlextInfraUtilitiesProjectDiscovery,
    FlextInfraUtilitiesPyproject,
    FlextInfraUtilitiesRopeAnalysis,
):
    """Canonical discovery helpers for path, package, and Rope-backed scans."""

    _PARENT_CONSTANTS_FLEXT_CACHE: ClassVar[
        MutableMapping[t.Pair[str, bool], t.StrSequence]
    ] = {}

    @staticmethod
    def _discover_project_root_from_path(file_path: str) -> str:
        """Discover the enclosing project root path cached by file path.

        Returns:
            The resulting ``str``.

        """
        resolved = Path(file_path).resolve()
        candidate = (
            resolved.parent if resolved.suffix == c.Infra.EXT_PYTHON else resolved
        )
        wrapper_root: Path | None = None
        for current in (candidate, *candidate.parents):
            if current.name == c.Infra.DEFAULT_SRC_DIR:
                wrapper_root = current.parent
                continue
            if current.name in c.Infra.ROOT_WRAPPER_SEGMENTS:
                wrapper_root = current.parent
                continue
            if (current / c.Infra.DEFAULT_SRC_DIR).is_dir():
                relative = candidate.relative_to(current)
                if (
                    not relative.parts
                    or relative.parts[0] in c.Infra.ROOT_WRAPPER_SEGMENTS
                ):
                    return str(current)
        return str(wrapper_root) if wrapper_root is not None else ""

    @staticmethod
    def _relative_path_parts(resolved: Path, project_root: Path | None) -> t.StrTuple:
        """Return path parts relative to project root when possible.

        Returns:
            Path parts relative to project root when possible.

        """
        if project_root is None or not resolved.is_relative_to(project_root):
            return ()
        return resolved.relative_to(project_root).parts

    @staticmethod
    def _normalized_python_parts(resolved: Path, path_parts: t.StrTuple) -> t.StrTuple:
        """Normalize filesystem parts into package/module parts.

        Returns:
            The resulting ``t.StrTuple``.

        """
        if path_parts and path_parts[-1] == c.Infra.INIT_PY:
            return path_parts[:-1]
        if resolved.suffix == c.Infra.EXT_PYTHON and path_parts:
            return (*path_parts[:-1], resolved.stem)
        return path_parts

    @staticmethod
    def _package_name_from_wrapper_parts(path_parts: t.StrSequence) -> str:
        """Return package name when path parts start with a known wrapper.

        Returns:
            Package name when path parts start with a known wrapper.

        """
        if not path_parts:
            return ""
        root_name = path_parts[0]
        if root_name not in c.Infra.ROOT_WRAPPER_SEGMENTS:
            return ""
        package_parts = (
            path_parts[1:] if root_name == c.Infra.DEFAULT_SRC_DIR else path_parts
        )
        return ".".join(package_parts)

    @staticmethod
    def _package_name_from_src_dir(resolved: Path) -> str:
        """Return the package name when the path is a project root with src/<pkg>.

        Returns:
            The package name when the path is a project root with src/<pkg>.

        """
        src_dir = resolved / c.Infra.DEFAULT_SRC_DIR
        if not src_dir.is_dir():
            return ""
        for child in sorted(src_dir.iterdir()):
            if child.is_dir() and (child / c.Infra.INIT_PY).is_file():
                child_path: Path = child
                return child_path.name
        return ""

    @staticmethod
    def pytest_test_module(file_path: Path) -> bool:
        """Return whether a file is a pytest test module, not a production module.

        Returns:
            Whether a file is a pytest test module, not a production module.

        """
        if c.Infra.DIR_TESTS not in file_path.parts:
            return False
        file_name = file_path.name
        return file_name.startswith(
            c.Infra.NAMESPACE_PYTEST_MODULE_PREFIX,
        ) or file_name.endswith(tuple(c.Infra.NAMESPACE_PYTEST_MODULE_SUFFIXES))

    @staticmethod
    def project_root(file_path: Path) -> Path | None:
        """Discover the enclosing project root for one file or directory path.

        Returns:
            The resulting ``Path | None``.

        """
        project_root = FlextInfraUtilitiesDiscovery._discover_project_root_from_path(
            str(file_path),
        )
        return Path(project_root) if project_root else None

    @classmethod
    def _discover_package_from_path(cls, file_path: str) -> str:
        """Discover the package path cached by file path.

        Returns:
            The resulting ``str``.

        """
        resolved = Path(file_path).resolve()
        project_root_value = cls._discover_project_root_from_path(file_path)
        project_root = Path(project_root_value) if project_root_value else None
        normalized_parts = cls._normalized_python_parts(
            resolved,
            cls._relative_path_parts(resolved, project_root),
        )
        package_name = cls._package_name_from_wrapper_parts(normalized_parts)
        if package_name:
            return package_name
        package_name = cls._package_name_from_src_dir(resolved)
        if package_name:
            return package_name
        absolute_parts = cls._normalized_python_parts(resolved, resolved.parts)
        for index, part in enumerate(absolute_parts):
            package_name = cls._package_name_from_wrapper_parts(absolute_parts[index:])
            if package_name and part in c.Infra.ROOT_WRAPPER_SEGMENTS:
                return package_name
        if resolved.name == c.Infra.INIT_PY:
            top_level_parts = tuple(
                part for part in absolute_parts if part and part != resolved.anchor
            )
            match top_level_parts:
                case (_, package_name):
                    resolved_package: str = package_name
                    return resolved_package
                case _:
                    pass
        if project_root is None:
            return ""

        return cls.project_package_name(project_root)

    @classmethod
    def package_name(cls, file_path: Path) -> str:
        """Discover the module or package path for one Python file or package directory.

        Returns:
            The resulting ``str``.

        """
        return cls._discover_package_from_path(str(file_path))

    @staticmethod
    def declared_package_dir(package_name: str) -> Path | None:
        """Return the package directory the active environment declares for a name.

        One rule, no alternative source (R32): a name outside the repository
        index is read from the environment the checkout declares (an editable
        workspace member or the pinned distribution — `find_spec`, no import
        executed). ``None`` is the typed absence: the name is not a package
        in this environment (absent, or a plain module). A caller that
        REQUIRES the package — a declared facade parent — raises.

        Returns:
            The package directory the active environment declares for a name.

        """
        spec = importlib_util.find_spec(package_name)
        if spec is None or not spec.submodule_search_locations:
            return None
        return Path(next(iter(spec.submodule_search_locations)))

    @classmethod
    def discover_python_dirs(
        cls,
        project_dir: Path,
        *,
        workspace_excluded_top_dirs: frozenset[str],
        skip_dirs: frozenset[str] | None = None,
    ) -> t.StrSequence:
        """Return top-level directories that contain at least one Python file.

        ``workspace_excluded_top_dirs`` is the caller's validated analysis
        scope: the service that owns the workspace topology computes it and
        passes it in, so discovery never reaches back into that service.

        Returns:
            Top-level directories that contain at least one Python file.

        """
        if not project_dir.is_dir():
            return list[str]()
        effective_skip = (
            skip_dirs if skip_dirs is not None else c.Infra.PYTHON_DISCOVERY_SKIP_DIRS
        )
        return [
            subdir.name
            for subdir in sorted(project_dir.iterdir())
            if subdir.is_dir()
            and not subdir.name.startswith(".")
            and subdir.name not in effective_skip
            and subdir.name not in workspace_excluded_top_dirs
            and any(
                cls._python_file_belongs_to_project(project_dir, source)
                for source in cls._walk_python_files(subdir, effective_skip)
            )
        ]

    @classmethod
    def discover_python_targets(
        cls,
        project_dir: Path,
        *,
        workspace_excluded_top_dirs: frozenset[str],
    ) -> t.StrSequence:
        """Return every first-party Python target owned by one project root.

        Directory discovery alone omits standalone modules stored directly at
        the repository root. Analyzer and codemod gates must use the same
        complete target inventory so semantic discovery cannot find a file
        that their safety measurements silently exclude.

        Returns:
            Every first-party Python target owned by one project root.

        """
        if not project_dir.is_dir():
            return list[str]()
        root_modules = [
            path.name
            for path in sorted(project_dir.iterdir())
            if path.is_file() and path.suffix in {".py", ".pyi"}
        ]
        return [
            *cls.discover_python_dirs(
                project_dir,
                workspace_excluded_top_dirs=workspace_excluded_top_dirs,
            ),
            *root_modules,
        ]

    @staticmethod
    def _walk_python_files(
        directory: Path,
        skip_dirs: frozenset[str],
    ) -> Iterator[Path]:
        """Yield Python files under ``directory``, pruning skipped directories.

        ``skip_dirs`` names trees that are never first-party source: virtual
        environments, caches, build output, vendored code. ``Path.rglob`` has no
        way to prune, so it descends into them and the walk costs whatever those
        directories happen to contain — in a workspace whose members each own a
        populated ``.venv`` that is tens of thousands of irrelevant files, and
        the caller's only signal is a timeout. Pruning applies the same names at
        every depth instead of only to the top-level entry.

        Yields:
            Each ``Path``.

        """
        for parent, child_dirs, file_names in directory.walk():
            child_dirs[:] = [
                name
                for name in child_dirs
                if name not in skip_dirs and not name.startswith(".")
            ]
            for file_name in file_names:
                if file_name.endswith((c.Infra.EXT_PYTHON, ".pyi")):
                    yield parent / file_name

    @staticmethod
    def _python_file_belongs_to_project(project_dir: Path, source: Path) -> bool:
        """Return whether ``source`` is owned by ``project_dir``'s manifest.

        Returns:
            Whether ``source`` is owned by ``project_dir``'s manifest.

        """
        for parent in source.parents:
            if parent == project_dir:
                return True
            if (parent / c.PYPROJECT_FILENAME).is_file():
                return False
        return False

    @classmethod
    def analyzer_python_roots(
        cls,
        project_dir: Path,
        declared: t.StrSequence,
        *,
        workspace_excluded_top_dirs: frozenset[str],
    ) -> t.StrSequence:
        """Return the Python roots every analyzer surface must agree on.

        Conform, the deps modernizer and the extra-paths sync each described
        the same concept on their own: some filtered the declared ``env_dirs``
        by existence, others discovered roots on disk. A project owning a
        Python directory outside ``env_dirs`` therefore had that root written
        by one surface and erased by the next, so apply never reached a fixed
        point and check reported permanent drift. This is the single owner:
        declared roots keep their configured order, because a pre-write
        scaffold can only offer those, and discovery appends the remaining
        roots that actually exist, which is the only set an analyzer accepts.

        A directory owning a ``pyproject.toml`` is a project in its own right,
        never a root of this one: workspace subprojects are Python directories
        too, and each is analyzed under its own local configuration.

        Returns:
            The Python roots every analyzer surface must agree on.

        """
        discovered = cls.discover_python_dirs(
            project_dir,
            workspace_excluded_top_dirs=workspace_excluded_top_dirs,
        )
        return (
            *declared,
            *(
                root
                for root in discovered
                if root not in declared
                and not (project_dir / root / c.PYPROJECT_FILENAME).is_file()
            ),
        )

    @classmethod
    def rope_repository_root(cls, repository_root: Path) -> Path:
        """Resolve a local project without expanding it to an ancestor workspace.

        Returns:
            The resulting ``Path``.

        """
        resolved_root = repository_root.resolve()
        execution_dir = (
            resolved_root if resolved_root.is_dir() else resolved_root.parent
        )
        discovered_root = cls.project_root(resolved_root)
        project_root = discovered_root
        if (
            resolved_root.is_dir()
            and not (execution_dir / c.PYPROJECT_FILENAME).is_file()
        ):
            relative_parts = (
                resolved_root.relative_to(discovered_root).parts
                if discovered_root is not None
                and resolved_root.is_relative_to(discovered_root)
                else ()
            )
            if (
                not relative_parts
                or relative_parts[0] not in c.Infra.ROOT_WRAPPER_SEGMENTS
            ):
                project_root = resolved_root
        if project_root is not None and (
            (project_root / c.PYPROJECT_FILENAME).is_file()
            or (project_root / c.Infra.GIT_DIR).exists()
        ):
            return project_root
        return resolved_root

    @classmethod
    def find_all_pyproject_files(
        cls,
        repository_root: Path,
        *,
        skip_dirs: frozenset[str] | None = None,
        project_paths: t.SequenceOf[Path] | None = None,
    ) -> p.Result[t.SequenceOf[Path]]:
        """Find all managed ``pyproject.toml`` files for one workspace root.

        Returns:
            The resulting ``p.Result[t.SequenceOf[Path]]``.

        """
        if not repository_root.exists() or not repository_root.is_dir():
            return r[t.SequenceOf[Path]].ok([])
        effective_skip = skip_dirs if skip_dirs is not None else c.Infra.SKIP_DIRS
        # Explicit project paths are a hard write-scope boundary. Without one,
        # discovery is strictly local to the repository supplied by the caller.
        scan_roots = (
            sorted({project_path.resolve() for project_path in project_paths})
            if project_paths is not None
            else [repository_root.resolve()]
        )
        all_files: list[Path] = []
        for scan_root in scan_roots:
            if scan_root.is_file():
                if scan_root.name != c.PYPROJECT_FILENAME:
                    return r[t.SequenceOf[Path]].fail(
                        f"explicit project file must be "
                        f"{c.PYPROJECT_FILENAME}: {scan_root}",
                    )
                all_files.append(scan_root)
                continue
            if not scan_root.is_dir():
                return r[t.SequenceOf[Path]].fail(
                    f"explicit project path is not accessible: {scan_root}",
                )
            try:
                all_files.extend(
                    sorted(
                        path
                        for path in scan_root.rglob(c.PYPROJECT_FILENAME)
                        if not any(
                            part.startswith(".") or part in effective_skip
                            for part in path.relative_to(scan_root).parts[:-1]
                        )
                    ),
                )
            except OSError as exc:
                return r[t.SequenceOf[Path]].fail_op("pyproject file scan", exc)
        if project_paths is not None:
            all_files = [
                path
                for path in all_files
                if any(
                    path.is_relative_to(project_path) for project_path in project_paths
                )
            ]
        return r[t.SequenceOf[Path]].ok(all_files)


__all__: list[str] = ["FlextInfraUtilitiesDiscovery"]
