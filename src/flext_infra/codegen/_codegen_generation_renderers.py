"""Template renderers for generated ``__init__`` files."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import u

from ._codegen_generation_lazy_entries import (
    FlextInfraCodegenGenerationLazyEntriesMixin,
)

if TYPE_CHECKING:
    from flext_infra import p


# NOTE (multi-agent, flext-wkii.17.26 / agent: codex): lazy generation delegates
# exact models to flext-cli and proves every rendered initializer is Ruff-clean.
class FlextInfraCodegenGenerationRenderersMixin(
    FlextInfraCodegenGenerationLazyEntriesMixin
):
    """Render codegen models through the canonical CLI template facade."""

    @staticmethod
    def _template_path(template_name: str) -> Path:
        """Resolve one packaged lazy-init template source."""
        template_root = (Path(__file__).resolve().parent.parent / "templates").resolve()
        template_path = (template_root / template_name).resolve()
        if not template_path.is_relative_to(template_root):
            msg = f"lazy-init template escapes its source root: {template_name}"
            raise ValueError(msg)
        return template_path

    @staticmethod
    def _render_model(
        template_name: str, context: p.Model, *, target_filename: str
    ) -> str:
        """Render one deterministic, already-canonical typed Python artifact."""
        template_path = FlextInfraCodegenGenerationRenderersMixin._template_path(
            template_name
        )
        rendered = u.Cli.template_render(template_path, context).unwrap()
        compile(rendered, target_filename, "exec")
        return rendered.rstrip() + "\n"


__all__: list[str] = ["FlextInfraCodegenGenerationRenderersMixin"]
