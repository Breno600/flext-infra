"""Root workspace ``[tool.uv]`` overlay rendering and validation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from flext_cli import r, u

from flext_infra import c, t

from ..dependencies import FlextInfraUtilitiesDependencies
from ..repository import FlextInfraUtilitiesRepository
from .requirements import FlextInfraUtilitiesPyprojectRequirements

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesPyprojectUvSources(FlextInfraUtilitiesPyprojectRequirements):
    """Keep managed uv sources only as the root local-workspace overlay."""

    @classmethod
    def _declared_uv_constraint_dependencies(
        cls, document: t.Cli.TomlDocument
    ) -> t.SequenceOf[str]:
        """Return the document-declared ``[tool.uv] constraint-dependencies``."""
        tool = u.Cli.toml_table_child(document, c.Infra.TOOL)
        if tool is None:
            return ()
        uv = u.Cli.toml_table_child(tool, "uv")
        if uv is None:
            return ()
        declared = u.Cli.toml_value(uv, "constraint-dependencies")
        return tuple(u.Cli.toml_as_string_list(declared))

    @classmethod
    def _document_requirement_lines(
        cls, document: t.Cli.TomlDocument
    ) -> p.Result[list[str]]:
        """Collect every declared requirement line of one pyproject document."""
        payload = u.Cli.toml_as_mapping(document)
        if payload is None:
            return r[list[str]].fail("pyproject document is not a TOML mapping")
        requirements: list[str] = []
        project = payload.get(c.Infra.PROJECT)
        if isinstance(project, Mapping):
            for key in (c.Infra.DEPENDENCIES, c.Infra.OPTIONAL_DEPENDENCIES):
                requirements.extend(cls.raw_requirement_values(project.get(key)))
        groups = payload.get(c.Infra.DEPENDENCY_GROUPS)
        if isinstance(groups, Mapping):
            for group in groups.values():
                requirements.extend(cls.raw_requirement_values(group))
        return r[list[str]].ok(requirements)

    @classmethod
    def _dependency_overrides(
        cls, workspace: p.Infra.WorkspaceSpec, *, requirements: t.SequenceOf[str]
    ) -> p.Result[t.VariadicTuple[str]]:
        """Render declared immutable revisions as uv override-dependencies.

        A manifest-declared revision pins one external provider-owned
        dependency to an explicit SHA. The URL is still detected — from that
        dependency's own declared direct Git source in the same document —
        so a pin without a declared source fails loudly instead of borrowing
        an URL from any catalog.
        """
        revisions: t.StrMapping = (
            workspace.project.dependency_revisions if workspace.project else {}
        )
        members = {member.distribution for member in workspace.subprojects}
        declared: dict[str, str] = {}
        for requirement in requirements:
            name = FlextInfraUtilitiesDependencies.dep_name(requirement)
            if name is not None and name in revisions:
                declared[name] = requirement
        overrides: list[str] = []
        for name in sorted(revisions):
            if name in members or not name.startswith("flext-"):
                return r[t.VariadicTuple[str]].fail(
                    f"dependency revision must name an external provider dependency: {name}"
                )
            source = FlextInfraUtilitiesRepository.declared_git_source(
                declared.get(name, name)
            )
            if source.failure:
                return r[t.VariadicTuple[str]].from_failure(source)
            url, _ref = source.value
            if not url:
                return r[t.VariadicTuple[str]].fail(
                    "pinned dependency declares no direct git source to detect "
                    f"its URL from: {name}"
                )
            overrides.append(f"{name} @ git+{url}@{revisions[name]}")
        return r[t.VariadicTuple[str]].ok(tuple(overrides))

    @classmethod
    def _sync_uv_sources(
        cls,
        document: t.Cli.TomlDocument,
        *,
        project_name: str,
        workspace: p.Infra.WorkspaceSpec,
        workspace_mode: c.Infra.MakeProfile,
        link_mode: str | None = None,
        constraint_dependencies: t.SequenceOf[str] | None = None,
        exclude_dependencies: t.SequenceOf[p.Model] | None = None,
        uv_environments: t.StrSequence | None = None,
    ) -> p.Result[bool]:
        """Keep managed uv sources only as the root local-workspace overlay."""
        repository_root = cls._is_workspace_context_root(
            project_name=project_name,
            workspace=workspace,
            workspace_mode=workspace_mode,
        )
        declared_requirements = cls._document_requirement_lines(document)
        if declared_requirements.failure:
            return r[bool].from_failure(declared_requirements)
        overrides = cls._dependency_overrides(
            workspace, requirements=declared_requirements.value
        )
        if overrides.failure:
            return r[bool].from_failure(overrides)
        tool = u.Cli.toml_table_child(document, c.Infra.TOOL)
        if tool is None:
            if (
                not repository_root
                and link_mode is None
                and not exclude_dependencies
                and not constraint_dependencies
                and not overrides.value
            ):
                return r[bool].ok(True)
            tool = u.Cli.toml_ensure_table(document, c.Infra.TOOL)
        uv = u.Cli.toml_table_child(tool, "uv")
        if uv is None:
            if (
                not repository_root
                and link_mode is None
                and not exclude_dependencies
                and not constraint_dependencies
                and not overrides.value
            ):
                return r[bool].ok(True)
            uv = u.Cli.toml_ensure_table(tool, "uv")
        if overrides.value:
            u.Cli.toml_sync_string_list(uv, "override-dependencies", overrides.value)
        else:
            u.Cli.toml_remove_key_if_present(uv, "override-dependencies")
        u.Cli.toml_remove_key_if_present(uv, "required-version")
        # Constraints are SSOT-rendered: the declared config value is the only
        # source, so a removed declaration exterminates the key everywhere and
        # no orphan cap can survive without an owner (flext-gzfd2 class).
        selected_constraints = tuple(constraint_dependencies or ())
        retained_constraints = tuple(
            requirement
            for requirement in selected_constraints
            if FlextInfraUtilitiesDependencies.dep_name(requirement) != "uv"
        )
        if retained_constraints:
            u.Cli.toml_sync_string_list(
                uv, "constraint-dependencies", retained_constraints
            )
        else:
            u.Cli.toml_remove_key_if_present(uv, "constraint-dependencies")
        if link_mode is not None:
            u.Cli.toml_sync_value(uv, "link-mode", link_mode)
        # The supply-chain cooldown was exterminated fleet-wide (flext-fphyv):
        # uv resolves every version published up to now. Removed declarations
        # exterminate the keys everywhere so no orphan cap survives without an
        # owner (flext-gzfd2 class).
        u.Cli.toml_remove_key_if_present(uv, "exclude-newer")
        u.Cli.toml_remove_key_if_present(uv, "exclude-newer-package")
        # Environments come from the fleet toolchain SSOT: an empty declaration
        # removes the key so uv resolves every environment, and a declared
        # sequence skips the splits the fleet does not support (win32 resolves
        # meltano's structlog cap against flext-core's floor and is
        # unsatisfiable).
        if uv_environments is not None and uv_environments:
            # Declared as list[JsonValue], not list[str]: `list` is invariant,
            # so the narrower element type is not assignable to the writer's
            # parameter even though every element is a valid JsonValue.
            environments: list[t.JsonValue] = list(uv_environments)
            u.Cli.toml_sync_value(uv, "environments", environments)
        elif uv_environments is not None:
            u.Cli.toml_remove_key_if_present(uv, "environments")
        # Project is a flext-infra routing key only; uv scoped form is
        # {package={name, version?}, dependencies=[...]} (uv settings docs).
        # Emit on every owning pyproject so standalone CI clones resolve;
        # do not gate on owns_uv_root_policy (that stripped member excludes).
        if exclude_dependencies is not None:
            exclude_payload = list(
                t.Cli.JSON_LIST_ADAPTER.validate_python([
                    {
                        key: value
                        for key, value in item.model_dump(
                            mode="json", exclude_none=True
                        ).items()
                        if key != "project"
                    }
                    for item in exclude_dependencies
                ])
            )
            if exclude_payload:
                u.Cli.toml_sync_value(uv, "exclude-dependencies", exclude_payload)
            else:
                u.Cli.toml_remove_key_if_present(uv, "exclude-dependencies")
        # Each repository owns its own frozen lock and external environment.
        # A root uv workspace would require every gitlink in root-only CI.
        u.Cli.toml_remove_key_if_present(uv, "workspace")
        sources = u.Cli.toml_table_child(uv, "sources")
        if sources is None:
            if not repository_root and not tuple(uv):
                u.Cli.toml_remove_key_if_present(tool, "uv")
            return r[bool].ok(True)
        for source_name in tuple(sources):
            if source_name.startswith("flext-"):
                u.Cli.toml_remove_key_if_present(sources, source_name)
        if not tuple(sources):
            u.Cli.toml_remove_key_if_present(uv, "sources")
        if not repository_root and not tuple(uv):
            u.Cli.toml_remove_key_if_present(tool, "uv")
        return r[bool].ok(True)

    @staticmethod
    def raw_requirement_values(raw: p.AttributeProbe) -> list[str]:
        """Collect raw requirement strings from a dependencies value or group table.

        ``project.dependencies`` is one array while ``optional-dependencies``
        and ``dependency-groups`` are tables of arrays; this is the single
        owner of that shape for read-only requirement scans.
        """
        if isinstance(raw, Mapping):
            values: list[str] = []
            for group in raw.values():
                values.extend(
                    FlextInfraUtilitiesPyprojectUvSources.raw_requirement_values(group)
                )
            return values
        if isinstance(raw, (list, tuple)):
            return [item for item in raw if isinstance(item, str)]
        return []

    @classmethod
    def _validate_root_uv_sources(
        cls, document: t.Cli.TomlDocument, *, workspace: p.Infra.WorkspaceSpec
    ) -> p.Result[bool]:
        """Reject retired root workspace state without rewriting TOML tables."""
        payload = u.Cli.toml_as_mapping(document)
        if payload is None:
            return r[bool].fail("pyproject document is not a TOML mapping")
        tool = payload.get(c.Infra.TOOL)
        if not isinstance(tool, Mapping):
            return r[bool].fail("root pyproject must define [tool]")
        uv = tool.get("uv")
        if not isinstance(uv, Mapping):
            return r[bool].fail("root pyproject must define [tool.uv]")
        declared_requirements = cls._document_requirement_lines(document)
        if declared_requirements.failure:
            return r[bool].from_failure(declared_requirements)
        overrides = cls._dependency_overrides(
            workspace, requirements=declared_requirements.value
        )
        if overrides.failure:
            return r[bool].from_failure(overrides)
        declared = u.Cli.toml_as_string_list(uv.get("override-dependencies"))
        if tuple(declared) != overrides.value:
            return r[bool].fail("root dependency overrides differ from workspace SSOT")
        if "workspace" in uv:
            return r[bool].fail("root pyproject retains retired uv workspace")
        sources = uv.get("sources")
        if isinstance(sources, Mapping) and any(
            source_name.startswith("flext-") for source_name in sources
        ):
            return r[bool].fail("root pyproject retains retired workspace sources")
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraUtilitiesPyprojectUvSources"]
