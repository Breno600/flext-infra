"""Canonical public-root and static-subpackage initializer rendering.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import operator
from collections.abc import MutableMapping
from sys import stdlib_module_names

from flext_infra import c, config, m, t, u
from flext_infra.codegen._codegen_generation_renderers import (
    FlextInfraCodegenGenerationRenderersMixin,
)
from flext_infra.deps.phases.tool_tables import FlextInfraToolTablesPhase


# Keep lazy loading only at the public package root and
# bind Ruff validation to each target project's real initializer path.
class FlextInfraCodegenGenerationStandardMixin(
    FlextInfraCodegenGenerationRenderersMixin,
):
    """Render the two canonical generated initializer forms."""

    @staticmethod
    def _is_stdlib_import(target: t.StrPair) -> bool:
        """Return whether an absolute import target belongs to the stdlib.

        Returns:
            Whether an absolute import target belongs to the stdlib.

        """
        module = target[0]
        return (
            not module.startswith(".")
            and module.partition(".")[0] in stdlib_module_names
        )

    @staticmethod
    def _type_checking_filtered(plan: m.Infra.LazyInitPlan) -> t.LazyAliasMap:
        """Filter static imports already resolved by the semantic planner.

        Public names resolved by a wildcard runtime import are KEPT: the lazy
        map names their defining module, which makes the static import
        ``from <module> import <name> as <name>`` always resolvable, and the
        type checkers cannot follow the runtime ``*`` — dropping these names
        is what left ``e``/``r`` invisible to pyright across the fleet.

        Returns:
            The resulting ``t.LazyAliasMap``.

        """
        source = plan.lazy_map
        public_names = frozenset(plan.exports)
        # Direct imports outside __all__ remain statically
        # declared because they are part of the established root interface.
        filtered: MutableMapping[str, t.StrPair] = {
            name: target
            for name, target in source.items()
            if name in public_names
            and name not in c.Infra.ROOT_TEMPLATE_BINDINGS
            and not FlextInfraCodegenGenerationStandardMixin._is_stdlib_import(target)
        }
        return filtered

    @classmethod
    def _runtime_import_lines(
        cls,
        plan: m.Infra.LazyInitPlan,
        root_names: frozenset[str],
    ) -> str:
        """Render the runtime imports as one Ruff-isort-ordered block.

        Wildcard, eager and lazy-helper imports are statements of the same
        kind: each is ranked by the project's isort section (``root_names``
        is the project's ``known-first-party``) and then by module, with a
        blank line only where the section changes. Ranking them apart made
        the helpers import a block of its own whenever its module sorted next
        to the package's ``__version__`` import, and ``make fix`` rewrote
        every generated root that ``make gen`` produced.

        Returns:
            The import block, or the lazy-helpers import alone.

        """
        current_pkg = plan.context.current_pkg
        statements: t.MutableSequenceOf[tuple[t.StrPair, t.StrSequence]] = []
        for module in sorted(set(plan.wildcard_runtime_modules)):
            rendered_module = cls._absolute_import_module(current_pkg, module)
            statements.append((
                cls._type_checking_sort_key(rendered_module, root_names),
                (f"from {rendered_module} import *",),
            ))
        eager_groups = cls._group_imports(plan.eager_dunders)
        for module in eager_groups:
            rendered_module = cls._absolute_import_module(
                current_pkg,
                cls._compact_lazy_module_path(current_pkg, module),
            )
            parts = tuple(
                cls._format_import_part(imported_name, export_name)
                for export_name, imported_name in sorted(eager_groups[module])
                if imported_name
            )
            if parts:
                statements.append((
                    cls._type_checking_sort_key(rendered_module, root_names),
                    cls._format_import("", rendered_module, parts),
                ))
        # The bootstrap owner imports the helpers from the module that defines
        # them: its root re-exports them, so importing the root from inside it
        # binds each helper to itself (a cyclic facade binding and a partially
        # initialized import). Every other distribution imports the root.
        lazy_module = (
            c.Infra.LAZY_BOOTSTRAP_MODULE
            if current_pkg.split(".", maxsplit=1)[0]
            == c.Infra.LAZY_BOOTSTRAP_ROOT_PACKAGE
            else c.Infra.LAZY_BOOTSTRAP_ROOT_PACKAGE
        )
        statements.append((
            cls._type_checking_sort_key(lazy_module, root_names),
            cls._format_import("", lazy_module, c.Infra.LAZY_BOOTSTRAP_HELPERS),
        ))
        lines: t.MutableSequenceOf[str] = []
        previous_section: str | None = None
        for (section, _), statement in sorted(statements, key=operator.itemgetter(0)):
            if previous_section is not None and section != previous_section:
                lines.append("")
            lines.extend(statement)
            previous_section = section
        return "\n".join(lines)

    @classmethod
    def _lazy_groups(
        cls,
        plan: m.Infra.LazyInitPlan,
    ) -> t.Triple[
        t.SequenceOf[t.StrSequencePair],
        t.SequenceOf[t.StrPairSequencePair],
        t.LazyAliasMap,
    ]:
        """Build owned lazy metadata groups and their filtered public map.

        Returns:
            The resulting ``t.Triple[t.SequenceOf[t.StrSequencePair],
                t.SequenceOf[t.StrPairSequencePair], t.LazyAliasMap]``.

        """
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
        indent: str = "            ",
    ) -> t.StrSequence:
        """Format one mapping entry exactly as Ruff formats a tuple value.

        An expanded mapping always ends each entry with a comma: Ruff's format
        keeps the magic trailing comma and its ``missing-trailing-comma`` fix
        (``make fix``) adds it, so the comma-less single-entry form made
        ``make gen`` and ``make fix`` rewrite each other forever.

        Returns:
            The entry lines, compact when they fit the configured width.

        """
        inner = ", ".join(values)
        if len(values) == 1:
            inner = f"{inner},"
        compact = f'{indent}"{module}": ({inner}),'
        if len(compact) <= config.Infra.tooling.tools.ruff.line_length:
            return (compact,)
        value_indent = f"{indent}    "
        return (
            f'{indent}"{module}": (',
            *(f"{value_indent}{value}," for value in values),
            f"{indent}),",
        )

    @classmethod
    def _format_exports_tuple(cls, exports: t.StrSequence) -> str:
        """Render a canonical public export tuple, including the empty form.

        Returns:
            The resulting ``str``.

        """
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

        Returns:
            The resulting ``str``.

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
        """Render the alias mapping as one indent-free call argument.

        Returns:
            The resulting ``str``.

        """
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
        cls,
        groups: t.SequenceOf[t.StrSequencePair],
    ) -> str:
        """Render the immutable module mapping without a formatter subprocess.

        Returns:
            The resulting ``str``.

        """
        compact = f"        {cls._lazy_module_argument_inline(groups)},"
        if len(compact) <= config.Infra.tooling.tools.ruff.line_length:
            return compact
        lines: t.MutableSequenceOf[str] = ["        MappingProxyType({"]
        for module, names in groups:
            lines.extend(
                cls._format_lazy_group_entry(
                    module,
                    tuple(f'"{name}"' for name in names),
                ),
            )
        lines.append("        }),")
        return "\n".join(lines)

    @classmethod
    def _format_lazy_alias_mapping(
        cls,
        groups: t.SequenceOf[t.StrPairSequencePair],
    ) -> str:
        """Render the immutable alias mapping without a formatter subprocess.

        Returns:
            The resulting ``str``.

        """
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
                ),
            )
        lines.append("        }),")
        return "\n".join(lines)

    @classmethod
    def _root_context(cls, plan: m.Infra.LazyInitPlan) -> m.Infra.LazyInitRootRender:
        """Build one lazy context for a public package root.

        Returns:
            Validated template data for the generated root initializer.

        """
        lazy_module_groups, lazy_alias_groups, lazy_map = cls._lazy_groups(plan)
        current_pkg = plan.context.current_pkg
        public_type_checking_imports = cls._type_checking_filtered(plan)
        # The generated blocks rank imports by the project's ruff isort
        # sections, so they read the one owner that projects known-first-party
        # into the same pyproject (FlextInfraToolTablesPhase); the package
        # being rendered is first-party to ruff through its declared ``src``
        # roots (tests, examples, scripts).
        project_root = next(
            candidate
            for candidate in (plan.context.pkg_dir, *plan.context.pkg_dir.parents)
            if (candidate / c.PYPROJECT_FILENAME).is_file()
        )
        first_party_names = {
            current_pkg,
            *FlextInfraToolTablesPhase.first_party_namespaces(path=project_root),
        }
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
        runtime_import_lines = cls._runtime_import_lines(plan, type_checking_root_names)
        # The bootstrap owner's packages import the helpers from the module
        # that defines them; every other distribution imports them from the
        # bootstrap root, which therefore publishes them in its __all__.
        published_helpers = (
            c.Infra.LAZY_BOOTSTRAP_HELPERS
            if current_pkg == c.Infra.LAZY_BOOTSTRAP_ROOT_PACKAGE
            else ()
        )
        return m.Infra.LazyInitRootRender(
            autogen_header=c.Infra.AUTOGEN_HEADER,
            docstring=cls._format_root_package_docstring(
                current_pkg,
                u.Infra.copyright_notice(plan.context.pkg_dir),
            ),
            runtime_import_lines=runtime_import_lines,
            type_checking_lines=type_checking_lines,
            exports_tuple=cls._format_exports_tuple(
                cls._build_published_exports(
                    (
                        *published_helpers,
                        *(
                            name
                            for name in plan.exports
                            if name in lazy_map or name in plan.eager_dunders
                        ),
                    ),
                    lazy_map,
                ),
            ),
            lazy_module_mapping=cls._format_lazy_module_mapping(lazy_module_groups),
            lazy_alias_mapping=cls._format_lazy_alias_mapping(lazy_alias_groups),
        )

    @classmethod
    def _static_context(
        cls,
        plan: m.Infra.LazyInitPlan,
    ) -> m.Infra.StaticPackageInitRender:
        """Build a side-effect-free private or non-production initializer.

        Returns:
            The resulting ``m.Infra.StaticPackageInitRender``.

        """
        return m.Infra.StaticPackageInitRender(
            autogen_header=c.Infra.AUTOGEN_HEADER,
            docstring=cls._format_root_package_docstring(
                plan.context.current_pkg.rsplit(".", maxsplit=1)[-1],
                u.Infra.copyright_notice(plan.context.pkg_dir),
            ),
        )

    @classmethod
    def _render_root(cls, plan: m.Infra.LazyInitPlan) -> str:
        """Render one inline lazy public-root initializer.

        Returns:
            The resulting ``str``.

        """
        return cls._render_model(
            c.Infra.TEMPLATE_ROOT_INIT,
            cls._root_context(plan),
            target_filename=str(plan.context.init_path),
        )

    @classmethod
    def _render_static(cls, plan: m.Infra.LazyInitPlan) -> str:
        """Render one explicit static or empty subpackage initializer.

        Returns:
            The resulting ``str``.

        """
        return cls._render_model(
            c.Infra.TEMPLATE_STATIC_INIT,
            cls._static_context(plan),
            target_filename=str(plan.context.init_path),
        )


__all__: list[str] = ["FlextInfraCodegenGenerationStandardMixin"]
