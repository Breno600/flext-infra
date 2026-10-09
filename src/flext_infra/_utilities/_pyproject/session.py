"""Consumer requirement preservation for an explicit local binding.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_cli import r, u

from flext_infra import c, m, p, t
from flext_infra._utilities import FlextInfraUtilitiesDependencies


class FlextInfraUtilitiesPyprojectSession:
    """Preserve active extras, version bounds, and unselected source overrides."""

    @staticmethod
    def session_dependency_requirements(
        document: t.Cli.TomlDocument,
        *,
        requirements: t.StrSequence,
        selected: t.StrSequence,
        environment: t.StrMapping,
    ) -> p.Result[m.Infra.BindingResolution]:
        """Resolve only consumer declarations; never restore retired topology.

        Returns:
            The resulting ``p.Result[m.Infra.BindingResolution]``.

        """
        tool = u.Cli.toml_table_child(document, c.Infra.TOOL)
        if (
            tool is not None
            and u.Cli.toml_table_child(tool, c.Infra.POETRY) is not None
        ):
            return r[m.Infra.BindingResolution].fail(
                "session binding requires PEP 621/735 dependency declarations",
            )
        uv = u.Cli.toml_table_child(tool, c.Infra.UV) if tool is not None else None
        if uv is not None and u.Cli.toml_table_child(uv, "sources") is not None:
            return r[m.Infra.BindingResolution].fail(
                "session binding requires dependency URLs, not tool.uv.sources",
            )
        active = tuple(
            parsed
            for item in requirements
            if (
                parsed := FlextInfraUtilitiesDependencies.active_requirement(
                    item,
                    environment=environment,
                )
            )
            is not None
        )
        explicit = (
            u.Cli.toml_as_string_list(uv.get("override-dependencies"))
            if uv is not None
            else ()
        )
        active_overrides = tuple(
            parsed
            for item in explicit
            if (
                parsed := FlextInfraUtilitiesDependencies.active_requirement(
                    item,
                    environment=environment,
                )
            )
            is not None
        )
        overrides = tuple(
            item
            for item in active_overrides
            if FlextInfraUtilitiesDependencies.dep_name(item) not in selected
        )
        override_names = frozenset(
            FlextInfraUtilitiesDependencies.dep_name(item) for item in active_overrides
        )
        declared_constraints = (
            u.Cli.toml_as_string_list(uv.get("constraint-dependencies"))
            if uv is not None
            else ()
        )
        constraints = tuple(
            dict.fromkeys(
                FlextInfraUtilitiesDependencies.dependency_constraint(
                    parsed,
                    replace_source=FlextInfraUtilitiesDependencies.dep_name(
                        parsed,
                    )
                    in selected,
                )
                for item in (
                    *(
                        item
                        for item in active
                        if FlextInfraUtilitiesDependencies.dep_name(item)
                        not in override_names
                    ),
                    *(
                        item
                        for item in active_overrides
                        if FlextInfraUtilitiesDependencies.dep_name(item) in selected
                    ),
                    *declared_constraints,
                )
                if (
                    parsed := FlextInfraUtilitiesDependencies.active_requirement(
                        item,
                        environment=environment,
                    )
                )
                is not None
            ),
        )
        return r[m.Infra.BindingResolution].ok(
            m.Infra.BindingResolution(overrides=overrides, constraints=constraints),
        )


__all__: list[str] = ["FlextInfraUtilitiesPyprojectSession"]
