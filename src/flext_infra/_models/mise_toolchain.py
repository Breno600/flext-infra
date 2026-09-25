"""Mise toolchain and beads configuration models."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from flext_core import m, t, u


class FlextInfraModelsMiseToolchain:
    """Mise toolchain and beads configuration models."""

    class _ConfigContract(m.ContractModel):
        """Private declarative base for schema-loaded codegen records."""

        model_config = m.ConfigDict(
            strict=False, frozen=True, extra="forbid", str_strip_whitespace=False
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

    class ToolchainSpec(_ConfigContract):
        """Language-runtime and native-tool versions shared by generated projects.

        Language runtimes and native tools are declared as moving ``latest``
        selectors or a major.minor line. Only ``make upg`` resolves them and
        writes the committed mise.lock; setup installs frozen from it. Python linters/type-checkers remain owned
        by pyproject manifests.
        """

        # Selector families rejected while their capabilities are suspended.
        # Operator order 2026-09-07: nothing stays suspended -- gc and beads are
        # operator-owned forks resolved as latest, so the default frees every
        # selector family and the vocabulary stays declared on this owner.
        suspended_mise_selector_patterns: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
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
            t.NonEmptyStr,
            m.Field(description="Runtime state directory beside the checkout"),
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
            t.NonEmptyStr, m.Field(description="Exact kubectl version, e.g. '1.32.0'")
        ]
        helm_version: Annotated[
            t.NonEmptyStr, m.Field(description="Exact Helm version, e.g. '3.19.4'")
        ]
        kind_version: Annotated[
            t.NonEmptyStr, m.Field(description="Exact kind version, e.g. '0.31.0'")
        ]
        direnv_version: Annotated[
            t.NonEmptyStr, m.Field(description="Compatible direnv major.minor line")
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
            t.NonEmptyStr, m.Field(description="Compatible uv major.minor line")
        ]
        mise_lockfile: Annotated[
            bool,
            m.Field(
                description=(
                    "Rendered as [settings] lockfile in .mise.toml. Keep true: "
                    "make upg writes the committed mise.lock. "
                    "Override toolchain.mise_lockfile; never edit the projection."
                )
            ),
        ] = True
        mise_locked: Annotated[
            bool,
            m.Field(
                description=(
                    "Rendered as [settings] locked and [tool_config] locked. "
                    "Keep true so setup installs only what mise.lock pins. "
                    "Override toolchain.mise_locked."
                )
            ),
        ] = True
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
            m.Field(description="Moving qlty release selector, e.g. 'latest'"),
        ]
        node_version: Annotated[
            t.NonEmptyStr, m.Field(description="Compatible Node.js major.minor line")
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
            t.NonEmptyStr,
            m.Field(description="Moving jscpd release selector, e.g. 'latest'"),
        ]
        jscpd_asset_patterns: Annotated[
            t.StrMapping,
            m.Field(
                description=(
                    "Mise platform -> release asset pattern for jscpd. Its "
                    "assets carry libc/ABI suffixes (-gnu, -musl, -msvc) that "
                    "mise autodetection cannot resolve into a lock entry."
                )
            ),
        ]
        prettier_selector: Annotated[
            t.NonEmptyStr,
            m.Field(
                default="npm:prettier",
                description=(
                    "Mise selector for prettier. Override toolchain.prettier_selector; "
                    "never the .mise.toml key."
                ),
            ),
        ]
        prettier_version: Annotated[
            t.NonEmptyStr,
            m.Field(
                default="latest",
                description="Moving prettier release selector, e.g. 'latest'",
            ),
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
            t.NonEmptyStr,
            m.Field(description="Moving Waza release selector, e.g. 'latest'"),
        ]
        waza_version_prefix: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Release tag prefix of the Waza tool. The repository also "
                    "publishes azd-extension tags that GitHub marks latest; the "
                    "prefix keeps them out of resolution."
                )
            ),
        ]
        taplo_version: Annotated[
            t.NonEmptyStr, m.Field(description="Exact Taplo formatter version")
        ]
        ast_grep_version: Annotated[
            t.NonEmptyStr, m.Field(description="Exact ast-grep analyzer version")
        ]
        gitleaks_version: Annotated[
            t.NonEmptyStr, m.Field(description="Exact Gitleaks scanner version")
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
            t.NonEmptyStr, m.Field(description="scc release selector (latest)")
        ]
        kubeconform_version: Annotated[
            t.NonEmptyStr, m.Field(description="Compatible kubeconform minor line")
        ]
        go_version: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Go runtime selector; mise resolves the go backend through it"
                )
            ),
        ]
        make_version: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Moving Make release selector (latest); mise provisions make "
                    "so direnv always resolves a real binary rather than a stale "
                    "host shim. Override toolchain.make_version; never pin."
                )
            ),
        ]
        beads: Annotated[
            FlextInfraModelsMiseToolchain.BeadsToolSpec,
            m.Field(description="Beads ledger projection (.beads config)"),
        ]

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
        version_pin_file: Annotated[
            t.NonEmptyStr,
            m.Field(
                pattern=r"^[A-Za-z0-9._-]+$",
                description=(
                    "Project-root file holding the Mise release `make upg` "
                    "resolved; setup launches exactly that release."
                ),
            ),
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
