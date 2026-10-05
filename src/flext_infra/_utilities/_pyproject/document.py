"""Public pyproject conformer over the requirement and uv-source owners.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from flext_cli import r, u

from flext_infra import c, m, t
from flext_infra._utilities._pyproject.uv_sources import (
    FlextInfraUtilitiesPyprojectUvSources,
)
from flext_infra._utilities.dependencies import FlextInfraUtilitiesDependencies

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesPyprojectDocument(FlextInfraUtilitiesPyprojectUvSources):
    """Render root workspace and autonomous library metadata deterministically."""

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
        family_line: str | None = None,
    ) -> p.Result[str]:
        """Return canonical TOML with autonomous dependencies and uv policy.

        The workspace manifest owns the topology facts, including the
        namespace production scope its project declares and the members a
        workspace root environment serves. Attached members, of any family,
        render on the workspace's declared integration line; ``family_line``
        is the detected FLEXT integration branch that re-renders commit residue
        in the other internal requirements. Without a line, both fail loudly.

        Returns:
            Canonical TOML with autonomous dependencies and uv policy.

        """
        parsed = cls._parsed_pyproject(pyproject_content)
        if parsed.failure:
            return r[str].from_failure(parsed)
        source, project_name = parsed.value
        cls._sync_dependency_groups(
            source,
            project_name=project_name,
            required_dev_dependencies=required_dev_dependencies,
            workspace_members=tuple(
                member.distribution
                for member in workspace.subprojects
                if member.package
            )
            if workspace.repository.role is c.Infra.MakeProfile.WORKSPACE
            else (),
        )
        declared_sources = (
            {
                member.distribution: f"git+{member.url}@{workspace.integration.branch}"
                for member in workspace.subprojects
            }
            if workspace.integration is not None
            else {}
        )
        candidate_sources = {
            item.distribution: f"git+{item.url}@{item.commit}"
            for item in workspace.candidate_dependencies
        }
        unused_candidates = sorted(
            candidate_sources.keys()
            - set(FlextInfraUtilitiesDependencies.declared_dependency_names(source)),
        )
        if unused_candidates:
            return r[str].fail(
                "candidate dependencies are not declared requirements: "
                + ", ".join(unused_candidates),
            )
        normalized = cls._normalize_requirements(
            source,
            declared_sources=declared_sources,
            candidate_sources=candidate_sources,
            family_line=family_line,
        )
        if normalized.failure:
            return r[str].from_failure(normalized)
        cls._remove_legacy_tooling(source)
        typecheck_paths = cls._sync_typecheck_paths(source)
        if typecheck_paths.failure:
            return r[str].from_failure(typecheck_paths)
        namespace_scope = cls._sync_namespace_scope(
            source,
            workspace.project.namespace_scan_dirs
            if workspace.project is not None
            else None,
        )
        if namespace_scope.failure:
            return r[str].from_failure(namespace_scope)
        sources_result = cls._sync_uv_sources(
            source,
            resolution=uv_resolution,
            candidate_sources=candidate_sources,
        )
        if sources_result.failure:
            return r[str].from_failure(sources_result)
        provenance_result = cls._validate_dependency_provenance(
            source,
            workspace=workspace,
        )
        if provenance_result.failure:
            return r[str].from_failure(provenance_result)
        rendered = u.Cli.toml_dumps(source)
        if u.Cli.toml_parse_text(rendered) is None:
            return r[str].fail("canonical pyproject rendering produced invalid TOML")
        return r[str].ok(rendered)

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
