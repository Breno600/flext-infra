"""Canonical Git responsibility mixin for ``u.Infra``.

The repository's committed ``.gitmodules`` is the only composition fact a
superproject owns. This mixin is its single reader: every path, URL, branch
and ``flext-managed`` flag reaches a consumer through
``git_submodule_declarations``, and the recorded member commits and the
dependency back edges derive from it.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path

from flext_cli import u
from git import GitCommandError
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from flext_infra import c, m, p, r, t
from flext_infra._utilities._git.semantic_identity import (
    FlextInfraUtilitiesGitSemanticIdentityMixin,
)


class FlextInfraUtilitiesGitSemanticSubmoduleMixin(
    FlextInfraUtilitiesGitSemanticIdentityMixin,
):
    """Own ``.gitmodules`` composition and its derivations."""

    @classmethod
    def git_submodule_init(
        cls,
        request: m.Infra.GitRefRequest,
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Initialize one declared submodule at its recorded gitlink.

        Returns:
            The resulting ``p.Result[m.Infra.GitBoolReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            repo.git.submodule("update", "--init", "--", request.reference)
        except (GitCommandError, OSError, ValueError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"could not initialize the governed gitlink {request.reference}: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=True))

    @classmethod
    def recorded_member_sources(
        cls,
        superproject_root: Path,
    ) -> p.Result[t.VariadicTuple[m.Infra.DependencyCommitSourceSpec]]:
        """Return each governed member's committed gitlink as a commit source.

        The commit is the superproject ``HEAD`` tree entry (the recorded
        position), never the index or the member checkout. The distribution
        is the member's own PEP 621 name and the URL its ``.gitmodules`` URL.

        Returns:
            One commit source per governed Python member.

        """
        result = r[t.VariadicTuple[m.Infra.DependencyCommitSourceSpec]]
        members = cls._member_manifests(superproject_root)
        if members.failure:
            return result.from_failure(members)
        sources: list[m.Infra.DependencyCommitSourceSpec] = []
        for declaration, manifest in members.value:
            recorded = cls.git_rev_parse(
                m.Infra.GitCommitishRequest(
                    repo_root=superproject_root,
                    commitish=f"{c.Infra.GIT_HEAD}:{declaration.path.as_posix()}",
                ),
            )
            if recorded.failure:
                return result.from_failure(recorded)
            try:
                source = m.Infra.DependencyCommitSourceSpec(
                    distribution=manifest.name,
                    url=declaration.url,
                    commit=recorded.value.oid,
                )
            except ValueError as exc:
                return result.fail(
                    f"{declaration.path.as_posix()}: {exc}",
                    exception=exc,
                )
            sources.append(source)
        return result.ok(tuple(sources))

    @classmethod
    def flext_back_edges(
        cls,
        superproject_root: Path,
    ) -> p.Result[t.VariadicTuple[m.Infra.DependencyEdgeSpec]]:
        """Derive the dependency-group edges that close a member cycle.

        A back edge is a dependency-group requirement ``X -> Y`` between
        members where ``X`` is already in ``Y``'s runtime closure. Removing
        every back edge must leave an acyclic graph; a cycle the rule cannot
        break (a runtime cycle, or a group-only cycle) fails loudly.

        Returns:
            Every back edge, sorted by dependent then dependency.

        """
        result = r[t.VariadicTuple[m.Infra.DependencyEdgeSpec]]
        members = cls._member_manifests(superproject_root)
        if members.failure:
            return result.from_failure(members)
        declared_runtime: MutableMapping[str, frozenset[str]] = {}
        grouped: MutableMapping[str, frozenset[str]] = {}
        for declaration, manifest in members.value:
            name = canonicalize_name(manifest.name)
            if name in declared_runtime:
                return result.fail(
                    f"workspace member distribution is declared twice: {name} "
                    f"({declaration.path.as_posix()})",
                )
            runtime_names = cls._requirement_names(manifest.dependencies)
            if runtime_names.failure:
                return result.from_failure(runtime_names)
            group_names = cls._requirement_names(
                tuple(
                    requirement
                    for group in manifest.dependency_groups.values()
                    for requirement in group
                ),
            )
            if group_names.failure:
                return result.from_failure(group_names)
            declared_runtime[name] = runtime_names.value - {name}
            grouped[name] = group_names.value - {name} - runtime_names.value
        names = frozenset(declared_runtime)
        runtime = {name: edges & names for name, edges in declared_runtime.items()}
        back = tuple(
            (dependent, dependency)
            for dependent in sorted(grouped)
            for dependency in sorted(grouped[dependent] & names)
            if dependent in cls._runtime_closure(dependency, runtime)
        )
        remaining = {
            name: runtime[name]
            | {
                dependency
                for dependency in grouped[name] & names
                if (name, dependency) not in back
            }
            for name in names
        }
        cycle = cls._unordered_members(remaining)
        if cycle:
            return result.fail(
                "workspace dependency cycle is not broken by a back edge: "
                + ", ".join(cycle),
            )
        return result.ok(
            tuple(
                m.Infra.DependencyEdgeSpec(dependent=dependent, dependency=dependency)
                for dependent, dependency in back
            ),
        )

    @classmethod
    def _member_manifests(
        cls,
        superproject_root: Path,
    ) -> p.Result[
        t.VariadicTuple[
            t.Pair[m.Infra.GitSubmoduleDeclaration, m.Infra.DependencyManifestSpec]
        ]
    ]:
        """Read every governed, materialized member's own ``pyproject.toml``.

        An opted-out member is not composition. A governed member whose
        checkout is not materialized fails; one without a ``pyproject.toml``
        is content-only and declares no distribution.

        Returns:
            Each governed Python member with its declared dependency facts.

        """
        result = r[
            t.VariadicTuple[
                t.Pair[m.Infra.GitSubmoduleDeclaration, m.Infra.DependencyManifestSpec]
            ]
        ]
        declared = cls.git_submodule_declarations(superproject_root)
        if declared.failure:
            return result.from_failure(declared)
        members: list[
            t.Pair[m.Infra.GitSubmoduleDeclaration, m.Infra.DependencyManifestSpec]
        ] = []
        for declaration in declared.value:
            if declaration.managed is False:
                continue
            member_root = superproject_root / declaration.path
            if not (member_root / c.Infra.GIT_DIR).exists():
                return result.fail(
                    "workspace member checkout is not materialized: "
                    f"{declaration.path.as_posix()}",
                )
            pyproject = member_root / c.PYPROJECT_FILENAME
            if not pyproject.is_file():
                continue
            payload = u.Cli.toml_mapping_from_text(
                pyproject.read_text(encoding=c.Cli.ENCODING_DEFAULT),
            )
            if payload is None:
                return result.fail(f"{pyproject} is not valid TOML")
            try:
                manifest = m.Infra.DependencyManifestSpec.model_validate(payload)
            except ValueError as exc:
                return result.fail(f"{pyproject}: {exc}", exception=exc)
            members.append((declaration, manifest))
        return result.ok(tuple(members))

    @staticmethod
    def _requirement_names(
        requirements: t.StrSequence,
    ) -> p.Result[frozenset[str]]:
        """Return the canonical distribution names of PEP 508 requirements.

        Returns:
            The canonical names; an invalid requirement fails.

        """
        names: set[str] = set()
        for raw in requirements:
            try:
                names.add(canonicalize_name(Requirement(raw).name))
            except InvalidRequirement as exc:
                return r[frozenset[str]].fail(
                    f"invalid requirement {raw!r}: {exc}",
                    exception=exc,
                )
        return r[frozenset[str]].ok(frozenset(names))

    @staticmethod
    def _runtime_closure(
        start: str,
        runtime: t.MappingKV[str, frozenset[str]],
    ) -> frozenset[str]:
        """Return every member reachable from ``start`` over runtime edges.

        Returns:
            The runtime closure, excluding ``start`` unless it is on a cycle.

        """
        reached: set[str] = set()
        pending = list(runtime.get(start, frozenset()))
        while pending:
            name = pending.pop()
            if name in reached:
                continue
            reached.add(name)
            pending.extend(runtime.get(name, frozenset()))
        return frozenset(reached)

    @staticmethod
    def _unordered_members(
        graph: t.MappingKV[str, frozenset[str]],
    ) -> t.StrSequence:
        """Return the members a topological order cannot place (a cycle).

        Returns:
            The sorted members left on a cycle; empty for an acyclic graph.

        """
        pending = {name: set(edges) for name, edges in graph.items()}
        placed = True
        while placed:
            ready = {name for name, edges in pending.items() if not edges}
            placed = bool(ready)
            for name in ready:
                del pending[name]
            for edges in pending.values():
                edges.difference_update(ready)
        return tuple(sorted(pending))


__all__: list[str] = ["FlextInfraUtilitiesGitSemanticSubmoduleMixin"]
