"""Mise toolchain and beads configuration models."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Annotated, Literal, Self

from flext_cli import m, u

from flext_infra import t


def _tool_version_field(description: str) -> object:
    """Shared ``Annotated[t.NonEmptyStr, ...]`` metadata for one tool version.

    Every native-toolchain version field in ``ToolchainSpec`` and its
    ``ProjectRenderContext`` render mirror previously repeated an identical
    ``m.Field(description=...)`` shape, differing only in the description
    text -- a structural clone SonarCloud's duplication detector flags as one
    family regardless of the literal string. One owned factory collapses
    every call site to this single declaration (SSOT, DRY).
    """
    return m.Field(description=description)


class _ConfigContract(m.ContractModel):
    """Private declarative base for schema-loaded codegen records."""

    model_config = m.ConfigDict(
        strict=False, frozen=True, extra="forbid", str_strip_whitespace=False
    )


class FlextInfraModelsMiseToolchain:
    """Mise toolchain and beads configuration models."""

    class MiseToolSpec(_ConfigContract):
        """One mise backend declared in ``codegen.yaml``, projected to ``.mise.toml``.

        Override the YAML fields. Never edit ``.mise.toml``. Never pin a SHA.
        ``track: release`` always uses ``version: latest``. ``track: branch``
        requires ``branch`` (no default ``main``) and interpolates that name.
        """

        selector: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Mise backend selector (github:/aqua:/npm:). Override "
                    "toolchain.<tool>.selector; never the .mise.toml key."
                )
            ),
        ]
        track: Annotated[
            Literal["release", "branch"],
            m.Field(
                description=(
                    "release = newest GitHub/registry release. branch = named "
                    "branch SHAs as they appear. Override toolchain.<tool>.track."
                )
            ),
        ] = "release"
        version: Annotated[
            Literal["latest"],
            m.Field(
                description=(
                    "Required when track=release; always latest, never a tag. "
                    "Override toolchain.<tool>.version."
                )
            ),
        ]
        prerelease: Annotated[
            bool,
            m.Field(
                description=(
                    "github backend: include prerelease tags in latest. "
                    "Override toolchain.<tool>.prerelease."
                )
            ),
        ] = False
        branch: Annotated[
            t.NonEmptyStr | None,
            m.Field(
                description=(
                    "Required when track=branch (e.g. 0.12.0-dev). No default "
                    "main. Override toolchain.<tool>.branch."
                )
            ),
        ] = None
        github_attestations: Annotated[
            bool,
            m.Field(
                description=(
                    "GitHub Artifact Attestations. Keep false so setup never "
                    "silently requires a GitHub credential. Override "
                    "toolchain.<tool>.github_attestations."
                )
            ),
        ] = False

        @u.model_validator(mode="after")
        def _validate_track(self) -> Self:
            """Fail closed: branch track names the branch; release forbids one."""
            if self.track == "branch":
                if self.branch is None:
                    msg = (
                        "track=branch requires branch in codegen.yaml (no default main)"
                    )
                    raise ValueError(msg)
            elif self.branch is not None:
                msg = "track=release forbids branch; use version: latest"
                raise ValueError(msg)
            return self

    class ToolchainSpec(_ConfigContract):
        """Language-runtime and native-tool versions shared by generated projects.

        Language runtimes and native tools are declared as moving ``latest``
        selectors or a major.minor line. No mise.lock: setup resolves the
        newest published release. Python linters/type-checkers remain owned
        by pyproject and uv.lock.
        """

        # Selector families rejected while their capabilities are suspended.
        # Operator order 2026-09-07: nothing stays suspended -- gc and beads are
        # operator-owned forks resolved as latest, so the default frees every
        # selector family and the vocabulary stays declared on this owner.
        suspended_mise_selector_patterns: Annotated[
            tuple[t.NonEmptyStr, ...],
            m.Field(
                default=(),
                description=(
                    "Mise selector families rejected while suspended; empty "
                    "frees every toolchain"
                ),
            ),
        ] = ()
        python_version: Annotated[
            t.NonEmptyStr,
            m.Field(
                pattern=r"^[0-9]+\.[0-9]+$",
                description="Python major.minor line, e.g. '3.13'",
            ),
        ]
        state_directory_name: Annotated[
            t.NonEmptyStr, m.Field(description="Runtime state directory beside the checkout"),
        ]
        scratch_namespace: Annotated[
            t.NonEmptyStr, m.Field(description="Scratch directory namespace")
        ]
        scratch_home_relative: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Home-relative scratch root; scratch never lives inside a "
                    "versioned tree, so it mirrors the checkout path below it"
                )
            ),
        ]
        pycache_namespace: Annotated[
            t.NonEmptyStr, m.Field(description="Python bytecode cache namespace")
        ]
        mise_namespace: Annotated[
            t.NonEmptyStr,
            m.Field(description="Mise publication namespace under runtime state"),
        ]
        uv_link_mode: Annotated[
            t.NonEmptyStr, m.Field(description="Portable uv installation link mode")
        ]
        uv_environments: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Marker expressions limiting the environments uv resolves "
                    "for the generated lock. Empty resolves every environment."
                )
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
                )
            ),
        ] = ()
        kubectl_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Exact kubectl version, e.g. '1.32.0'")
        ]
        helm_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Exact Helm version, e.g. '3.19.4'")
        ]
        kind_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Exact kind version, e.g. '0.31.0'")
        ]
        direnv_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Compatible direnv major.minor line")
        ]
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
        uv_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Compatible uv major.minor line")
        ]
        mise_lockfile: Annotated[
            bool,
            m.Field(
                description=(
                    "Rendered as [settings] lockfile in .mise.toml. Keep false. "
                    "Override toolchain.mise_lockfile; never run mise lock; "
                    "never edit the projection."
                )
            ),
        ] = False
        mise_locked: Annotated[
            bool,
            m.Field(
                description=(
                    "Rendered as [settings] locked and [tool_config] locked. "
                    "Keep false so new SHAs/releases install without a lockfile. "
                    "Override toolchain.mise_locked."
                )
            ),
        ] = False
        qlty_selector: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Mise selector for qlty. Override toolchain.qlty_selector; "
                    "never the .mise.toml key."
                )
            ),
        ]
        qlty_version: Annotated[
            t.NonEmptyStr,
            _tool_version_field("Moving qlty release selector, e.g. 'latest'"),
        ]
        node_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Compatible Node.js major.minor line")
        ]
        jscpd_selector: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Mise selector for jscpd. Override toolchain.jscpd_selector; "
                    "never the .mise.toml key."
                )
            ),
        ]
        jscpd_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Moving jscpd release selector, e.g. 'latest'"),
        ]
        waza_selector: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Mise selector for Waza. Override toolchain.waza_selector; "
                    "never the .mise.toml key."
                )
            ),
        ]
        waza_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Moving Waza release selector, e.g. 'latest'"),
        ]
        taplo_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Exact Taplo formatter version")
        ]
        ast_grep_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Exact ast-grep analyzer version")
        ]
        gitleaks_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Exact Gitleaks scanner version")
        ]
        scc_selector: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Mise selector for scc. Override toolchain.scc_selector; "
                    "never the .mise.toml key."
                )
            ),
        ]
        scc_version: Annotated[
            t.NonEmptyStr, _tool_version_field("scc release selector (latest)")
        ]
        kubeconform_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Compatible kubeconform minor line")
        ]
        go_version: Annotated[
            t.NonEmptyStr,
            _tool_version_field(
                "Go runtime selector; mise resolves the go backend through it"
            ),
        ]
        beads: Annotated[
            BeadsToolSpec,
            m.Field(description="Official Beads CLI installed through mise"),
        ]
        gascity: Annotated[
            ProtectedMiseToolSpec,
            m.Field(description="Gas City CLI (gc) installed through mise"),
        ]
        protected_mise_tools: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description="Toolchain field names protected from alternate distributions",
            ),
        ]
        uv_exclude_newer: Annotated[
            t.NonEmptyStr,
            m.Field(
                description="uv [tool.uv] exclude-newer cutoff (exterminated fleet-wide, rendered then conform-stripped)"
            ),
        ]
        dependency_cooldown_exclusions: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Package distributions frozen at their current floor by the "
                    "fleet-wide dependency cooldown policy; absent frees all packages"
                ),
            ),
        ] = ()
        dependency_cooldown_overrides: Annotated[
            t.MappingKV[str, str],
            m.Field(
                default_factory=immutable_empty_mapping,
                description=(
                    "Per-package cooldown cutoff dates overriding the fleet default; "
                    "maps distribution name to a PEP 440 version cutoff string"
                ),
            ),
        ]

        @u.model_validator(mode="after")
        def _validate_protected_mise_tools(self) -> Self:
            """Resolve every protected owner to the generic identity contract."""
            if len(set(self.protected_mise_tools)) != len(self.protected_mise_tools):
                msg = "protected_mise_tools must be unique"
                raise ValueError(msg)
            for owner in self.protected_mise_tools:
                if not isinstance(
                    getattr(self, owner, None),
                    ProtectedMiseToolSpec,
                ):
                    msg = f"protected_mise_tools references invalid owner: {owner}"
                    raise TypeError(msg)
            return self

        @m.computed_field
        @property
        def python_required_version(self) -> str:
            """PEP 440 requirement spanning the configured Python minor line."""
            major, _, minor = self.python_version.partition(".")
            next_minor = int(minor) + 1
            return f">={self.python_version},<{major}.{next_minor}"

        @m.computed_field
        @property
        def python_selector(self) -> str:
            """Mise/pyenv-style selector for the configured Python minor line."""
            return self.python_version

    class ProtectedMiseToolSpec(MiseToolSpec):
        """One fleet-owned mise distribution identity."""

        selector_patterns: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description="Glob patterns identifying equivalent mise distributions",
            ),
        ]

        @u.model_validator(mode="after")
        def _validate_distribution_patterns(self) -> Self:
            """Require one unambiguous pattern set covering the canonical selector."""
            if len(set(self.selector_patterns)) != len(self.selector_patterns):
                msg = "protected mise selector_patterns must be unique"
                raise ValueError(msg)
            if not any(
                fnmatchcase(self.selector, pattern)
                for pattern in self.selector_patterns
            ):
                msg = (
                    "canonical mise selector is not covered by selector_patterns: "
                    f"{self.selector}"
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

    class BeadsToolSpec(ProtectedMiseToolSpec):
        """Canonical Beads distribution and Gas City projection contract."""

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
                    "Rendered as dolt.mode in .beads/config.yaml. Change "
                    "toolchain.beads.dolt_mode; never the projection."
                )
            ),
        ]
        export_auto: Annotated[
            bool,
            m.Field(
                description=(
                    "Rendered as export.auto. Override toolchain.beads.export_auto."
                )
            ),
        ]
        backup_enabled: Annotated[
            bool,
            m.Field(
                description=(
                    "Rendered as backup.enabled. Override "
                    "toolchain.beads.backup_enabled."
                )
            ),
        ]
        dolt_disable_event_flush: Annotated[
            bool,
            m.Field(
                description=(
                    "Rendered as dolt.disable-event-flush. Override "
                    "toolchain.beads.dolt_disable_event_flush."
                )
            ),
        ]

        @u.model_validator(mode="after")
        def _validate_required_custom_types(self) -> Self:
            """Reject ambiguous duplicate type declarations at the owner."""
            if len(set(self.required_custom_types)) != len(self.required_custom_types):
                msg = "beads required_custom_types must be unique"
                raise ValueError(msg)
            return self

    class MiseBootstrapEnvironmentSpec(_ConfigContract):
        """Validated environment contract rendered into generated Mise setup."""

        storage_root_variable: Annotated[
            t.NonEmptyStr,
            m.Field(description="Required caller variable naming persistent storage"),
        ]
        fixed_environment: Annotated[
            t.VariadicTuple[t.Pair[str, str]],
            m.Field(min_length=1, description="Literal fail-closed Mise settings"),
        ]
        transient_environment: Annotated[
            t.VariadicTuple[t.Pair[t.NonEmptyStr, t.NonEmptyStr]],
            m.Field(min_length=1, description="Scratch-relative environment paths"),
        ]
        persistent_environment: Annotated[
            t.VariadicTuple[t.Pair[t.NonEmptyStr, t.NonEmptyStr]],
            m.Field(min_length=1, description="Storage-relative environment paths"),
        ]
        empty_files: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Scratch-relative empty policy files"),
        ]
        passthrough_environment: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Explicitly reinjected host variables"),
        ]

        @u.model_validator(mode="after")
        def _validate_environment_contract(self) -> Self:
            """Reject shell-unsafe, ambiguous, or escaping generated values."""
            groups = (
                self.fixed_environment,
                self.transient_environment,
                self.persistent_environment,
            )
            names = [name for group in groups for name, _ in group]
            names.extend(self.passthrough_environment)
            if len(names) != len(set(names)):
                msg = "Mise bootstrap environment variables must be globally unique"
                raise ValueError(msg)
            for name in names:
                normalized = name.replace("_", "A")
                if not normalized.isalnum() or name != name.upper():
                    msg = f"invalid Mise bootstrap environment variable: {name}"
                    raise ValueError(msg)
                persistent = dict(self.persistent_environment)
                if persistent.get(self.storage_root_variable) != ".":
                    msg = "Mise storage variable must own the persistent root"
                    raise ValueError(msg)
                for _name, value in self.fixed_environment:
                    if any(character in value for character in ("'", "\n", "\r", "\0")):
                        msg = "Mise fixed environment values must be literal-shell safe"
                        raise ValueError(msg)
                relative_paths = (
                    *(value for _, value in self.transient_environment),
                    *(value for _, value in self.persistent_environment),
                    *self.empty_files,
                )
                for path in relative_paths:
                    if path.startswith("/") or ".." in path:
                        msg = f"relative path must not be absolute or escape: {path}"
                        raise ValueError(msg)
            return self


__all__: list[str] = ["FlextInfraModelsMiseToolchain"]
