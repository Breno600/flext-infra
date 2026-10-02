"""Census duplicate grouping and object/analysis filters.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import MutableMapping
from typing import TYPE_CHECKING, ClassVar

from flext_infra import m

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraRefactorCensusFiltersMixin:
    """Duplicate detection and inclusion filters.

    Composed into FlextInfraRefactorCensus via inheritance; self-contained
    static helpers over report Object/convention models (no census state).
    """

    _MIN_DUPLICATE_DEFINITIONS: ClassVar[int] = 2

    @staticmethod
    def _duplicate_groups(
        project_objects: t.VariadicTuple[t.SequenceOf[m.Infra.Object]],
    ) -> t.VariadicTuple[m.Infra.DuplicateGroup]:
        """Duplicate groups.

        Returns:
            The resulting ``t.VariadicTuple[m.Infra.DuplicateGroup]``.

        """

        def object_location(item: m.Infra.Object) -> t.Triple[str, str, int]:
            return item.project, item.file_path, item.line

        groups: MutableMapping[t.Triple[str, str, str], list[m.Infra.Object]] = (
            defaultdict(list)
        )
        for item in (obj for objects in project_objects for obj in objects):
            owner = item.scope_path.rpartition(".")[0]
            groups[item.kind, item.name, owner].append(item)
        duplicates: list[m.Infra.DuplicateGroup] = []
        for key in sorted(groups):
            definitions = groups[key]
            if (
                len(definitions)
                < FlextInfraRefactorCensusFiltersMixin._MIN_DUPLICATE_DEFINITIONS
            ):
                continue
            canonical = min(definitions, key=object_location)
            duplicates.append(
                m.Infra.DuplicateGroup(
                    name=definitions[0].name,
                    kind=definitions[0].kind,
                    definitions=tuple(definitions),
                    canonical=canonical.project,
                    value_identical=len({item.fingerprint for item in definitions})
                    == 1,
                ),
            )
        return tuple(duplicates)

    @staticmethod
    def _include_object(
        item: m.Infra.Object,
        *,
        selected_families: frozenset[str],
        selected_kinds: frozenset[str] | None,
    ) -> bool:
        """Return whether one inventory object passes the kind and family filters.

        Returns:
            Whether one inventory object passes the kind and family filters.

        """
        if selected_kinds and item.kind not in selected_kinds:
            return False
        if not selected_families:
            return True
        return (
            item.actual_tier.lower() in selected_families
            or item.expected_tier.lower() in selected_families
        )

    @staticmethod
    def _include_rule(
        rule: str,
        *,
        rule_names: t.StrSequence | None,
        selected_rules: frozenset[str] | None = None,
    ) -> bool:
        """Include rule.

        ``selected_rules`` is a precomputed frozenset of ``rule_names``;
        callers in hot loops MUST pass it to avoid per-call set construction.

        Returns:
            The resulting ``bool``.

        """
        if selected_rules is None:
            return rule_names is None or rule in frozenset(rule_names)
        return rule in selected_rules


__all__: list[str] = ["FlextInfraRefactorCensusFiltersMixin"]
