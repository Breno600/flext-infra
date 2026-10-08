"""Resolve a bounded candidate package from canonical pinned workspace sources.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from pathlib import Path

from flext_infra import c, m, p, r, u
from flext_infra.workspace import FlextInfraWorkspaceDetector


class FlextInfraStagedPackage:
    """Plan one complete package view and its static workspace import closure."""

    @staticmethod
    def workspace_root(root: Path) -> p.Result[Path]:
        """Resolve the package's Git workspace identity.

        Returns:
            The superproject root or the standalone repository root.
        """
        identity = u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=root))
        if identity.failure:
            return r[Path].from_failure(identity)
        return r[Path].ok(identity.value.superproject_root or identity.value.repo_root)

    @classmethod
    def plan(
        cls,
        root: Path,
        file: m.Infra.CodegenFilePlan,
    ) -> p.Result[m.Infra.StagePackagePlan]:
        """Pin the package closure and read its canonical facade contract.

        Returns:
            The immutable candidate plan or the first discovery failure.
        """
        result_type = r[m.Infra.StagePackagePlan]
        workspace = cls.workspace_root(root)
        if workspace.failure:
            return result_type.from_failure(workspace)
        discovered = cls._workspace_layouts(workspace.value)
        if discovered.failure:
            return result_type.from_failure(discovered)
        layouts = discovered.value
        local = u.Infra.layout(root)
        if local is None or file.desired_content is None:
            return result_type.fail(
                "staged facade requires an existing package and desired bytes"
            )
        layouts[local.package_name] = local
        selected: list[m.Infra.RopeProjectLayout] = []
        states: dict[Path, m.Cli.AtomicFileState] = {}
        pinned = cls._pin_closure(local, layouts, selected, states)
        if pinned.failure:
            return result_type.from_failure(pinned)
        metadata = cls._pin_workspace_metadata(workspace.value, states)
        if metadata.failure:
            return result_type.from_failure(metadata)
        return cls._facade_plan(file, local, selected, states, layouts)

    @staticmethod
    def _workspace_layouts(
        workspace: Path,
    ) -> p.Result[dict[str, m.Infra.RopeProjectLayout]]:

        spec = FlextInfraWorkspaceDetector.load_workspace_spec(workspace)
        if spec.failure:
            return r[dict[str, m.Infra.RopeProjectLayout]].from_failure(spec)
        layouts: dict[str, m.Infra.RopeProjectLayout] = {}
        for repository in (
            workspace,
            *(workspace / ref.path for ref in spec.value.subprojects),
        ):
            layout = u.Infra.layout(repository)
            if layout is not None:
                if layout.package_name in layouts:
                    return r[dict[str, m.Infra.RopeProjectLayout]].fail(
                        f"ambiguous candidate package: {layout.package_name}"
                    )
                layouts[layout.package_name] = layout
        return r[dict[str, m.Infra.RopeProjectLayout]].ok(layouts)

    @staticmethod
    def _source_paths(layout: m.Infra.RopeProjectLayout) -> p.Result[list[Path]]:
        paths = [layout.project_root / c.PYPROJECT_FILENAME]
        for directory in (
            layout.package_dir,
            layout.project_root / c.Infra.CODEGEN_CONFIG_DIR,
        ):
            if directory.is_symlink():
                return r[list[Path]].fail(
                    f"candidate source directory is a symlink: {directory}"
                )
            if directory.is_dir():
                paths.extend(
                    path
                    for path in directory.rglob("*")
                    if "__pycache__" not in path.parts
                )
        return r[list[Path]].ok(sorted(set(paths)))

    @staticmethod
    def _runtime_imports(path: Path, content: bytes) -> tuple[str, ...]:
        tree = ast.parse(content.decode(c.Cli.ENCODING_DEFAULT), filename=str(path))
        excluded = {
            id(child)
            for guard in ast.walk(tree)
            if isinstance(guard, ast.If)
            and (
                (isinstance(guard.test, ast.Name) and guard.test.id == "TYPE_CHECKING")
                or (
                    isinstance(guard.test, ast.Attribute)
                    and guard.test.attr == "TYPE_CHECKING"
                )
            )
            for statement in guard.body
            for child in ast.walk(statement)
        }
        modules: list[str] = []
        for node in ast.walk(tree):
            if id(node) in excluded:
                continue
            if isinstance(node, ast.ImportFrom) and not node.level and node.module:
                modules.append(node.module)
            elif isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
        return tuple(modules)

    @classmethod
    def _pin_layout(
        cls,
        layout: m.Infra.RopeProjectLayout,
        states: dict[Path, m.Cli.AtomicFileState],
    ) -> p.Result[tuple[str, ...]]:
        paths = cls._source_paths(layout)
        if paths.failure:
            return r[tuple[str, ...]].from_failure(paths)
        modules: list[str] = []
        for path in paths.value:
            if path.is_symlink():
                return r[tuple[str, ...]].fail(f"candidate source is a symlink: {path}")
            if not path.is_file():
                continue
            observed = u.Cli.atomic_read_binary_file_state(path, required=True)
            if observed.failure:
                return r[tuple[str, ...]].from_failure(observed)
            state = observed.value
            states[path] = state
            if path.suffix == c.Infra.EXT_PYTHON and state.content is not None:
                modules.extend(cls._runtime_imports(path, state.content))
        return r[tuple[str, ...]].ok(tuple(modules))

    @classmethod
    def _pin_closure(
        cls,
        local: m.Infra.RopeProjectLayout,
        layouts: dict[str, m.Infra.RopeProjectLayout],
        selected: list[m.Infra.RopeProjectLayout],
        states: dict[Path, m.Cli.AtomicFileState],
    ) -> p.Result[bool]:
        queue = [local.package_name]
        while queue:
            name = queue.pop(0)
            layout = layouts[name]
            selected.append(layout)
            pinned = cls._pin_layout(layout, states)
            if pinned.failure:
                return r[bool].from_failure(pinned)
            for module in pinned.value:
                dependency = module.partition(".")[0]
                if (
                    dependency in layouts
                    and dependency not in queue
                    and not any(item.package_name == dependency for item in selected)
                ):
                    queue.append(dependency)
        return r[bool].ok(value=True)

    @staticmethod
    def _pin_workspace_metadata(
        workspace: Path,
        states: dict[Path, m.Cli.AtomicFileState],
    ) -> p.Result[bool]:
        for path in (
            workspace / c.PYPROJECT_FILENAME,
            workspace / ".gitmodules",
            workspace / "uv.lock",
        ):
            observed = u.Cli.atomic_read_binary_file_state(path, required=False)
            if observed.failure:
                return r[bool].from_failure(observed)
            states[path] = observed.value
        return r[bool].ok(value=True)

    @staticmethod
    def _absolute_imports(tree: ast.Module) -> dict[str, tuple[str, str]]:
        return {
            alias.asname or alias.name: (node.module, alias.name)
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and not node.level and node.module
            for alias in node.names
        }

    @classmethod
    def _facade_owner(
        cls,
        tree: ast.Module,
        local: m.Infra.RopeProjectLayout,
    ) -> p.Result[tuple[str, str]]:
        result_type = r[tuple[str, str]]
        classes = tuple(node for node in tree.body if isinstance(node, ast.ClassDef))
        if (
            len(classes) != 1
            or len(classes[0].bases) != 1
            or not isinstance(classes[0].bases[0], ast.Name)
        ):
            return result_type.fail(
                "staged t consumer requires one thin full-owner class"
            )
        public = classes[0]
        parent = public.bases[0]
        if not isinstance(parent, ast.Name):
            return result_type.fail("staged public class has no named full owner")
        imported = cls._absolute_imports(tree).get(parent.id)
        if (
            imported is None
            or imported[1] != public.name
            or not imported[0].startswith(f"{local.package_name}.")
        ):
            return result_type.fail(
                "staged facade must inherit its canonical local full owner"
            )
        return result_type.ok((imported[0], public.name))

    @classmethod
    def _owner_contract(
        cls,
        tree: ast.Module,
        classname: str,
    ) -> p.Result[tuple[tuple[tuple[str, str], ...], tuple[str, ...]]]:
        result_type = r[tuple[tuple[tuple[str, str], ...], tuple[str, ...]]]
        owner = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == classname
            ),
            None,
        )
        if owner is None:
            return result_type.fail("canonical owner class is absent")
        upstream_imports = cls._absolute_imports(tree)
        upstream: list[tuple[str, str]] = []
        for parent in owner.bases:
            if not isinstance(parent, ast.Name) or parent.id not in upstream_imports:
                return result_type.fail(
                    "full owner must declare an importable upstream base"
                )
            upstream.append(upstream_imports[parent.id])
        members = tuple(
            node.name if isinstance(node, ast.ClassDef) else node.name.id
            for node in owner.body
            if isinstance(node, ast.ClassDef | ast.TypeAlias)
        )
        return result_type.ok((tuple(upstream), members))

    @staticmethod
    def _facade_plan(
        file: m.Infra.CodegenFilePlan,
        local: m.Infra.RopeProjectLayout,
        selected: list[m.Infra.RopeProjectLayout],
        states: dict[Path, m.Cli.AtomicFileState],
        layouts: dict[str, m.Infra.RopeProjectLayout],
    ) -> p.Result[m.Infra.StagePackagePlan]:
        result_type = r[m.Infra.StagePackagePlan]
        if file.desired_content is None:
            return result_type.fail(
                "staged facade requires an existing package and desired bytes"
            )
        tree = ast.parse(
            file.desired_content.decode(c.Cli.ENCODING_DEFAULT),
            filename=str(file.path),
        )
        facade = FlextInfraStagedPackage._facade_owner(tree, local)
        if facade.failure:
            return result_type.from_failure(facade)
        owner_module, classname = facade.value
        owner_path = local.src_dir / Path(*owner_module.split(".")).with_suffix(
            c.Infra.EXT_PYTHON
        )
        owner_state = states.get(owner_path)
        if owner_state is None or owner_state.content is None:
            return result_type.fail(f"canonical owner was not pinned: {owner_path}")
        owner_tree = ast.parse(
            owner_state.content.decode(c.Cli.ENCODING_DEFAULT), filename=str(owner_path)
        )
        contract = FlextInfraStagedPackage._owner_contract(owner_tree, classname)
        if contract.failure:
            return result_type.from_failure(contract)
        upstream, members = contract.value
        return result_type.ok(
            m.Infra.StagePackagePlan(
                package=local.package_name,
                module=f"{local.package_name}.{file.path.stem}",
                classname=classname,
                owner_module=owner_module,
                upstream=upstream,
                members=members,
                layouts=tuple(selected),
                inputs=tuple(states.values()),
                workspace_packages=tuple(sorted(layouts)),
            )
        )


__all__ = ("FlextInfraStagedPackage",)
