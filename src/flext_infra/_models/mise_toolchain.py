"""Mise toolchain and beads configuration models.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from flext_core import m, t, u


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

        @u.model_validator(mode="after")
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

    class ToolchainSpec(_ConfigContract):
        """Language-runtime and native-tool versions shared by generated projects.

        Native tools use moving ``latest`` selectors; Python retains its
        required major.minor runtime line. Only ``make upg`` resolves the
        selectors and writes mise.lock; setup installs frozen from that lock.
        Python linters and type checkers remain owned by pyproject manifests.
        """

        # Selector families rejected while their capabilities are suspended.
        # Nothing stays suspended -- gc and beads are
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
        kubectl_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Exact kubectl version, e.g. '1.32.0'"),
        ]
        helm_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Exact Helm version, e.g. '3.19.4'"),
        ]
        kind_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Exact kind version, e.g. '0.31.0'"),
        ]
        direnv_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Compatible direnv major.minor line"),
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
            t.NonEmptyStr,
            m.Field(description="Compatible uv major.minor line"),
        ]
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
        mise_transaction_lock_file: Annotated[
            t.NonEmptyStr,
            m.Field(
                pattern=r"^\.[A-Za-z0-9._-]+\.lock$",
                description=(
                    "Ignored project-root mutex for Mise lock publication/recovery"
                ),
            ),
        ]
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
        npm_package_manager: Annotated[
            Literal["aube"],
            m.Field(description="Mise npm installer with a locked dependency graph"),
        ]
        mise_selector: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Selector `make upg` resolves for the Mise release itself. "
                    "Override toolchain.mise_selector."
                ),
            ),
        ]
        mise_version: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Mise release `make upg` writes to mise.version and the "
                    "launchers: 'latest', or a held release while upstream's "
                    "newest one is broken"
                ),
            ),
        ]
        qlty_selector: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Mise selector for qlty. Override toolchain.qlty_selector; "
                    "never the .mise.toml key."
                ),
            ),
        ]
        qlty_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Moving qlty release selector, e.g. 'latest'"),
        ]
        node_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Compatible Node.js major.minor line"),
        ]
        jscpd_selector: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Mise selector for jscpd. Override toolchain.jscpd_selector; "
                    "never the .mise.toml key."
                ),
            ),
        ]
        jscpd_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Moving jscpd release selector, e.g. 'latest'"),
        ]
        prettier_selector: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Mise selector for prettier. Override toolchain.prettier_selector; "
                    "never the .mise.toml key."
                ),
            ),
        ]
        prettier_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Prettier release selector, e.g. 'latest'"),
        ]
        waza_selector: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Mise selector for Waza. Override toolchain.waza_selector; "
                    "never the .mise.toml key."
                ),
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
                ),
            ),
        ]
        taplo_version: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Taplo release selector; the committed mise.lock pins the "
                    "version generation authenticates"
                ),
            ),
        ]
        ast_grep_selector: Annotated[
            t.NonEmptyStr,
            m.Field(description="Mise selector for the ast-grep CLI"),
        ]
        ast_grep_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Exact ast-grep analyzer version"),
        ]
        gitleaks_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Exact Gitleaks scanner version"),
        ]
        scc_selector: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Mise selector for scc. Override toolchain.scc_selector; "
                    "never the .mise.toml key."
                ),
            ),
        ]
        scc_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="scc release selector (latest)"),
        ]
        kubeconform_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Compatible kubeconform minor line"),
        ]
        go_version: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Go runtime selector; mise resolves the go backend through it"
                ),
            ),
        ]
        make_version: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Moving Make release selector (latest); mise provisions make "
                    "so direnv always resolves a real binary rather than a stale "
                    "host shim. Override toolchain.make_version; never pin."
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
            """PEP 440 requirement spanning the configured Python minor line."""
            major, minor = self.python_version.split(".")[:2]
            next_minor = int(minor) + 1
            return f">={self.python_version},<{major}.{next_minor}"

        @m.computed_field
        @property
        def python_selector(self) -> str:
            """Pyenv-style selector for the configured Python minor line."""
            return self.python_version

        @u.model_validator(mode="after")
        def _validate_version_selectors(self) -> Self:
            """Reject build-identity selectors mise/aube cannot resolve.

            A value like ``0.45.3~7a027ead`` is an aube lock build-identity
            directory name, not a published package version; aube rejects it
            ("no version ... matches range") and the whole toolchain lifecycle
            (make upg/gen/setup, and therefore CI) breaks. Only real selectors
            (``latest``, a major.minor line, or a released version) may reach
            the lock.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If ``offenders``.

            """
            offenders = sorted(
                field
                for field, value in self
                if field.endswith("_version")
                and isinstance(value, str)
                and "~" in value
            )
            if offenders:
                msg = (
                    "toolchain version selectors must be resolvable package "
                    "versions, not build identities: " + ", ".join(offenders)
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
        offline_environment: Annotated[
            t.VariadicTuple[t.Pair[t.NonEmptyStr, t.NonEmptyStr]],
            m.Field(
                min_length=1,
                description=(
                    "Settings that keep a non-install Mise call off the network"
                ),
            ),
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
        version_pin_header: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description=(
                    "Generated-marker comments `make upg` writes above the release"
                ),
            ),
        ]
        version_pin_reader: Annotated[
            t.NonEmptyStr,
            m.Field(description="POSIX awk program selecting the first release line"),
        ]
        release_selector: Annotated[
            t.NonEmptyStr,
            m.Field(
                # "@version" suffix pins the selector to a known-good
                # release when upstream ships a broken one.
                pattern=r"^[a-z]+:[A-Za-z0-9._/@-]+$",
                description="Tool selector `make upg` resolves for the Mise release",
            ),
        ]
        artifact_specs: Annotated[
            t.VariadicTuple[t.Pair[t.NonEmptyStr, int]],
            m.Field(
                min_length=3,
                max_length=3,
                description="Unix launcher, Windows launcher, and pin with modes",
            ),
        ]
        lock_file: Annotated[
            t.NonEmptyStr,
            m.Field(
                pattern=r"^[A-Za-z0-9._-]+$",
                description="Committed native graph watched by runtime activation",
            ),
        ]
        lock_transaction_script: Annotated[
            t.NonEmptyStr,
            m.Field(
                pattern=r"^[A-Za-z0-9._/-]+\.py$",
                description=(
                    "Project-relative generated publisher of a staged mise.lock"
                ),
            ),
        ]
        lock_converge_script: Annotated[
            t.NonEmptyStr,
            m.Field(
                pattern=r"^[A-Za-z0-9._/-]+\.py$",
                description=(
                    "Project-relative generated script `make upg` runs to hold "
                    "broken releases inside a lock stage"
                ),
            ),
        ]
        credential_commands: Annotated[
            t.VariadicTuple[t.VariadicTuple[t.NonEmptyStr]],
            m.Field(
                description=(
                    "Candidate commands (in probe order) that print a GitHub "
                    "token for private tool downloads; the bootstrap probes "
                    "each in turn and takes the first non-empty output."
                ),
            ),
        ] = ()
        transaction_lock_file: Annotated[
            t.NonEmptyStr,
            m.Field(
                pattern=r"^\.[A-Za-z0-9._-]+\.lock$",
                description="Project-root physical mutex declared by toolchain config",
            ),
        ]
        runtime_install_relative_template: Annotated[
            t.NonEmptyStr,
            m.Field(
                pattern=r"^[A-Za-z0-9_-]+/[A-Za-z0-9_-]+\{release\}$",
                description="Storage-relative address of an installed Mise release",
            ),
        ]
        resolved_release_pattern: Annotated[
            t.NonEmptyStr,
            m.Field(description="Shared Python and shell resolved-release grammar"),
        ]

        @staticmethod
        def _ensure_unique_environment_names(
            fixed_environment: t.VariadicTuple[tuple[str, str]],
            transient_environment: t.VariadicTuple[tuple[str, str]],
            persistent_environment: t.VariadicTuple[tuple[str, str]],
            passthrough_environment: t.StrSequence,
        ) -> None:
            """Reject duplicated Mise bootstrap environment variable names.

            Raises:
                ValueError: If a Mise bootstrap environment variable name is
                    duplicated or shell-unsafe.

            """
            names = [
                name
                for group in (
                    fixed_environment,
                    transient_environment,
                    persistent_environment,
                )
                for name, _ in group
            ]
            names.extend(passthrough_environment)
            if len(names) != len(set(names)):
                msg = "Mise bootstrap environment variables must be globally unique"
                raise ValueError(msg)
            for name in names:
                normalized = name.replace("_", "A")
                if not normalized.isalnum() or name != name.upper():
                    msg = f"invalid Mise bootstrap environment variable: {name}"
                    raise ValueError(msg)

        @staticmethod
        def _ensure_persistent_and_fixed_values(
            storage_root_variable: str,
            fixed_environment: t.VariadicTuple[tuple[str, str]],
            persistent_environment: t.VariadicTuple[tuple[str, str]],
        ) -> None:
            """Reject a foreign persistent root and shell-unsafe fixed values.

            Raises:
                ValueError: If the persistent root is foreign or a fixed
                    environment value is shell-unsafe.

            """
            persistent = dict(persistent_environment)
            if persistent.get(storage_root_variable) != ".":
                msg = "Mise storage variable must own the persistent root"
                raise ValueError(msg)
            for _name, value in fixed_environment:
                if any(character in value for character in ("'", "\n", "\r", "\0")):
                    msg = "Mise fixed environment values must be literal-shell safe"
                    raise ValueError(msg)

        @staticmethod
        def _ensure_relative_paths(
            transient_environment: t.VariadicTuple[tuple[str, str]],
            persistent_environment: t.VariadicTuple[tuple[str, str]],
            empty_files: t.StrSequence,
        ) -> None:
            """Reject absolute or escaping generated relative paths.

            Raises:
                ValueError: If a generated relative path is absolute or escapes.

            """
            relative_paths = (
                *(value for _, value in transient_environment),
                *(value for _, value in persistent_environment),
                *empty_files,
            )
            for path in relative_paths:
                if path.startswith("/") or ".." in path:
                    msg = f"relative path must not be absolute or escape: {path}"
                    raise ValueError(msg)

        @u.model_validator(mode="after")
        def _validate_environment_contract(self) -> Self:
            """Reject shell-unsafe, ambiguous, or escaping generated values.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If Mise bootstrap environment variables must be globally
                    unique; or if invalid Mise bootstrap environment variable; or if
                    Mise storage variable must own the persistent root; or if Mise
                    fixed environment values must be literal-shell safe; or if
                    relative path must not be absolute or escape; or if Mise pin
                    header and reader must be literal-shell safe; or if Mise pin
                    header lines must be comments.

            """
            literal_environment = (*self.fixed_environment, *self.offline_environment)
            self._ensure_unique_environment_names(
                literal_environment,
                self.transient_environment,
                self.persistent_environment,
                self.passthrough_environment,
            )
            names = [
                name
                for group in (
                    literal_environment,
                    self.transient_environment,
                    self.persistent_environment,
                )
                for name, _ in group
            ]
            names.extend(self.passthrough_environment)
            # The member/persistent/fixed-path checks run inside the names
            # loop, exactly as this contract always executed: a toolchain
            # declaring no bootstrap names skips them (renders without a
            # bootstrap environment are valid).
            for name in names:
                normalized = name.replace("_", "A")
                if not normalized.isalnum() or name != name.upper():
                    msg = f"invalid Mise bootstrap environment variable: {name}"
                    raise ValueError(msg)
                self._ensure_persistent_and_fixed_values(
                    self.storage_root_variable,
                    literal_environment,
                    self.persistent_environment,
                )
                self._ensure_relative_paths(
                    self.transient_environment,
                    self.persistent_environment,
                    self.empty_files,
                )
            unsafe = ("'", "\n", "\r", "\0")
            for line in (*self.version_pin_header, self.version_pin_reader):
                if any(character in line for character in unsafe):
                    msg = "Mise pin header and reader must be literal-shell safe"
                    raise ValueError(msg)
            if not all(line.startswith("#") for line in self.version_pin_header):
                msg = "Mise pin header lines must be comments"
                raise ValueError(msg)
            return self


__all__: list[str] = ["FlextInfraModelsMiseToolchain"]
