"""Per-package and per-module export resolution for the lazy-init planner.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import operator
from collections.abc import MutableMapping
from typing import TYPE_CHECKING

from flext_infra import c, m, u

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraCodegenLazyInitPlannerExportsMixin:
    if TYPE_CHECKING:
        rope_workspace: p.Infra.RopeWorkspaceDsl
        lazy_init: m.Infra.LazyInitConfig
        _module_exports_cache: MutableMapping[
            tuple[str, bool, bool, bool, bool, bool],
            t.LazyAliasMap,
        ]
        _version_module_name: str
        _project_layout_cache: MutableMapping[Path, m.Infra.RopeProjectLayout]

        def _package_entry(
            self,
            pkg_dir: Path,
        ) -> m.Infra.RopePackageIndexEntry | None: ...

        def _add(
            self,
            index: t.MutableLazyAliasMap,
            name: str,
            target: t.StrPair,
        ) -> None: ...

        @staticmethod
        def _publish(name: str, *, allow_main: bool) -> bool: ...

    def _project_layout_for(self, pkg_dir: Path) -> m.Infra.RopeProjectLayout | None:
        """Reuse the project's canonical layout during one planning snapshot.

        Returns:
            The resulting ``m.Infra.RopeProjectLayout | None``.

        """
        project_root = u.Infra.project_root(pkg_dir)
        if project_root is None:
            return None
        layout = self._project_layout_cache.get(project_root)
        if layout is None:
            layout = u.Infra.layout(project_root)
            if layout is not None:
                self._project_layout_cache[project_root] = layout
        return layout

    def _package_exports(
        self,
        context: m.Infra.LazyInitPackageContext,
    ) -> t.MutableLazyAliasMap:
        """Return the lazy export map for a package (excluding child packages).

        Returns:
            The lazy export map for a package (excluding child packages).

        Raises:
            ValueError: If unindexed publication source.

        """
        package_entry = self._package_entry(context.pkg_dir)
        # Operator init law (2026-09-16): every package with public children —
        # underscore internals included — carries a light lazy-init export
        # surface. When the rope index does not track the package, enumerate
        # direct children from the filesystem instead of rendering an empty
        # init; emptiness here is a defect, never canonical.
        # The rope index exposes modules in its own scan order, which follows
        # the filesystem's directory-entry order and therefore differs between
        # machines. Sorting the entries makes the rendered lazy map — whose
        # insertion order the generated ``__init__`` preserves — byte-identical
        # for the same sources on every host, so a render on one machine can
        # never drift against a render on another.
        module_entries: t.MutableSequenceOf[t.Pair[Path, str]] = (
            sorted(
                (
                    (entry.file_path, entry.module_name)
                    for entry in package_entry.modules
                ),
                key=operator.itemgetter(0, 1),
            )
            if package_entry is not None
            else []
        )
        if not module_entries:
            module_entries = [
                (
                    child,
                    f"{context.current_pkg}.{child.stem}"
                    if context.current_pkg
                    else child.stem,
                )
                for child in sorted(context.pkg_dir.glob("*.py"))
                if child.name != c.Infra.INIT_PY
            ]
        index: t.MutableLazyAliasMap = {}
        project_layout = self._project_layout_for(context.pkg_dir)
        # Generated support modules are output, never public input.
        # conftest.py is pytest-private: its hook variables (pytest_plugins) are
        # never public package ABI and must not enter the lazy export map.
        skip_names = {
            c.Infra.INIT_PY,
            "__main__.py",
            "conftest.py",
            self._version_module_name,
            *c.Infra.OBSOLETE_GENERATED_INIT_FILES,
        }
        for py_file, module_name in module_entries:
            # Universal, no exceptions: a light
            # package init exports ONLY its direct children. Subdirectory
            # symbols stay in the subpackage's own init — never re-exported
            # upward, in the root or anywhere else.
            if py_file.parent != context.pkg_dir:
                continue
            child_dir = py_file.parent / py_file.stem
            child_entry = self._package_entry(child_dir)
            # Test artifacts never enter an installable package ABI.
            test_only_source_module = (
                context.surface != c.Infra.DIR_TESTS
                or context.current_pkg == c.Infra.DIR_TESTS
            ) and (
                c.Infra.TEST_ONLY_SOURCE_MODULE_RE.fullmatch(py_file.name) is not None
            )
            # Extract predicate to satisfy PLR0916
            # (>5 boolean expressions); retired/generated/test modules are
            # never semantic input for the lazy export map.
            is_generated_or_test = (
                py_file.name in skip_names
                or c.Infra.GENERATED_EXPORT_SIDECAR_RE.match(py_file.name)
                or py_file.stem in c.Infra.OBSOLETE_ROOT_SUPPORT_NAMES
                or test_only_source_module
                # A stem that is not an identifier (numbered example scripts,
                # dash-named files) can never appear in a from-import: it is
                # unimportable and never semantic input for the lazy export map.
                or not py_file.stem.isidentifier()
            )
            is_child_package = child_entry is not None and child_entry.package_name
            if is_generated_or_test or is_child_package:
                continue
            policy = u.Infra.publication_policy(
                py_file,
                rel_path=py_file.relative_to(context.pkg_dir),
                current_pkg=context.current_pkg,
                rope_project=self.rope_workspace.rope_project,
                project_layout=project_layout,
            )
            entry = self.rope_workspace.module(py_file)
            if entry is None:
                msg = f"unindexed publication source: {py_file}"
                raise ValueError(msg)
            module_path = entry.module_name
            root_private_contract = (
                py_file.parent == context.pkg_dir
                and py_file.stem in {"_config", "_settings"}
                and bool(
                    self._module_exports(
                        py_file,
                        module_path,
                        export_options=m.Infra.ExportOptions(
                            allow_main=True,
                            allow_assignments=True,
                            allow_functions=True,
                            require_explicit_all=True,
                        ),
                    ),
                )
            )
            if (
                not policy.include_in_lazy_init and not root_private_contract
            ) or not module_name:
                continue
            # In public src packages, public submodules (without expected_alias) derive
            # from their explicit __all__; non-public/private subpackages auto-discover.
            require_explicit_all = context.surface in c.Infra.NON_PUBLIC_LAZY_ROOTS or (
                not any(part.startswith("_") for part in context.pkg_dir.parts)
                and not py_file.stem.startswith("_")
                and (
                    u.Infra.matches_root_namespace_file(py_file.name)
                    or policy.expected_alias is not None
                    or "." in context.current_pkg
                )
            )
            targets = self._module_exports(
                py_file,
                module_path,
                export_options=m.Infra.ExportOptions(
                    allow_main=True,
                    allow_assignments=True,
                    allow_functions=True,
                    require_explicit_all=require_explicit_all,
                ),
            )
            for name, target in targets.items():
                self._add(index, name, target)
        return index

    def _module_exports(
        self,
        py_file: Path,
        module_path: str,
        *,
        export_options: m.Infra.ExportOptions | None = None,
    ) -> t.MutableLazyAliasMap:
        """Return the lazy export map for one Python module (cache-backed).

        Returns:
            The lazy export map for one Python module (cache-backed).

        """
        resolved_export_options = export_options or m.Infra.ExportOptions()
        cache_key = (
            str(py_file.resolve()),
            resolved_export_options.include_dunder,
            resolved_export_options.allow_main,
            resolved_export_options.allow_assignments,
            resolved_export_options.allow_functions,
            resolved_export_options.require_explicit_all,
        )
        cached = self._module_exports_cache.get(cache_key)
        if cached is not None:
            return dict(cached)
        if self.rope_workspace.resource(py_file) is None:
            return {}
        names = self.rope_workspace.exports(
            py_file,
            export_options=resolved_export_options.model_copy(
                update={
                    "require_explicit_all": (
                        resolved_export_options.require_explicit_all
                        and not resolved_export_options.include_dunder
                    ),
                },
            ),
        )
        exports = {
            name: (module_path, name)
            for name in names
            if resolved_export_options.include_dunder
            or self._publish(name, allow_main=resolved_export_options.allow_main)
        }
        self._module_exports_cache[cache_key] = exports
        return dict(exports)
