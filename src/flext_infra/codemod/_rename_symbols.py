"""CSV symbol plans delegated to Rope's identity-aware restructuring owner.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from difflib import SequenceMatcher
from pathlib import Path

from flext_infra import m, p, t, u


class FlextInfraRenameSymbols:
    """Translate declared CSV prefixes into current-owner Rope constraints."""

    @staticmethod
    def _member_paths(source: str, path: Path) -> frozenset[tuple[str, ...]]:
        """Index AST attribute paths that can match a declared Rope pattern.

        Returns:
            The resulting ``frozenset[tuple[str, ...]]``.

        """
        paths: set[tuple[str, ...]] = set()
        for node in ast.walk(ast.parse(source, filename=str(path))):
            if not isinstance(node, ast.Attribute):
                continue
            parts: list[str] = []
            cursor: ast.expr = node
            while isinstance(cursor, ast.Attribute):
                parts.append(cursor.attr)
                paths.add(tuple(reversed(parts)))
                cursor = cursor.value
        return frozenset(paths)

    @staticmethod
    def resolve_member(
        project: p.Infra.RopeProject,
        owner: str,
        suffix: str,
    ) -> p.Infra.RopePyName | None:
        """Resolve the current destination without importing a retired object.

        Returns:
            The resulting ``p.Infra.RopePyName | None``.

        """
        module, *attributes = owner.split(".")
        value: p.Infra.RopePyModule | p.Infra.RopePyObject = project.get_module(module)
        binding: p.Infra.RopePyName | None = None
        for attribute in (*attributes, *suffix.split(".")):
            if attribute not in value.get_attributes():
                return None
            binding = value.get_attribute(attribute)
            value = binding.get_object()
        return binding

    @classmethod
    def _eligible_spans(
        cls,
        project: p.Infra.RopeProject,
        change: p.Infra.RopeChangeContents,
        source: str,
        symbols: t.Triple[str, str, str],
        rewrites: t.SequenceOf[m.Infra.SourceRewrite],
    ) -> t.VariadicTuple[t.Triple[int, int, bool]]:
        """Retain effective-member identity after Rope's receiver/MRO match.

        Returns:
            The resulting ``t.VariadicTuple[t.Triple[int, int, bool]]``.

        Raises:
            TypeError: If CSV symbol campaign does not own attribute mutation.
            ValueError: If CSV destination disappeared during planning; or if CSV symbol
                has no authenticated expression span; or if CSV target overrides the
                declared destination; or if retired member has an independently owned
                namespace.

        """
        runtime = u.Infra
        module = project.get_pymodule(change.resource)
        owner, old, new = symbols
        expected = cls.resolve_member(project, owner, old)
        destination = cls.resolve_member(project, owner, new)
        if destination is None:
            msg = f"CSV destination disappeared during planning: {owner}.{new}"
            raise ValueError(msg)
        spans: t.MutableSequenceOf[t.Triple[int, int, bool]] = []
        old_parts = old.split(".")
        for node in ast.walk(ast.parse(source)):
            receiver = node
            for part in reversed(old_parts):
                if not isinstance(receiver, ast.Attribute) or receiver.attr != part:
                    break
                receiver = receiver.value
            else:
                text = ast.get_source_segment(source, node)
                receiver_text = ast.get_source_segment(source, receiver)
                if text is None or receiver_text is None:
                    msg = "CSV symbol has no authenticated expression span"
                    raise ValueError(msg)
                start = runtime.source_offset(source, node)
                if not any(
                    start <= edit.start and edit.end <= start + len(text)
                    for edit in rewrites
                ):
                    continue
                scope = runtime.scope_at(module, start)
                actual = runtime.resolve_symbol(scope, node)
                if actual is not None and (
                    expected is None or not runtime.same_name(expected, actual)
                ):
                    spans.append((start, start + len(text), False))
                    continue
                if isinstance(node, ast.Attribute) and not isinstance(
                    node.ctx,
                    ast.Load,
                ):
                    msg = "CSV symbol campaign does not own attribute mutation"
                    raise TypeError(msg)
                for depth in range(1, len(old_parts)):
                    prefix = ".".join(old_parts[:depth])
                    declared_prefix = cls.resolve_member(project, owner, prefix)
                    actual_prefix = runtime.resolve_symbol(
                        scope,
                        ast.parse(f"{receiver_text}.{prefix}", mode="eval").body,
                    )
                    if actual_prefix is not None and (
                        declared_prefix is None
                        or not runtime.same_name(declared_prefix, actual_prefix)
                    ):
                        msg = f"retired member owns an independent namespace: {text}"
                        raise ValueError(msg)
                target = runtime.resolve_symbol(
                    scope,
                    ast.parse(f"{receiver_text}.{new}", mode="eval").body,
                )
                if not runtime.same_name(destination, target):
                    msg = f"CSV target overrides the declared destination: {text}"
                    raise ValueError(msg)
                spans.append((start, start + len(text), True))
        return tuple(spans)

    @classmethod
    def plan(
        cls,
        project: p.Infra.RopeProject,
        sources: t.MappingKV[Path, str],
        pairs: t.SequenceOf[t.Pair[str, str]],
        bindings: t.MappingKV[str, t.StrSequence],
    ) -> t.MappingKV[Path, t.VariadicTuple[m.Infra.SourceRewrite]]:
        """Merge non-overlapping Rope previews against one immutable snapshot.

        Returns:
            The resulting ``t.MappingKV[Path, t.VariadicTuple[m.Infra.SourceRewrite]]``.

        Raises:
            TypeError: If CSV Rope campaign produced a non-content effect.
            ValueError: If Rope input changed after authentication; or if CSV
                destination has no declared current public owner; or if symbol campaign
                requires identifier paths; or if CSV Rope campaign escaped authenticated
                inventory; or if Rope CSV edit has no single authenticated member span.

        """
        root = Path(project.root.real_path)
        ordered_paths = tuple(sorted(sources))
        members = {
            path: cls._member_paths(source, path) for path, source in sources.items()
        }
        resources = {
            path: project.get_resource(path.relative_to(root).as_posix())
            for path in ordered_paths
        }
        for path, resource in resources.items():
            if resource.read() != sources[path]:
                msg = f"Rope input changed after authentication: {path}"
                raise ValueError(msg)
        planned: t.MutableMappingKV[
            Path,
            t.MutableSequenceOf[m.Infra.SourceRewrite],
        ] = {}
        for old, new in pairs:
            accepted = False
            for prefix, owners in bindings.items():
                qualifier = prefix + "." if prefix else ""
                if not old.startswith(qualifier) or not new.startswith(qualifier):
                    continue
                old_suffix, new_suffix = (
                    old.removeprefix(qualifier),
                    new.removeprefix(qualifier),
                )
                if not all(
                    part.isidentifier()
                    for part in (*old_suffix.split("."), *new_suffix.split("."))
                ):
                    msg = f"symbol campaign requires identifier paths: {old}, {new}"
                    raise ValueError(msg)
                member_path = tuple(old_suffix.split("."))
                elected = tuple(
                    resources[path]
                    for path in ordered_paths
                    if member_path in members[path]
                )
                for owner in owners:
                    if cls.resolve_member(project, owner, new_suffix) is None:
                        continue
                    accepted = True
                    if not elected:
                        continue
                    changes = u.Infra.restructure_changes(
                        project,
                        f"${{owner}}.{old_suffix}",
                        f"${{owner}}.{new_suffix}",
                        arguments={"owner": "instance=" + owner},
                        resources=elected,
                    )
                    for change in changes.changes:
                        if not isinstance(change, p.Infra.RopeChangeContents):
                            msg = "CSV Rope campaign produced a non-content effect"
                            raise TypeError(msg)
                        path = Path(change.resource.real_path)
                        if path not in sources:
                            msg = f"CSV Rope campaign escaped known inventory: {path}"
                            raise ValueError(msg)
                        original = sources[path]
                        matcher = SequenceMatcher(
                            a=original,
                            b=change.new_contents,
                            autojunk=False,
                        ).get_opcodes()
                        rewrites = tuple(
                            m.Infra.SourceRewrite(
                                start=start,
                                end=end,
                                text=change.new_contents[updated_start:updated_end],
                            )
                            for kind, start, end, updated_start, updated_end in matcher
                            if kind != "equal"
                        )
                        spans = cls._eligible_spans(
                            project,
                            change,
                            original,
                            (owner, old_suffix, new_suffix),
                            rewrites,
                        )
                        for edit in rewrites:
                            containing = tuple(
                                allowed
                                for begin, finish, allowed in spans
                                if begin <= edit.start and edit.end <= finish
                            )
                            if not containing:
                                msg = (
                                    f"Rope CSV edit has no single authenticated "
                                    f"member span: {path}"
                                )
                                raise ValueError(msg)
                            if not all(containing):
                                continue
                            edits = planned.setdefault(path, [])
                            if edit not in edits:
                                edits.append(edit)
            if bindings and not accepted:
                msg = f"CSV destination has no declared current public owner: {new}"
                raise ValueError(msg)
        return {path: tuple(edits) for path, edits in planned.items()}


__all__: list[str] = ["FlextInfraRenameSymbols"]
