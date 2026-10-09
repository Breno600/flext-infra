"""Public pyproject conformer over the requirement and uv-source owners.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated

from flext_cli import r, u

from flext_infra import c, m, p, t
from flext_infra._utilities import FlextInfraUtilitiesDependencies
from flext_infra._utilities._pyproject.uv_sources import (
    FlextInfraUtilitiesPyprojectUvSources,
)


class FlextInfraUtilitiesPyprojectDocument(FlextInfraUtilitiesPyprojectUvSources):
    """Render root workspace and autonomous library metadata deterministically."""

    class PyprojectConformOptions(m.ImmutableValueModel):
        """Detected integration provenance for internal requirements and dev floors."""

        flext_line: Annotated[
            m.Infra.WorkspaceIntegrationSpec | None,
            m.Field(
                description="Detected provider and branch for internal requirements",
            ),
        ] = None

    @classmethod
    def _parsed_pyproject(
        cls,
        pyproject_content: str,
    ) -> p.Result[t.Pair[t.Cli.TomlDocument, str]]:
        """Parse one pyproject source and return it with its declared project name.

        Returns:
            The resulting ``p.Result[t.Pair[t.Cli.TomlDocument, str]]``.

        """
        source = u.Cli.toml_parse_text(pyproject_content)
        if source is None:
            return r[t.Pair[t.Cli.TomlDocument, str]].fail(
                "pyproject content is not valid TOML",
            )
        project = u.Cli.toml_table_child(source, c.Infra.PROJECT)
        if project is None:
            return r[t.Pair[t.Cli.TomlDocument, str]].fail(
                "pyproject content must define [project]",
            )
        project_name_raw = u.Cli.toml_value(project, c.Infra.NAME)
        if not isinstance(project_name_raw, str) or not project_name_raw.strip():
            return r[t.Pair[t.Cli.TomlDocument, str]].fail(
                "[project].name must be a non-empty string",
            )
        return r[t.Pair[t.Cli.TomlDocument, str]].ok((source, project_name_raw.strip()))

    @classmethod
    def pyproject_conform(
        cls,
        pyproject_content: str,
        *,
        workspace: m.Infra.WorkspaceSpec,
        required_dev_dependencies: t.StrSequence,
        uv_resolution: m.Infra.UvResolutionSpec,
        options: PyprojectConformOptions | None = None,
    ) -> p.Result[str]:
        """Return canonical TOML with autonomous dependencies and uv policy.

        The workspace manifest owns the topology facts, including the
        namespace production scope its project declares and the members a
        workspace root environment serves. Attached members, of any family,
        render on the workspace's declared integration line; ``options.flext_line``
        is the detected FLEXT integration line whose branch re-renders commit
        residue in the other internal requirements. Without a line, both fail
        loudly. Generated bare dev floors use the same detected provider line as
        the scaffold; CUSTOM requirements never acquire provenance from provider
        policy unless that dependency is a declared floor.

        Returns:
            Canonical TOML with autonomous dependencies and uv policy.

        """
        parsed = cls._parsed_pyproject(pyproject_content)
        if parsed.failure:
            return r[str].from_failure(parsed)
        source, project_name = parsed.value
        provenance = options if options is not None else cls.PyprojectConformOptions()
        # Only the workspace root normalizes member requirements to bare names.
        # Attached members retain inline Git provenance for published metadata;
        # their containing workspace identity is applied separately to uv sources.
        workspace_members = (
            tuple(
                member.distribution
                for member in workspace.subprojects
                if member.package
            )
            if workspace.repository.role is c.Infra.MakeProfile.WORKSPACE
            else ()
        )
        cls._sync_dependency_groups(
            source,
            project_name=project_name,
            required_dev_dependencies=required_dev_dependencies,
        )
        requirement_sources = cls._declared_requirement_sources(
            source,
            project_name=project_name,
            workspace=workspace,
            required_dev_dependencies=required_dev_dependencies,
            flext_line=provenance.flext_line,
        )
        if requirement_sources.failure:
            return r[str].from_failure(requirement_sources)
        declared_sources, candidate_sources = requirement_sources.value
        normalized = cls._normalize_requirements(
            source,
            declared_sources=declared_sources,
            candidate_sources=candidate_sources,
            family_line=(
                None if provenance.flext_line is None else provenance.flext_line.branch
            ),
            workspace_members=workspace_members,
        )
        if normalized.failure:
            return r[str].from_failure(normalized)
        cls._remove_legacy_tooling(source)
        synced = cls._synced_conform_tables(
            source,
            uv_resolution=uv_resolution,
            candidate_sources=candidate_sources,
            workspace_members=workspace_members or workspace.superproject_members,
            workspace=workspace,
        )
        if synced.failure:
            return r[str].from_failure(synced)
        return cls._render_pyproject(source)

    @staticmethod
    def _declared_floor_sources(
        workspace: m.Infra.WorkspaceSpec,
        *,
        project_name: str,
        requirements: t.StrSequence,
        flext_line: m.Infra.WorkspaceIntegrationSpec | None,
    ) -> p.Result[t.StrMapping]:
        """Derive member sources and provider provenance only for generated floors.

        Returns:
            Declared sources, or the missing provider URL failure.

        """
        declared_sources = (
            {
                member.distribution: f"git+{member.url}@{workspace.integration.branch}"
                for member in workspace.subprojects
            }
            if workspace.integration is not None
            else {}
        )
        if flext_line is not None:
            floors = {
                name
                for requirement in requirements
                if (name := FlextInfraUtilitiesDependencies.dep_name(requirement))
                and name not in {project_name, *declared_sources}
                and name.startswith("flext-")
                and requirement.strip() == name
            }
            if floors and flext_line.base_url is None:
                return r[t.StrMapping].fail(
                    "detected FLEXT line carries no provider base URL",
                )
            declared_sources.update({
                name: f"git+{flext_line.base_url}/{name}.git@{flext_line.branch}"
                for name in floors
            })
        return r[t.StrMapping].ok(declared_sources)

    @staticmethod
    def _render_pyproject(source: t.Cli.TomlDocument) -> p.Result[str]:
        """Serialize the conformed document and validate the rendered TOML.

        Returns:
            Rendered TOML, or the original invalid-render failure.

        """
        rendered = u.Cli.toml_dumps(source)
        if u.Cli.toml_parse_text(rendered) is None:
            return r[str].fail("canonical pyproject rendering produced invalid TOML")
        return r[str].ok(rendered)

    @classmethod
    def _declared_requirement_sources(
        cls,
        source: t.Cli.TomlDocument,
        *,
        project_name: str,
        workspace: m.Infra.WorkspaceSpec,
        required_dev_dependencies: t.StrSequence,
        flext_line: m.Infra.WorkspaceIntegrationSpec | None,
    ) -> p.Result[t.Pair[t.StrMapping, t.StrMapping]]:
        """Return the declared and candidate Git sources of internal requirements.

        Workspace members render on the declared integration line; generated
        bare ``flext-*`` dev floors render on the detected FLEXT line; candidate
        dependencies must be declared requirements.

        Returns:
            The declared and candidate requirement sources.

        """
        declared = cls._declared_floor_sources(
            workspace,
            project_name=project_name,
            requirements=required_dev_dependencies,
            flext_line=flext_line,
        )
        if declared.failure:
            return r[t.Pair[t.StrMapping, t.StrMapping]].from_failure(declared)
        declared_sources = declared.value
        candidate_sources = {
            item.distribution: f"git+{item.url}@{item.commit}"
            for item in workspace.candidate_dependencies
        }
        unused_candidates = sorted(
            candidate_sources.keys()
            - set(FlextInfraUtilitiesDependencies.declared_dependency_names(source)),
        )
        if unused_candidates:
            return r[t.Pair[t.StrMapping, t.StrMapping]].fail(
                "candidate dependencies are not declared requirements: "
                + ", ".join(unused_candidates),
            )
        return r[t.Pair[t.StrMapping, t.StrMapping]].ok(
            (declared_sources, candidate_sources),
        )

    @classmethod
    def _synced_conform_tables(
        cls,
        source: t.Cli.TomlDocument,
        *,
        uv_resolution: m.Infra.UvResolutionSpec,
        candidate_sources: t.StrMapping,
        workspace_members: t.StrSequence,
        workspace: m.Infra.WorkspaceSpec,
    ) -> p.Result[bool]:
        """Sync the canonical typecheck, namespace, uv, and provenance tables.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        typecheck_paths = cls._sync_typecheck_paths(source)
        if typecheck_paths.failure:
            return r[bool].from_failure(typecheck_paths)
        namespace_scope = cls._sync_namespace_scope(
            source,
            workspace.project.namespace_scan_dirs
            if workspace.project is not None
            else None,
        )
        if namespace_scope.failure:
            return r[bool].from_failure(namespace_scope)
        sources_result = cls._sync_uv_sources(
            source,
            resolution=uv_resolution,
            candidate_sources=candidate_sources,
            workspace_members=workspace_members,
            owns_workspace_table=(
                workspace.repository.role is c.Infra.MakeProfile.WORKSPACE
            ),
        )
        if sources_result.failure:
            return r[bool].from_failure(sources_result)
        provenance_result = cls._validate_dependency_provenance(
            source,
            workspace=workspace,
        )
        if provenance_result.failure:
            return r[bool].from_failure(provenance_result)
        return r[bool].ok(value=True)

    @staticmethod
    def _remove_legacy_tooling(document: t.Cli.TomlDocument) -> None:
        """Delete legacy packaging owners superseded by canonical conformance.

        The ``[tool.flext]`` table is preserved because it carries project-local
        tooling policy unrelated to repository topology.
        """
        tool = u.Cli.toml_table_child(document, c.Infra.TOOL)
        if tool is None:
            return
        u.Cli.toml_remove_key_if_present(tool, c.Infra.POETRY)

    @staticmethod
    def _sync_namespace_scope(
        document: t.Cli.TomlDocument,
        namespace_scan_dirs: t.StrSequence | None,
    ) -> p.Result[bool]:
        """Sync ``[tool.flext.namespace].scan_dirs`` from the project SSOT.

        ``None`` or an empty sequence leaves the section untouched: projects
        without a declared scope keep the dynamic every-root behavior. A
        non-empty sequence is the workspace manifest's production scope.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if not namespace_scan_dirs:
            return r[bool].ok(value=True)
        namespace = u.Cli.toml_ensure_path(document, c.Infra.CONFORM_NAMESPACE_TABLE)
        u.Cli.toml_sync_string_list(namespace, "scan_dirs", list(namespace_scan_dirs))
        return r[bool].ok(value=True)

    @staticmethod
    def _sync_typecheck_paths(document: t.Cli.TomlDocument) -> p.Result[bool]:
        """Remove checkout-absolute type checker interpreter pins.

        Search paths belong to FlextInfraExtraPathsManager. Top-level
        ``venv`` / ``venvPath`` belong to deps modernize (root vs child
        runtime). Conform must not strip those or gen oscillates.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        tool = u.Cli.toml_table_child(document, c.Infra.TOOL)
        if tool is None:
            return r[bool].ok(value=True)
        pyrefly = u.Cli.toml_table_child(tool, c.Infra.PYREFLY)
        if pyrefly is not None:
            u.Cli.toml_remove_key_if_present(pyrefly, "python-interpreter-path")

        pyright = u.Cli.toml_table_child(tool, c.Infra.PYRIGHT)
        if pyright is None:
            return r[bool].ok(value=True)

        # venv / venvPath are owned by deps modernize (workspace vs child
        # runtime). Conform only strips checkout-absolute interpreter pins.
        interpreter_keys = ("pythonPath", "pythonInterpreterPath")
        for key in interpreter_keys:
            u.Cli.toml_remove_key_if_present(pyright, key)
        raw_environments = u.Cli.json_as_sequence(
            u.Cli.toml_value(pyright, "executionEnvironments"),
        )
        normalized_environments: t.JsonValueList = []
        for index, environment in enumerate(raw_environments):
            if not isinstance(environment, Mapping):
                return r[bool].fail(
                    f"tool.pyright.executionEnvironments[{index}] must be a mapping",
                )
            mapping = t.Cli.JSON_MAPPING_ADAPTER.validate_python(environment)
            normalized: t.JsonDict = dict(mapping)
            root = normalized.get("root")
            normalized[c.Infra.EXTRA_PATHS] = ["src"] if root == "src" else [".", "src"]
            for key in ("venv", "venvPath", "pythonPath", "pythonInterpreterPath"):
                normalized.pop(key, None)
            normalized_environments.append(normalized)
        if raw_environments:
            u.Cli.toml_sync_value(
                pyright,
                "executionEnvironments",
                normalized_environments,
            )
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraUtilitiesPyprojectDocument"]
