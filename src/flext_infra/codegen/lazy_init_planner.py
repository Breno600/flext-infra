"""Lazy-init planning over generic Rope workspace indexes."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, override

from flext_infra import c, m, p, t, u
from flext_infra.codegen._lazy_init_planner_aliases import (
    FlextInfraCodegenLazyInitPlannerAliasesMixin,
)
from flext_infra.codegen._lazy_init_planner_cache import (
    FlextInfraCodegenLazyInitPlannerCacheMixin,
)
from flext_infra.codegen._lazy_init_planner_children import (
    FlextInfraCodegenLazyInitPlannerChildrenMixin,
)
from flext_infra.codegen._lazy_init_planner_collision import (
    FlextInfraCodegenLazyInitPlannerCollisionMixin,
)
from flext_infra.codegen._lazy_init_planner_exports import (
    FlextInfraCodegenLazyInitPlannerExportsMixin,
)


class FlextInfraCodegenLazyInitPlannerBase(m.ArbitraryTypesModel):
    """Pydantic state base for lazy-init planning."""

    rope_workspace: Annotated[
        p.Infra.RopeWorkspaceDsl,
        m.Field(description="Shared Rope workspace DSL reused by the planner"),
    ]
    lazy_init: m.Infra.LazyInitConfig = m.Field(
        description="Validated lazy-init policy document"
    )

    _module_exports_cache: dict[
        tuple[str, bool, bool, bool, bool, bool], t.LazyAliasMap
    ] = u.PrivateAttr(default_factory=dict)
    _package_exports_cache: dict[str, frozenset[str]] = u.PrivateAttr(
        default_factory=dict
    )
    _source_exports_cache: dict[str, frozenset[str]] = u.PrivateAttr(
        default_factory=dict
    )
    _source_plan_cache: dict[str, m.Infra.LazyInitPlan] = u.PrivateAttr(
        default_factory=dict
    )
    _source_exports_visiting: set[str] = u.PrivateAttr(default_factory=set)
    _module_file_by_name: dict[str, Path] = u.PrivateAttr(default_factory=dict)
    _version_module_name: str = u.PrivateAttr(
        default_factory=lambda: f"{c.Infra.DUNDER_VERSION}.py"
    )
    _collision_count: int = u.PrivateAttr(default_factory=int)
    _parent_package_cache: dict[str, t.StrSequence] = u.PrivateAttr(
        default_factory=dict
    )

    @property
    def collision_count(self) -> int:
        """Number of export collisions resolved so far."""
        return self._collision_count


class FlextInfraCodegenLazyInitPlanner(
    FlextInfraCodegenLazyInitPlannerBase,
    FlextInfraCodegenLazyInitPlannerAliasesMixin,
    FlextInfraCodegenLazyInitPlannerExportsMixin,
    FlextInfraCodegenLazyInitPlannerChildrenMixin,
    FlextInfraCodegenLazyInitPlannerCollisionMixin,
    FlextInfraCodegenLazyInitPlannerCacheMixin,
):
    """Resolve lazy-init plans using one shared Rope workspace index."""

    @override
    def build_plan(
        self, pkg_dir: Path, *, dir_exports: t.MappingKV[str, t.LazyAliasMap]
    ) -> m.Infra.LazyInitPlan:
        """Build the lazy-init render plan for one package directory."""
        context = self.context(pkg_dir)
        is_test_child_package = (
            context.surface == c.Infra.DIR_TESTS
            and context.current_pkg != c.Infra.DIR_TESTS
        )
        empty_action: c.Infra.LazyInitAction = (
            c.Infra.LazyInitAction.WRITE
            if is_test_child_package
            else (
                c.Infra.LazyInitAction.REMOVE
                if context.generated_init
                else c.Infra.LazyInitAction.SKIP
            )
        )
        if not context.importable:
            return m.Infra.LazyInitPlan(context=context, action=empty_action)
        lazy_map = self._package_exports(context)
        version_map = self._module_exports(
            context.pkg_dir / self._version_module_name,
            f"{context.current_pkg}.{c.Infra.DUNDER_VERSION}",
            export_options=m.Infra.ExportOptions(include_dunder=True),
        )
        child_lazy = self._merge_children(context.pkg_dir, lazy_map, dir_exports)
        eager_dunders = dict(version_map)
        for name in eager_dunders:
            lazy_map.pop(name, None)
        self._resolve_aliases(
            lazy_map,
            current_pkg=context.current_pkg,
            pkg_dir=context.pkg_dir,
            surface=context.surface,
        )
        for name in c.Infra.INFRA_ONLY_EXPORTS:
            lazy_map.pop(name, None)
            eager_dunders.pop(name, None)
        if not lazy_map and not eager_dunders:
            return m.Infra.LazyInitPlan(context=context, action=empty_action)
        type_checking_map = dict(lazy_map)
        all_export_names = tuple(
            sorted(u.Infra.ordered_namespace_exports(
                package_dir=context.pkg_dir,
                package_name=context.current_pkg,
                export_names=lazy_map.keys() | eager_dunders.keys(),
            ))
        )
        plan = m.Infra.LazyInitPlan(
            context=context,
            action=c.Infra.LazyInitAction.WRITE,
            exports=all_export_names,
            lazy_map=dict(lazy_map),
            type_checking_map=type_checking_map,
            eager_dunders=eager_dunders,
            wildcard_runtime_modules=(),
            child_packages_for_lazy=child_lazy,
            excluded_lazy_names=(),
        )
        self._source_plan_cache[str(context.pkg_dir.resolve())] = plan
        self._source_exports_cache[context.current_pkg] = frozenset(plan.exports)
        return plan

    def context(self, pkg_dir: Path) -> m.Infra.LazyInitPackageContext:
        """Return the lazy-init package context for the requested package directory."""
        return self.rope_workspace.package_context(pkg_dir)


__all__: list[str] = ["FlextInfraCodegenLazyInitPlanner"]
