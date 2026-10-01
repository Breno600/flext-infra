"""Root public-export decisions for the lazy-init planner.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, m, t, u

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraCodegenLazyInitPlannerPublicRootMixin:
    """Public root-facade export filtering helpers."""

    if TYPE_CHECKING:
        rope_workspace: p.Infra.RopeWorkspaceDsl

    def _filter_public_root_exports(
        self,
        *,
        context: m.Infra.LazyInitPackageContext,
        export_names: set[str],
        lazy_map: t.MutableLazyAliasMap,
        eager_names: frozenset[str],
    ) -> t.Pair[set[str], t.MutableLazyAliasMap]:
        # The root publishes what its modules declare (ADR-018 p.1/p.10): a
        # hand-written __init__ on a flat package is the only declared filter.
        # No manifest stands between the declarations and the projection, so
        # the plan is identical whichever root the planner was opened from.
        declared_contract = self._declared_root_contract(context)

        governed_lazy_map = {
            name: target
            for name, target in lazy_map.items()
            if self._is_declared_root_export(
                name,
                target,
                root_pkg=context.current_pkg,
                declared_contract=declared_contract,
            )
        }
        lazy_map.clear()
        lazy_map.update(governed_lazy_map)
        # The published surface is what the package actually delivers: the eager
        # names plus everything the governed lazy map resolves. Gating the lazy
        # half on `export_names` — the scan of the package's OWN modules — drops
        # every alias a package inherits from the facade it extends, so
        # flext-infra published c/m/p/s/t/u and silently withheld d/e/h/r/x even
        # though all eleven resolve at runtime. The governed map is already
        # narrowed by the declared contract.
        public_export_names = {name for name in export_names if name in eager_names} | {
            name
            for name in governed_lazy_map
            if name not in c.Infra.PUBLISHED_ALL_EXCLUDE
        }
        filtered_lazy_map = {
            name: target
            for name, target in lazy_map.items()
            if name in public_export_names
        }
        return public_export_names, filtered_lazy_map

    def _declared_root_contract(
        self,
        context: m.Infra.LazyInitPackageContext,
    ) -> frozenset[str] | None:
        if context.generated_init or not context.init_path.is_file():
            return None
        # If the project declares subpackages (e.g. services/), root aggregates from sources;
        # only single-directory/flat projects can declare an ABI filter via manual __init__.py.
        entry = self.rope_workspace.package(context.pkg_dir)
        if entry is not None and entry.descendant_child_dirs:
            return None
        constants_path = context.pkg_dir / c.Infra.CONSTANTS_PY
        resource = self.rope_workspace.resource(constants_path)
        if resource is not None:
            imports = u.Infra.resolve_declared_module_imports(
                self.rope_workspace.rope_project,
                resource,
            )
            if any(
                name != "annotations" and not target.startswith("__future__")
                for name, target in imports.items()
            ):
                return None
        contract = frozenset(
            self.rope_workspace.exports(
                context.init_path,
                export_options=m.Infra.ExportOptions(allow_assignments=True),
            ),
        )
        return contract or None

    @staticmethod
    def _is_declared_root_export(
        name: str,
        target: t.StrPair,
        *,
        root_pkg: str,
        declared_contract: frozenset[str] | None,
    ) -> bool:
        # Private names never widen the public root ABI.
        if name.startswith("_"):
            return False
        if declared_contract is not None and name not in declared_contract:
            return False
        module_path, _attr_name = target
        runtime_module = f"{module_path.rsplit('.', maxsplit=1)[-1]}.py"
        if u.Infra.runtime_singleton_export(runtime_module) == name:
            return True
        if (module_path == f"{root_pkg}._config" and name.endswith("Config")) or (
            module_path == f"{root_pkg}._settings" and name.endswith("Settings")
        ):
            return True
        return not FlextInfraCodegenLazyInitPlannerPublicRootMixin._is_private_owner(
            module_path,
            root_pkg=root_pkg,
        )

    @staticmethod
    def _is_private_owner(module_path: str, *, root_pkg: str) -> bool:
        """Return whether a module below ``root_pkg`` sits behind a private segment.

        Any underscore-prefixed source segment below the root marks the owner as
        private; its symbols stay behind their facade and never widen the root ABI.

        Returns:
            Whether a module below ``root_pkg`` sits behind a private segment.

        """
        if not module_path.startswith(f"{root_pkg}."):
            return False
        tail = module_path[len(root_pkg) + 1 :].split(".")
        return any(part.startswith("_") and not part.startswith("__") for part in tail)

    @staticmethod
    def _is_facade_root(context: m.Infra.LazyInitPackageContext) -> bool:
        """Return whether a package is a public project root or the tests facade root.

        Returns:
            Whether a package is a public project root or the tests facade root.

        """
        is_public_project_root = bool(
            context.pkg_dir.parent.name == c.Infra.DEFAULT_SRC_DIR
            and context.current_pkg
            and "." not in context.current_pkg
            # Why: governed consumer packages
            # are first-class project roots; package prefixes are not architecture.
            and u.Infra.matches_project_namespace_package(context.current_pkg),
        )
        is_test_facade_root = (
            context.current_pkg == c.Infra.DIR_TESTS
            and context.pkg_dir.name == c.Infra.DIR_TESTS
            and context.surface == c.Infra.DIR_TESTS
        )
        return is_public_project_root or is_test_facade_root


__all__: list[str] = ["FlextInfraCodegenLazyInitPlannerPublicRootMixin"]
