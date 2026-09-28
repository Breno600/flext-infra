"""Canonical generated package artifact selection."""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, m, t

from ._codegen_generation_standard import FlextInfraCodegenGenerationStandardMixin


class FlextInfraCodegenGenerationFileMixin(FlextInfraCodegenGenerationStandardMixin):
    """Render canonical initializer artifacts from one validated plan."""

    @staticmethod
    def _init_template_name(plan: m.Infra.LazyInitPlan) -> str:
        """Select the sole template source for one resolved initializer.

        The bootstrap-cycle exception (side-effect-free static init) belongs
        ONLY to the bootstrap-owning distribution (``flext_core``): its
        ``_typings``/``_lazy_parts`` are imported while the lazy runtime is
        still initializing. Every other distribution's private packages load
        normally and receive the populated lazy facade (operator init law
        2026-09-16: light init WITH exports — never an empty facade).
        """
        root_package = plan.context.current_pkg.split(".", maxsplit=1)[0]
        segments = frozenset(plan.context.current_pkg.split("."))
        if (
            root_package == c.Infra.LAZY_BOOTSTRAP_ROOT_PACKAGE
            and segments & c.Infra.BOOTSTRAP_CYCLE_EXCEPTION_SEGMENTS
        ):
            return c.Infra.TEMPLATE_STATIC_INIT
        return c.Infra.TEMPLATE_ROOT_INIT

    @classmethod
    def init_template_path(cls, plan: m.Infra.LazyInitPlan) -> Path:
        """Return the exact template path consumed by one initializer plan."""
        return cls._template_path(cls._init_template_name(plan))

    @classmethod
    def init_template_paths(cls) -> t.Pair[Path, Path]:
        """Return the closed lazy-init template input set."""
        return (
            cls._template_path(c.Infra.TEMPLATE_ROOT_INIT),
            cls._template_path(c.Infra.TEMPLATE_STATIC_INIT),
        )

    @classmethod
    def render_init(cls, plan: m.Infra.LazyInitPlan) -> str:
        """Render a lazy facade for each importable package boundary.

        Real cycle exceptions (bootstrap packages imported during lazy-runtime
        initialization) keep side-effect-free empty inits. All other packages
        get PEP 562 lazy-loading facades.
        """
        if cls._init_template_name(plan) == c.Infra.TEMPLATE_STATIC_INIT:
            return cls._render_static(plan)
        return cls._render_root(plan)


__all__: list[str] = ["FlextInfraCodegenGenerationFileMixin"]
