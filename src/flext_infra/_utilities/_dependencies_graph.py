"""Dependency-graph ordering helpers for the dependency facade.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping

from packaging.utils import canonicalize_name

# Why: dependency_waves subscripts r[t.SequenceOf[t.StrSequence]] at runtime, so
# the typings facade cannot be TYPE_CHECKING-only here. c -> t is a forward
# facade import and stays cycle-free.
from flext_core import r
from flext_infra import p, t


class FlextInfraUtilitiesDependenciesGraphMixin:
    """Dependency-first ordering and wave partitioning of named graphs."""

    @staticmethod
    def dependency_order(
        direct_names: t.StrSequence,
        *,
        dependencies: Callable[[str], t.StrSequence],
        prefix: str = "",
        normalize: Callable[[str], str] = canonicalize_name,
    ) -> t.StrSequence:
        """Return a dependency-first order for any named dependency graph.

        Returns:
            A dependency-first order for any named dependency graph.

        """
        graph: MutableMapping[str, t.VariadicTuple[str]] = {}

        def collect(dependency_name: str) -> None:
            normalized = normalize(dependency_name)
            if normalized in graph:
                return
            children = tuple(
                child
                for raw_child in dependencies(normalized)
                if (child := normalize(raw_child))
                and (not prefix or child.startswith(prefix))
            )
            graph[normalized] = children
            for dependency in children:
                collect(dependency)

        roots = tuple(
            normalized
            for name in direct_names
            if (normalized := normalize(name))
            and (not prefix or normalized.startswith(prefix))
        )
        for root in roots:
            collect(root)
        ordered: list[str] = []
        visited: set[str] = set()
        active: list[str] = []

        def visit(distribution_name: str) -> None:
            if distribution_name in visited:
                return
            if distribution_name in active:
                cycle_start = active.index(distribution_name)
                cycle = " -> ".join((*active[cycle_start:], distribution_name))
                msg = f"cyclic dependency graph: {cycle}"
                raise ValueError(msg)
            active.append(distribution_name)
            for dependency in graph[distribution_name]:
                visit(dependency)
            active.pop()
            visited.add(distribution_name)
            ordered.append(distribution_name)

        for root in roots:
            visit(root)
        return tuple(ordered)

    @staticmethod
    def dependency_waves(
        edges: Mapping[str, t.StrSequence],
    ) -> p.Result[t.SequenceOf[t.StrSequence]]:
        """Split a closed named dependency graph into dependency-first waves.

        Wave ``n`` contains only names whose dependencies all live in earlier
        waves, so each wave may proceed in parallel while the sequence between
        waves stays strict. The graph is closed: every referenced name must be
        a key of ``edges``; an unknown reference or a cycle fails the result
        instead of raising, so callers (release publish ordering, codemod
        provider ordering) compose it through ``p.Result`` chaining.

        Returns:
            The resulting ``p.Result[t.SequenceOf[t.StrSequence]]``.

        """
        unknown = sorted({
            dependency
            for deps in edges.values()
            for dependency in deps
            if dependency not in edges
        })
        if unknown:
            return r[t.SequenceOf[t.StrSequence]].fail(
                "dependency graph references names outside the graph: "
                + ", ".join(unknown),
            )
        pending = {name: set(deps) for name, deps in edges.items()}
        waves: list[t.StrSequence] = []
        while pending:
            ready = frozenset(name for name, deps in pending.items() if not deps)
            if not ready:
                return r[t.SequenceOf[t.StrSequence]].fail(
                    "cyclic dependency graph: " + ", ".join(sorted(pending)),
                )
            waves.append(tuple(sorted(ready)))
            pending = {
                name: deps - ready
                for name, deps in pending.items()
                if name not in ready
            }
        return r[t.SequenceOf[t.StrSequence]].ok(tuple(waves))


__all__: list[str] = ["FlextInfraUtilitiesDependenciesGraphMixin"]
