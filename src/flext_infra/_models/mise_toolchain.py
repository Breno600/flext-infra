"""Mise toolchain and beads configuration models.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from typing import Annotated, Literal, Self

from flext_core import m, t


class FlextInfraModelsMiseToolchain:
    """Mise toolchain and beads configuration models."""

    class _ConfigContract(m.ContractModel):
        """Private declarative base for schema-loaded codegen records."""

        model_config = m.ConfigDict(
            strict=False,
            frozen=True,
            extra="forbid",
            str_strip_whitespace=False,
        )

    class BeadsToolSpec(_ConfigContract):
        """Beads ledger and Gas City projection contract."""

        endpoint_origin: Annotated[
            Literal["inherited_city"],
            m.Field(description="Gas City-owned endpoint inheritance mode"),
        ]
        endpoint_status: Annotated[
            Literal["verified"],
            m.Field(description="Canonical status for a managed-city inherited rig"),
        ]
        required_custom_types: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description="Immutable custom bead types required by Gas City",
            ),
        ]
        dolt_mode: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Rendered as dolt_mode in .beads/metadata.json and, for a "
                    "Gas City rig, as dolt.mode in .beads/config.yaml. Change "
                    "toolchain.beads.dolt_mode; never the projection."
                ),
            ),
        ]
        export_auto: Annotated[
            bool,
            m.Field(
                description=(
                    "Rendered as export.auto. Override toolchain.beads.export_auto."
                ),
            ),
        ]
        backup_enabled: Annotated[
            bool,
            m.Field(
                description=(
                    "Rendered as backup.enabled. Override "
                    "toolchain.beads.backup_enabled."
                ),
            ),
        ]
        dolt_disable_event_flush: Annotated[
            bool,
            m.Field(
                description=(
                    "Rendered for a Gas City rig as the nested "
                    "dolt: disable-event-flush switch gc reads. Override "
                    "toolchain.beads.dolt_disable_event_flush."
                ),
            ),
        ]

        @m.model_validator(mode="after")
        def _validate_required_custom_types(self) -> Self:
            """Reject ambiguous duplicate type declarations at the owner.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If beads required_custom_types must be unique.

            """
            if len(set(self.required_custom_types)) != len(self.required_custom_types):
                msg = "beads required_custom_types must be unique"
                raise ValueError(msg)
            return self

    class MiseToolVersionProbe(_ConfigContract):
        """Declared command whose output proves the provisioned tool version.

        The setup reality proof resolves ``binary`` through ``mise which``,
        runs it with ``arguments``, and searches the output for ``pattern``
        with its single ``{version}`` placeholder replaced by the escaped
        mise.lock version. The probe is data; no tool has a default probe.
        """

        binary: Annotated[
            t.NonEmptyStr,
            m.Field(description="Executable name resolved through `mise which`"),
        ]
        arguments: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Arguments that make the binary print its version"),
        ]
        pattern: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Multiline regular expression the probe output must match; "
                    "exactly one `{version}` placeholder stands for the escaped "
                    "mise.lock version"
                ),
            ),
        ]

        @m.model_validator(mode="after")
        def _validate_pattern(self) -> Self:
            """Require one version placeholder and a compilable expression.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If the pattern carries no single placeholder.

            """
            placeholder = "{version}"
            if self.pattern.count(placeholder) != 1:
                msg = (
                    "version_probe.pattern must carry exactly one "
                    f"{placeholder} placeholder: {self.pattern}"
                )
                raise ValueError(msg)
            # A malformed expression raises re.PatternError unchanged here.
            re.compile(self.pattern.replace(placeholder, "0"))
            return self

    class MiseToolEntry(_ConfigContract):
        """One declarative fleet tool rendered into generated ``.mise.toml``.

        The entry table is the single toolchain surface: per-tool YAML keys,
        model fields, and template lines do not exist (ADR-005 s1 data-backed
        structures, ADR-018 p.10 deriving beats listing).
        """

        name: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Tool identity; the [tools] key when no selector is declared"
                ),
            ),
        ]
        selector: Annotated[
            t.NonEmptyStr | None,
            m.Field(
                default=None,
                description=(
                    "Full Mise selector (aqua:, github:) rendered as the "
                    "[tools] key; the fleet toolchain has no npm: backend"
                ),
            ),
        ] = None
        version: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Release selector: 'latest', a major.minor line, or an "
                    "exact released version; never a lock build identity"
                ),
            ),
        ]
        version_prefix: Annotated[
            t.NonEmptyStr | None,
            m.Field(
                default=None,
                description=(
                    "Release tag prefix keeping unrelated tags out of resolution"
                ),
            ),
        ] = None
        form: Annotated[
            Literal["scalar", "table"],
            m.Field(
                default="scalar",
                description=(
                    "Rendered [tools] shape; the projection byte contract. "
                    "scalar (default) is the bare assignment, table carries "
                    "version_prefix"
                ),
            ),
        ] = "scalar"
        lock_checksum: Annotated[
            bool,
            m.Field(
                default=True,
                description=(
                    "Whether the tool's current-platform mise.lock section "
                    "must carry a checksum; false only for a tool whose "
                    "upstream release metadata publishes none"
                ),
            ),
        ] = True
        version_probe: Annotated[
            FlextInfraModelsMiseToolchain.MiseToolVersionProbe,
            m.Field(
                description=(
                    "Command whose output proves the provisioned version in "
                    "the setup reality proof; every tool declares one"
                ),
            ),
        ]

    class ToolchainSpec(_ConfigContract):
        """Language-runtime and native-tool versions shared by generated projects.

        Native tools use moving ``latest`` selectors; Python retains its
        required major.minor runtime line. Only ``make upg`` resolves the
        selectors and writes mise.lock; setup installs frozen from that lock.
        Python linters and type checkers remain owned by pyproject manifests.
        """

        python_version: Annotated[
            t.NonEmptyStr,
            m.Field(
                pattern=r"^[0-9]+\.[0-9]+(\.[0-9]+)?$",
                description=(
                    "Python toolchain line: major.minor ('3.13') or the full "
                    "install pin ('3.13.15') when the mise asset registry "
                    "requires it"
                ),
            ),
        ]
        worktree_environment_directory: Annotated[
            t.NonEmptyStr,
            m.Field(
                pattern=r"^\.[A-Za-z][A-Za-z0-9._-]*$",
                description=(
                    "Sibling directory for physical linked-worktree environments"
                ),
            ),
        ]
        dependency_cooldown_days: Annotated[
            int,
            m.Field(
                ge=1,
                description=(
                    "Supply-chain cooldown in days, the single value every "
                    "resolver honours: the generated mise minimum_release_age "
                    "and every dependabot ecosystem entry. Forks and local "
                    "projects (direct git references) are excluded."
                ),
            ),
        ]
        uv_link_mode: Annotated[
            t.NonEmptyStr,
            m.Field(description="Portable uv installation link mode"),
        ]
        uv_environments: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Marker expressions limiting the environments uv resolves "
                    "for the generated lock. Empty resolves every environment."
                ),
            ),
        ] = ()
        uv_constraint_dependencies: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "PEP 508 constraints rendered into every generated "
                    "[tool.uv] constraint-dependencies from this SSOT. The "
                    "declared value replaces any retained value; empty "
                    "removes the key so no orphan cap survives without an "
                    "owner (operator directive 2026-09-08: artificial pins "
                    "are exterminated, never retained)."
                ),
            ),
        ] = ()
        environment_path_prepends: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Extra directories the generated shell activation prepends "
                    "to PATH when they exist. Installation data expressed as "
                    "shell-expandable paths; empty by default so the engine "
                    "never names a specific tool installation."
                ),
            ),
        ] = ()
        mise_lockfile: Annotated[
            bool,
            m.Field(
                description=(
                    "Rendered as [settings] lockfile and bootstrap MISE_LOCKFILE. "
                    "Keep true: "
                    "make upg writes the committed mise.lock. "
                    "Override toolchain.mise_lockfile; never edit the projection."
                ),
            ),
        ] = True
        mise_locked: Annotated[
            bool,
            m.Field(
                description=(
                    "Rendered as [settings] locked, [tool_config] locked, "
                    "and bootstrap MISE_LOCKED. "
                    "Keep true so setup installs only what mise.lock pins. "
                    "Override toolchain.mise_locked."
                ),
            ),
        ] = True
        mise_provenance_api_failures_fatal: Annotated[
            bool,
            m.Field(
                description=(
                    "Rendered as [settings] provenance_api_failures_fatal. "
                    "Keep false: third-party manifest releases (jscpd, qlty) "
                    "publish no SLSA attestations, so treating provenance API "
                    "and attestation-absence failures as fatal would block "
                    "every lock; release checksums still enforce integrity."
                ),
            ),
        ] = False
        mise_locked_verify_provenance: Annotated[
            bool,
            m.Field(
                description=(
                    "Rendered as [settings] locked_verify_provenance. "
                    "Keep false while manifest releases lack attestations; "
                    "flip true once every pinned release publishes SLSA "
                    "attestations."
                ),
            ),
        ] = False
        mise_lockfile_platforms: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description=(
                    "Rendered as [settings] lockfile_platforms: the platforms "
                    "`make upg` resolves into mise.lock, with the current host "
                    "always included by mise. "
                    "Override toolchain.mise_lockfile_platforms."
                ),
            ),
        ]
        python_compile: Annotated[
            bool,
            m.Field(
                description=(
                    "Rendered as [settings.python] compile and bootstrap "
                    "MISE_PYTHON_COMPILE. False restricts Python resolution "
                    "and installation to precompiled builds. "
                    "Override toolchain.python_compile."
                ),
            ),
        ]
        tools: Annotated[
            t.VariadicTuple[FlextInfraModelsMiseToolchain.MiseToolEntry],
            m.Field(
                min_length=1,
                description=(
                    "Declarative fleet tool table rendered into generated "
                    ".mise.toml [tools]; entry order is the projection order. "
                    "Override toolchain.tools entries; never the projection"
                ),
            ),
        ]
        tool_version_pins: Annotated[
            t.MappingKV[t.NonEmptyStr, t.NonEmptyStr],
            m.Field(
                description=(
                    "Exact-version pins layered over the tools table by the "
                    "override files (dict keys deep-merge per tool); `latest` "
                    "re-resolves upstream and drifts from mise.lock between "
                    "upg runs, so overrides pin the versions mise.lock "
                    "resolves and `make upg` advances them deliberately"
                ),
            ),
        ]
        mise_selector: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Mise backend selector rendered as the self-managed [tools] "
                    "entry: mise installs and pins itself through mise.lock. "
                    "Override toolchain.mise_selector."
                ),
            ),
        ]
        mise_version: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Mise release rendered as the self-managed [tools] entry "
                    "version: 'latest', or a held release while upstream's "
                    "newest one is broken"
                ),
            ),
        ]
        beads: Annotated[
            FlextInfraModelsMiseToolchain.BeadsToolSpec,
            m.Field(description="Beads ledger projection (.beads config)"),
        ]

        @m.computed_field
        @property
        def python_required_version(self) -> str:
            """PEP 440 requirement spanning the configured Python minor line.

            Returns:
                The resulting ``str``.
            """
            major, minor = self.python_version.split(".")[:2]
            next_minor = int(minor) + 1
            return f">={self.python_version},<{major}.{next_minor}"

        @m.computed_field
        @property
        def python_selector(self) -> str:
            """Pyenv-style selector for the configured Python minor line.

            Returns:
                The resulting ``str``.
            """
            return self.python_version

        @m.computed_field
        @property
        def tool_versions(self) -> t.MappingKV[str, str]:
            """Effective release selector per tool: pins layered over entries.

            Returns:
                The resulting ``t.MappingKV[str, str]``.
            """
            return {
                entry.name: self.tool_version_pins.get(entry.name, entry.version)
                for entry in self.tools
            }

        @m.computed_field
        @property
        def tool_selectors(self) -> t.MappingKV[str, str]:
            """Declared Mise selector of every selector-bearing fleet tool.

            Returns:
                The resulting ``t.MappingKV[str, str]``.
            """
            return {
                entry.name: entry.selector
                for entry in self.tools
                if entry.selector is not None
            }

        @m.computed_field
        @property
        def tool_keys(self) -> t.MappingKV[str, str]:
            """The [tools] key (selector, else name) of every fleet tool.

            The same key names the tool's ``mise.lock`` table.

            Returns:
                The resulting ``t.MappingKV[str, str]``.
            """
            return {entry.name: entry.selector or entry.name for entry in self.tools}

        @m.computed_field
        @property
        def mise_install_keys(self) -> t.VariadicTuple[str]:
            """Every [tools] key the project declares, in projection order.

            ``make setup``/``make upg`` pass this explicit list to
            ``mise install`` so only the declared toolchain is provisioned,
            never a tool from the operator's global Mise registry.

            Returns:
                The resulting ``t.VariadicTuple[str]``.
            """
            return (
                "python",
                self.mise_selector,
                *(entry.selector or entry.name for entry in self.tools),
            )

        @m.computed_field
        @property
        def tool_version_prefixes(self) -> t.MappingKV[str, str]:
            """Declared release tag prefix of every prefix-bearing fleet tool.

            Returns:
                The resulting ``t.MappingKV[str, str]``.
            """
            return {
                entry.name: entry.version_prefix
                for entry in self.tools
                if entry.version_prefix is not None
            }

        @m.model_validator(mode="after")
        def _validate_version_selectors(self) -> Self:
            """Reject build-identity selectors mise/aube cannot resolve.

            A value like ``0.45.3~7a027ead`` is an aube lock build-identity
            directory name, not a published package version; aube rejects it
            ("no version ... matches range") and the whole toolchain lifecycle
            (make upg/gen/setup, and therefore CI) breaks. Only real selectors
            (``latest``, a major.minor line, or a released version) may reach
            the lock. Tool identities are unique and every non-scalar form
            carries the selector its projection renders as the [tools] key.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If ``offenders``, ``duplicate_names``, or ``keyless``.

            """
            offenders = (
                sorted(
                    f"tools[{entry.name}].version"
                    for entry in self.tools
                    if "~" in entry.version
                )
                + sorted(
                    f"tool_version_pins[{name}]"
                    for name, pinned in self.tool_version_pins.items()
                    if "~" in pinned
                )
                + sorted(
                    field
                    for field, value in self
                    if field.endswith("_version")
                    and isinstance(value, str)
                    and "~" in value
                )
            )
            if offenders:
                msg = (
                    "toolchain version selectors must be resolvable package "
                    "versions, not build identities: " + ", ".join(offenders)
                )
                raise ValueError(msg)
            unknown_pins = sorted(
                set(self.tool_version_pins) - {entry.name for entry in self.tools},
            )
            if unknown_pins:
                msg = "tool_version_pins must name declared tools: " + ", ".join(
                    unknown_pins,
                )
                raise ValueError(msg)
            duplicate_names = sorted(
                {
                    entry.name
                    for entry in self.tools
                    if [other.name for other in self.tools].count(entry.name) > 1
                },
            )
            if duplicate_names:
                msg = "toolchain tools must declare unique names: " + ", ".join(
                    duplicate_names,
                )
                raise ValueError(msg)
            keyless = sorted(
                entry.name
                for entry in self.tools
                if entry.form == "table" and entry.selector is None
            )
            if keyless:
                msg = (
                    "toolchain tools with table form must declare their "
                    "selector: " + ", ".join(keyless)
                )
                raise ValueError(msg)
            npm_backed = sorted(
                entry.name
                for entry in self.tools
                if (entry.selector or entry.name).startswith("npm:")
            )
            if npm_backed:
                msg = (
                    "the fleet toolchain has no npm backend (ADR-025); "
                    "declare a checksum-locked native selector for: "
                    + ", ".join(npm_backed)
                )
                raise ValueError(msg)
            return self

    class BeadsEndpointSpec(_ConfigContract):
        """Static network endpoint projected into Beads configuration."""

        host: Annotated[t.NonEmptyStr, m.Field(description="Beads server host")]
        port: Annotated[
            int,
            m.Field(
                ge=1,
                le=65535,
                description="Beads server TCP port declared by deployment",
            ),
        ]


__all__: list[str] = ["FlextInfraModelsMiseToolchain"]
