"""Parsing and normalization of dependency requirement spellings.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from flext_infra import p, t


class FlextInfraUtilitiesDependencyRequirements:
    """Parse, normalize, and deduplicate dependency requirement spellings."""

    @staticmethod
    def raw_requirement_values(raw: p.AttributeProbe) -> list[str]:
        """Collect requirement strings from dependency arrays or group tables.

        Returns:
            Requirement strings retained from the declared arrays.
        """
        if isinstance(raw, Mapping):
            values: list[str] = []
            for group in raw.values():
                values.extend(
                    FlextInfraUtilitiesDependencyRequirements.raw_requirement_values(
                        group,
                    ),
                )
            return values
        if isinstance(raw, (list, tuple)):
            return [item for item in raw if isinstance(item, str)]
        return []

    @staticmethod
    def active_requirement(
        requirement: str,
        *,
        environment: t.StrMapping,
    ) -> str | None:
        """Evaluate a strictly parsed requirement on the consumer interpreter.

        Returns:
            The resulting ``str | None``.

        """
        parsed = Requirement(requirement)
        return (
            str(parsed)
            if parsed.marker is None
            or parsed.marker.evaluate(environment=dict(environment))
            else None
        )

    @staticmethod
    def dependency_extras(requirements: t.StrSequence, name: str) -> str:
        """Retain the union of requested extras for one selected distribution.

        Returns:
            The resulting ``str``.

        """
        extras: set[str] = set()
        for requirement in requirements:
            parsed = Requirement(requirement)
            if canonicalize_name(parsed.name) == name:
                extras.update(parsed.extras)
        return f"[{','.join(sorted(extras))}]" if extras else ""

    @staticmethod
    def dependency_constraint(requirement: str, *, replace_source: bool) -> str:
        """Keep version bounds while installation inputs own extras and sources.

        Returns:
            The resulting ``str``.

        """
        parsed = Requirement(requirement)
        source = (
            f" @ {parsed.url}"
            if parsed.url and not replace_source
            else str(parsed.specifier)
        )
        marker = f"; {parsed.marker}" if parsed.marker is not None else ""
        return f"{parsed.name}{source}{marker}"

    @staticmethod
    def dep_name(requirement: str, *, active_only: bool = False) -> str | None:
        """Extract one normalized dependency name, optionally evaluating markers.

        Returns:
            The resulting ``str | None``.

        """
        text = requirement.strip()
        if not text:
            return None
        try:
            parsed = Requirement(text)
        except InvalidRequirement:
            parsed = None
        if parsed is not None:
            if (
                active_only
                and parsed.marker is not None
                and not parsed.marker.evaluate()
            ):
                return None
            return canonicalize_name(parsed.name)
        if ";" in text:
            text = text.split(";", maxsplit=1)[0].strip()
        if " @ " in text:
            text = text.split(" @ ", maxsplit=1)[0].strip()
        for separator in ("[", "==", ">=", "<=", "~=", "!=", ">", "<"):
            if separator in text:
                text = text.split(separator, maxsplit=1)[0].strip()
        if "/" in text:
            text = text.rsplit("/", maxsplit=1)[-1].strip()
        normalized = text.lower()
        return normalized or None

    @staticmethod
    def dedupe_specs(specs: t.StrSequence) -> t.StrSequence:
        """Return deterministic unique dependency specs keyed by normalized name.

        Returns:
            Deterministic unique dependency specs keyed by normalized name.

        """
        selected_by_name: MutableMapping[str, str] = {}
        for raw in specs:
            item = raw.strip()
            if not item:
                continue
            dependency_name = FlextInfraUtilitiesDependencyRequirements.dep_name(item)
            if dependency_name is None or dependency_name in selected_by_name:
                continue
            selected_by_name[dependency_name] = item
        return tuple(selected_by_name[name] for name in sorted(selected_by_name))


__all__: list[str] = ["FlextInfraUtilitiesDependencyRequirements"]
