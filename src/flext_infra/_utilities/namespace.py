"""Canonical codegen namespace utilities shared by census and auto-fix.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import operator
from collections.abc import MutableMapping
from functools import cache
from importlib import import_module
from inspect import getfile
from os.path import commonpath
from pathlib import Path
from types import MappingProxyType
from typing import ClassVar

from flext_cli import r, u

from flext_infra import c, config, m, p, t
from flext_infra._utilities import (
    FlextInfraUtilitiesDiscovery,
    FlextInfraUtilitiesDocsScope,
    FlextInfraUtilitiesRopeAnalysis,
    FlextInfraUtilitiesRopeCore,
    FlextInfraUtilitiesRopeSource,
)


class FlextInfraUtilitiesCodegenNamespace:
    """Canonical namespace helpers for codegen discovery, parsing, and fixes."""

    # Cache __all__ AST extraction by path+mtime
    # so the 4-5 redundant _declared_exports calls per policy() hit memory
    # instead of re-reading + re-parsing the same file from disk each time.
    _declared_exports_cache: ClassVar[
        MutableMapping[str, t.Pair[int, t.StrSequence]]
    ] = {}

    @staticmethod
    @cache
    def facade_families() -> t.MappingKV[str, m.Infra.FacadeFamily]:
        """Derive the facade families from the core package's declarations.

        A family is a layer of the import-layer order that the core package
        binds to a class whose module has a private ``_<module>/`` package
        beside it. Its suffix is the bound class name past the stem every
        family class shares. No letter, file or suffix is listed here.

        Returns:
            The resulting ``t.MappingKV[str, m.Infra.FacadeFamily]``.

        Raises:
            ValueError: If ``not bound``.

        """
        core = import_module(c.Infra.PKG_CORE_UNDERSCORE)
        core_dir = Path(getfile(core)).parent
        bound: MutableMapping[str, t.StrPair] = {}
        for layer in config.Infra.tooling.lazy_init.import_layer_order:
            facade = getattr(core, layer, None)
            if not isinstance(facade, type):
                continue
            module = facade.__module__.rpartition(".")[2]
            if (core_dir / f"_{module}").is_dir():
                bound[layer] = (module, facade.__name__)
        if not bound:
            msg = f"{c.Infra.PKG_CORE_UNDERSCORE} binds no facade family"
            raise ValueError(msg)
        stem = commonpath([name for _, name in bound.values()])
        return MappingProxyType({
            letter: m.Infra.FacadeFamily(
                letter=letter,
                module=module,
                suffix=name.removeprefix(stem),
            )
            for letter, (module, name) in bound.items()
        })

    @classmethod
    def facade_family_of_file(cls, file_name: str) -> str | None:
        """Return the family letter whose facade module file is ``file_name``.

        Returns:
            The family letter whose facade module file is ``file_name``.

        """
        return next(
            (
                letter
                for letter, family in cls.facade_families().items()
                if file_name in family.file_names
            ),
            None,
        )

    @classmethod
    def facade_family_declared_by(cls, file_name: str) -> m.Infra.FacadeFamily:
        """Return the family whose facade module is ``file_name``.

        Returns:
            The family whose facade module is ``file_name``.

        Raises:
            ValueError: If no facade family declares the module.

        """
        letter = cls.facade_family_of_file(file_name)
        if letter is None:
            msg = f"no facade family declares the module {file_name}"
            raise ValueError(msg)
        return cls.facade_families()[letter]

    @classmethod
    def facade_family_of_directory(cls, directory: str) -> str | None:
        """Return the family letter whose private package is ``directory``.

        Returns:
            The family letter whose private package is ``directory``.

        """
        return next(
            (
                letter
                for letter, family in cls.facade_families().items()
                if directory == family.directory
            ),
            None,
        )

    @classmethod
    def matches_root_namespace_file(cls, file_name: str) -> bool:
        """Return whether *file_name* is a governed root-namespace facade file.

        Returns:
            Whether *file_name* is a governed root-namespace facade file.

        """
        return file_name.endswith(c.Infra.EXT_PYTHON) and not file_name.startswith("_")

    @staticmethod
    def runtime_singleton_export(file_name: str) -> str | None:
        """Return the sole public singleton owned by a sanctioned runtime module.

        Returns:
            The sole public singleton owned by a sanctioned runtime module.

        """
        return next(
            (
                Path(module_file).stem.removeprefix("_")
                for module_file, *_ in c.Infra.RUNTIME_MODULES
                if file_name == module_file
            ),
            None,
        )

    @classmethod
    def surface_name(cls, package_name: str) -> str:
        """Return the configured surface name for one import package.

        Returns:
            The configured surface name for one import package.

        """
        parts = tuple(part for part in package_name.split(".") if part)
        if not parts:
            return ""
        return parts[0] if parts[0] in c.Infra.NON_PUBLIC_LAZY_ROOTS else "src"

    @classmethod
    def matches_project_namespace_package(cls, package_name: str) -> bool:
        """Return whether a package behaves like a project namespace root.

        Project package roots under ``src/`` qualify, as do namespace packages under
        governed wrapper surfaces like ``tests/``, ``examples/``, and ``scripts/``.
        Ordinary nested runtime subpackages such as ``<pkg>.services`` do not.

        Returns:
            Whether a package behaves like a project namespace root.

        """
        parts = tuple(part for part in package_name.split(".") if part)
        if not parts:
            return False
        if len(parts) == 1:
            return True
        # A governed wrapper surface is not itself an importable package: its
        # namespace root is the directory under it, so `tests.unit` is what
        # `flext_demo` is under `src/`. Requiring a single part made every such
        # package publish the inherited test aliases and none of its own
        # declarations, which is the opposite of the contract above.
        return (
            len(parts) == c.Infra.WRAPPER_NAMESPACE_DEPTH
            and parts[0] in c.Infra.NON_PUBLIC_LAZY_ROOTS
        )

    @staticmethod
    def ordered_namespace_exports(
        *,
        package_dir: Path,
        package_name: str,
        export_names: t.StrSequence,
    ) -> t.StrSequence:
        """Order root-package exports with alias hierarchy preserved.

        Returns:
            The resulting ``t.StrSequence``.

        """
        _ = (package_dir, package_name)
        ordered_unique = tuple(dict.fromkeys(export_names))
        export_set = set(ordered_unique)
        preferred_aliases = tuple(
            alias for alias in c.Infra.PUBLIC_ROOT_ALIAS_ORDER if alias in export_set
        )
        declared_aliases = tuple(
            name
            for name in ordered_unique
            if (
                name.islower()
                and len(name) <= c.Infra.MAX_ALIAS_LENGTH
                and name not in preferred_aliases
            )
        )
        ordered_aliases = (*preferred_aliases, *declared_aliases)
        alias_set = set(ordered_aliases)
        other_exports = tuple(name for name in ordered_unique if name not in alias_set)
        return (*other_exports, *ordered_aliases)

    @staticmethod
    def package_alias(*, package_name: str) -> str:
        """Derive the canonical root API alias from the import package.

        Returns:
            The resulting ``str``.

        """
        root = package_name.split(".", maxsplit=1)[0]
        if root.startswith(c.Infra.PKG_PREFIX_UNDERSCORE):
            return root.removeprefix(c.Infra.PKG_PREFIX_UNDERSCORE)
        return root

    @classmethod
    def _runtime_aliases(cls, package_dir: Path) -> t.StrSequence:
        """Read root aliases from declarations, never from initializer outputs.

        Returns:
            The resulting ``t.StrSequence``.

        """
        return tuple(
            alias
            for module_file in sorted(package_dir.glob("*.py"))
            if module_file.name != c.Infra.INIT_PY
            for alias in cls._declared_exports(module_file)
            if (
                alias.isidentifier()
                and alias.islower()
                and len(alias) <= c.Infra.MAX_ALIAS_LENGTH
            )
        )

    @staticmethod
    def _literal_exports(
        tree: ast.Module,
        value: ast.expr,
        file_path: Path,
    ) -> t.StrSequence:
        """Resolve a literal ``__all__`` or the former generated tuple alias.

        Returns:
            The resulting ``t.StrSequence``.

        Raises:
            ValueError: If ``not isinstance(literal, (list, tuple)) or not
                all((isinstance(item, str) for item in literal))``; or if a
                ``(ValueError, SyntaxError)`` is caught; or if ``source_name not in
                assignments``.

        """
        assignments: MutableMapping[str, ast.expr] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                assignments.update(
                    (target.id, node.value)
                    for target in node.targets
                    if isinstance(target, ast.Name)
                )
            elif (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.value is not None
            ):
                assignments[node.target.id] = node.value
        resolved = value
        match value:
            case ast.Call(
                func=ast.Name(id="tuple"),
                args=[ast.Name(id=source_name)],
                keywords=[],
            ):
                if source_name not in assignments:
                    msg = f"{file_path}: __all__ references missing {source_name}"
                    raise ValueError(msg)
                resolved = assignments[source_name]
            case _:
                pass
        try:
            literal = ast.literal_eval(resolved)
        except (ValueError, SyntaxError) as exc:
            msg = f"{file_path}: invalid __all__: {exc}"
            raise ValueError(msg) from exc
        if not isinstance(literal, (list, tuple)) or not all(
            isinstance(item, str) for item in literal
        ):
            msg = f"{file_path}: __all__ must contain only strings"
            raise ValueError(msg)
        return tuple(literal)

    @classmethod
    def _declared_exports(cls, file_path: Path) -> t.StrSequence:
        if not file_path.is_file():
            return ()
        resolved = file_path.resolve()
        mtime_ns = resolved.stat().st_mtime_ns
        cache_key = str(resolved)
        cached = cls._declared_exports_cache.get(cache_key)
        if cached is not None and cached[0] == mtime_ns:
            return cached[1]
        tree = ast.parse(
            file_path.read_text(encoding=c.Infra.ENCODING_DEFAULT),
            filename=str(file_path),
        )
        result: t.StrSequence = ()
        for node in tree.body:
            match node:
                case ast.Assign(targets=targets, value=value) if any(
                    isinstance(target, ast.Name) and target.id == c.Infra.DUNDER_ALL
                    for target in targets
                ):
                    result = cls._literal_exports(tree, value, file_path)
                    break
                case ast.AnnAssign(target=ast.Name(id=name), value=value) if (
                    name == c.Infra.DUNDER_ALL and value is not None
                ):
                    result = cls._literal_exports(tree, value, file_path)
                    break
                case _:
                    continue
        cls._declared_exports_cache[cache_key] = (mtime_ns, result)
        return result

    @classmethod
    def layout(
        cls,
        project_root: Path,
        *,
        project: p.Infra.ProjectInfo | None = None,
    ) -> m.Infra.RopeProjectLayout | None:
        """Return the canonical project layout contract for one project root.

        Returns:
            The canonical project layout contract for one project root.

        """
        resolved_root = project_root.resolve()
        package_name = (
            project.package_name
            if project is not None and project.package_name
            else FlextInfraUtilitiesDiscovery.project_package_name(resolved_root)
        )
        if not package_name:
            return None
        if project is not None and project.name:
            project_name = project.name
        elif (resolved_root / c.PYPROJECT_FILENAME).is_file():
            project_name = FlextInfraUtilitiesDocsScope.project_name_from_payload(
                resolved_root,
                FlextInfraUtilitiesDocsScope.project_payload(resolved_root),
            )
        else:
            project_name = resolved_root.name
        # The facade class stem carries the PACKAGE identity, never the
        # checkout directory: a linked worktree or renamed clone is the same
        # project (same declared package), so deriving from project_name or
        # the directory name made the namespace enforcement demand a
        # different prefix per checkout shape.
        class_name_source = package_name.split(".", maxsplit=1)[0].replace("_", "-")
        src_dir = resolved_root / c.Infra.DEFAULT_SRC_DIR
        package_dir = src_dir / Path(*package_name.split("."))
        return m.Infra.RopeProjectLayout(
            project_root=resolved_root,
            project_name=project_name,
            package_name=package_name,
            package_alias=cls.package_alias(package_name=package_name),
            class_stem=u.derive_class_stem(class_name_source),
            src_dir=src_dir,
            package_dir=package_dir,
            init_path=package_dir / c.Infra.INIT_PY,
            runtime_aliases=cls._runtime_aliases(package_dir),
        )

    @classmethod
    def _resolve_family(
        cls,
        file_path: Path,
        *,
        rope_project: t.Infra.RopeProject,
        project_layout: m.Infra.RopeProjectLayout | None = None,
    ) -> t.Quad[str | None, str | None, str | None, t.StrSequence]:
        """Return (family_alias, expected_family, expected_alias, family_tokens).

        Returns:
            (family_alias, expected_family, expected_alias, family_tokens).

        Raises:
            ValueError: If facade source is unavailable to Rope.

        """
        family_alias = cls.facade_family_of_directory(file_path.parent.name)
        declared_exports = cls._declared_exports(file_path)
        uppercase_names = tuple(name for name in declared_exports if name[:1].isupper())
        # Family nesting remains a separate concern. Public alias ownership
        # comes from local class identity and declared bases, never the path.
        expected_alias: str | None = None
        expected_family = (
            uppercase_names[0]
            if len(uppercase_names) == 1
            else (
                cls.facade_families()[family_alias].suffix
                if family_alias is not None
                else None
            )
        )
        project_root = (
            project_layout.project_root
            if project_layout is not None
            else FlextInfraUtilitiesDiscovery.project_root(file_path)
        )
        if project_root is not None:
            layout = project_layout or cls.layout(project_root)
            direct_tier = file_path.parent.parent == project_root
            public_root = layout is not None and file_path.parent == layout.package_dir
            # A stub is never a facade source: Rope loads only Python sources,
            # and stub law is judged by its own rule.
            facade_source = file_path.suffix == c.Infra.EXT_PYTHON
            if facade_source and (direct_tier or public_root):
                resource = FlextInfraUtilitiesRopeCore.fetch_python_resource(
                    rope_project,
                    file_path,
                )
                if resource is None:
                    message = f"facade source is unavailable to Rope: {file_path}"
                    raise ValueError(message)
                owner = FlextInfraUtilitiesRopeAnalysis.published_facade_owner(
                    rope_project,
                    resource,
                )
                if owner is not None and owner[0] in declared_exports:
                    expected_alias, expected_family = owner
        family_tokens: t.StrSequence = (expected_family,) if expected_family else ()
        return family_alias, expected_family, expected_alias, family_tokens

    @classmethod
    def _resolve_module_flags(
        cls,
        file_path: Path,
        resolved_rel_path: Path,
        package_parts: t.StrSequence,
        family_alias: str | None,
    ) -> tuple[bool, bool, bool, bool, bool, bool, bool]:
        """Return the module/package placement booleans for one file.

        Returns: (is_fixture_module, is_family_module, is_family_package,
                  is_services_module, is_services_package, is_namespace_file,
                  is_root_namespace)

        Returns:
            The module/package placement booleans for one file.

        """
        package_depth = len(package_parts)
        is_fixture_module = file_path.parent.name == "_fixtures"
        family_dir_values = {
            family.directory for family in cls.facade_families().values()
        }
        is_family_module = any(
            part in family_dir_values for part in resolved_rel_path.parts
        )
        is_family_package = family_alias is not None or any(
            part in family_dir_values for part in package_parts
        )
        is_services_module = "services" in resolved_rel_path.parts
        is_services_package = "services" in package_parts
        is_namespace_file = bool(cls._declared_exports(file_path))
        is_root_namespace = (
            is_namespace_file
            and len(resolved_rel_path.parts) == 1
            and package_depth <= 1
        )
        return (
            is_fixture_module,
            is_family_module,
            is_family_package,
            is_services_module,
            is_services_package,
            is_namespace_file,
            is_root_namespace,
        )

    @classmethod
    def project_prefix(
        cls,
        file_path: Path,
        *,
        project_layout: m.Infra.RopeProjectLayout | None = None,
    ) -> str:
        """Derive the class-stem prefix for one file inside a project.

        Returns:
            The resulting ``str``.

        """
        project_root = (
            project_layout.project_root
            if project_layout is not None
            else FlextInfraUtilitiesDiscovery.project_root(file_path)
        )
        if project_root is None:
            return ""
        layout = project_layout or cls.layout(project_root)
        if layout is None:
            return ""
        class_stem: str = layout.class_stem
        if not file_path.is_relative_to(project_root):
            return class_stem
        rel_parts = file_path.relative_to(project_root).parts
        surface_prefix = (
            rel_parts[0].title()
            if rel_parts and rel_parts[0] in c.Infra.NON_PUBLIC_LAZY_ROOTS
            else ""
        )
        return f"{surface_prefix}{class_stem}" if surface_prefix else class_stem

    @staticmethod
    def _policy_surface_name(package_parts: t.StrSequence) -> str:
        """Return the lazy-root surface name of one module, else ``src``.

        Returns:
            The resulting ``str``.

        """
        surface_name = package_parts[0] if package_parts else ""
        return surface_name if surface_name in c.Infra.NON_PUBLIC_LAZY_ROOTS else "src"

    @staticmethod
    def _policy_enforces_contract(
        flags: t.VariadicTuple[bool],
        *,
        governed_namespace: bool,
    ) -> bool:
        """Whether one module's publication must enforce the facade contract.

        Returns:
            The resulting ``bool``.

        """
        (
            is_fixture_module,
            is_family_module,
            _is_family_package,
            is_services_module,
            _is_services_package,
            _is_namespace_file,
            is_root_namespace,
        ) = flags
        return (
            is_fixture_module
            or is_family_module
            or is_services_module
            or governed_namespace
            or is_root_namespace
        )

    @staticmethod
    def _policy_exports_symbols(
        flags: t.VariadicTuple[bool],
        *,
        src_surface: bool,
    ) -> bool:
        """Whether one module's names join the namespace publication surface.

        Returns:
            The resulting ``bool``.

        """
        (
            is_fixture_module,
            is_family_module,
            is_family_package,
            is_services_module,
            is_services_package,
            is_namespace_file,
            is_root_namespace,
        ) = flags
        return (
            src_surface
            or is_fixture_module
            or is_family_module
            or is_family_package
            or is_services_module
            or is_services_package
            or is_namespace_file
            or is_root_namespace
        )

    @staticmethod
    def _policy_includes_in_lazy_init(
        flags: t.VariadicTuple[bool],
        *,
        private_stem: str,
        declared_exports: t.StrSequence,
    ) -> bool:
        """Whether one module joins its package's lazy facade init.

        A private module that declares ``__all__`` publishes those names
        through its package's lazy facade: siblings import them as
        ``from . import Name`` (R33), never through a relative module path.

        Returns:
            The resulting ``bool``.

        """
        (
            is_fixture_module,
            _is_family_module,
            is_family_package,
            _is_services_module,
            _is_services_package,
            _is_namespace_file,
            is_root_namespace,
        ) = flags
        return not private_stem[:1].isdigit() and (
            not private_stem.startswith("_")
            or is_fixture_module
            or is_family_package
            or is_root_namespace
            or bool(declared_exports)
        )

    @staticmethod
    def _type_checking_import_names(
        declared_exports: t.StrSequence,
    ) -> t.VariadicTuple[str]:
        """Filter declared exports down to type-checking-only import names.

        Returns:
            The resulting ``t.VariadicTuple[str]``.

        """
        return tuple(
            name
            for name in declared_exports
            if (
                name.isidentifier()
                and name.islower()
                and len(name) <= c.Infra.MAX_ALIAS_LENGTH
            )
        )

    @classmethod
    def publication_policy(
        cls,
        file_path: Path,
        *,
        rope_project: t.Infra.RopeProject,
        rel_path: Path | None = None,
        current_pkg: str = "",
        project_layout: m.Infra.RopeProjectLayout | None = None,
    ) -> m.Infra.NamespaceModulePolicy:
        """Derive publication from existing declarations, without repair inference.

        Returns:
            The resulting ``m.Infra.NamespaceModulePolicy``.

        """
        package_name = current_pkg or FlextInfraUtilitiesDiscovery.package_name(
            file_path,
        )
        resolved_rel_path = rel_path or Path(file_path.name)
        package_parts = tuple(part for part in package_name.split(".") if part)

        family_alias, expected_family, expected_alias, family_tokens = (
            cls._resolve_family(
                file_path,
                rope_project=rope_project,
                project_layout=project_layout,
            )
        )
        flags = cls._resolve_module_flags(
            file_path,
            resolved_rel_path,
            package_parts,
            family_alias,
        )
        declared_exports = cls._declared_exports(file_path)
        project_root = (
            project_layout.project_root
            if project_layout is not None
            else FlextInfraUtilitiesDiscovery.project_root(file_path)
        )
        return m.Infra.NamespaceModulePolicy(
            enforce_contract=cls._policy_enforces_contract(
                flags,
                governed_namespace=(
                    expected_alias is not None or expected_family is not None
                ),
            ),
            export_symbols=cls._policy_exports_symbols(
                flags,
                src_surface=cls._policy_surface_name(package_parts) == "src",
            ),
            include_in_lazy_init=cls._policy_includes_in_lazy_init(
                flags,
                private_stem=file_path.stem,
                declared_exports=declared_exports,
            ),
            project_prefix=cls.project_prefix(
                file_path,
                project_layout=project_layout,
            ),
            expected_alias=expected_alias,
            expected_family=expected_family,
            is_internal_namespace=project_root is not None
            and file_path.parent.parent == project_root,
            family_tokens=family_tokens,
            accepted_suffixes=((expected_family,) if expected_family else ()),
            allow_main_export="main" in declared_exports,
            allow_type_alias=(
                file_path.name == c.Infra.TYPINGS_PY
                or cls.facade_family_of_directory(file_path.parent.name)
                == cls.facade_family_of_file(c.Infra.TYPINGS_PY)
            ),
            is_fixture_module=flags[0],
            type_checking_imports=cls._type_checking_import_names(declared_exports),
        )

    @classmethod
    def policy(
        cls,
        file_path: Path,
        *,
        rope_project: t.Infra.RopeProject,
        rel_path: Path | None = None,
        current_pkg: str = "",
    ) -> m.Infra.NamespaceModulePolicy:
        """Enrich publication declarations with repair and inherited-shape evidence.

        Returns:
            The resulting ``m.Infra.NamespaceModulePolicy``.

        Raises:
            ValueError: If facade source is unavailable to Rope.

        """
        policy = cls.publication_policy(
            file_path,
            rope_project=rope_project,
            rel_path=rel_path,
            current_pkg=current_pkg,
        )
        project_root = FlextInfraUtilitiesDiscovery.project_root(file_path)
        # A stub is never a facade source (Rope loads only Python sources).
        if project_root is None or file_path.suffix != c.Infra.EXT_PYTHON:
            return policy
        layout = cls.layout(project_root)
        if file_path.parent.parent != project_root and (
            layout is None or file_path.parent != layout.package_dir
        ):
            return policy
        resource = FlextInfraUtilitiesRopeCore.fetch_python_resource(
            rope_project,
            file_path,
        )
        if resource is None:
            msg = f"facade source is unavailable to Rope: {file_path}"
            raise ValueError(msg)
        owner = FlextInfraUtilitiesRopeAnalysis.declared_facade_owner(
            rope_project,
            resource,
        )
        if owner is None:
            return policy
        alias, family = owner
        inherited = FlextInfraUtilitiesRopeAnalysis.inherited_facade_namespaces(
            rope_project,
            resource,
            class_name=family,
        )
        return policy.model_copy(
            update={
                "expected_alias": alias,
                "expected_family": family,
                "family_tokens": (family,),
                "accepted_suffixes": (family,),
                "inherited_namespaces": inherited,
                "enforce_contract": True,
                "export_symbols": True,
            },
        )

    @classmethod
    def projects(
        cls,
        repository_root: Path,
        *,
        projects: t.SequenceOf[m.Infra.ProjectInfo] | None = None,
    ) -> p.Result[t.SequenceOf[m.Infra.ProjectInfo]]:
        """Discover only projects that participate in codegen automation.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.ProjectInfo]]``.

        """
        if projects is None:
            projects_result = FlextInfraUtilitiesDocsScope.discover_projects(
                repository_root,
            )
            if not projects_result.success:
                return r[t.SequenceOf[m.Infra.ProjectInfo]].fail(
                    projects_result.error or "project discovery failed",
                )
            discovered = projects_result.unwrap()
        else:
            discovered = projects
        selected = tuple(
            project
            for project in discovered
            if (project.path / c.PYPROJECT_FILENAME).exists()
        )
        return r[t.SequenceOf[m.Infra.ProjectInfo]].ok(selected)

    @classmethod
    def normalize_canonical_facades(
        cls,
        *,
        pkg_dir: Path,
        ctx: m.Infra.FixContext,
    ) -> None:
        """Normalize canonical facade base classes for codegen auto-fix."""
        for file_name, base_import, base_name in (
            (
                c.Infra.CONSTANTS_PY,
                "from flext_core import FlextConstants as Constants",
                "Constants",
            ),
            (c.Infra.TYPINGS_PY, "from flext_core import FlextTypes as Types", "Types"),
        ):
            cls._normalize_facade_base(
                file_path=pkg_dir / file_name,
                base_import=base_import,
                base_name=base_name,
                ctx=ctx,
            )

    @classmethod
    def _normalize_facade_base(
        cls,
        *,
        file_path: Path,
        base_import: str,
        base_name: str,
        ctx: m.Infra.FixContext,
    ) -> None:
        """Add the canonical flext-core base to a *baseless* facade class only.

        A facade that already declares a base inherits from its proper owning
        project — flext-core directly, or an intermediate such as flext-web
        (``FlextApiConstants(FlextWebConstants)``). Those are left untouched:
        the pass never rebases an already-parented facade onto flext-core, so
        it is idempotent and correct across project boundaries.
        """
        if not file_path.is_file():
            return
        with FlextInfraUtilitiesRopeCore.open_project(file_path.parent) as rope_project:
            resource = FlextInfraUtilitiesRopeCore.resolve_resource_from_path(
                rope_project,
                file_path,
            )
            if resource is None:
                return
            updated = cls._rebased_facade_source(
                rope_project,
                resource,
                base_import,
                base_name,
            )
            if updated is None:
                return
            resource.write(updated)
            ctx.files_modified.add(str(file_path))
            ctx.fix(
                module=str(file_path),
                rule="NAMESPACE",
                line=1,
                message=(f"normalized facade class to inherit from {base_name}"),
            )

    @classmethod
    def _rebased_facade_source(
        cls,
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeFile,
        base_import: str,
        base_name: str,
    ) -> str | None:
        """Return the facade source rebased onto the canonical base, or None.

        Returns:
            The resulting ``str | None``.

        """
        source = resource.read()
        class_infos = sorted(
            FlextInfraUtilitiesRopeAnalysis.resolve_class_info(
                rope_project,
                resource,
            ),
            key=operator.attrgetter("line"),
        )
        if not class_infos:
            return None
        class_info = class_infos[0]
        if class_info.bases:
            return None
        lines = source.splitlines()
        header_idx = class_info.line - 1
        if not 0 <= header_idx < len(lines):
            return None
        rewritten_header = cls._normalize_class_header(
            line=lines[header_idx],
            class_name=class_info.name,
            base_name=base_name,
        )
        if rewritten_header == lines[header_idx]:
            return None
        lines[header_idx] = rewritten_header
        updated = "\n".join(lines)
        if source.endswith("\n"):
            updated += "\n"
        if base_import not in updated:
            updated = cls._insert_import_line(
                source=updated,
                import_line=base_import,
            )
        if updated == source:
            return None
        return updated

    @staticmethod
    def _normalize_class_header(*, line: str, class_name: str, base_name: str) -> str:
        """Normalize class header.

        Returns:
            The resulting ``str``.

        """
        stripped = line.strip()
        prefix = f"class {class_name}"
        if not stripped.startswith(prefix) or not stripped.endswith(":"):
            return line
        indent = line[: len(line) - len(line.lstrip())]
        return f"{indent}class {class_name}({base_name}):"

    @classmethod
    def _insert_import_line(cls, *, source: str, import_line: str) -> str:
        """Insert an import after the module docstring and future imports.

        Uses the docstring-aware position helper so the import can never land
        inside a multi-line module docstring (the cause of the F821/"unexpected
        indent" corruption).

        Returns:
            The resulting ``str``.

        """
        lines = source.splitlines()
        if import_line in lines:
            return source
        insert_at = (
            FlextInfraUtilitiesRopeSource.index_after_docstring_and_future_imports(
                lines,
            )
        )
        before = lines[:insert_at]
        after = lines[insert_at:]
        inserted: t.MutableSequenceOf[str] = list(before)
        if inserted and inserted[-1]:
            inserted.append("")
        inserted.append(import_line)
        if after and after[0]:
            inserted.append("")
        inserted.extend(after)
        return "\n".join(inserted) + ("\n" if source.endswith("\n") else "")

    @classmethod
    def classify_violation_outcomes(
        cls,
        *,
        project_path: Path,
        initial_violations: t.SequenceOf[m.Infra.CensusViolation],
        remaining_violations: t.SequenceOf[m.Infra.CensusViolation],
    ) -> t.Pair[
        t.VariadicTuple[m.Infra.CensusViolation],
        t.VariadicTuple[m.Infra.CensusViolation],
    ]:
        """Split initial violations into fixed and still-skipped groups.

        Returns:
            The resulting ``t.Pair[t.VariadicTuple[m.Infra.CensusViolation],
                t.VariadicTuple[m.Infra.CensusViolation]]``.

        """
        if not initial_violations:
            return ((), ())
        source_cache: MutableMapping[str, t.StrSequence] = {}
        remaining_keys = frozenset(
            cls._build_violation_key(
                violation=violation,
                project_path=project_path,
                source_cache=source_cache,
            )
            for violation in remaining_violations
        )
        fixed: t.MutableSequenceOf[m.Infra.CensusViolation] = []
        skipped: t.MutableSequenceOf[m.Infra.CensusViolation] = []
        for violation in initial_violations:
            key = cls._build_violation_key(
                violation=violation,
                project_path=project_path,
                source_cache=source_cache,
            )
            if violation.fixable and key not in remaining_keys:
                fixed.append(violation)
                continue
            skipped.append(violation)
        return (tuple(fixed), tuple(skipped))

    @staticmethod
    def _read_source_lines(project_path: Path, module: str) -> t.StrSequence:
        """Read source lines.

        Returns:
            The resulting ``t.StrSequence``.

        """
        module_path = project_path / module
        if not module_path.is_file():
            return ()
        return module_path.read_text(encoding=c.Cli.ENCODING_DEFAULT).splitlines()

    @classmethod
    def _build_violation_key(
        cls,
        *,
        violation: m.Infra.CensusViolation,
        project_path: Path,
        source_cache: MutableMapping[str, t.StrSequence],
    ) -> m.Infra.ViolationKey:
        """Build violation key.

        Returns:
            The resulting ``m.Infra.ViolationKey``.

        """
        if violation.module not in source_cache:
            source_cache[violation.module] = cls._read_source_lines(
                project_path,
                violation.module,
            )
        source_lines = source_cache[violation.module]
        context = "\n".join(
            source_lines[
                max(0, violation.line - 2) : min(len(source_lines), violation.line + 3)
            ],
        )
        return m.Infra.ViolationKey(
            module=violation.module,
            rule=violation.rule,
            content_hash=u.Cli.sha256_content(context),
        )

    # -- import law: namespace, layer and lazy-export facts --------------------------

    @classmethod
    def import_namespace(
        cls,
        project_root: Path,
        file_path: Path,
    ) -> t.Pair[Path, str] | None:
        """Return the namespace directory and dotted module of one file.

        A namespace is a top-level package of a project: the source package
        under ``src/`` or an internal tier (``tests``, ``examples``,
        ``scripts``) whose directory carries an ``__init__.py``.

        Returns:
            The namespace directory and the file's dotted module name, or
            ``None`` when the file belongs to no namespace of the project.

        """
        root = project_root.resolve()
        resolved = file_path.resolve()
        if not resolved.is_relative_to(root):
            return None
        relative = resolved.relative_to(root)
        source_dir = root / c.Infra.DEFAULT_SRC_DIR
        if relative.parts and relative.parts[0] == c.Infra.DEFAULT_SRC_DIR:
            relative = resolved.relative_to(source_dir)
            base = source_dir
        else:
            base = root
        namespace_name, *module_parts = relative.parts
        if not module_parts:
            return None
        namespace_dir = base / namespace_name
        if not (namespace_dir / c.Infra.INIT_PY).is_file():
            return None
        parts = relative.with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        return namespace_dir, ".".join(parts)

    @classmethod
    def import_layer_order(cls) -> t.StrSequence:
        """Return the declared import-layer order.

        Returns:
            The layer names, lowest layer first.

        """
        return tuple(config.Infra.tooling.lazy_init.import_layer_order)

    @classmethod
    def module_import_layer(cls, module: str) -> int:
        """Return the layer rank of one dotted module of a namespace.

        A module's layer is the first path segment, from its namespace
        downwards, that names a layer either directly (``settings``,
        ``config``, ``base``, ``services``, ``api``, ``cli``) or through the
        facade family it stands for (``_models`` and ``models.py`` stand for
        ``m``); a module naming no layer sits in the ``other`` slot.

        Returns:
            The index of the module's layer in the declared order.

        """
        order = cls.import_layer_order()
        families = {
            family.module: letter for letter, family in cls.facade_families().items()
        }
        for part in module.split(".")[1:]:
            stem = part.lstrip("_")
            layer = families.get(stem, stem)
            if layer in order:
                return order.index(layer)
        return order.index(c.Infra.IMPORT_LAW_OTHER_LAYER)

    @staticmethod
    def import_direct_module(namespace_dir: Path, file_path: Path) -> bool:
        """Return whether one module keeps direct leaf imports.

        A settings/config module (any path segment starting with ``settings``
        or ``config``, with or without leading underscores) and a family
        ``base.py`` (a ``base.py`` inside a private ``_<family>/`` package)
        import their own namespace only through direct leaf modules, so the
        settings/config graph and the family bases never re-enter a lazy
        package that is still initializing.

        Returns:
            Whether the module is exempt from root-alias and lazy routing.

        """
        relative = file_path.resolve().relative_to(namespace_dir.resolve())
        stems = tuple(part.removesuffix(".py").lstrip("_") for part in relative.parts)
        if any(
            stem.startswith(tuple(c.Infra.IMPORT_LAW_ROOT_SINGLETONS)) for stem in stems
        ):
            return True
        return (
            len(relative.parts) > 1
            and relative.name == c.Infra.IMPORT_LAW_FAMILY_BASE_FILE
            and relative.parts[-2].startswith("_")
        )

    @staticmethod
    def import_package_dir(project_root: Path, package: str) -> Path | None:
        """Return the directory of one dotted package the project owns.

        Returns:
            The package directory, or ``None`` for a module, a missing path or
            a package of another project.

        """
        top, *rest = package.split(".")
        for base in (project_root / c.Infra.DEFAULT_SRC_DIR, project_root):
            if not (base / top / c.Infra.INIT_PY).is_file():
                continue
            candidate = base.joinpath(top, *rest)
            return candidate if (candidate / c.Infra.INIT_PY).is_file() else None
        return None

    @staticmethod
    def import_lazy_exports(package_dir: Path, package: str) -> t.StrMapping:
        """Map each name one package ``__init__`` publishes to its module.

        Relative targets resolve against the package; a target naming another
        distribution (``flext_cli``) stays absolute.

        Returns:
            The published name to absolute defining module mapping.

        Raises:
            ValueError: If the package init declares its lazy map indirectly.

        """
        init = package_dir / c.Infra.INIT_PY
        if not init.is_file():
            return {}
        targets, references = (
            FlextInfraUtilitiesRopeAnalysis.lazy_import_mapping_source(
                init.read_text(encoding=c.Cli.ENCODING_DEFAULT),
            )
        )
        if references:
            msg = f"{init}: lazy map is declared through {', '.join(references)}"
            raise ValueError(msg)
        return {
            name: f"{package}{module}" if module.startswith(".") else module
            for module, names in targets
            for name in names
        }


__all__: list[str] = ["FlextInfraUtilitiesCodegenNamespace"]
