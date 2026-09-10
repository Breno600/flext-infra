"""Declarative Rope rule models for family part shape (ADR-014)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from flext_meltano import m, u


class FlextInfraModelsRopeRules:
    """Typed declarative Rope rule payloads; the engine holds no rule-specific code."""

    class RopeSelect(m.ImmutableValueModel):
        """Data-driven selection predicate evaluated by the generic engine."""

        level: Annotated[
            Literal["top_level", "direct_child_of_part"] | None,
            u.Field(default=None, description="Where the candidate class must sit"),
        ]
        name_not_prefix_of_stem: Annotated[
            bool,
            u.Field(
                default=False,
                description="Require the name not to start with the project stem",
            ),
        ]
        bases_max: Annotated[
            int | None,
            u.Field(default=None, description="Maximum explicit bases allowed"),
        ]
        body_functions: Annotated[
            bool | None,
            u.Field(default=None, description="Whether the body may define functions"),
        ]
        body_classes_or_assigns: Annotated[
            bool | None,
            u.Field(default=None, description="Whether the body declares classes/assigns"),
        ]

    class RopeOp(m.ImmutableValueModel):
        """One generic structural operation; semantics live only in the engine."""

        kind: Annotated[
            Literal["move", "lift", "rename"],
            u.Field(description="Fixed engine primitive to apply"),
        ]
        target: Annotated[
            Literal["enclosing_part_class"] | None,
            u.Field(default=None, description="Move destination selector"),
        ]
        drop_hops: Annotated[
            int,
            u.Field(default=0, description="Attribute chain segments dropped by lift"),
        ]
        delete_source: Annotated[
            bool,
            u.Field(default=False, description="Lift deletes the source class"),
        ]
        strip_underscore: Annotated[
            bool,
            u.Field(default=False, description="Rename strips the leading underscore"),
        ]
        case: Annotated[
            Literal["pascal"] | None,
            u.Field(default=None, description="Rename case policy"),
        ]

    class RopeRule(m.ImmutableValueModel):
        """One declarative Rope rule parsed from ``codemod/rope_rules/**.yml``."""

        group: Annotated[str, u.Field(description="Rule group name for reference")]
        number: Annotated[int, u.Field(description="Reference number within the group")]
        name: Annotated[str, u.Field(description="Stable rule slug")]
        severity: Annotated[str, u.Field(description="Rule severity level")]
        message: Annotated[
            str,
            u.Field(
                description=(
                    "Violation template with {module}, {class}, and {line} placeholders"
                )
            ),
        ]
        files: Annotated[
            tuple[str, ...], u.Field(description="Package-relative glob selectors")
        ]
        select: Annotated[
            "FlextInfraModelsRopeRules.RopeSelect",
            u.Field(description="Selection predicate"),
        ]
        ops: Annotated[
            tuple["FlextInfraModelsRopeRules.RopeOp", ...],
            u.Field(description="Ordered generic operations"),
        ]
        auto_fix: Annotated[
            bool, u.Field(default=True, description="Apply the ops automatically")
        ]
        propagate_mro: Annotated[
            bool,
            u.Field(
                default=True,
                description="Rewire references reached through any MRO facade alias",
            ),
        ]
        propagate_workspace: Annotated[
            bool,
            u.Field(
                default=True,
                description="Rewire across the whole workspace, not only the package",
            ),
        ]

    class FamilyShapeFinding(m.ImmutableValueModel):
        """One detected family part shape violation with its rendered message."""

        file_path: Annotated[Path, u.Field(description="Repository-relative file")]
        line: Annotated[int, u.Field(description="One-based violation line")]
        class_name: Annotated[str, u.Field(description="Violating class name")]
        module: Annotated[str, u.Field(description="Dotted module of the violation")]
        rule_id: Annotated[str, u.Field(description="Full rule id group.name.number")]
        reference: Annotated[str, u.Field(description="Short group-number reference")]
        rendered: Annotated[str, u.Field(description="Message resolved with context")]
        ops: Annotated[
            tuple["FlextInfraModelsRopeRules.RopeOp", ...],
            u.Field(description="Ops the engine will apply"),
        ]


__all__: list[str] = ["FlextInfraModelsRopeRules"]
