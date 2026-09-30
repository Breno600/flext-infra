"""Phase: Ensure bounded Hatch wheel and source-distribution targets.

Every project's wheel gets an explicit ``[tool.hatch.build.targets.wheel]``
with the primary ``src/<pkg>`` plus every project-declared additional package.
Project-declared standalone modules under ``src/<module>.py`` and root data
paths declared by the project are validated and force-included into the wheel, so they survive ``pip install`` (``<pkg>/<dir>``). The source
distribution is bounded to the package source and those validated data roots,
preventing caches and ignored workspace state from entering release artifacts.
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, m, t, u


class FlextInfraEnsurePackagingPhase:
    """Ensure bounded Hatch wheel and source-distribution targets."""

    @staticmethod
    def resolve_data_paths(
        project_dir: Path, package_name: str, declarations: t.StrSequence
    ) -> t.StrTuple:
        """Validate archive inputs before rendering or changing a manifest."""
        root = project_dir.resolve()
        package_root = root / c.Infra.DEFAULT_SRC_DIR / package_name
        paths: list[Path] = []
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
            if not source.exists():
                msg = f"declared packaged data path is missing: {declaration}"
                raise FileNotFoundError(msg)
            if not source.resolve().is_relative_to(root):
                msg = f"packaged data path escapes repository: {declaration}"
                raise ValueError(msg)
            if not source.is_file() and not source.is_dir():
                msg = f"packaged data path is not a file or directory: {declaration}"
                raise ValueError(msg)
            if (package_root / relative).exists():
                msg = f"packaged data path collides with package source: {declaration}"
                raise ValueError(msg)
            if any(
                relative.is_relative_to(previous)
                or previous.is_relative_to(relative)
                for previous in paths
            ):
                msg = f"packaged data declarations overlap: {declaration}"
                raise ValueError(msg)
            if source.is_dir():
                for child in source.rglob("*"):
                    if not child.resolve().is_relative_to(root):
                        msg = f"packaged data path escapes repository: {child}"
                        raise ValueError(msg)
            paths.append(relative)
        return tuple(path.as_posix() for path in paths)

    def _phase(
        self,
        *,
        package_name: str,
        data_dirs: t.StrSequence,
        root_modules: t.StrSequence,
        root_packages: t.StrSequence,
    ) -> m.Infra.DepsToml.PhaseConfig:
        """Build bounded distribution targets for one resolved package name."""
        package_path = f"{c.Infra.DEFAULT_SRC_DIR}/{package_name}"
        package_paths = (
            package_path,
            *(f"{c.Infra.DEFAULT_SRC_DIR}/{package}" for package in root_packages),
        )
        module_paths = tuple(
            f"{c.Infra.DEFAULT_SRC_DIR}/{module}.py" for module in root_modules
        )
        toml = m.Infra.DepsToml
        force_include = tuple(
            (data_dir, f"{package_name}/{data_dir}") for data_dir in data_dirs
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
                        toml.ListOp(key="packages", values=package_paths),
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
                            values=(*package_paths, *module_paths, *data_dirs),
                        ),
                    ),
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
        root_modules: t.StrSequence = (),
        root_packages: t.StrSequence = (),
        packaged_data_paths: t.StrSequence = (),
    ) -> t.StrSequence:
        """Emit bounded build targets for a distributable project.

        Every package gets the same explicit targets so initial rendering and
        ongoing modernization converge. Only declared module/package roots and
        data paths enter those targets after existence, containment and collision
        validation, keeping both distribution formats consistent.
        """
        project_dir = path.parent
        docs_meta = u.Infra.docs_meta_from_payload(payload)
        package_name = u.Infra.package_name_from_payload(
            project_dir, payload, docs_meta
        )
        if not package_name:
            if root_modules or root_packages or packaged_data_paths:
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
                for module in root_modules
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
                for package in root_packages
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
        data_paths = self.resolve_data_paths(
            project_dir, package_name, packaged_data_paths
        )
        return u.Infra.apply_toml_phases(
            payload,
            self._phase(
                package_name=package_name,
                data_dirs=data_paths,
                root_modules=root_modules,
                root_packages=root_packages,
            ),
        )


__all__: list[str] = ["FlextInfraEnsurePackagingPhase"]
