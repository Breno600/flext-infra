"""Phase: Ensure bounded Hatch wheel and source-distribution targets.

Every project's wheel gets an explicit ``[tool.hatch.build.targets.wheel]``
with the primary ``src/<pkg>`` plus every project-declared additional package.
Project-declared standalone modules under ``src/<module>.py`` and root data
paths declared by the project are validated and mapped into the package.
Directories use the same Hatch selection rules in both archives; explicit files
are included individually. The source
distribution is bounded to the package source and those validated data roots,
preventing caches and ignored workspace state from entering release artifacts.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import keyword
from pathlib import Path

from flext_infra import c, m, t, u


class FlextInfraEnsurePackagingPhase:
    """Ensure bounded Hatch wheel and source-distribution targets."""

    @staticmethod
    def _validate_data_tree(
        root: Path,
        source: Path,
        ancestors: frozenset[Path],
    ) -> None:
        """Follow every link Hatch follows while rejecting cycles and escape.

        Raises:
            ValueError: If packaged data path escapes repository; or if packaged data
                directory cycle; or if packaged data path is not a file or directory.

        """
        resolved = source.resolve(strict=True)
        if not resolved.is_relative_to(root):
            msg = f"packaged data path escapes repository: {source}"
            raise ValueError(msg)
        if resolved in ancestors:
            msg = f"packaged data directory cycle: {source}"
            raise ValueError(msg)
        if source.is_dir():
            for child in source.iterdir():
                FlextInfraEnsurePackagingPhase._validate_data_tree(
                    root,
                    child,
                    ancestors | {resolved},
                )
        elif not source.is_file():
            msg = f"packaged data path is not a file or directory: {source}"
            raise ValueError(msg)

    @staticmethod
    def resolve_data_paths(
        project_dir: Path,
        package_name: str,
        declarations: t.StrSequence,
        planned_files: t.StrSequence = (),
    ) -> m.Infra.PackagedDataSelection:
        """Validate existing inputs or exact future scaffold destinations.

        Returns:
            The resulting ``m.Infra.PackagedDataSelection``.

        Raises:
            FileNotFoundError: If declared packaged data path is missing.
            ValueError: If packaged data path must be repository-relative; or if
                packaged data path escapes repository; or if packaged data path collides
                with package source; or if packaged data declarations overlap.

        """
        root = project_dir.resolve()
        package_root = root / c.Infra.DEFAULT_SRC_DIR / package_name
        paths: list[Path] = []
        files: list[str] = []
        directories: list[str] = []
        for declaration in declarations:
            relative = Path(declaration)
            if (
                relative.is_absolute()
                or not relative.parts
                or ".." in relative.parts
                or relative.as_posix() != declaration
            ):
                msg = f"packaged data path must be repository-relative: {declaration}"
                raise ValueError(msg)
            source = root / relative
            if not source.resolve().is_relative_to(root):
                msg = f"packaged data path escapes repository: {declaration}"
                raise ValueError(msg)
            if source.exists() or source.is_symlink():
                FlextInfraEnsurePackagingPhase._validate_data_tree(
                    root,
                    source,
                    frozenset(),
                )
            elif not any(
                Path(planned).is_relative_to(relative) for planned in planned_files
            ):
                msg = f"declared packaged data path is missing: {declaration}"
                raise FileNotFoundError(msg)
            destination = package_root / relative
            if (
                destination.exists()
                or any(
                    parent.is_file() for parent in destination.parents if parent != root
                )
                or any(
                    (root / planned).is_relative_to(destination)
                    for planned in planned_files
                )
            ):
                msg = f"packaged data path collides with package source: {declaration}"
                raise ValueError(msg)
            if any(
                relative.is_relative_to(previous) or previous.is_relative_to(relative)
                for previous in paths
            ):
                msg = f"packaged data declarations overlap: {declaration}"
                raise ValueError(msg)
            paths.append(relative)
            if source.is_file() or declaration in planned_files:
                files.append(declaration)
            else:
                directories.append(declaration)
        return m.Infra.PackagedDataSelection(
            files=tuple(files),
            directories=tuple(directories),
        )

    @staticmethod
    def resolve_data_excludes(
        project_dir: Path,
        data: m.Infra.PackagedDataSelection,
        declarations: t.StrSequence,
    ) -> t.StrSequence:
        """Validate exact files omitted within declared distribution directories.

        Returns:
            The resulting ``t.StrSequence``.

        Raises:
            ValueError: If invalid packaged data exclusion.

        """
        root = project_dir.resolve()
        directories = tuple(Path(item) for item in data.directories)
        excluded: list[str] = []
        for declaration in declarations:
            relative = Path(declaration)
            source = root / relative
            valid_path = (
                bool(declaration)
                and not relative.is_absolute()
                and ".." not in relative.parts
                and relative.as_posix() == declaration
                and source.resolve().is_relative_to(root)
            )
            declared_child = any(
                relative.is_relative_to(directory) and relative != directory
                for directory in directories
            )
            if (
                not valid_path
                or not declared_child
                or (
                    declaration in excluded
                    or not source.is_file()
                    or source.is_symlink()
                )
            ):
                msg = f"invalid packaged data exclusion: {declaration}"
                raise ValueError(msg)
            excluded.append(declaration)
        return tuple(excluded)

    @staticmethod
    def _phase(
        *,
        package_name: str,
        data: m.Infra.PackagedDataSelection,
        data_excludes: t.StrSequence,
        surfaces: t.Triple[t.StrSequence, t.StrSequence, t.StrSequence],
    ) -> m.Infra.DepsToml.PhaseConfig:
        """Build bounded distribution targets for one resolved package name.

        Returns:
            The resulting ``m.Infra.DepsToml.PhaseConfig``.

        """
        root_modules, root_packages, repository_namespace_packages = surfaces
        package_path = f"{c.Infra.DEFAULT_SRC_DIR}/{package_name}"
        package_paths = (
            package_path,
            *(f"{c.Infra.DEFAULT_SRC_DIR}/{package}" for package in root_packages),
        )
        module_paths = tuple(
            f"{c.Infra.DEFAULT_SRC_DIR}/{module}.py" for module in root_modules
        )
        selected_directories = (
            *package_paths,
            *data.directories,
            *repository_namespace_packages,
        )
        toml = m.Infra.DepsToml
        force_include = tuple(
            (data_dir, f"{package_name}/{data_dir}") for data_dir in data.files
        ) + tuple(
            (module_path, f"{module}.py")
            for module_path, module in zip(module_paths, root_modules, strict=True)
        )
        return toml.PhaseConfig(
            name="packaging",
            table_path=("hatch", "build", "targets"),
            nested_tables=(
                toml.PhaseConfig(
                    name="packaging",
                    root_path=(),
                    table_path=("wheel",),
                    operations=(
                        toml.ListOp(
                            key="only-include",
                            values=selected_directories,
                        ),
                        toml.RemoveOp(key="packages"),
                        toml.RemoveOp(key="include"),
                        toml.SetOp(
                            key="sources",
                            value={
                                **dict(
                                    zip(
                                        package_paths,
                                        (package_name, *root_packages),
                                        strict=True,
                                    ),
                                ),
                                **{
                                    directory: f"{package_name}/{directory}"
                                    for directory in data.directories
                                },
                                **{
                                    namespace: namespace
                                    for namespace in repository_namespace_packages
                                },
                            },
                        ),
                        toml.RemoveOp(key="force-include"),
                    ),
                ),
                toml.PhaseConfig(
                    name="packaging",
                    root_path=(),
                    table_path=("sdist",),
                    operations=(
                        toml.ListOp(
                            key="only-include",
                            values=selected_directories,
                        ),
                        toml.RemoveOp(key="packages"),
                        toml.RemoveOp(key="include"),
                        (
                            toml.ListOp(
                                key="exclude",
                                values=tuple(f"/{item}" for item in data_excludes),
                            )
                            if data_excludes
                            else toml.RemoveOp(key="exclude")
                        ),
                        toml.RemoveOp(key="force-include"),
                    ),
                ),
                (
                    toml.PhaseConfig(
                        name="packaging",
                        root_path=(),
                        table_path=("sdist", "force-include"),
                        operations=tuple(
                            toml.SetOp(key=source, value=source)
                            for source, _destination in force_include
                        ),
                    )
                    if force_include
                    else toml.PhaseConfig(
                        name="packaging",
                        root_path=(),
                        table_path=("sdist",),
                        operations=(toml.RemoveOp(key="force-include"),),
                    )
                ),
                (
                    toml.PhaseConfig(
                        name="packaging",
                        root_path=(),
                        table_path=("wheel", "force-include"),
                        operations=tuple(
                            toml.SetOp(key=key, value=value)
                            for key, value in force_include
                        ),
                    )
                    if force_include
                    else toml.PhaseConfig(
                        name="packaging",
                        root_path=(),
                        table_path=("wheel",),
                        operations=(toml.RemoveOp(key="force-include"),),
                    )
                ),
            ),
        )

    def apply_payload(
        self,
        payload: t.MutableJsonMapping,
        *,
        path: Path,
        topology: m.Infra.PyprojectDeclaredTopology,
    ) -> t.StrSequence:
        """Emit bounded build targets for a distributable project.

        Every package gets the same explicit targets so initial rendering and
        ongoing modernization converge. Only declared module/package roots and
        data paths enter those targets after existence, containment and collision
        validation, keeping both distribution formats consistent.

        Returns:
            The resulting ``t.StrSequence``.

        Raises:
            FileNotFoundError: If declared project root module source is missing; or if
                declared project root package source is missing a package initializer;
                or if repository namespace directory is missing.
            ValueError: If project package name is required when additional distribution
                roots are declared; or if repository namespace must be one Python
                identifier; or if repository namespace must be implicit; or if
                repository namespace overlaps packaged data.

        """
        project_dir = path.parent
        docs_meta = u.Infra.docs_meta_from_payload(payload)
        package_name = u.Infra.package_name_from_payload(
            project_dir,
            payload,
            docs_meta,
        )
        if not package_name:
            if (
                topology.root_modules
                or topology.root_packages
                or topology.packaged_data_paths
                or topology.repository_namespace_packages
            ):
                msg = (
                    "project package name is required when additional distribution "
                    "roots are declared"
                )
                raise ValueError(msg)
            return ()
        source_root = project_dir / c.Infra.DEFAULT_SRC_DIR
        missing_module = next(
            (
                source_root / f"{module}.py"
                for module in topology.root_modules
                if not (source_root / f"{module}.py").is_file()
            ),
            None,
        )
        if missing_module is not None:
            msg = f"declared project root module source is missing: {missing_module}"
            raise FileNotFoundError(msg)
        missing_package = next(
            (
                source_root / package
                for package in topology.root_packages
                if not (source_root / package).is_dir()
                or not (source_root / package / c.Infra.INIT_PY).is_file()
            ),
            None,
        )
        if missing_package is not None:
            msg = (
                "declared project root package source is missing a package "
                f"initializer: {missing_package / c.Infra.INIT_PY}"
            )
            raise FileNotFoundError(msg)
        for namespace in topology.repository_namespace_packages:
            relative = Path(namespace)
            source = project_dir / relative
            if (
                len(relative.parts) != 1
                or not namespace.isidentifier()
                or keyword.iskeyword(namespace)
            ):
                msg = f"repository namespace must be one Python identifier: {namespace}"
                raise ValueError(msg)
            if not source.is_dir() or source.is_symlink():
                msg = f"repository namespace directory is missing: {source}"
                raise FileNotFoundError(msg)
            if (source / c.Infra.INIT_PY).exists():
                msg = f"repository namespace must be implicit: {source}"
                raise ValueError(msg)
            self._validate_data_tree(project_dir.resolve(), source, frozenset())
            if any(
                path == namespace or path.startswith(f"{namespace}/")
                for path in topology.packaged_data_paths
            ):
                msg = f"repository namespace overlaps packaged data: {namespace}"
                raise ValueError(msg)
        data_paths = self.resolve_data_paths(
            project_dir,
            package_name,
            topology.packaged_data_paths,
            topology.planned_data_files,
        )
        data_excludes = self.resolve_data_excludes(
            project_dir,
            data_paths,
            topology.packaged_data_excludes,
        )
        return u.Infra.apply_toml_phases(
            payload,
            self._phase(
                package_name=package_name,
                data=data_paths,
                data_excludes=data_excludes,
                surfaces=(
                    topology.root_modules,
                    topology.root_packages,
                    topology.repository_namespace_packages,
                ),
            ),
        )


__all__: list[str] = ["FlextInfraEnsurePackagingPhase"]
