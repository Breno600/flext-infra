"""Phase: Ensure bounded Hatch wheel and source-distribution targets.

Every project's wheel gets an explicit ``[tool.hatch.build.targets.wheel]``
with the primary ``src/<pkg>`` plus every project-declared additional package.
Project-declared standalone modules under ``src/<module>.py`` and root data
directories declared by the project are force-included into the wheel when they exist at the
project root, so they survive ``pip install`` (``<pkg>/<dir>``). The source
distribution is bounded to the package source and those validated data roots,
preventing caches and ignored workspace state from entering release artifacts.
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, m, t, u


class FlextInfraEnsurePackagingPhase:
    """Ensure bounded Hatch wheel and source-distribution targets."""

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
                    operations=(toml.ListOp(key="packages", values=package_paths),),
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
        packaged_data_dirs: t.StrSequence = (),
    ) -> t.StrSequence:
        """Emit bounded build targets for a distributable project.

        Every package gets the same explicit targets so initial rendering and
        ongoing modernization converge. Only declared module/package roots and
        data directories that actually exist at the project root enter those
        targets, keeping distributions free of phantom paths.
        """
        project_dir = path.parent
        docs_meta = u.Infra.docs_meta_from_payload(payload)
        package_name = u.Infra.package_name_from_payload(
            project_dir, payload, docs_meta
        )
        if not package_name:
            if root_modules or root_packages:
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
        package_root = project_dir / c.Infra.DEFAULT_SRC_DIR / package_name
        for data_dir in packaged_data_dirs:
            if Path(data_dir).parts != (data_dir,):
                msg = f"packaged data directory must be a root directory: {data_dir}"
                raise ValueError(msg)
            if not (project_dir / data_dir).is_dir():
                msg = f"declared packaged data directory is missing: {data_dir}"
                raise FileNotFoundError(msg)
        present_dirs = tuple(
            data_dir
            for data_dir in dict.fromkeys(packaged_data_dirs)
            # Force-include a root data dir only when it exists at the project
            # root AND is not already shipped from inside the package (which
            # would collide on the same wheel path).
            if (project_dir / data_dir).is_dir()
            and not (package_root / data_dir).is_dir()
        )
        return u.Infra.apply_toml_phases(
            payload,
            self._phase(
                package_name=package_name,
                data_dirs=present_dirs,
                root_modules=root_modules,
                root_packages=root_packages,
            ),
        )


__all__: list[str] = ["FlextInfraEnsurePackagingPhase"]
