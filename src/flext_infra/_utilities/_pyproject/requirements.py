"""Internal requirement rendering and workspace dependency-group policy.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from flext_cli import r, u

from flext_infra import c, t
from flext_infra._utilities.dependencies import FlextInfraUtilitiesDependencies
from flext_infra._utilities.repository import FlextInfraUtilitiesRepository

if TYPE_CHECKING:
    from collections.abc import Iterator

    from flext_infra import p


class FlextInfraUtilitiesPyprojectRequirements:
    """Render internal requirements for the active workspace topology."""

    @staticmethod
    def requirement_group_fields(
        document: t.Cli.TomlDocument,
        project: t.Cli.TomlTable,
    ) -> Iterator[t.Pair[t.Cli.TomlTable, str]]:
        """Yield ``(section, group_name)`` for every declared requirement group.

        Optional dependencies hang off ``[project]`` while dependency groups hang
        off the document root; this is the single owner of that traversal for
        every requirement rewriter.

        Yields:
            Each ``t.Pair[t.Cli.TomlTable, str]``.

        """
        for section_name in (c.Infra.OPTIONAL_DEPENDENCIES, c.Infra.DEPENDENCY_GROUPS):
            parent = (
                project if section_name == c.Infra.OPTIONAL_DEPENDENCIES else document
            )
            section = u.Cli.toml_table_child(parent, section_name)
            if section is None:
                continue
            for group_name in tuple(section):
                yield section, group_name

    @classmethod
    def _normalize_requirements(
        cls,
        document: t.Cli.TomlDocument,
        *,
        declared_sources: t.StrMapping,
        candidate_sources: t.StrMapping,
        family_line: str | None,
    ) -> p.Result[bool]:
        """Render internal requirements from their declared Git provenance.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        project = u.Cli.toml_ensure_table(document, c.Infra.PROJECT)
        normalized = cls._normalize_requirement_field(
            project,
            c.Infra.DEPENDENCIES,
            declared_sources=declared_sources,
            candidate_sources=candidate_sources,
            family_line=family_line,
        )
        if normalized.failure:
            return normalized
        for section, group_name in cls.requirement_group_fields(document, project):
            group_result = cls._normalize_requirement_field(
                section,
                group_name,
                declared_sources=declared_sources,
                candidate_sources=candidate_sources,
                family_line=family_line,
            )
            if group_result.failure:
                return group_result
        return r[bool].ok(value=True)

    @classmethod
    def _normalize_requirement_field(
        cls,
        container: t.Cli.TomlDocument | t.Cli.TomlTable,
        key: str,
        *,
        declared_sources: t.StrMapping,
        candidate_sources: t.StrMapping,
        family_line: str | None,
    ) -> p.Result[bool]:
        """Normalize one dependency array and fail on model-less entries.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        raw_value = u.Cli.toml_value(container, key)
        if raw_value is None:
            return r[bool].ok(value=True)
        raw_items = u.Cli.json_as_sequence(raw_value)
        validated_items: p.Result[t.StrSequence] = u.validate_value(
            t.Infra.STR_SEQ_ADAPTER,
            raw_items,
            strict=True,
        )
        if validated_items.failure:
            return r[bool].fail_op(
                f"validate dependency group {key}",
                validated_items.error,
            )
        items = validated_items.value
        normalized_items: t.MutableSequenceOf[str] = []
        for item in items:
            normalized = cls._canonical_requirement(
                item,
                declared_sources=declared_sources,
                candidate_sources=candidate_sources,
                family_line=family_line,
            )
            if normalized.failure:
                return r[bool].from_failure(normalized)
            normalized_items.append(normalized.value)
        canonical = tuple(
            sorted(dict.fromkeys(normalized_items), key=cls.dependency_order_key),
        )
        u.Cli.toml_sync_string_list(container, key, canonical)
        return r[bool].ok(value=True)

    @staticmethod
    def dependency_order_key(requirement: str) -> t.Pair[str, str]:
        """Order preserved and conformed requirements by name and complete spec.

        Returns:
            The resulting ``t.Pair[str, str]``.

        Raises:
            ValueError: If dependency ordering requires a named requirement.

        """
        name = FlextInfraUtilitiesDependencies.dep_name(requirement)
        if name is None:
            message = "dependency ordering requires a named requirement"
            raise ValueError(message)
        return name, requirement

    @classmethod
    def _canonical_requirement(
        cls,
        requirement: str,
        *,
        declared_sources: t.StrMapping,
        candidate_sources: t.StrMapping,
        family_line: str | None,
    ) -> p.Result[str]:
        """Render one internal requirement from its own declared Git source.

        The requirement line is the only authority for an internal
        dependency's canonical URL and branch: it is parsed and canonicalized
        (transport scheme only), never rewritten from provider policy. The ref
        is the dependency's integration line: uv.lock alone records the commit
        it resolves to, so a commit left in this generated projection is
        residue re-rendered on its line (an attached member's declared line,
        otherwise the detected FLEXT line) and never written back; without a
        line it fails loudly. Internal means the FLEXT family or an attached
        workspace member of any family. A source-less internal dependency that
        the active workspace overlay does not own is a loud failure.

        Returns:
            The resulting ``p.Result[str]``.

        """
        dependency_name = FlextInfraUtilitiesDependencies.dep_name(requirement)
        if dependency_name is None or not (
            dependency_name.startswith("flext-")
            or dependency_name in declared_sources
            or dependency_name in candidate_sources
        ):
            return r[str].ok(requirement.strip())
        requirement_part, separator, marker = requirement.partition(";")
        head_match = c.Infra.PEP621_REQUIREMENT_HEAD_RE.match(requirement_part.strip())
        if head_match is None:
            return r[str].fail(f"invalid internal requirement: {requirement}")
        head = head_match.group("head").strip()
        marker_text = marker.strip()
        source = FlextInfraUtilitiesRepository.declared_git_source(requirement)
        if source.failure:
            return r[str].from_failure(source)
        url, declared_ref = source.value
        line = family_line
        declared = declared_sources.get(dependency_name)
        if declared is not None:
            # An attached member renders on the line its declaration carries.
            parsed = FlextInfraUtilitiesRepository.declared_git_source(
                f"{head} @ {declared}",
            )
            if parsed.failure:
                return r[str].from_failure(parsed)
            declared_url, line = parsed.value
            if not url:
                url, declared_ref = declared_url, line
        candidate = candidate_sources.get(dependency_name)
        if candidate is not None:
            if not url:
                return r[str].fail(
                    "candidate dependency has no declared Git provenance: "
                    f"{dependency_name}",
                )
            selected = FlextInfraUtilitiesRepository.declared_git_source(
                f"{head} @ {candidate}",
            )
            if selected.failure:
                return r[str].from_failure(selected)
            candidate_url, candidate_commit = selected.value
            if not FlextInfraUtilitiesRepository.ref_is_commit(candidate_commit):
                return r[str].fail(
                    f"candidate dependency must pin a full Git commit: "
                    f"{dependency_name}",
                )
            if url and url != candidate_url:
                return r[str].fail(
                    "candidate dependency Git URL differs from declared provenance: "
                    f"{dependency_name}",
                )
            url, declared_ref = candidate_url, candidate_commit
            line = candidate_commit
        if not url:
            return r[str].fail(
                f"internal dependency declares no direct git source: {dependency_name}",
            )
        if candidate is None and FlextInfraUtilitiesRepository.ref_is_commit(
            declared_ref,
        ):
            if line is None:
                return r[str].fail(
                    f"internal dependency {dependency_name} pins commit "
                    f"{declared_ref} and no line is declared to re-render "
                    "it: uv.lock records the commit and only `make upg` moves it",
                )
            declared_ref = line
        # The inline Git source is the sole provenance for each independent
        # project lock, including the orchestration repository.
        inline = f"{head} @ git+{url}@{declared_ref}"
        return r[str].ok(
            f"{inline}; {marker_text}" if separator and marker_text else inline,
        )

    @classmethod
    def _sync_dependency_groups(
        cls,
        document: t.Cli.TomlDocument,
        *,
        project_name: str,
        required_dev_dependencies: t.StrSequence,
        workspace_members: t.StrSequence,
    ) -> None:
        """Migrate optional dev dependencies and normalize declared groups."""
        project = u.Cli.toml_ensure_table(document, c.Infra.PROJECT)
        groups = u.Cli.toml_ensure_table(document, c.Infra.DEPENDENCY_GROUPS)
        optional = u.Cli.toml_table_child(project, c.Infra.OPTIONAL_DEPENDENCIES)
        optional_dev: t.StrSequence = ()
        if optional is not None:
            optional_dev = u.Cli.toml_as_string_list(
                u.Cli.toml_value(optional, str(c.Infra.DEV)),
            )
        # SSOT required floors win over existing same-name pins: dedupe_specs
        # keeps the first occurrence, so toolchain floors must lead the merge.
        # Otherwise stale member pins override the declared fleet floor. One
        # exception is structural: a bare internal floor name carries no Git
        # source and no version to enforce, so a live requirement that declares
        # its own direct source is the authority for that dependency and the
        # floor yields to it.
        live_dev = u.Cli.toml_as_string_list(u.Cli.toml_value(groups, str(c.Infra.DEV)))
        sourced_live_names = {
            name
            for requirement in live_dev
            if (name := FlextInfraUtilitiesDependencies.dep_name(requirement))
            and cls._declares_direct_source(requirement)
        }
        required_dev = tuple(
            requirement
            for requirement in required_dev_dependencies
            if FlextInfraUtilitiesDependencies.dep_name(requirement) != project_name
            and not cls._floor_yields_to_declared_source(
                requirement,
                sourced_live_names,
            )
        )
        dev = [*required_dev, *live_dev, *optional_dev]
        if dev:
            u.Cli.toml_sync_string_list(
                groups,
                str(c.Infra.DEV),
                FlextInfraUtilitiesDependencies.dedupe_specs(tuple(dev)),
            )
        else:
            u.Cli.toml_remove_key_if_present(groups, str(c.Infra.DEV))

        codegen = u.Cli.toml_as_string_list(u.Cli.toml_value(groups, "codegen"))
        if codegen:
            u.Cli.toml_sync_string_list(
                groups,
                "codegen",
                FlextInfraUtilitiesDependencies.dedupe_specs(tuple(codegen)),
            )
        else:
            u.Cli.toml_remove_key_if_present(groups, "codegen")
        cls._sync_workspace_dependency_group(document, workspace_members)

        if optional is not None:
            u.Cli.toml_remove_key_if_present(optional, str(c.Infra.DEV))
            if not tuple(optional):
                u.Cli.toml_remove_key_if_present(project, c.Infra.OPTIONAL_DEPENDENCIES)

    @staticmethod
    def _declares_direct_source(requirement: str) -> bool:
        """Whether one requirement line declares a direct ``@ source``.

        Returns:
            The resulting ``bool``.

        """
        return "@" in requirement.partition(";")[0]

    @staticmethod
    def _floor_yields_to_declared_source(
        requirement: str,
        sourced_live_names: frozenset[str] | set[str],
    ) -> bool:
        """Whether a bare internal floor name must yield to a declared source.

        Returns:
            The resulting ``bool``.

        """
        name = FlextInfraUtilitiesDependencies.dep_name(requirement)
        return (
            name is not None
            and name.startswith("flext-")
            and not FlextInfraUtilitiesPyprojectRequirements._declares_direct_source(
                requirement,
            )
            and name in sourced_live_names
        )

    @staticmethod
    def _sync_workspace_dependency_group(
        document: t.Cli.TomlDocument,
        workspace_members: t.StrSequence,
    ) -> None:
        """Declare the attached members in the workspace root's own group.

        A workspace root environment serves every attached member, so its lock
        must carry the member distributions: setup syncs every group, and an
        absent group makes the exact sync uninstall the members. Each name is
        canonicalized afterwards to its inline Git source like any other
        internal requirement, so the root keeps its own independent lock and
        no uv workspace. Every other repository carries no such group.
        """
        if workspace_members:
            groups = u.Cli.toml_ensure_table(document, c.Infra.DEPENDENCY_GROUPS)
            u.Cli.toml_sync_string_list(
                groups,
                "workspace",
                tuple(sorted(workspace_members)),
            )
            return
        groups = u.Cli.toml_table_child(document, c.Infra.DEPENDENCY_GROUPS)
        if groups is not None:
            u.Cli.toml_remove_key_if_present(groups, "workspace")

    @staticmethod
    def _validate_dependency_provenance(
        document: t.Cli.TomlDocument,
        *,
        workspace: p.Infra.WorkspaceSpec,
    ) -> p.Result[bool]:
        """Require one internal dependency provenance for the active topology.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        payload = u.Cli.toml_as_mapping(document)
        if payload is None:
            return r[bool].fail("pyproject document is not a TOML mapping")
        member_names = frozenset(
            member.distribution for member in workspace.subprojects
        )
        raw_values: list[str] = []
        project = payload.get(c.Infra.PROJECT)
        if not isinstance(project, Mapping):
            return r[bool].fail("pyproject content must define [project]")
        for key in (c.Infra.DEPENDENCIES, c.Infra.OPTIONAL_DEPENDENCIES):
            value = project.get(key)
            if isinstance(value, Mapping):
                for group in value.values():
                    raw_values.extend(u.Cli.toml_as_string_list(group))
            else:
                raw_values.extend(u.Cli.toml_as_string_list(value))
        groups = payload.get(c.Infra.DEPENDENCY_GROUPS)
        if isinstance(groups, Mapping):
            for group in groups.values():
                raw_values.extend(u.Cli.toml_as_string_list(group))
        for requirement in raw_values:
            dependency_name = FlextInfraUtilitiesDependencies.dep_name(requirement)
            if dependency_name not in member_names:
                continue
            # The manifest owns the Git URL; the requirement keeps its exact
            # branch or locked revision in both root and standalone contexts.
            member = next(
                (
                    item
                    for item in workspace.subprojects
                    if item.distribution == dependency_name
                ),
                None,
            )
            if member is not None and not member.url.startswith("https://"):
                return r[bool].fail(
                    "internal dependency manifest provenance must be HTTPS: "
                    f"{dependency_name} ({member.url})",
                )
            if member is not None and "@" in requirement.partition(";")[0]:
                declared = FlextInfraUtilitiesRepository.declared_git_source(
                    requirement,
                )
                if declared.failure:
                    return r[bool].from_failure(declared)
                if declared.value[0] != member.url:
                    return r[bool].fail(
                        "internal dependency Git URL differs from manifest: "
                        f"{dependency_name}",
                    )
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraUtilitiesPyprojectRequirements"]
