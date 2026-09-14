"""Typed immutable inputs for one documentation generation pass."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar, Literal, Self

from flext_cli import m as cli_m

from flext_core import m, u
from flext_infra import t


class FlextInfraModelsDocsGeneration:
    """Declaration-only documentation generation contracts."""

    class DocScope(m.ArbitraryTypesModel):
        """Documentation scope targeting a project or workspace root."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            arbitrary_types_allowed=True, extra="forbid", frozen=True
        )

        name: Annotated[t.NonEmptyStr, m.Field(description="Scope name")]
        path: Annotated[Path, m.Field(description="Absolute lexical scope root")]
        report_dir: Annotated[
            Path, m.Field(description="Absolute lexical report output directory")
        ]
        project_class: Annotated[
            str, m.Field(description="Docs scope classification")
        ] = "root"
        package_name: Annotated[
            str, m.Field(description="Primary package name for scope")
        ] = ""

        @u.field_validator("path", "report_dir")
        @classmethod
        def _validate_absolute_lexical_path(cls, value: Path) -> Path:
            if not value.is_absolute() or ".." in value.parts:
                msg = f"docs scope path must be absolute and lexical: {value}"
                raise ValueError(msg)
            return value

        @u.model_validator(mode="after")
        def _validate_report_owner(self) -> Self:
            if not self.report_dir.is_relative_to(self.path):
                msg = f"docs report directory escapes its scope: {self.report_dir}"
                raise ValueError(msg)
            return self

    class DocsRenderedArtifact(m.ArbitraryTypesModel):
        """One immutable desired docs artifact relative to its owning scope."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            arbitrary_types_allowed=True, extra="forbid", frozen=True
        )

        relative_path: Annotated[
            Path, m.Field(description="Normalized scope-relative destination")
        ]
        desired_content: Annotated[
            bytes | None, m.Field(description="Exact desired bytes, or absence")
        ]
        desired_mode: Annotated[
            Literal[0o644] | None, m.Field(description="Exact desired mode, or absence")
        ]

        @u.field_validator("relative_path")
        @classmethod
        def _validate_relative_path(cls, value: Path) -> Path:
            if (
                value.is_absolute()
                or not value.parts
                or value.as_posix() in {"", "."}
                or ".." in value.parts
            ):
                msg = f"unsafe docs artifact selector: {value}"
                raise ValueError(msg)
            return value

        @u.model_validator(mode="after")
        def _validate_desired_tuple(self) -> Self:
            if (self.desired_content is None) != (self.desired_mode is None):
                msg = "docs artifact content and mode must be present together"
                raise ValueError(msg)
            return self

    class DocsScopeArtifacts(m.ArbitraryTypesModel):
        """One scope paired with its complete rendered artifact inventory."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            arbitrary_types_allowed=True, extra="forbid", frozen=True
        )

        scope: Annotated[
            FlextInfraModelsDocsGeneration.DocScope,
            m.Field(description="Exact scope that owns every relative artifact"),
        ]
        artifacts: Annotated[
            t.VariadicTuple[FlextInfraModelsDocsGeneration.DocsRenderedArtifact],
            m.Field(description="Complete ordered desired artifact inventory"),
        ]

    class DocsGenerationBundle(m.ArbitraryTypesModel):
        """Single render and source snapshot consumed through publication."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            arbitrary_types_allowed=True, extra="forbid", frozen=True
        )

        scopes: Annotated[
            t.VariadicTuple[FlextInfraModelsDocsGeneration.DocsScopeArtifacts],
            m.Field(min_length=1, description="Ordered selected scope inventories"),
        ]
        source_states: Annotated[
            t.VariadicTuple[cli_m.Cli.AtomicFileState],
            m.Field(min_length=1, description="Exact sources consumed by rendering"),
        ]

        @u.model_validator(mode="after")
        def _validate_unique_complete_inputs(self) -> Self:
            scope_names = tuple(item.scope.name for item in self.scopes)
            if len(set(scope_names)) != len(scope_names):
                msg = "docs generation scope names must be unique"
                raise ValueError(msg)
            destinations = tuple(
                item.scope.path / artifact.relative_path
                for item in self.scopes
                for artifact in item.artifacts
            )
            if len(set(destinations)) != len(destinations):
                msg = "docs generation destinations must be unique"
                raise ValueError(msg)
            source_paths = tuple(state.path for state in self.source_states)
            if len(set(source_paths)) != len(source_paths):
                msg = "docs generation source paths must be unique"
                raise ValueError(msg)
            if any(
                state.content is None
                or state.mode is None
                or state.device is None
                or state.inode is None
                or state.link_count != 1
                or state.reparse_tag not in {None, 0}
                for state in self.source_states
            ):
                msg = "docs generation source state is absent or unauthenticated"
                raise ValueError(msg)
            return self


__all__: list[str] = ["FlextInfraModelsDocsGeneration"]
