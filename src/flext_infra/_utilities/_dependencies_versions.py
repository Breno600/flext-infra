"""Resolved-version floor and requirement-rewrite helpers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping

from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version

from flext_infra import c, t


class FlextInfraUtilitiesDependenciesVersionsMixin:
    """Resolved runtime versions and PEP 621 requirement constraint rewrites."""

    @classmethod
    def resolved_dependency_versions(cls) -> t.MappingKV[str, str]:
        """Read registry versions from the provisioned runtime, not release provenance.

        Returns:
            The resulting ``t.MappingKV[str, str]``.

        Raises:
            TypeError: If Installed distribution has no Name metadata.
            ValueError: If No registry packages found in the provisioned runtime; or if
                Invalid installed distribution name; or if Ambiguous installed version.

        """
        from flext_cli import u

        from flext_infra._utilities import FlextInfraUtilitiesDependencies

        versions: MutableMapping[str, str] = {}
        for distribution in u.installed_distributions():
            if distribution.read_text("direct_url.json") is not None:
                continue
            name = distribution.metadata.get("Name")
            if name is None:
                msg = "Installed distribution has no Name metadata"
                raise TypeError(msg)
            normalized = FlextInfraUtilitiesDependencies.dep_name(name)
            if normalized is None:
                msg = f"Invalid installed distribution name: {name}"
                raise ValueError(msg)
            version = distribution.version
            if normalized in versions and versions[normalized] != version:
                msg = f"Ambiguous installed version: {normalized}"
                raise ValueError(msg)
            versions[normalized] = version
        if not versions:
            msg = "No registry packages found in the provisioned runtime"
            raise ValueError(msg)
        return versions

    @staticmethod
    def _parsed_requirement(requirement_text: str) -> Requirement | None:
        """Parse one PEP 508 requirement string, or None when invalid.

        Returns:
            The resulting ``Requirement | None``.
        """
        try:
            return Requirement(requirement_text.strip())
        except InvalidRequirement:
            return None

    @classmethod
    def rewrite_requirement_constraint(
        cls,
        requirement: str,
        *,
        resolved_versions: t.MappingKV[str, str],
        internal_names: t.StrSequence = (),
    ) -> str | None:
        """Rewrite one PEP 621 requirement to the resolved runtime floor.

        Returns:
            The resulting ``str | None``.

        """
        guard = cls._rewritable_requirement(requirement, internal_names)
        if guard is None:
            return None
        dependency_name, requirement_part = guard
        raw_text = requirement.strip()
        requirement_part, marker_separator, marker_part = raw_text.partition(
            ";",
        )
        head = cls._requirement_head(requirement_part)
        locked_version = resolved_versions.get(dependency_name)
        if locked_version is None:
            return None
        parsed = cls._parsed_requirement(requirement_part)
        if parsed is not None and not parsed.specifier.contains(
            locked_version,
            prereleases=True,
        ):
            return None
        retained = (
            ()
            if parsed is None
            else tuple(
                str(specifier)
                for specifier in parsed.specifier
                if specifier.operator in {"<", "<=", "!="}
            )
        )
        constraint = cls._constraint_specifier(locked_version)
        if not constraint:
            return None
        if retained:
            constraint = ",".join((constraint, *retained))
        rewritten = f"{head}{constraint}"
        marker_text = marker_part.strip()
        if marker_separator and marker_text:
            rewritten = f"{rewritten}; {marker_text}"
        return rewritten if rewritten != raw_text else None

    @classmethod
    def _rewritable_requirement(
        cls,
        requirement: str,
        internal_names: t.StrSequence,
    ) -> t.Pair[str, str] | None:
        """Return the dependency name and part of one rewritable requirement.

        Returns:
            The dependency name and requirement part, or None when the
            requirement carries a direct URL, an unparsable head, or an
            internal dependency name.

        """
        from flext_infra._utilities import FlextInfraUtilitiesDependencies

        raw_text = requirement.strip()
        if not raw_text or " @ " in raw_text:
            return None
        requirement_part = raw_text.partition(";")[0]
        if " @ " in requirement_part:
            return None
        head = cls._requirement_head(requirement_part)
        dependency_name = FlextInfraUtilitiesDependencies.dep_name(head)
        if dependency_name is None or dependency_name in set(internal_names):
            return None
        return dependency_name, requirement_part

    @staticmethod
    def _requirement_head(requirement_part: str) -> str:
        """Return the canonical head of one requirement part.

        Returns:
            The resulting ``str``.

        """
        head_match = c.Infra.PEP621_REQUIREMENT_HEAD_RE.match(
            requirement_part.strip(),
        )
        return head_match.group("head").strip() if head_match is not None else ""

    @staticmethod
    def _constraint_specifier(version: str) -> str:
        """Return the resolved installed version as an open-ended dependency floor.

        PEP 440 permits a local version label only with ``==`` or ``!=``, so a
        floor built straight from a locally tagged resolution is rejected by
        every build backend. The public release is what a floor means, and the
        local build satisfies it.

        A prerelease resolution is not a floor either: publishing ``>=X.Yb1``
        forces every downstream consumer onto that beta, which is how the fleet
        ended up pinned to ``pydantic>=2.14.0b1`` from a single runtime resolution. The
        empty string means "this resolution cannot serve as a public floor", and
        every caller keeps the declared constraint instead of rewriting it.

        Returns:
            The resolved installed version as an open-ended dependency floor.

        """
        public_version = version.strip().partition("+")[0]
        if not public_version:
            return ""
        try:
            parsed_version = Version(public_version)
        except InvalidVersion:
            return ""
        if parsed_version.is_prerelease:
            return ""
        return f">={public_version}"


__all__: list[str] = ["FlextInfraUtilitiesDependenciesVersionsMixin"]
