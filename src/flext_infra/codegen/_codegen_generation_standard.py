"""Canonical public-root and static-subpackage initializer rendering."""

from __future__ import annotations

from collections.abc import MutableMapping
from sys import stdlib_module_names
from typing import TYPE_CHECKING

from flext_infra import c, config, m, t, u

from ._codegen_generation_renderers import FlextInfraCodegenGenerationRenderersMixin

if TYPE_CHECKING:
    from pathlib import Path


# Keep lazy loading only at the public package root and
# bind Ruff validation to each target project's real initializer path.
class FlextInfraCodegenGenerationStandardMixin(
    FlextInfraCodegenGenerationRenderersMixin,
):
    """Render the two canonical generated initializer forms."""

    @staticmethod
    def _is_stdlib_import(target: t.StrPair) -> bool:
        """Return whether an absolute import target belongs to the stdlib."""
        module = target[0]
        return (
            not module.startswith(".")
            and module.partition(".")[0] in stdlib_module_names
        )

    @staticmethod
    def _type_checking_filtered(plan: m.Infra.LazyInitPlan) -> t.LazyAliasMap:
        """Filter static imports already resolved by the semantic planner."""
        source = plan.type_checking_map or plan.lazy_map
        public_names = frozenset(plan.exports)
        wildcard_modules = frozenset(plan.wildcard_runtime_modules)
        # Direct imports outside __all__ remain statically
        # declared because they are part of the established root interface.
        filtered: MutableMapping[str, t.StrPair] = {
            name: target
            for name, target in source.items()
            if name in public_names
            and target[0] not in wildcard_modules
            and name not in c.Infra.ROOT_TEMPLATE_BINDINGS
            and not FlextInfraCodegenGenerationStandardMixin._is_stdlib_import(target)
        }
        return filtered

    @classmethod
    def _runtime_import_lines(cls, plan: m.Infra.LazyInitPlan) -> str:
        """Render explicit eager and wildcard runtime imports."""
        current_pkg = plan.context.current_pkg
        lines: t.MutableSequenceOf[str] = [
            f"from {cls._absolute_import_module(current_pkg, module)} import *"
            for module in sorted(set(plan.wildcard_runtime_modules))
        ]
        eager_lines: t.MutableSequenceOf[str] = []
        eager_groups = cls._group_imports(plan.eager_dunders)
        previous_top: str | None = None
        for module in sorted(eager_groups, key=str.lower):
            rendered_module = cls._absolute_import_module(
                current_pkg, cls._compact_lazy_module_path(current_pkg, module),
            )
            top = rendered_module.split(".", maxsplit=1)[0]
            if previous_top is not None and top != previous_top:
                eager_lines.append("")
            parts = tuple(
                f"{imported_name} as {export_name}"
                for export_name, imported_name in sorted(eager_groups[module])
                if imported_name
            )
            if parts:
                # One statement per module group: member-per-statement rendering
                # diverged from the formatter's canonical single (parenthesized)
                # import and every generation re-diverged after the autofix.
                eager_lines.extend(cls._format_import("", rendered_module, parts))
            previous_top = top
        if lines and eager_lines:
            lines.append("")
        lines.extend(eager_lines)
        return "\n".join(lines)

    @classmethod
    def _lazy_groups(
        cls, plan: m.Infra.LazyInitPlan,
    ) -> t.Triple[
        t.SequenceOf[t.StrSequencePair],
        t.SequenceOf[t.StrPairSequencePair],
        t.LazyAliasMap,
    ]:
        """Build owned lazy metadata groups and their filtered public map."""
        current_pkg = plan.context.current_pkg
        public_names = frozenset(plan.exports)
        lazy_map = {
            name: target
            for name, target in plan.lazy_map.items()
            if name in public_names
            and name not in c.Infra.ROOT_TEMPLATE_BINDINGS
            and not cls._is_stdlib_import(target)
        }
        lazy_entries = cls._build_lazy_entries(
            tuple(lazy_map),
            lazy_map,
            (current_pkg, frozenset(plan.child_packages_for_lazy), True),
        )
        lazy_module_groups, lazy_alias_groups = cls._group_lazy_entries(lazy_entries)
        return lazy_module_groups, lazy_alias_groups, lazy_map

    @classmethod
    def _format_lazy_group_entry(
        cls,
        module: str,
        values: t.StrSequence,
        *,
        trailing: bool,
        indent: str = "            ",
    ) -> t.StrSequence:
        """Format one mapping entry exactly as Ruff formats a tuple value.

        Why (charts gen↔fmt churn): the compact form previously hardcoded the
        item-ending comma, while Ruff's magic-trailing-comma rule removes it on
        a single-entry mapping that stays expanded — the next ``make fmt``
        rewrote the projection and the following ``make gen`` restored it,
        looping forever. The item comma belongs to the ``trailing`` decision
        (multi-entry mapping), exactly like the expanded form below.
        """
        inner = ", ".join(values)
        if len(values) == 1:
            inner = f"{inner},"
        separator = "," if trailing else ""
        compact = f'{indent}"{module}": ({inner}){separator}'
        if len(compact) <= config.Infra.tooling.tools.ruff.line_length:
            return (compact,)
        value_indent = f"{indent}    "
        return (
            f'{indent}"{module}": (',
            *(f"{value_indent}{value}," for value in values),
            f"{indent}){separator}",
        )

    @classmethod
    def _format_exports_tuple(cls, exports: t.StrSequence) -> str:
        """Render a canonical public export tuple, including the empty form."""
        if not exports:
            return "()"
        inner = ", ".join(f'"{name}"' for name in exports)
        if len(exports) == 1:
            inner = f"{inner},"
        compact = f"({inner})"
        if (
            len("__all__: tuple[str, ...] = ") + len(compact)
            <= config.Infra.tooling.tools.ruff.line_length
        ):
            return compact
        # A wrapped export set renders exactly as Ruff formats it (one name per
        # line): the projection is a formatter fixed point, never re-packed to
        # dodge a LOC gate (ADR-018 p.13 — the hack's permission dies with it).
        wrapped = ",\n    ".join(f'"{name}"' for name in exports)
        return "(\n    " + wrapped + ",\n)"

    @staticmethod
    def _lazy_module_argument_inline(groups: t.SequenceOf[t.StrSequencePair]) -> str:
        """Render the module mapping as one indent-free call argument.

        The caller keeps the inline form only when its line fits; it carries no
        trailing comma inside the braces, so Ruff keeps it joined.
        """
        entries: t.MutableSequenceOf[str] = []
        for module, names in groups:
            inner = ", ".join(f'"{name}"' for name in names)
            if len(names) == 1:
                inner = f"{inner},"
            entries.append(f'"{module}": ({inner})')
        return f"MappingProxyType({{{', '.join(entries)}}})"

    @staticmethod
    def _lazy_alias_argument_inline(groups: t.SequenceOf[t.StrPairSequencePair]) -> str:
        """Render the alias mapping as one indent-free call argument."""
        entries: t.MutableSequenceOf[str] = []
        for module, pairs in groups:
            values = tuple(
                f'("{export_name}", "{attr_name}")' for export_name, attr_name in pairs
            )
            inner = ", ".join(values)
            if len(values) == 1:
                inner = f"{inner},"
            entries.append(f'"{module}": ({inner})')
        return f"alias_groups=MappingProxyType({{{', '.join(entries)}}})"

    @classmethod
    def _format_lazy_module_mapping(
        cls, groups: t.SequenceOf[t.StrSequencePair],
    ) -> str:
        """Render the immutable module mapping without a formatter subprocess."""
        compact = f"        {cls._lazy_module_argument_inline(groups)},"
        if len(compact) <= config.Infra.tooling.tools.ruff.line_length:
            return compact
        lines: t.MutableSequenceOf[str] = ["        MappingProxyType({"]
        for module, names in groups:
            lines.extend(
                cls._format_lazy_group_entry(
                    module,
                    tuple(f'"{name}"' for name in names),
                    trailing=len(groups) > 1,
                ),
            )
        lines.append("        }),")
        return "\n".join(lines)

    @classmethod
    def _format_lazy_alias_mapping(
        cls, groups: t.SequenceOf[t.StrPairSequencePair],
    ) -> str:
        """Render the immutable alias mapping without a formatter subprocess."""
        compact = f"        {cls._lazy_alias_argument_inline(groups)},"
        if len(compact) <= config.Infra.tooling.tools.ruff.line_length:
            return compact
        lines: t.MutableSequenceOf[str] = ["        alias_groups=MappingProxyType({"]
        for module, pairs in groups:
            lines.extend(
                cls._format_lazy_group_entry(
                    module,
                    tuple(
                        f'("{export_name}", "{attr_name}")'
                        for export_name, attr_name in pairs
                    ),
                    trailing=len(groups) > 1,
                ),
            )
        lines.append("        }),")
        return "\n".join(lines)

    @staticmethod
    def _project_package_name(pkg_dir: Path) -> str | None:
        """Return the distribution package that owns ``pkg_dir``.

        The nearest ancestor carrying the project manifest is the project
        root, and the distribution package is its manifest-declared name
        (``u.Infra.read_project_metadata_result``). The root directory
        name was the historical proxy; it broke every checkout whose root
        directory is not named after the package — a git worktree named
        after its branch (``0.12.0-dev``) rendered wrapper roots
        (``examples/``, ``scripts/``, ``tests/``) whose TYPE_CHECKING
        block sorted the project package as third-party, diverging from
        CI renders and failing ruff I001 at the generated fixed point.
        Return ``None`` when no manifest is reachable; an unreadable manifest
        raises with the metadata reader's diagnostic.
        """
        for candidate in (pkg_dir, *pkg_dir.parents):
            if not (candidate / c.PYPROJECT_FILENAME).is_file():
                continue
            return u.Infra.read_project_metadata_result(candidate).unwrap().package_name
        return None

    @staticmethod
    def _copyright_notice(pkg_dir: Path) -> str:
        """Render the copyright notice of the project that owns ``pkg_dir``.

        The author is the manifest's first declared author and the year is
        the scaffold copyright year, the same owners the scaffold templates
        render; a package outside any project, or a project without a named
        author, raises.
        """
        for candidate in (pkg_dir, *pkg_dir.parents):
            if not (candidate / c.PYPROJECT_FILENAME).is_file():
                continue
            authors = (
                u.Infra.read_project_metadata_result(candidate).unwrap().project.authors
            )
            author = authors[0].name if authors else None
            if not author:
                msg = f"project manifest declares no author name: {candidate}"
                raise ValueError(msg)
            scaffold = config.Infra.codegen.scaffold.project
            return (
                f"Copyright (c) {scaffold.copyright_year} {author}. "
                "All rights reserved.\n"
                f"SPDX-License-Identifier: {scaffold.supported_licenses[0]}"
            )
        msg = f"package is outside any project manifest: {pkg_dir}"
        raise ValueError(msg)

    @staticmethod
    def _project_first_party_names(project_root: Path) -> t.StrSequence:
        """Read strict Ruff policy, deriving namespaces only when it is absent."""
        project_payload = u.Infra.pyproject_payload(
            (project_root / c.PYPROJECT_FILENAME).resolve(),
        )
        projected: t.JsonValue | None = project_payload.get("tool")
        for section in ("ruff", "lint", "isort", "known-first-party"):
            if projected is None:
                break
            if not isinstance(projected, dict):
                msg = f"Ruff configuration before {section!r} must be a table"
                raise TypeError(msg)
            projected = projected.get(section)
        if projected is not None:
            return t.str_sequence_adapter().validate_python(projected, strict=True)
        return (
            *u.Infra.discover_first_party_namespaces(project_root),
            *u.Infra.flext_dependency_namespaces_from_payload(project_payload),
        )

    @classmethod
    def _root_context(cls, plan: m.Infra.LazyInitPlan) -> m.Infra.LazyInitRootRender:
        """Build one lazy context for a public package root."""
        lazy_module_groups, lazy_alias_groups, lazy_map = cls._lazy_groups(plan)
        current_pkg = plan.context.current_pkg
        public_type_checking_imports = cls._type_checking_filtered(plan)
        # The generated TYPE_CHECKING block must mirror the project's ruff
        # isort sections exactly: every namespace the project's
        # known-first-party declares must be emitted in the first-party
        # section. That set is the config-owned base namespaces (e.g.
        # flext_core, the shared upstream), this package root, and the
        # project's own package. The last matters for roots outside the
        # source tree (tests, examples, scripts, pulumi): their initializers
        # import the distribution package absolutely, and ruff lists it as
        # first-party. Without the full set the block lands in the wrong
        # section, omitting or inserting the blank line ruff expects and
        # violating I001.
        first_party_names = {
            current_pkg,
            *config.Infra.tooling.tools.deptry.known_first_party,
        }
        project_pkg = cls._project_package_name(plan.context.pkg_dir)
        if project_pkg is not None:
            first_party_names.add(project_pkg)
        # I001 parity is judged by THIS project's ruff table, so the render
        # reads the same projected ``known-first-party`` list the linter reads
        # Deriving the set from declared dependencies races
        # the deps projection: a pyproject whose tool tables predate a
        # dependency wave renders one order while ruff enforces another, and
        # the generated block fails I001 on every cycle. The derived set stays
        # only as the fallback for projects without a projected table.
        project_root = next(
            (
                candidate
                for candidate in (plan.context.pkg_dir, *plan.context.pkg_dir.parents)
                if (candidate / c.PYPROJECT_FILENAME).is_file()
            ),
            None,
        )
        if project_root is not None:
            first_party_names.update(cls._project_first_party_names(project_root))
        type_checking_root_names = frozenset(first_party_names)
        type_checking_lines = "\n".join(
            cls.generate_type_checking(
                cls._group_imports(public_type_checking_imports),
                include_flext_types=False,
                child_packages=plan.child_packages_for_lazy,
                local_package_root=current_pkg,
                root_names=type_checking_root_names,
            ),
        )
        runtime_import_lines = cls._runtime_import_lines(plan)
        return m.Infra.LazyInitRootRender(
            autogen_header=c.Infra.AUTOGEN_HEADER,
            docstring=cls._format_root_package_docstring(
                current_pkg, cls._copyright_notice(plan.context.pkg_dir),
            ),
            runtime_import_lines=runtime_import_lines,
            blank_lines_before_exports=(
                "\n" if not (runtime_import_lines or type_checking_lines) else "\n\n"
            ),
            type_checking_lines=type_checking_lines,
            exports_tuple=cls._format_exports_tuple(
                cls._build_published_exports(
                    tuple(
                        name
                        for name in plan.exports
                        if name in lazy_map or name in plan.eager_dunders
                    ),
                    lazy_map,
                ),
            ),
            lazy_module_mapping=cls._format_lazy_module_mapping(lazy_module_groups),
            lazy_alias_mapping=cls._format_lazy_alias_mapping(lazy_alias_groups),
        )

    @classmethod
    def _static_context(
        cls, plan: m.Infra.LazyInitPlan,
    ) -> m.Infra.StaticPackageInitRender:
        """Build a side-effect-free private or non-production initializer."""
        return m.Infra.StaticPackageInitRender(
            autogen_header=c.Infra.AUTOGEN_HEADER,
            docstring=cls._format_root_package_docstring(
                plan.context.current_pkg.rsplit(".", maxsplit=1)[-1],
                cls._copyright_notice(plan.context.pkg_dir),
            ),
        )

    @classmethod
    def _render_root(cls, plan: m.Infra.LazyInitPlan) -> str:
        """Render one inline lazy public-root initializer."""
        return cls._render_model(
            c.Infra.TEMPLATE_ROOT_INIT,
            cls._root_context(plan),
            target_filename=str(plan.context.init_path),
        )

    @classmethod
    def _render_static(cls, plan: m.Infra.LazyInitPlan) -> str:
        """Render one explicit static or empty subpackage initializer."""
        return cls._render_model(
            c.Infra.TEMPLATE_STATIC_INIT,
            cls._static_context(plan),
            target_filename=str(plan.context.init_path),
        )


__all__: list[str] = ["FlextInfraCodegenGenerationStandardMixin"]
