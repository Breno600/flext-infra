"""Root workspace ``[tool.uv]`` overlay rendering and validation."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from pathlib import Path
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
    def active_session_requirements(
        cls, document: t.Cli.TomlDocument, *, environment: t.StrMapping | None = None
    ) -> t.VariadicTuple[str]:
        """Read strictly parsed requirements active on the consumer's physical host."""
        return tuple(
            active
            for item in cls._document_requirement_lines(document).unwrap()
            if (
                active := FlextInfraUtilitiesDependencies.active_requirement(
                    item, environment=environment
                )
            )
            is not None
        )

    @classmethod
    def session_dependency_requirements(
        cls,
        document: t.Cli.TomlDocument,
        workspace: p.Infra.WorkspaceSpec,
        *,
        selected: t.StrSequence,
        consumer_root: Path,
        environment: t.StrMapping | None = None,
    ) -> p.Result[t.Pair[t.VariadicTuple[str], t.VariadicTuple[str]]]:
        """Preserve consumer resolution declarations during a local binding."""
        tool = u.Cli.toml_table_child(document, c.Infra.TOOL)
        if (
            tool is not None
            and u.Cli.toml_table_child(tool, c.Infra.POETRY) is not None
        ):
            return r[t.Pair[t.VariadicTuple[str], t.VariadicTuple[str]]].fail(
                "session binding requires PEP 621/735 dependency declarations"
            )
        requirements = cls._document_requirement_lines(document).unwrap()
        uv = u.Cli.toml_table_child(tool, "uv") if tool is not None else None
        explicit: list[str] = []
        if uv is not None:
            explicit = list(u.Cli.toml_as_string_list(uv.get("override-dependencies")))
        local_sources = cls.session_workspace_sources(
            document,
            workspace,
            consumer_root=consumer_root,
            selected=selected,
            environment=environment,
        )
        if local_sources.failure:
            return r[t.Pair[t.VariadicTuple[str], t.VariadicTuple[str]]].from_failure(
                local_sources
            )
        sources = FlextInfraUtilitiesRepository.declared_dependency_sources(
            workspace.project.dependency_sources if workspace.project else {}
        ).unwrap()
        declared_revisions = (
            workspace.project.dependency_revisions if workspace.project else {}
        )
        requirements, explicit = [
            [
                cls.canonical_requirement(
                    item,
                    sources=sources,
                    revisions=declared_revisions,
                    workspace_dependencies={},
                ).unwrap()
                if FlextInfraUtilitiesDependencies.dep_name(item)
                in {*sources, *declared_revisions}
                and FlextInfraUtilitiesDependencies.dep_name(item)
                not in {*selected, *local_sources.value}
                else item
                for item in group
            ]
            for group in (requirements, explicit)
        ]
        revisions = cls._dependency_overrides(
            workspace, requirements=requirements
        ).unwrap()
        revision_names = {
            FlextInfraUtilitiesDependencies.dep_name(item) for item in revisions
        }
        revisions = tuple(
            item
            for item in requirements
            if FlextInfraUtilitiesDependencies.dep_name(item) in revision_names
        )
        explicit = [
            item
            for item in explicit
            if FlextInfraUtilitiesDependencies.dep_name(item) not in revision_names
        ]
        overrides = [
            *(
                item
                for item in (
                    *explicit,
                    *revisions,
                    *(
                        item
                        for item in requirements
                        if FlextInfraUtilitiesDependencies.dep_name(item) in sources
                    ),
                )
                if FlextInfraUtilitiesDependencies.dep_name(item)
                not in local_sources.value
            ),
            *(
                f"{name} @ {path.as_uri()}"
                for name, path in local_sources.value.items()
            ),
        ]
        overrides = [
            item
            for item in overrides
            if FlextInfraUtilitiesDependencies.active_requirement(
                item, environment=environment
            )
            is not None
        ]
        override_names = {
            FlextInfraUtilitiesDependencies.dep_name(item) for item in overrides
        }
        constraints = [
            FlextInfraUtilitiesDependencies.dependency_constraint(
                item,
                replace_source=FlextInfraUtilitiesDependencies.dep_name(item)
                in {*selected, *local_sources.value},
            )
            for item in requirements
            if FlextInfraUtilitiesDependencies.dep_name(item) not in override_names
            or FlextInfraUtilitiesDependencies.dep_name(item)
            in {*selected, *local_sources.value}
        ]
        return r[t.Pair[t.VariadicTuple[str], t.VariadicTuple[str]]].ok((
            tuple(
                dict.fromkeys(
                    item
                    for item in overrides
                    if FlextInfraUtilitiesDependencies.dep_name(item) not in selected
                )
            ),
            tuple(
                dict.fromkeys(
                    item
                    for item in (
                        *constraints,
                        *cls._declared_uv_constraint_dependencies(document),
                    )
                    if FlextInfraUtilitiesDependencies.active_requirement(
                        item, environment=environment
                    )
                    is not None
                )
            ),
        ))

    @classmethod
    def session_workspace_sources(
        cls,
        document: t.Cli.TomlDocument,
        workspace: p.Infra.WorkspaceSpec,
        *,
        consumer_root: Path,
        selected: t.StrSequence,
        environment: t.StrMapping | None = None,
    ) -> p.Result[t.MappingKV[str, Path]]:
        """Authenticate canonical local workspace sources against declared members."""
        tool = u.Cli.toml_table_child(document, c.Infra.TOOL)
        uv = u.Cli.toml_table_child(tool, "uv") if tool is not None else None
        sources = u.Cli.toml_table_child(uv, "sources") if uv is not None else None
        members = {member.distribution: member for member in workspace.subprojects}
        declared = {
            FlextInfraUtilitiesDependencies.dep_name(item)
            for item in cls.active_session_requirements(
                document, environment=environment
            )
        }
        local: dict[str, Path] = {}
        if sources is not None:
            normalized_sources = u.Cli.toml_as_mapping(sources)
            if normalized_sources is None:
                return r[t.MappingKV[str, Path]].fail(
                    "session binding dependency sources must be a TOML mapping"
                )
            for name, source in normalized_sources.items():
                if name in selected or name not in declared:
                    continue
                member = members.get(name)
                if (
                    not isinstance(source, Mapping)
                    or source.get("workspace") is not True
                    or tuple(source) != ("workspace",)
                    or member is None
                ):
                    return r[t.MappingKV[str, Path]].fail(
                        f"session binding cannot resolve unselected dependency sources: {name}"
                    )
                declared_path = consumer_root.resolve() / member.path
                path = declared_path.resolve()
                if path != declared_path or not path.is_relative_to(
                    consumer_root.resolve()
                ):
                    return r[t.MappingKV[str, Path]].fail(
                        f"session binding requires a physical workspace member: {name}: {declared_path}"
                    )
                if not (path / c.Infra.PYPROJECT_FILENAME).is_file():
                    return r[t.MappingKV[str, Path]].fail(
                        f"session binding workspace member is not provisioned: {name}: {path}"
                    )
                local[name] = path
        return r[t.MappingKV[str, Path]].ok(local)

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
        member_paths = tuple(member.path.as_posix() for member in workspace.subprojects)
        # Only an actual multi-project owner declares a uv workspace. A leaf
        # can also be a composed member; inserting an empty workspace there
        # breaks execution from the parent with uv's nested-workspace error.
        if repository_root and member_paths:
            workspace_table = u.Cli.toml_table_child(uv, "workspace")
            if workspace_table is None:
                workspace_table = u.Cli.toml_ensure_table(uv, "workspace")
            u.Cli.toml_sync_string_list(workspace_table, "members", member_paths)
        else:
            u.Cli.toml_remove_key_if_present(uv, "workspace")
        sources = u.Cli.toml_table_child(uv, "sources")
        if sources is None and repository_root:
            sources = u.Cli.toml_ensure_table(uv, "sources")
        if sources is None:
            if not repository_root and not tuple(uv):
                u.Cli.toml_remove_key_if_present(tool, "uv")
            return r[bool].ok(True)
        workspace_names = {member.distribution for member in workspace.subprojects}
        for source_name in tuple(sources):
            # Member documents resolve internal siblings through the direct
            # Git requirement; a git [tool.uv.sources] entry on a workspace
            # member is rejected by uv itself, and only the root carries the
            # workspace overlay.
            if source_name.startswith("flext-") and (
                not repository_root or source_name not in workspace_names
            ):
                u.Cli.toml_remove_key_if_present(sources, source_name)
        if repository_root:
            for member in workspace.subprojects:
                u.Cli.toml_sync_mapping_table(
                    sources, member.distribution, {"workspace": True}
                )
        elif not tuple(sources):
            u.Cli.toml_remove_key_if_present(uv, "sources")
        if not repository_root and not tuple(uv):
            u.Cli.toml_remove_key_if_present(tool, "uv")
        return r[bool].ok(True)

    @staticmethod
    def raw_requirement_values(raw: object) -> list[str]:
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

    @staticmethod
    def _resolved_root_sources(
        *, workspace: p.Infra.WorkspaceSpec
    ) -> MutableMapping[str, MutableMapping[str, t.JsonValue]]:
        """Resolve the workspace source overlay from the declared topology."""
        return {
            member.distribution: {"workspace": True} for member in workspace.subprojects
        }

    @classmethod
    def _validate_root_uv_sources(
        cls, document: t.Cli.TomlDocument, *, workspace: p.Infra.WorkspaceSpec
    ) -> p.Result[bool]:
        """Validate the root overlay without rewriting out-of-order TOML tables."""
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
        uv_workspace = uv.get("workspace")
        if not isinstance(uv_workspace, Mapping):
            return r[bool].fail("root pyproject must define [tool.uv.workspace]")
        validated_members: p.Result[t.StrSequence] = u.validate_value(
            t.Infra.STR_SEQ_ADAPTER, uv_workspace.get("members"), strict=True
        )
        if validated_members.failure:
            return r[bool].fail_op(
                "validate root uv workspace package entries", validated_members.error
            )
        members = validated_members.value
        expected_members = tuple(
            member.path.as_posix() for member in workspace.subprojects
        )
        if tuple(members) != expected_members:
            return r[bool].fail(
                "root uv workspace package entries differ from workspace SSOT"
            )
        sources = uv.get("sources")
        if not isinstance(sources, Mapping):
            return r[bool].fail("root pyproject must define [tool.uv.sources]")
        expected_sources = cls._resolved_root_sources(workspace=workspace)
        if tuple(sources) != tuple(expected_sources):
            return r[bool].fail("root uv workspace sources differ from workspace SSOT")
        for source_name, expected_source in expected_sources.items():
            source = sources.get(source_name)
            if (
                not isinstance(source, Mapping)
                or tuple(source) != tuple(expected_source)
                or dict(source) != expected_source
            ):
                return r[bool].fail(
                    f"root uv workspace sources differ from workspace SSOT: {source_name}"
                )
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraUtilitiesPyprojectUvSources"]
