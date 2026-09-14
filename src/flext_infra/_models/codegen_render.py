"""Render context models for codegen templates."""

from __future__ import annotations

from typing import Annotated, ClassVar

from flext_core import m
from flext_infra import t

from .deps_tool_config import FlextInfraModelsDepsToolSettings


class FlextInfraModelsCodegenRender:
    """Typed render contexts for generated codegen artifacts."""

    class MarkdownLintRenderSpec(m.ContractModel):
        """Validated tooling-only context for Markdown lint projections."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            extra="forbid", frozen=True, strict=True
        )

        tooling: Annotated[
            FlextInfraModelsDepsToolSettings.ToolConfigDocument,
            m.Field(description="Canonical validated tooling policy."),
        ]

    # NOTE (multi-agent, flext-wkii.17 / agent: uv_overlay_owner): keep the
    # module-skeleton template boundary model-backed and immutable.
    class ModuleSkeletonRenderContext(m.ContractModel):
        """Validated context for one generated module skeleton."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            extra="forbid", frozen=True, str_strip_whitespace=False
        )

        class_name: t.NonEmptyStr = m.Field(description="Generated class name.")
        base_class: t.NonEmptyStr = m.Field(description="Generated base class name.")
        base_module: t.NonEmptyStr = m.Field(description="Module owning base_class.")
        docstring: t.NonEmptyStr = m.Field(description="Generated module docstring.")

    # NOTE (multi-agent, flext-p4s3.2 / agent: uv_overlay_owner): the docs
    # renderer sends one immutable model directly to the flext-cli boundary.
    class MkdocsRenderContext(m.ContractModel):
        """Validated common context for a generated MkDocs configuration."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            extra="forbid", frozen=True, strict=True, str_strip_whitespace=False
        )

        site_title: t.NonEmptyStr = m.Field(description="Rendered site title.")
        site_url: t.NonEmptyStr = m.Field(description="Published site URL.")
        repo_url: t.NonEmptyStr = m.Field(description="Source repository URL.")
        repo_name: t.NonEmptyStr = m.Field(description="Source repository name.")
        exclude_docs_block: str = m.Field(description="Rendered docs exclusions.")
        exclude_plugin_block: str = m.Field(description="Rendered plugin exclusions.")
        mkdocstrings_paths_block: str = m.Field(
            description="Rendered mkdocstrings source paths."
        )

    class MkdocsProjectRenderContext(MkdocsRenderContext):
        """Validated MkDocs context with a project edit scope."""

        scope_name: t.NonEmptyStr = m.Field(description="Workspace project scope.")

    class LazyInitRootRender(m.ArbitraryTypesModel):
        """Template context for one lazy public root ``__init__.py``."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        autogen_header: t.NonEmptyStr = m.Field(description="Generated file header.")
        docstring: t.NonEmptyStr = m.Field(description="Generated module docstring.")
        runtime_import_lines: str = m.Field(
            default_factory=str,
            description="Eager runtime imports for explicit reexports.",
        )
        type_checking_lines: str = m.Field(
            default_factory=str,
            description="Static declarations for public lazy exports.",
        )
        exports_tuple: t.NonEmptyStr = m.Field(
            description="Canonical rendered root ``__all__`` tuple."
        )
        lazy_module_mapping: t.NonEmptyStr = m.Field(
            description="Canonical rendered lazy module mapping."
        )
        lazy_alias_mapping: t.NonEmptyStr = m.Field(
            description="Canonical rendered lazy alias mapping."
        )

    class StaticPackageInitRender(m.ArbitraryTypesModel):
        """Template context for a non-root static ``__init__.py``."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        autogen_header: t.NonEmptyStr = m.Field(description="Generated file header.")
        docstring: t.NonEmptyStr = m.Field(description="Generated module docstring.")


__all__: list[str] = ["FlextInfraModelsCodegenRender"]
