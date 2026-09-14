"""Pure Pydantic config and codegen contracts for flext-infra.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Annotated, ClassVar, Literal, Self

from flext_cli import m, u
from pydantic import AliasChoices

from flext_infra import t

from .._constants.codegen_project import FlextInfraConstantsCodegenProject
from .._constants.make import FlextInfraConstantsMake
from .._constants.release import FlextInfraConstantsRelease
from .._constants.validate import FlextInfraConstantsSharedInfra
from ._defaults import ImmutableEmptyMapping, immutable_empty_mapping
from .deps_tool_config import FlextInfraModelsDepsToolSettings
from .layout import FlextInfraModelsLayout

__all__: list[str] = ["FlextInfraConfigModels"]


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


class FlextInfraConfigModels:
    """Field-only models for config loading and codegen plans."""

    # These models replace the former model-less workspace/make dictionaries.
    # YAML is accepted only at the flext-cli loading boundary and is immediately
    # model-validated here.

    class _ConfigContract(m.ContractModel):
        """Private declarative base for schema-loaded codegen records."""

        # Rendered file payloads are
        # byte contracts; Pydantic must never trim their final newline.
        model_config = m.ConfigDict(
            strict=False, frozen=True, extra="forbid", str_strip_whitespace=False
        )

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
            for value in relative_paths:
                path = Path(value)
                if path.is_absolute() or ".." in path.parts:
                    msg = f"Mise bootstrap path must stay below its owner: {value}"
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
            t.NonEmptyStr,
            m.Field(description="Runtime state directory beside the checkout"),
        ]
        scratch_namespace: Annotated[
            t.NonEmptyStr, m.Field(description="Scratch directory namespace")
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
        additional_python_tool_distributions: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description="Tool identities outside the scaffold requirement owners",
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
            t.NonEmptyStr,
            _tool_version_field("Moving jscpd release selector, e.g. 'latest'"),
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
            _tool_version_field("Moving Waza release selector, e.g. 'latest'"),
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
            FlextInfraConfigModels.BeadsToolSpec,
            m.Field(description="Official Beads CLI installed through mise"),
        ]
        gascity: Annotated[
            FlextInfraConfigModels.ProtectedMiseToolSpec,
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
                    FlextInfraConfigModels.ProtectedMiseToolSpec,
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

    class ProviderSpec(_ConfigContract):
        """One GitHub organization and its mandatory branch policy."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Provider key")]
        organization: Annotated[
            t.NonEmptyStr, m.Field(description="GitHub organization")
        ]
        base_url: Annotated[t.NonEmptyStr, m.Field(description="GitHub HTTPS base URL")]
        branch: Annotated[t.NonEmptyStr, m.Field(description="Provider branch")]

    class RepositorySourceSpec(_ConfigContract):
        """Portable repository identity derived through one declared provider."""

        distribution: Annotated[
            t.NonEmptyStr, m.Field(description="Repository distribution name")
        ]
        provider: Annotated[
            t.NonEmptyStr, m.Field(description="Provider key owning URL and branch")
        ]

        @m.computed_field
        @property
        def internal_distribution_prefix(self) -> str:
            """Derive the internal distribution namespace from the owner name."""
            namespace, _, _ = self.distribution.partition("-")
            return f"{namespace}-"

    class BranchPolicySpec(_ConfigContract):
        """Global ancestry policy shared by every governed provider."""

        REQUIRED_TECHNICAL_PATTERNS: ClassVar[t.VariadicTuple[str]] = (
            "__dolt_remote_info__",
            "dolt/*",
            "gh-readonly-queue/*",
        )
        technical_branch_patterns: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "GitHub/Dolt technical branches excluded from ancestry validation"
                )
            ),
        ]
        governed_branch_patterns: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description=(
                    "Development lines whose descent from the baseline is enforced. "
                    "Refs outside this allowlist are inventoried but never gated: "
                    "parked releases, snapshots and lane branches must not block."
                ),
            ),
        ]
        ci_trigger_branches: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description=(
                    "Branches whose pushes trigger the generated CI workflow. "
                    "Config owns this list: the renderer adds only the repository's "
                    "own integration branch, so no fleet name is hardcoded in code."
                ),
            ),
        ]
        integration_branch_preference: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=FlextInfraConstantsSharedInfra.INTEGRATION_BRANCH_PREFERENCE,
                min_length=1,
                description=(
                    "Ordered names tried against live Git to derive one "
                    "repository's integration baseline. A workspace that "
                    "integrates on a versioned line declares it here, so a "
                    "release name never has to be hardcoded in the package. "
                    "The provider default stays the last-resort fallback, "
                    "never the answer."
                ),
            ),
        ] = FlextInfraConstantsSharedInfra.INTEGRATION_BRANCH_PREFERENCE

        @u.model_validator(mode="after")
        def _validate_technical_patterns(self) -> Self:
            """Keep the global exclusion set exact and non-extensible."""
            if self.technical_branch_patterns != self.REQUIRED_TECHNICAL_PATTERNS:
                msg = (
                    "technical branch patterns must equal the canonical GitHub/Dolt "
                    f"set: {', '.join(self.REQUIRED_TECHNICAL_PATTERNS)}"
                )
                raise ValueError(msg)
            return self

    class GithubActionPinSpec(_ConfigContract):
        """One GitHub Action reference from the codegen catalog."""

        repository: Annotated[
            t.NonEmptyStr, m.Field(description="GitHub owner/repository action name")
        ]
        version: Annotated[
            t.NonEmptyStr,
            m.Field(description="Upstream floating release tag the action rides"),
        ]

    class CiPrivateSubmoduleDeployKeySpec(_ConfigContract):
        """One read-only deploy key that unlocks a private workspace subproject in CI."""

        secret: Annotated[
            t.NonEmptyStr,
            m.Field(
                description="GitHub Actions secret name holding the deploy key PEM"
            ),
        ]
        submodule: Annotated[
            t.NonEmptyStr,
            m.Field(
                description="gitmodules submodule name (git config submodule.<name>.url)"
            ),
        ]
        path: Annotated[
            t.NonEmptyStr, m.Field(description="Checkout-relative submodule path")
        ]
        remote: Annotated[
            t.NonEmptyStr,
            m.Field(
                pattern=r"^git@github\.com:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git$",
                description="Canonical GitHub SSH clone URL without a Host alias",
            ),
        ]

    class CiPrivateDependencyAuthSpec(_ConfigContract):
        """GitHub App identity minting installation tokens for private deps."""

        app_id_secret: Annotated[
            t.NonEmptyStr,
            m.Field(
                pattern=r"^[A-Z][A-Z0-9_]*$",
                description="CI secret holding the private-dependency App id",
            ),
        ]
        private_key_secret: Annotated[
            t.NonEmptyStr,
            m.Field(
                pattern=r"^[A-Z][A-Z0-9_]*$",
                description="CI secret holding the private-dependency App key",
            ),
        ]

    class CiPrivateSubmodulesSpec(_ConfigContract):
        """Per-distribution private submodule init contract for generated CI."""

        _KNOWN_HOSTS_FIELD_COUNT: ClassVar[int] = 3

        known_hosts: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description="Pinned official SSH host-key lines used only in runner temp",
            ),
        ]

        paths: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1, description="Submodule paths to init before make setup"
            ),
        ]
        deploy_keys: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.CiPrivateSubmoduleDeployKeySpec],
            m.Field(min_length=1, description="Ordered deploy-key materializations"),
        ]

        @u.model_validator(mode="after")
        def _validate_private_submodule_identity(self) -> Self:
            """Keep path, key, and host identities complete and unambiguous."""
            key_paths = tuple(key.path for key in self.deploy_keys)
            if key_paths != self.paths:
                msg = "private submodule deploy-key paths must exactly match paths"
                raise ValueError(msg)
            for field, values in (
                ("secret", tuple(key.secret for key in self.deploy_keys)),
                ("submodule", tuple(key.submodule for key in self.deploy_keys)),
                ("remote", tuple(key.remote for key in self.deploy_keys)),
                ("known_hosts", self.known_hosts),
            ):
                if len(set(values)) != len(values):
                    msg = f"private submodule {field} values must be unique"
                    raise ValueError(msg)
            for line in self.known_hosts:
                fields = line.split()
                if (
                    len(fields) != self._KNOWN_HOSTS_FIELD_COUNT
                    or fields[0] != "github.com"
                    or fields[1] != "ssh-ed25519"
                ):
                    msg = (
                        "private submodule known_hosts must pin github.com ssh-ed25519"
                    )
                    raise ValueError(msg)
            return self

    class GithubWorkflowRenderSpec(_ConfigContract):
        """Typed input consumed by generated GitHub workflow templates."""

        dist: Annotated[t.NonEmptyStr, m.Field(description="Distribution name")]
        make_profile: Annotated[
            FlextInfraConstantsCodegenProject.MakeProfile,
            m.Field(
                description=(
                    "Make/codegen profile; ci-matrix projected only for "
                    "workspace/standalone; standalone excluded "
                    "and orphan copies pruned"
                )
            ),
        ]
        gascity_enabled: Annotated[
            bool,
            m.Field(
                description=(
                    "Gas City runtime-contract participation; gates the Dolt "
                    "server mode the generated Beads policy script asserts."
                )
            ),
        ] = True
        repository_branch: Annotated[
            t.NonEmptyStr, m.Field(description="Repository integration branch")
        ]
        python_version: Annotated[
            t.NonEmptyStr, m.Field(description="Python major.minor line")
        ]
        state_directory_name: Annotated[
            t.NonEmptyStr, m.Field(description="External runtime state directory name")
        ]
        github_actions: Annotated[
            Mapping[str, FlextInfraConfigModels.GithubActionPinSpec],
            m.Field(description="Immutable GitHub Action catalog"),
        ]
        make: Annotated[
            FlextInfraConfigModels.MakeSpec,
            m.Field(description="Canonical workflow command contract"),
        ]
        workspace_repositories: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.RepositoryRef],
            m.Field(
                default=(),
                description=(
                    "Governed subproject repositories consumed by workspace-scoped "
                    "workflow templates (docs paths, dependabot directories)"
                ),
            ),
        ]
        ci_trigger_branches: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(), description="Ordered, deduplicated blocking CI branches"
            ),
        ] = ()
        has_devcontainer: Annotated[
            bool,
            m.Field(
                default=False,
                description=(
                    "Whether the rendered repository ships a .devcontainer "
                    "directory. Dependabot only accepts a devcontainers "
                    "ecosystem entry when one exists; declaring it for a "
                    "repository without that directory makes GitHub reject the "
                    "whole manifest, which silently disables EVERY ecosystem in "
                    "it, security updates included. Derived from the repository "
                    "on disk rather than declared, because the directory is the "
                    "fact and a second declaration could disagree with it "
                    "(hq-36xk)"
                ),
            ),
        ] = False
        checkout_submodules: Annotated[
            t.NonEmptyStr,
            m.Field(
                default="false",
                pattern=r"^(true|false|recursive)$",
                description=(
                    "actions/checkout submodules mode. Defaults to 'false' "
                    "because the default GITHUB_TOKEN cannot clone sibling "
                    "private repositories: 'recursive' aborts the job at "
                    "checkout with 'Repository not found'. Projects whose "
                    "submodules are public, or that provide a PAT, override "
                    "it per project in codegen.yaml"
                ),
            ),
        ]
        custom_steps: Annotated[
            str,
            m.Field(
                default="",
                description=(
                    "Verbatim project-owned workflow steps injected before the "
                    "toolchain installer, read from the project's own "
                    "custom-steps file; empty when the project declares none"
                ),
            ),
        ] = ""
        private_submodules: Annotated[
            FlextInfraConfigModels.CiPrivateSubmodulesSpec | None,
            m.Field(
                default=None,
                description=(
                    "Optional private-subproject deploy-key init for this "
                    "distribution; None means the workflow skips the step"
                ),
            ),
        ] = None
        private_dependency_auth: Annotated[
            FlextInfraConfigModels.CiPrivateDependencyAuthSpec | None,
            m.Field(
                default=None,
                description=(
                    "Optional GitHub App token minting for private git "
                    "dependencies; None means the workflow skips the step"
                ),
            ),
        ] = None
        system_packages: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Runner packages this distribution's tests need; empty "
                    "means the workflow renders no install step"
                ),
            ),
        ] = ()

    class MakeWorkflowRenderSpec(_ConfigContract):
        """Typed input shared by generated local workflow surfaces."""

        dist: Annotated[t.NonEmptyStr, m.Field(description="Distribution name")]
        make: Annotated[
            FlextInfraConfigModels.MakeSpec,
            m.Field(description="Canonical workflow command contract"),
        ]

    class ToolingRenderSpec(_ConfigContract):
        """Typed input for project-independent generated tooling surfaces."""

        tooling: Annotated[
            FlextInfraModelsDepsToolSettings.ToolConfigDocument,
            m.Field(description="Canonical validated tooling policy"),
        ]

    class DistroDockerRenderSpec(_ConfigContract):
        """Typed input consumed by generated distro Dockerfiles."""

        package_name: Annotated[
            t.NonEmptyStr, m.Field(description="Python import package name")
        ]
        python_version: Annotated[
            t.NonEmptyStr, m.Field(description="Python major.minor line")
        ]
        make: Annotated[
            FlextInfraConfigModels.MakeSpec,
            m.Field(description="Canonical Make CI token contract for ENV CI=Y"),
        ]
        mise_bootstrap: Annotated[
            FlextInfraConfigModels.MiseBootstrapEnvironmentSpec,
            m.Field(description="Strict Mise environment projected into containers"),
        ]

    class EnvrcRenderSpec(_ConfigContract):
        """Typed input consumed only by the generated project ``.envrc``."""

        state_directory_name: Annotated[
            t.NonEmptyStr, m.Field(description="External runtime state directory")
        ]
        scratch_namespace: Annotated[
            t.NonEmptyStr, m.Field(description="External scratch namespace")
        ]
        pycache_namespace: Annotated[
            t.NonEmptyStr, m.Field(description="External bytecode cache namespace")
        ]

        environment_path_prepends: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Project-relative executable paths"),
        ]
        mise_bootstrap: Annotated[
            FlextInfraConfigModels.MiseBootstrapEnvironmentSpec,
            m.Field(description="Strict persistent Mise storage contract"),
        ]
        gascity: Annotated[
            FlextInfraConfigModels.BeadsWorkspaceEnvironmentSpec | None,
            m.Field(
                description=(
                    "Gas City Beads projection present only when the repository "
                    "declares gascity_enabled"
                )
            ),
        ] = None

    class UvPackageSelectorSpec(_ConfigContract):
        """Package selector for one official uv scoped dependency exclusion."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Selected package name")]
        version: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Optional selected package version expression"),
        ] = None

    class UvScopedDependencyExclusionSpec(_ConfigContract):
        """Project-routed official uv scoped dependency exclusion."""

        project: Annotated[
            t.NonEmptyStr,
            m.Field(exclude=True, description="Owning project distribution route"),
        ]
        package: Annotated[
            FlextInfraConfigModels.UvPackageSelectorSpec,
            m.Field(description="Package whose transitive edge is scoped"),
        ]
        dependencies: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Excluded transitive dependency names"),
        ]

    class ProfileSpec(_ConfigContract):
        """Execution semantics for one generated Make profile."""

        name: Annotated[
            FlextInfraConstantsCodegenProject.MakeProfile,
            m.Field(description="Closed Make profile name"),
        ]
        environment_scope: Annotated[
            t.NonEmptyStr, m.Field(description="uv environment ownership")
        ]
        setup_scope: Annotated[
            t.NonEmptyStr, m.Field(description="setup orchestration scope")
        ]
        execution_scope: Annotated[
            t.NonEmptyStr, m.Field(description="check/test runtime scope")
        ]
        discovery_scope: Annotated[
            Literal["gitmodules", "none"],
            m.Field(description="repository-local discovery authority"),
        ]

    class MakeVerbSpec(_ConfigContract):
        """One selector-free public Make operation."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Public Make verb")]
        description: Annotated[
            t.NonEmptyStr, m.Field(description="Operator-facing help text")
        ]

    class MakeWorkflowStepSpec(_ConfigContract):
        """One canonical workflow step."""

        verb: Annotated[t.NonEmptyStr, m.Field(description="Declared public verb")]
        contexts: Annotated[
            t.VariadicTuple[Literal["local", "ci", "pre_commit", "pre_push"]],
            m.Field(
                min_length=1,
                description="Execution contexts consuming this single workflow row",
            ),
        ]
        gates_skip: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Gate ids this step omits when it runs from a hook context "
                    "(pre_commit/pre_push). Local and CI invocations of the "
                    "same verb keep the full default set."
                ),
            ),
        ] = ()

        @u.model_validator(mode="after")
        def _validate_contexts(self) -> Self:
            """Require unique contexts and retain every step in the local workflow."""
            if len(set(self.contexts)) != len(self.contexts):
                msg = f"make workflow contexts must be unique for {self.verb}"
                raise ValueError(msg)
            if "local" not in self.contexts:
                msg = f"make workflow step {self.verb} must run locally"
                raise ValueError(msg)
            allowed = set(FlextInfraConstantsMake.CANONICAL_GATE_IDS)
            unknown = sorted(set(self.gates_skip) - allowed)
            if unknown:
                msg = (
                    f"make workflow step {self.verb} gates_skip contains "
                    f"unknown gates: {', '.join(unknown)}"
                )
                raise ValueError(msg)
            return self

    class MakeCiSpec(_ConfigContract):
        """The only permitted environment delta between local and CI execution."""

        variable: Annotated[t.NonEmptyStr, m.Field(description="CI environment key")]
        value: Annotated[t.NonEmptyStr, m.Field(description="CI environment value")]
        local_value: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Local form of the CI ternary. A hook declares this value "
                    "explicitly so an inherited CI token from the caller can "
                    "never revoke pytest or the type-checker gates."
                )
            ),
        ] = "N"
        local_check_gates: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Gate ids run by make check under the local CI token: the "
                    "slow whole-program type checkers. This is the ONLY "
                    "declared set; the CI token runs its strict complement and "
                    "an unset token runs every allowed gate."
                )
            ),
        ]

        @u.model_validator(mode="after")
        def _validate_local_check_gates(self) -> Self:
            """Every locally owned gate must be in the allowed check vocabulary."""
            allowed = set(FlextInfraConstantsMake.CANONICAL_GATE_IDS)
            unknown = sorted(set(self.local_check_gates) - allowed)
            if unknown:
                msg = (
                    "make.ci.local_check_gates contains unknown gates: "
                    f"{', '.join(unknown)}"
                )
                raise ValueError(msg)
            return self

        @m.computed_field
        @property
        def check_gates(self) -> t.VariadicTuple[str]:
            """Gates run under the CI token, as the strict complement.

            CI=Y is the inverse of CI=N by construction, never a second list: a
            gate that moves into or out of ``local_check_gates`` moves out of or
            into this set in the same edit, so the two can never overlap nor
            leave a gate unowned.

            The complement is taken over the DEFAULT vocabulary, not ALLOWED.
            ``format`` is allowed as an explicit ``CHECK_GATES=format`` request
            but is absent from the default set because it MUTATES files, so
            deriving over ALLOWED silently scheduled a formatter inside CI's
            read-only check — the one thing the comment on ``local_check_gates``
            says must never happen.
            """
            local = frozenset(self.local_check_gates)
            return tuple(
                gate
                for gate in FlextInfraConstantsMake.CANONICAL_DEFAULT_GATE_IDS
                if gate not in local
            )

    class ScriptDispatchSpec(_ConfigContract):
        """Opt-in routing of non-builtin verbs to a script command framework."""

        dispatcher: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Repository-relative dispatcher entrypoint that resolves "
                    "scripts/<verb>/<what>.{py,sh} commands"
                )
            ),
        ]
        roots: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description=(
                    "Repository-relative script roots scanned for a matching "
                    "<verb>/<what> command before falling back to a builtin"
                ),
            ),
        ]

    class CustomHandlerPolicy(_ConfigContract):
        """Strict schema for the only handwritten Make extension file."""

        filename: Annotated[
            t.NonEmptyStr, m.Field(description="Versioned custom handler filename")
        ]
        target_pattern: Annotated[
            t.NonEmptyStr,
            m.Field(description="Required private target regular expression"),
        ]
        allow_public_targets: bool = m.Field(description="Permit public targets")
        allow_toolchain_declarations: bool = m.Field(
            description="Permit toolchain declarations"
        )

    class CustomHandlerPolicyOverride(_ConfigContract):
        """Per-profile relaxation of the strict custom-handler contract.

        Every field is optional: a profile declares ONLY what it relaxes, so a
        new permission added to the base policy propagates automatically
        instead of having to be repeated in each profile.
        """

        allow_public_targets: bool | None = m.Field(
            default=None, description="Permit public targets"
        )
        allow_toolchain_declarations: bool | None = m.Field(
            default=None, description="Permit toolchain declarations"
        )

    class DocsGithubRepoSpec(_ConfigContract):
        """One governed GitHub repository used for cross-repo doc links."""

        organization: Annotated[
            t.NonEmptyStr, m.Field(description="GitHub organization")
        ]
        repository: Annotated[t.NonEmptyStr, m.Field(description="GitHub repository")]
        branch: Annotated[
            t.NonEmptyStr, m.Field(description="Working-line branch for doc links")
        ]
        local_checkout: Annotated[
            str,
            m.Field(
                default="",
                description=(
                    "Optional local checkout path (~ expanded) for existence checks"
                ),
            ),
        ] = ""

    class MakeCleanSpec(_ConfigContract):
        """Disposable artifacts the generated clean verb removes.

        Stale caches and traces cause FALSE DIAGNOSES, so the disposable set is
        declared data rather than a literal buried in a recipe: every project
        cleans exactly the same things and a new artifact kind is one config row.
        """

        cache_dirs: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Cache directory names removed anywhere in the tree"),
        ]
        root_dirs: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Directories removed at the project root only"),
        ]
        root_files: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Files removed at the project root only"),
        ]
        trace_globs: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Trace/profile globs removed anywhere in the tree"),
        ]

    class MakeDocsSpec(_ConfigContract):
        """Generated Makefile docs verb lifecycle and audit policy."""

        api_modules: Annotated[
            Mapping[t.NonEmptyStr, t.VariadicTuple[t.NonEmptyStr]],
            m.Field(
                min_length=1,
                description=(
                    "Public API modules generated per distribution; absent "
                    "distributions own no module pages"
                ),
            ),
        ]
        mutable_actions: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Docs actions that mutate"),
        ]
        reports_dir: Annotated[
            Path, m.Field(description="Repository-relative docs reports directory")
        ]
        cross_project_relative_link_pattern: Annotated[
            t.NonEmptyStr,
            m.Field(
                description="Regex rejecting cross-project relative Markdown links"
            ),
        ]
        stale_github_organizations: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=("organization",),
                description="Placeholder GitHub orgs that must be rewritten",
            ),
        ] = ("organization",)
        github_repos: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.DocsGithubRepoSpec],
            m.Field(
                default=(),
                description="Governed org/repo/branch map for cross-repo doc URLs",
            ),
        ] = ()

        @u.model_validator(mode="after")
        def _validate_api_modules(self) -> Self:
            """Reject duplicate or non-importable API module declarations."""
            for distribution, modules in self.api_modules.items():
                if not modules:
                    msg = f"docs api_modules must not be empty: {distribution}"
                    raise ValueError(msg)
                if len(set(modules)) != len(modules):
                    msg = f"docs api_modules must be unique: {distribution}"
                    raise ValueError(msg)
                invalid = next(
                    (
                        module
                        for module in modules
                        if not all(part.isidentifier() for part in module.split("."))
                    ),
                    None,
                )
                if invalid is not None:
                    msg = f"docs api module is not importable: {invalid}"
                    raise ValueError(msg)
            return self

    class TestmonCacheSpec(_ConfigContract):
        """Adaptive pytest-testmon GitHub Actions cache policy."""

        schema_version: Annotated[
            int, m.Field(ge=1, description="Cache key schema version")
        ]
        namespace: Annotated[
            t.NonEmptyStr, m.Field(description="Persistent state namespace")
        ]
        invocation_namespace: Annotated[
            t.NonEmptyStr, m.Field(description="Pytest invocation namespace")
        ]
        database_filename: Annotated[
            t.NonEmptyStr, m.Field(description="pytest-testmon database filename")
        ]
        target_directory: Annotated[
            Path, m.Field(description="Repository-relative pytest target")
        ]
        reports_directory: Annotated[
            Path, m.Field(description="Repository-relative pytest reports root")
        ]
        mode: Annotated[
            Literal["bootstrap", "stable"], m.Field(description="Cache renewal phase")
        ]
        save_enabled: Annotated[
            bool,
            m.Field(
                description=(
                    "Whether CI may upload a new testmon generation. False while "
                    "quota/HTTP 402 blocks fleet-wide saves (QUOTA_HOLD)."
                )
            ),
        ]
        max_bootstrap_generations: Annotated[
            int, m.Field(ge=1, le=10, description="Max retained bootstrap generations")
        ]
        max_stable_generations: Annotated[
            int, m.Field(ge=1, le=10, description="Max retained stable generations")
        ]
        per_repo_budget_bytes: Annotated[
            int, m.Field(ge=1, description="Per-repo testmon namespace budget in bytes")
        ]
        warning_threshold_percent: Annotated[
            int, m.Field(ge=1, le=100, description="Quota warning threshold percent")
        ]
        maintenance_threshold_percent: Annotated[
            int,
            m.Field(ge=1, le=100, description="Quota maintenance threshold percent"),
        ]
        block_threshold_percent: Annotated[
            int, m.Field(ge=1, le=100, description="Quota block-save threshold percent")
        ]
        allowed_save_refs: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Refs allowed to save cache generations"),
        ]
        key_prefix: Annotated[
            t.NonEmptyStr, m.Field(description="Immutable cache key prefix")
        ]

        @u.model_validator(mode="after")
        def _validate_thresholds(self) -> Self:
            """Require warning < maintenance < block."""
            if not (
                self.warning_threshold_percent
                < self.maintenance_threshold_percent
                < self.block_threshold_percent
            ):
                msg = "testmon cache thresholds must satisfy warning < maintenance < block"
                raise ValueError(msg)
            return self

    class MakeWorkInProgressSpec(_ConfigContract):
        """Predicate for work-in-progress branches and draft-PR gate behavior.

        A hook that runs the full gate matrix on every push turns an
        in-progress branch into a stop-and-wait loop, so contributors start
        bypassing the hook entirely -- which costs more than it saves. The
        predicate is DATA so the escape is declared and auditable rather than
        improvised per-repository with `--no-verify`.
        """

        draft_pr: Annotated[
            bool, m.Field(description="Treat GitHub draft PRs as work-in-progress")
        ]
        branch_patterns: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description="Regex patterns that mark a branch as work-in-progress",
            ),
        ]
        merge_lock_target_branches: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description="Target branches that are blocked for WIP merges",
            ),
        ]

    class MakeRuffSpec(_ConfigContract):
        """Ruff CLI contract for generated Make verbs and quality gates.

        Operator 2026-09-08: ruff is the style and autofix rule. Every
        invocation uses preview. ``make fmt`` also applies unsafe
        autofixes. Never weaken ruff to keep a file; change the code.
        """

        format_check: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Flags for ruff format --check (read-only fmt)"),
        ]
        format_apply: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Flags for ruff format APPLY"),
        ]
        lint_check: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Flags for ruff check without mutation"),
        ]
        lint_fix: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Flags for ruff check --fix including unsafe-fixes; used by "
                    "make fmt and make fix"
                )
            ),
        ]

    class MakeSpec(_ConfigContract):
        """Complete generated Makefile public and extension contract."""

        ruff: Annotated[
            FlextInfraConfigModels.MakeRuffSpec,
            m.Field(description="Ruff CLI flags for fmt/fix/check Make verbs"),
        ]
        work_in_progress: Annotated[
            FlextInfraConfigModels.MakeWorkInProgressSpec,
            m.Field(description="WIP branch and draft PR gate predicate"),
        ]
        # Why (operator law 2026-09-11): the APPLY write-enable flag is
        # exterminated — every public verb mutates by default with zero
        # variables; read-only verification lives in dedicated verbs (check).
        # Why (operator law 2026-08-24): git-hook stages are OFF by default and
        # re-enabled case by case via these config gates. The workflow keeps
        # owning WHICH steps belong to each stage; the booleans only govern
        # whether the stage is generated and installed at all.
        pre_commit: Annotated[
            bool,
            m.Field(
                default=False,
                description="Generate and install the pre-commit git-hook stage",
            ),
        ] = False
        pre_push: Annotated[
            bool,
            m.Field(
                default=False,
                description="Generate and install the pre-push git-hook stage",
            ),
        ] = False
        workflow: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.MakeWorkflowStepSpec],
            m.Field(min_length=1, description="Ordered canonical validation workflow"),
        ]
        ci: Annotated[
            FlextInfraConfigModels.MakeCiSpec,
            m.Field(description="Config-owned CI-only environment delta"),
        ]
        testmon_cache: Annotated[
            FlextInfraConfigModels.TestmonCacheSpec,
            m.Field(description="Adaptive testmon Actions cache policy"),
        ]
        verbs: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.MakeVerbSpec],
            m.Field(description="Ordered canonical public verbs"),
        ]
        clean: Annotated[
            FlextInfraConfigModels.MakeCleanSpec,
            m.Field(description="Disposable artifacts removed by the clean verb"),
        ]
        docs: Annotated[
            FlextInfraConfigModels.MakeDocsSpec,
            m.Field(description="Public documentation lifecycle policy"),
        ]
        custom_handler_policy: Annotated[
            FlextInfraConfigModels.CustomHandlerPolicy,
            m.Field(description="Private custom target policy"),
        ]
        custom_handler_profile_overrides: Annotated[
            Mapping[t.NonEmptyStr, FlextInfraConfigModels.CustomHandlerPolicyOverride],
            m.Field(
                default_factory=immutable_empty_mapping,
                description="Per-profile overrides of the custom handler policy",
            ),
        ]
        project_check_gates: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Check gates this project implements itself, unioned into "
                    "the built-in vocabulary. Without this seam the vocabulary "
                    "is a closed Final tuple, so a project that ships a working "
                    "`_custom_check_<gate>` handler still cannot reach it "
                    "through `make check`: the gate is rejected as unknown. A "
                    "gate that can never run is not a gate, which is how "
                    "references, agents, census and waza ended up outside the "
                    "gate matrix in consuming repositories. Each id must have a "
                    "`_custom_check_<id>` handler in the project's "
                    f"{FlextInfraConstantsCodegenProject.CUSTOM_MAKE_FILENAME}."
                ),
            ),
        ] = ()

        @u.model_validator(mode="after")
        def _validate_project_check_gates(self) -> Self:
            """Project gates must be unique and must not shadow a built-in."""
            if len(set(self.project_check_gates)) != len(self.project_check_gates):
                msg = "make project_check_gates must be unique"
                raise ValueError(msg)
            builtin = set(FlextInfraConstantsMake.CANONICAL_GATE_IDS)
            shadowed = sorted(set(self.project_check_gates) & builtin)
            if shadowed:
                msg = (
                    "make project_check_gates shadow built-in gates: "
                    f"{', '.join(shadowed)}"
                )
                raise ValueError(msg)
            return self

        @u.model_validator(mode="after")
        def _validate_verbs(self) -> Self:
            """Validate declared public verbs against workflow and contract.

            Why there is no `"setup" in declared` rejection here (flext-lq86m):
            the message it carried -- "make setup cannot require the managed
            validation environment" -- is a statement about a verb's
            ENVIRONMENT DEPENDENCY, not about the name `setup`. Testing the
            name was the wrong predicate, and it contradicted
            `config/codegen.yaml`, which declares `setup` as a public verb; the
            config singleton builds eagerly at import, so every entrypoint died
            on that contradiction. The real invariant is enforced structurally
            in the template, which excludes `setup` from
            `_builtin_require_environment` (`$(filter-out setup,$(PUBLIC_VERBS))`
            and `{% raw %}{% for verb in make.verbs if verb.name != "setup" %}{% endraw %}`),
            so `setup` never depends on the environment it exists to create.
            """
            declared = {verb.name for verb in self.verbs}
            if len(declared) != len(self.verbs):
                msg = "make public verb names must be unique"
                raise ValueError(msg)
            # Why (hq-36xk, flext-lq86m): the guard that lived here read
            # `if "setup" in serialized` and protected `make setup` from being
            # placed in the serialized mutation set, so it could never require
            # the managed validation environment it is supposed to CREATE.
            # 3e5fbc747 exterminated the serialize-make lifecycle and deleted
            # `self.serialization`, but rebound this condition to `declared`
            # instead of removing it with the concept it guarded. `setup` is a
            # mandatory canonical verb, so the inverted check rejected every
            # valid configuration and `flext_infra.config` could not be built at
            # all. The serialized set no longer exists; the guard has no object.
            workflow_verbs = tuple(step.verb for step in self.workflow)
            if len(set(workflow_verbs)) != len(workflow_verbs):
                msg = "make workflow verbs must be unique"
                raise ValueError(msg)
            unknown_workflow = set(workflow_verbs) - declared
            if unknown_workflow:
                msg = (
                    "make workflow verbs are not declared public verbs: "
                    f"{', '.join(sorted(unknown_workflow))}"
                )
                raise ValueError(msg)
            if "docs" not in declared:
                msg = "make docs verb must be declared"
                raise ValueError(msg)
            if (
                self.docs.reports_dir.is_absolute()
                or ".." in self.docs.reports_dir.parts
            ):
                msg = "make docs reports_dir must be repository-relative"
                raise ValueError(msg)
            return self

        @m.computed_field
        @property
        def check_gates_allowed(self) -> t.VariadicTuple[str]:
            """Canonical generated Make check-gate vocabulary.

            The built-in gates this package implements, plus the gates the
            project declares for itself. The built-in tuple is the BASE, never
            the whole vocabulary: a consuming repository owns gates this
            package knows nothing about, and rejecting them as unknown is what
            kept working handlers unreachable from `make check`.
            """
            return (
                *FlextInfraConstantsMake.CANONICAL_GATE_IDS,
                *self.project_check_gates,
            )

        @m.computed_field
        @property
        def check_gates_default(self) -> t.VariadicTuple[str]:
            """Canonical generated Make default check gates.

            A declared project gate runs by default, exactly like a built-in:
            a gate that must be asked for by name is a gate nobody runs.
            """
            return (
                *FlextInfraConstantsMake.CANONICAL_DEFAULT_GATE_IDS,
                *self.project_check_gates,
            )

        @m.computed_field
        @property
        def check_gates_fixable(self) -> t.VariadicTuple[str]:
            """Gates ``make fix`` can actually repair.

            Asking for a gate that cannot fix anything still pays its full cost;
            a fix pass built from the ALLOWED vocabulary once timed out doing
            exactly that.
            """
            return FlextInfraConstantsMake.CANONICAL_FIXABLE_GATE_IDS

        @m.computed_field
        @property
        def custom_handler_policies(
            self,
        ) -> Mapping[str, FlextInfraConfigModels.CustomHandlerPolicy]:
            """Effective custom-handler policy for every Make profile.

            The base policy states the strictest contract (private handlers
            only). A profile whose custom surface legitimately owns more --
            a workspace root orchestrating its subprojects -- declares only the
            fields it relaxes, so the engine never has to know which project
            it is conforming.
            """
            base = self.custom_handler_policy
            overrides = self.custom_handler_profile_overrides
            # Keys are normalised to the profile's string value: MakeProfile is a
            # StrEnum, so a raw YAML key and its enum subproject must land on the SAME
            # entry. Mixing both would make a lookup silently miss and fall back to
            # the strict base policy.
            return {
                str(profile): (
                    base.model_copy(update=override.model_dump(exclude_none=True))
                    if (override := overrides.get(str(profile)))
                    else base
                )
                for profile in (
                    *overrides,
                    *FlextInfraConstantsCodegenProject.MakeProfile,
                )
            }

    class ManagedFileSpec(_ConfigContract):
        """One versioned file governed by codegen lifecycle policy."""

        path: Annotated[Path, m.Field(description="Repository-relative file path")]
        owner: Annotated[t.NonEmptyStr, m.Field(description="Canonical owner")]
        policy: Annotated[
            Literal["full", "merge", "create-only", "delegated", "manual"],
            m.Field(
                description=(
                    "Conform ownership and mutation policy; create-only files are "
                    "emitted during creation, preserved when present, and never "
                    "backfilled into existing trees"
                )
            ),
        ]
        mode: Annotated[
            int,
            m.Field(
                ge=0,
                le=0o7777,
                strict=True,
                description="Exact permission bits owned by generated publication",
            ),
        ] = 0o644
        conflict_sections: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Dotted sections the owner renders, so a merge conflict in "
                    "them is resolvable by re-rendering rather than by hand. A "
                    "section the owner produces but does not declare here "
                    "dead-ends the merge: absorbing an integration base that "
                    "still carries the previous projection leaves a conflict "
                    "the canonical surface cannot resolve."
                )
            ),
        ] = ()
        preserve_project_keys: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "CUSTOM PEP 621 [project] keys kept from the live file when "
                    "policy is merge."
                )
            ),
        ] = ()
        overwrite_project_keys: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "MANAGED PEP 621 [project] keys the template overwrites. "
                    "Must be disjoint from preserve_project_keys."
                )
            ),
        ] = ()

        @m.computed_field
        @property
        def managed_tool_tables(self) -> t.VariadicTuple[str]:
            """First ``tool.*`` segment of each declared conflict section."""
            return tuple(
                dict.fromkeys(
                    section.split(".", 1)[1].split(".", 1)[0]
                    for section in self.conflict_sections
                    if section.startswith("tool.") and "." in section
                )
            )

    class ExternallyManagedSpec(_ConfigContract):
        """One externally-managed file declared by a .gen contract.

        Replaces the old bypass policies (manual/delegated/create-only) with
        an explicit, auditable ownership declaration. The file is not generated
        from a .j2 template but is still subject to .gen compliance validation.
        """

        owner: Annotated[t.NonEmptyStr, m.Field(description="Canonical external owner")]
        validation: Annotated[
            Literal["exists_and_validated", "conforms_to_layout", "exists_or_absent"],
            m.Field(
                description=(
                    "Validation contract: exists_and_validated = file must exist "
                    "and pass schema/layout checks; conforms_to_layout = file must "
                    "pass the layout engine; exists_or_absent = file may exist "
                    "(create-only semantics) but must not be regenerated"
                )
            ),
        ]
        description: Annotated[
            t.NonEmptyStr,
            m.Field(description="Human-readable purpose of this external file"),
        ]

    class TemplateEntrySpec(_ConfigContract):
        """One scaffold-only template mapping consumed by ``codegen new``."""

        source: Annotated[Path, m.Field(description="Template-root-relative source")]
        destination: Annotated[
            t.NonEmptyStr,
            m.Field(description="Tokenized repository-relative destination"),
        ]
        profiles: Annotated[
            t.VariadicTuple[FlextInfraConstantsCodegenProject.MakeProfile],
            m.Field(description="Profiles that consume the template"),
        ]
        delegate: Annotated[
            t.NonEmptyStr, m.Field(description="Canonical rendering delegate")
        ]
        overwrite: Annotated[
            bool, m.Field(description="Whether the template owns existing content")
        ] = False

    class TemplatesSpec(_ConfigContract):
        """New-project scaffold root and its complete ordered manifest."""

        root: Annotated[Path, m.Field(description="Package-relative template root")]
        entries: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.TemplateEntrySpec],
            m.Field(description="Complete ordered template manifest"),
        ]

    class ScaffoldBuildSpec(_ConfigContract):
        """Configured Python build backend for newly scaffolded projects."""

        backend: Annotated[t.NonEmptyStr, m.Field(description="PEP 517 backend")]
        requirements: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Build-system requirements"),
        ]

    class ScaffoldDependencyProfileSpec(_ConfigContract):
        """Dependencies selected by the declared upstream FLEXT facade."""

        upstream: Annotated[
            t.NonEmptyStr, m.Field(description="Supported upstream facade package")
        ]
        project: Annotated[
            t.NonEmptyStr | None,
            m.Field(
                description="Distribution receiving additional requirements; unset selects the shared upstream profile"
            ),
        ] = None
        runtime: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Runtime requirements"),
        ]
        codegen: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Code-generation requirements"),
        ] = ()

    class ScaffoldProjectSpec(_ConfigContract):
        """Project metadata policy for newly scaffolded distributions."""

        readme: Annotated[t.NonEmptyStr, m.Field(description="PEP 621 readme path")]
        supported_licenses: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Licenses with complete templates"),
        ]
        classifiers: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Default PyPI classifiers"),
        ]
        keywords: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Default project keywords"),
        ] = ()
        copyright_year: Annotated[
            int,
            m.Field(
                ge=2025,
                description=(
                    "LICENSE/NOTICE year for existing-tree ProjectSpec. "
                    "Override scaffold.project.copyright_year; gen must not "
                    "use the clock."
                ),
            ),
        ]
        dev: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description="Canonical development and validation requirements",
            ),
        ]
        dependency_profiles: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.ScaffoldDependencyProfileSpec],
            m.Field(min_length=1, description="Upstream dependency profiles"),
        ]

    class ScaffoldPingExampleSpec(_ConfigContract):
        """Values for the functional ping example created only by codegen new."""

        command_name: Annotated[
            t.NonEmptyStr, m.Field(description="Public CLI command")
        ]
        help_text: Annotated[
            t.NonEmptyStr, m.Field(description="Public CLI command help")
        ]
        success_message: Annotated[
            t.NonEmptyStr, m.Field(description="CLI success message")
        ]
        enabled_default: Annotated[
            bool, m.Field(description="Default runtime enablement")
        ]
        reply: Annotated[t.NonEmptyStr, m.Field(description="Enabled ping response")]
        disabled_reply: Annotated[
            t.NonEmptyStr, m.Field(description="Disabled ping response")
        ]

    class ScaffoldGitignoreSectionSpec(_ConfigContract):
        """One configured section of the generated Git ignore policy."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Section heading")]
        patterns: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Ignored path patterns"),
        ]
        profiles: Annotated[
            t.VariadicTuple[FlextInfraConstantsCodegenProject.MakeProfile],
            m.Field(
                description=(
                    "Make profiles this section applies to; empty means every "
                    "profile (universal). Sections that only make sense at the "
                    "superproject root (subproject-directory allowlists, workspace "
                    "manifest, submodule/Beads coordination) declare "
                    "[workspace] so subprojects and standalone projects never "
                    "receive the phantom entries."
                )
            ),
        ] = ()

    class ScaffoldSpec(_ConfigContract):
        """Complete typed policy consumed only by new-project templates."""

        build: Annotated[
            FlextInfraConfigModels.ScaffoldBuildSpec,
            m.Field(description="Build-system policy"),
        ]
        project: Annotated[
            FlextInfraConfigModels.ScaffoldProjectSpec,
            m.Field(description="Project metadata and dependency policy"),
        ]
        ping_example: Annotated[
            FlextInfraConfigModels.ScaffoldPingExampleSpec,
            m.Field(description="Functional scaffold example"),
        ]
        gitignore_sections: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.ScaffoldGitignoreSectionSpec],
            m.Field(min_length=1, description="Generated Git ignore sections"),
        ]

    class GitignoreRenderContext(_ConfigContract):
        """Profile-filtered input consumed by the Git ignore template."""

        gitignore_sections: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.ScaffoldGitignoreSectionSpec],
            m.Field(min_length=1, description="Applicable Git ignore sections"),
        ]

    class RepositoryRef(_ConfigContract):
        """One declared repository and its immutable Git origin contract."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(use_enum_values=False)

        name: Annotated[t.NonEmptyStr, m.Field(description="Catalog key")]
        distribution: Annotated[
            t.NonEmptyStr, m.Field(description="Python distribution or repository name")
        ]
        url: Annotated[
            t.NonEmptyStr,
            m.Field(description="Canonical GitHub clone URL ending in .git"),
        ]
        path: Annotated[
            Path, m.Field(description="POSIX path relative to its workspace root")
        ]
        role: Annotated[
            FlextInfraConstantsCodegenProject.MakeProfile,
            m.Field(description="Repository role in the declared topology"),
        ]
        state: Annotated[
            FlextInfraConstantsCodegenProject.RepositoryState,
            m.Field(description="Repository lifecycle state"),
        ] = FlextInfraConstantsCodegenProject.RepositoryState.ACTIVE
        checkout: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Physical checkout topology of the declared tree; "
                    "'root' marks the workspace's own primary checkout"
                )
            ),
        ] = "root"
        provider: Annotated[
            t.NonEmptyStr,
            m.Field(description="Provider key from the codegen configuration"),
        ]
        kind: Annotated[
            FlextInfraConstantsCodegenProject.ProjectKind,
            m.Field(
                description=(
                    "Governance kind; only internal_flext repositories are "
                    "rewritten by generation"
                )
            ),
        ]
        codegen: Annotated[
            FlextInfraConstantsCodegenProject.CodegenKind,
            m.Field(description="Repository code-generation policy"),
        ]
        package: Annotated[
            bool, m.Field(description="Repository publishes a Python package")
        ]
        editable: Annotated[
            bool, m.Field(description="Overlay repository as an editable dependency")
        ]
        read_only: Annotated[
            bool, m.Field(description="Repository rejects generated mutations")
        ]
        uv_link_mode: Annotated[
            Literal["clone", "copy", "hardlink", "symlink"] | None,
            m.Field(
                description=(
                    "Repository-specific uv installation link mode; absent uses "
                    "the fleet toolchain default"
                )
            ),
        ] = None
        duplication_trees: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Project-relative directory trees the duplication gate "
                    "must scan besides the canonical src/tests scope (e.g. "
                    "declared Helm charts)"
                )
            ),
        ] = ()
        extra_verbs: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.MakeVerbSpec],
            m.Field(
                description=(
                    "Additional public Make verbs this repository dispatches "
                    "beyond the canonical set (e.g. a script command framework)"
                )
            ),
        ] = ()
        script_dispatch: Annotated[
            FlextInfraConfigModels.ScriptDispatchSpec | None,
            m.Field(
                description=(
                    "Opt-in script command-framework routing for non-builtin "
                    "verbs and WHAT selectors; None keeps builtin-only dispatch"
                )
            ),
        ] = None
        dependency_cooldown_exclusions: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Repository-specific package distributions frozen at their "
                    "current floor by the dependency cooldown policy"
                ),
            ),
        ] = ()
        dependency_cooldown_overrides: Annotated[
            t.MappingKV[str, str],
            m.Field(
                default_factory=immutable_empty_mapping,
                description=(
                    "Repository-specific per-package cooldown override cutoff dates; "
                    "maps distribution name to a PEP 440 version cutoff string"
                ),
            ),
        ]

    class BeadsProjectSpec(_ConfigContract):
        """Repository-local Beads identity from ``config/beads.yaml``."""

        version: Annotated[
            Literal[1],
            m.Field(description="Beads project configuration schema version"),
        ]
        workspace: Annotated[
            t.NonEmptyStr, m.Field(description="Stable workspace identity")
        ]
        database: Annotated[
            t.NonEmptyStr, m.Field(description="Repository-owned Dolt database")
        ]
        issue_prefix: Annotated[
            t.NonEmptyStr, m.Field(description="Repository-owned issue prefix")
        ]
        custom_issue_types: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description="Repository-owned custom types beyond the Gas City baseline"
            ),
        ] = ()

        @u.model_validator(mode="after")
        def _validate_custom_issue_types(self) -> Self:
            """Reject duplicate project extensions before projection."""
            if len(set(self.custom_issue_types)) != len(self.custom_issue_types):
                msg = "beads custom_issue_types must be unique"
                raise ValueError(msg)
            return self

    class RepositoryConformTarget(_ConfigContract):
        """Runtime-derived conformance identity for one repository."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(use_enum_values=False)

        repository: Annotated[
            FlextInfraConfigModels.RepositoryRef,
            m.Field(description="Declared immutable repository identity"),
        ]
        root: Annotated[
            Path, m.Field(description="Resolved repository root receiving conformance")
        ]
        make_profile: Annotated[
            FlextInfraConstantsCodegenProject.MakeProfile,
            m.Field(description="Make profile inferred from live Git topology"),
        ]
        beads: Annotated[
            FlextInfraConfigModels.BeadsProjectSpec,
            m.Field(description="Repository-local Beads identity"),
        ]
        project: Annotated[
            FlextInfraConfigModels.ProjectSpec | None,
            m.Field(
                description=(
                    "Declared project metadata of the manifest, when the "
                    "repository declares one; carries the distribution roots "
                    "the packaging phase must prove present"
                )
            ),
        ] = None
        canonical_project_name: Annotated[
            t.NonEmptyStr, m.Field(description="Canonical PEP 621 project name")
        ]
        baseline_branch: Annotated[
            t.NonEmptyStr,
            m.Field(description="Provider-owned integration ancestry baseline"),
        ]
        baseline_reference: Annotated[
            t.NonEmptyStr,
            m.Field(
                description="Exact local or remote Git ref used as ancestry baseline"
            ),
        ]
        ci_enabled: Annotated[
            bool, m.Field(description="Whether conform owns the CI projection")
        ]
        gascity_enabled: Annotated[
            bool,
            m.Field(
                description=(
                    "Whether the repository consumes the Gas City runtime "
                    "contract; gates the gc tool projection and the inherited "
                    "Dolt endpoint keys at render time."
                )
            ),
        ] = True
        external_dependency_paths: Annotated[
            t.VariadicTuple[Path],
            m.Field(description="Observed external or fork Git submodule paths"),
        ] = ()
        technical_branch_patterns: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Technical branches excluded from ancestry policy"),
        ] = ()
        governed_branch_patterns: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description=(
                    "Development lines gated by ancestry policy; required because "
                    "an empty tuple would match no ref and silently disable the "
                    "gate instead of failing closed"
                ),
            ),
        ]

    class ManagedGitlinkSpec(_ConfigContract):
        """One governed submodule with its provider-owned baseline branch."""

        repository: Annotated[
            FlextInfraConfigModels.RepositoryRef,
            m.Field(description="Governed repository identity"),
        ]
        branch: Annotated[
            t.NonEmptyStr,
            m.Field(description="Declared gitlink branch (. follows the superproject)"),
        ]

    class MakeCommandContext(_ConfigContract):
        """Shared command identity required by every generated Make surface."""

        infra_cli: Annotated[
            t.NonEmptyStr, m.Field(description="Installed infrastructure CLI command")
        ]
        pytest: Annotated[
            FlextInfraModelsDepsToolSettings.PytestConfig,
            m.Field(description="Typed pytest execution policy"),
        ]

    class MakefileRenderSpec(MakeCommandContext):
        """Field-only render input for an existing repository Makefile."""

        mise_bootstrap: Annotated[
            FlextInfraConfigModels.MiseBootstrapEnvironmentSpec,
            m.Field(description="Generated strict Mise bootstrap environment"),
        ]

        dist: Annotated[t.NonEmptyStr, m.Field(description="PEP 621 project name")]
        state_directory_name: Annotated[
            t.NonEmptyStr,
            m.Field(description="External runtime state directory beside checkout"),
        ]
        scratch_namespace: Annotated[
            t.NonEmptyStr,
            m.Field(description="Scratch namespace below external project state"),
        ]
        make_profile: Annotated[
            FlextInfraConstantsCodegenProject.MakeProfile,
            m.Field(description="Selected repository Make profile"),
        ]
        repository_root_rel: Annotated[
            t.NonEmptyStr, m.Field(description="Relative workspace root path")
        ]
        workspace_subprojects: Annotated[
            t.VariadicTuple[str],
            m.Field(description="Declared workspace subproject paths"),
        ] = ()
        workspace_repositories: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.RepositoryRef],
            m.Field(description="Repositories editable from the selected workspace"),
        ] = ()
        workspace_gitlinks: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.ManagedGitlinkSpec],
            m.Field(description="Provider-resolved governed Git submodules"),
        ] = ()
        uv_link_mode: Annotated[
            t.NonEmptyStr, m.Field(description="Configured uv installation link mode")
        ]
        uv_version: Annotated[
            t.NonEmptyStr,
            m.Field(description="mise-owned uv version used by bootstrap validation"),
        ]
        make: Annotated[
            FlextInfraConfigModels.MakeSpec,
            m.Field(description="Generated Make command contract"),
        ]
        extra_verbs: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.MakeVerbSpec],
            m.Field(description="Repository-specific public Make verbs"),
        ] = ()
        script_dispatch: Annotated[
            FlextInfraConfigModels.ScriptDispatchSpec | None,
            m.Field(description="Optional script command dispatch contract"),
        ] = None

        makefile_custom_include: Annotated[
            t.NonEmptyStr,
            m.Field(description="Generated custom Make policy include directive"),
        ]
        workspace_cli_group: Annotated[
            t.NonEmptyStr,
            m.Field(description="CLI group used for workspace orchestration"),
        ]
        mypy_memory_limit_mb: Annotated[
            int, m.Field(gt=0, description="Generated Mypy address-space limit in MiB")
        ]
        mypy_timeout_seconds: Annotated[
            int, m.Field(gt=0, description="Generated Mypy wall-time limit in seconds")
        ]
        mypy_timeout_exit_code: Annotated[
            int, m.Field(gt=0, description="Wall-time limiter timeout exit code")
        ]
        mypy_signal_exit_offset: Annotated[
            int, m.Field(gt=0, description="Shell signal exit-code offset")
        ]
        prlimit_command: Annotated[
            t.NonEmptyStr, m.Field(description="Address-space limiter executable")
        ]
        prlimit_address_space_option: Annotated[
            t.NonEmptyStr, m.Field(description="Address-space limiter option")
        ]
        timeout_command: Annotated[
            t.NonEmptyStr, m.Field(description="Wall-time limiter executable")
        ]
        timeout_kill_after_seconds: Annotated[
            int, m.Field(gt=0, description="Forced-termination grace period")
        ]
        pytest_process_timeout_seconds: Annotated[
            int, m.Field(gt=0, description="Pytest process wall-time boundary")
        ]

    class BeadsConfigRenderSpec(_ConfigContract):
        """Field-only render input for the generated Beads ledger config."""

        issue_prefix: Annotated[
            t.NonEmptyStr,
            m.Field(description="Issue prefix from local config/beads.yaml"),
        ]
        endpoint_origin: Annotated[
            Literal["inherited_city"],
            m.Field(description="Gas City endpoint ownership projection"),
        ]
        endpoint_status: Annotated[
            Literal["verified"],
            m.Field(description="Gas City inherited endpoint status"),
        ]
        gascity_enabled: Annotated[
            bool,
            m.Field(
                description=(
                    "Gas City runtime-contract participation; False drops the "
                    "gc endpoint keys and makes Beads own a repository-local "
                    "Dolt server (dolt.auto-start: true)."
                )
            ),
        ] = True
        custom_issue_types: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Union of project and required custom bead types"),
        ] = ()
        dolt_mode: Annotated[
            t.NonEmptyStr, m.Field(description="From toolchain.beads.dolt_mode")
        ]
        export_auto: Annotated[
            bool, m.Field(description="From toolchain.beads.export_auto")
        ]
        backup_enabled: Annotated[
            bool, m.Field(description="From toolchain.beads.backup_enabled")
        ]
        dolt_disable_event_flush: Annotated[
            bool, m.Field(description="From toolchain.beads.dolt_disable_event_flush")
        ]

    class MiseTomlRenderSpec(ToolchainSpec):
        """Toolchain render context for ``.mise.toml`` plus per-project gates.

        The template consumes flat toolchain field names, so the context is the
        fleet ToolchainSpec narrowed by the per-project Gas City participation
        resolved from the workspace manifest overlay.
        """

        gascity_enabled: Annotated[
            bool,
            m.Field(
                description=("Whether the gc tool block is projected into .mise.toml.")
            ),
        ] = True

    class BeadsMetadataRenderSpec(_ConfigContract):
        """Field-only render input for the generated Beads ledger marker.

        The marker carries portable storage and database identity plus the
        checkout's ledger identity. ``project_id`` is NOT invented here: it is
        read back from the checkout's own ``.beads/identity.toml`` so a
        regeneration preserves it. Omitting it made every ``make gen`` strip the
        key, and Beads then minted a fresh identity on next access — observed in
        rig ``gmn`` (commit 3e7ba1e), where the ledger identity changed from
        2b1a0582-… to e9a551fc-…. ``None`` means the checkout has no ledger
        identity yet, and Beads mints the first one.
        """

        database: Annotated[
            t.NonEmptyStr,
            m.Field(description="Dolt database from local config/beads.yaml"),
        ]
        project_id: Annotated[
            t.NonEmptyStr | None,
            m.Field(
                default=None,
                description=(
                    "Ledger identity read back from .beads/identity.toml; "
                    "None only before Beads has minted one"
                ),
            ),
        ] = None

    class GitignoreRenderSpec(_ConfigContract):
        """Typed, profile-filtered input for the generated Git ignore file."""

        gitignore_sections: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.ScaffoldGitignoreSectionSpec],
            m.Field(
                min_length=1,
                description="Canonical ignore sections applicable to one profile",
            ),
        ]

    class StaticTextRenderSpec(_ConfigContract):
        """Empty typed context for a variable-free governed text template."""

    class ReleaseAutomationOverrideSpec(_ConfigContract):
        """One distribution's deviation from the shared release contract."""

        release_branch: Annotated[
            t.NonEmptyStr | None,
            m.Field(default=None, description="Branch that produces releases"),
        ] = None
        build_command: Annotated[
            t.NonEmptyStr | None,
            m.Field(default=None, description="Command that produces the artifacts"),
        ] = None
        version_variables: Annotated[
            tuple[t.NonEmptyStr, ...],
            m.Field(description="Extra file:variable version anchors"),
        ] = ()

    class ReleaseAutomationSpec(_ConfigContract):
        """Automated semantic versioning, owned by the market tool.

        Why: bump_version/parse_semver and the release orchestrator already
        existed, but nothing DERIVED the bump -- a human passed
        ``bump=minor`` by hand, which is exactly the judgement the commit
        history already encodes and the one a human gets wrong. Conventional
        Commits plus python-semantic-release replace that judgement with a
        rule, and replace local implementation with a maintained dependency.

        Declared once here so every generated pyproject carries the same
        contract. A project that genuinely differs is expressed in
        ``overrides``, never by editing its own pyproject.
        """

        tool: Annotated[
            t.NonEmptyStr, m.Field(description="Release automation distribution")
        ]
        runner: Annotated[
            t.NonEmptyStr, m.Field(description="Command runner that invokes the tool")
        ]
        commit_parser: Annotated[
            t.NonEmptyStr, m.Field(description="Commit convention driving the bump")
        ]
        release_branch: Annotated[
            t.NonEmptyStr, m.Field(description="Branch that produces releases")
        ]
        version_variables: Annotated[
            tuple[t.NonEmptyStr, ...],
            m.Field(description="file:variable anchors the tool rewrites"),
        ]
        version_toml: Annotated[
            tuple[t.NonEmptyStr, ...],
            m.Field(description="file:tomlpath anchors the tool rewrites"),
        ]
        build_command: Annotated[
            t.NonEmptyStr, m.Field(description="Command that produces the artifacts")
        ]
        tag_format: Annotated[
            t.NonEmptyStr, m.Field(description="Tag shape, shared with the workflow")
        ]
        changelog_file: Annotated[
            t.NonEmptyStr, m.Field(description="Generated changelog destination")
        ]
        overrides: Annotated[
            Mapping[
                t.NonEmptyStr, FlextInfraConfigModels.ReleaseAutomationOverrideSpec
            ],
            m.Field(
                default_factory=ImmutableEmptyMapping,
                description="Per-distribution deviations from the shared contract",
            ),
        ]

        @u.model_validator(mode="after")
        def _validate_anchors(self) -> Self:
            """Every anchor must name a target, or the tool rewrites nothing."""
            for anchor in (*self.version_variables, *self.version_toml):
                if ":" not in anchor:
                    msg = f"release version anchor must be '<file>:<target>': {anchor}"
                    raise ValueError(msg)
            return self

    class SgconfigRenderSpec(_ConfigContract):
        """Typed input for the generated ast-grep project config.

        Why (ai-hub-qwoc): a provider manifest can declare ``sgconfig.yml`` as a
        required surface, but no generator owned it, so the file was authored by
        hand in one repository and simply absent in another -- provider discovery
        then failed closed with ``missing declared file: sgconfig.yml``. The rule
        and fixture directories are declared here so every repository renders the
        same contract from the SSOT instead of a hand-written copy.
        """

        rule_dirs: Annotated[
            tuple[str, ...],
            m.Field(
                min_length=1,
                description="Directories holding this project's ast-grep rules",
            ),
        ]
        test_dirs: Annotated[
            tuple[str, ...],
            m.Field(
                default=(),
                description="Directories holding rule fixtures and snapshots",
            ),
        ]

    # Project creation metadata remains a typed manifest input.
    class ProjectSpec(_ConfigContract):
        """Deterministic project metadata required to materialize a new tree."""

        package_name: Annotated[
            t.NonEmptyStr, m.Field(description="Import package name")
        ]
        class_stem: Annotated[
            t.NonEmptyStr, m.Field(description="Canonical public facade class stem")
        ]
        namespace: Annotated[
            t.NonEmptyStr, m.Field(description="Nested c/t/p/m/u namespace")
        ]
        constant_name: Annotated[
            t.NonEmptyStr,
            m.Field(description="Configured project name exposed through constants"),
        ]
        namespace_attribute: Annotated[
            t.NonEmptyStr, m.Field(description="Private module namespace token")
        ]
        alias: Annotated[
            t.NonEmptyStr, m.Field(description="Canonical public instance alias")
        ]
        environment_prefix: Annotated[
            t.NonEmptyStr, m.Field(description="Project settings environment prefix")
        ]
        description: Annotated[
            t.NonEmptyStr, m.Field(description="Project description")
        ]
        license: Annotated[t.NonEmptyStr, m.Field(description="SPDX license id")]
        author_name: Annotated[
            t.NonEmptyStr, m.Field(description="Author display name")
        ]
        author_email: Annotated[t.NonEmptyStr, m.Field(description="Author email")]
        upstream: Annotated[
            t.NonEmptyStr, m.Field(description="Upstream FLEXT facade module")
        ]
        namespace_scan_dirs: Annotated[
            t.StrSequence,
            m.Field(
                description=(
                    "Production source roots the namespace validator enforces; "
                    "empty keeps every root in scope (previous behavior)"
                )
            ),
        ] = ()
        inherited_facets: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Upstream facets re-exported by the project root. The lazy-init "
                    "public-root planner reads this to decide which upstream "
                    "namespace names the generated root __init__ may re-export: a "
                    "facet is inherited when declared here or actually imported "
                    "from source. Without the field the planner cannot honour a "
                    "manifest declaration and re-exports only what source imports "
                    "prove -- which silently drops manifest-declared facets."
                ),
            ),
        ] = ()
        root_packages: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Additional top-level packages under the source directory "
                    "that the distribution must ship beyond the primary "
                    "package. Declared per repository because the layout is a "
                    "fact of that repository, not of its upstream profile."
                ),
            ),
        ] = ()
        root_modules: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Top-level single-file modules under the source directory "
                    "shipped alongside the packages; see the root_packages "
                    "namesake for why the declaration is per repository."
                ),
            ),
        ] = ()
        runtime_dependency_overlay: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Runtime requirements this repository adds ahead of its "
                    "dependency profile's runtime set. The profile states what "
                    "every project on that upstream needs; the overlay states "
                    "what this one additionally needs, so neither owner has to "
                    "encode the other's scope."
                ),
            ),
        ] = ()
        homepage: Annotated[t.NonEmptyStr, m.Field(description="Project homepage")]
        documentation: Annotated[
            t.NonEmptyStr, m.Field(description="Project documentation URL")
        ]
        repository_root_rel: Annotated[
            t.NonEmptyStr,
            m.Field(description="Declared relative path to the workspace root"),
        ]
        year: Annotated[int, m.Field(ge=2025, description="Copyright year")]

    class MakeRenderContext(MakeCommandContext):
        """Typed input consumed by the generated Make surface."""

        mise_bootstrap: Annotated[
            FlextInfraConfigModels.MiseBootstrapEnvironmentSpec,
            m.Field(description="Generated strict Mise bootstrap environment"),
        ]

        make: Annotated[
            FlextInfraConfigModels.MakeSpec,
            m.Field(description="Generated Make command contract"),
        ]
        mypy_memory_limit_mb: Annotated[
            int, m.Field(gt=0, description="Generated Mypy address-space limit in MiB")
        ]
        mypy_timeout_seconds: Annotated[
            int, m.Field(gt=0, description="Generated Mypy wall-time limit in seconds")
        ]
        mypy_timeout_exit_code: Annotated[
            int, m.Field(gt=0, description="Wall-time limiter timeout exit code")
        ]
        mypy_signal_exit_offset: Annotated[
            int, m.Field(gt=0, description="Shell signal exit-code offset")
        ]
        prlimit_command: Annotated[
            t.NonEmptyStr, m.Field(description="Address-space limiter executable")
        ]
        prlimit_address_space_option: Annotated[
            t.NonEmptyStr, m.Field(description="Address-space limiter option")
        ]
        timeout_command: Annotated[
            t.NonEmptyStr, m.Field(description="Wall-time limiter executable")
        ]
        timeout_kill_after_seconds: Annotated[
            int, m.Field(gt=0, description="Forced-termination grace period")
        ]
        tooling_runtime: Annotated[
            FlextInfraModelsDepsToolSettings.ToolingRuntimeContext,
            m.Field(description="Resolved project/workspace tooling values"),
        ]

        dist: Annotated[t.NonEmptyStr, m.Field(description="Distribution name")]

        python_version: Annotated[
            t.NonEmptyStr, m.Field(description="Python major.minor tool value")
        ]
        uv_link_mode: Annotated[
            t.NonEmptyStr, m.Field(description="Configured uv installation link mode")
        ]
        ruff_per_file_ignores: Annotated[
            t.MappingKV[str, t.StrSequence],
            m.Field(
                default_factory=immutable_empty_mapping,
                description=(
                    "Effective Ruff exemptions: fleet policy composed with this "
                    "repository's own ManagedArtifacts overlay"
                ),
            ),
        ]
        make_profile: Annotated[
            FlextInfraConstantsCodegenProject.MakeProfile,
            m.Field(description="Generated Make execution profile"),
        ]
        repository_root_rel: Annotated[
            t.NonEmptyStr,
            m.Field(description="Relative path to the declared workspace root"),
        ]
        makefile_custom_include: Annotated[
            str,
            m.Field(
                min_length=1,
                description=("Make directive that includes the custom Make surface"),
            ),
        ]
        workspace_subprojects: Annotated[
            t.VariadicTuple[str],
            m.Field(description="Ordered workspace subproject paths"),
        ] = ()
        workspace_repositories: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.RepositoryRef],
            m.Field(description="Ordered workspace subproject records"),
        ] = ()
        workspace_gitlinks: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.ManagedGitlinkSpec],
            m.Field(description="Provider-resolved governed Git submodules"),
        ] = ()
        extra_verbs: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.MakeVerbSpec],
            m.Field(description="Repository-specific additional public Make verbs"),
        ] = ()
        script_dispatch: Annotated[
            FlextInfraConfigModels.ScriptDispatchSpec | None,
            m.Field(description="Opt-in script command-framework routing contract"),
        ] = None
        workspace_cli_group: Annotated[
            str,
            m.Field(
                description=(
                    "CLI group name for the flext-infra workspace orchestrate route"
                )
            ),
        ] = ""
        uv_exclude_newer: Annotated[
            t.NonEmptyStr,
            m.Field(
                description="uv [tool.uv] exclude-newer cutoff rendered into pyproject.toml"
            ),
        ]
        dependency_cooldown_exclusions: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Fleet-wide package distributions frozen at their current floor "
                    "by the dependency cooldown policy"
                )
            ),
        ] = ()
        dependency_cooldown_overrides: Annotated[
            t.MappingKV[str, str],
            m.Field(
                default_factory=immutable_empty_mapping,
                description=(
                    "Per-package cooldown cutoff dates overriding the fleet default"
                ),
            ),
        ]

    class ProjectRenderContext(MakeRenderContext):
        """Complete typed input consumed by project scaffold templates."""

        namespace_scan_dirs: Annotated[
            t.StrSequence,
            m.Field(
                description=(
                    "Production source roots rendered as the namespace "
                    "validator's declared scan scope; empty keeps every root "
                    "in scope"
                )
            ),
        ] = ()
        gate_budgets: Annotated[
            Mapping[str, Mapping[str, int]],
            m.Field(
                description=(
                    "Per-gate budget rows rendered as the managed "
                    "[tool.flext.project.budget] table; keys cover exactly "
                    "the gate registry"
                )
            ),
        ] = {}

        @m.computed_field
        @property
        def repository_env_prefix(self) -> str:
            """Settings environment prefix derived from the distribution name."""
            return f"{self.dist.upper().replace('-', '_')}_"

        scaffold: Annotated[
            FlextInfraConfigModels.ScaffoldSpec,
            m.Field(description="New-project scaffold policy"),
        ]
        gitignore_sections: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.ScaffoldGitignoreSectionSpec],
            m.Field(
                min_length=1,
                description=(
                    "Canonical .gitignore sections derived from the artifact SSOT"
                ),
            ),
        ]
        dependency_profile: Annotated[
            FlextInfraConfigModels.ScaffoldDependencyProfileSpec,
            m.Field(description="Resolved upstream dependency profile"),
        ]
        tooling: Annotated[
            FlextInfraModelsDepsToolSettings.ToolConfigDocument,
            m.Field(description="Canonical validated tooling policy"),
        ]
        environment_path_prepends: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Configured read-only PATH additions for direnv"),
        ] = ()
        beads_tool_selector: Annotated[
            t.NonEmptyStr, m.Field(description="Official Beads mise selector")
        ]
        beads_tool_version: Annotated[
            Literal["latest"], m.Field(description="Moving Beads release selector")
        ]
        beads_tool_prerelease: Annotated[
            bool,
            m.Field(description="Whether mise may resolve prerelease Beads versions"),
        ] = False
        beads: Annotated[
            FlextInfraConfigModels.BeadsProjectSpec,
            m.Field(description="Repository-local Beads identity"),
        ]
        canonical_project_name: Annotated[
            t.NonEmptyStr, m.Field(description="Canonical PEP 621 project name")
        ]
        const_name: Annotated[
            t.NonEmptyStr, m.Field(description="Configured constant project name")
        ]
        package_name: Annotated[
            t.NonEmptyStr, m.Field(description="Python import package name")
        ]
        packaged_data_dirs: Annotated[
            t.StrSequence,
            m.Field(description="Generated root data directories shipped in wheels"),
        ]
        class_stem: Annotated[
            t.NonEmptyStr, m.Field(description="Public facade class stem")
        ]
        ns: Annotated[t.NonEmptyStr, m.Field(description="Public model namespace")]
        ns_attr: Annotated[
            t.NonEmptyStr, m.Field(description="Private namespace module token")
        ]
        alias: Annotated[t.NonEmptyStr, m.Field(description="Public instance alias")]
        env_prefix: Annotated[
            t.NonEmptyStr, m.Field(description="Settings environment prefix")
        ]
        upstream: Annotated[
            t.NonEmptyStr, m.Field(description="Upstream FLEXT facade module")
        ]
        inherited_facets: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Upstream facets re-exported by the project root; see the "
                    "RepositoryRef namesake for the lazy-init contract."
                ),
            ),
        ] = ()
        root_packages: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Additional shipped top-level packages; see the ProjectSpec "
                    "namesake for the declaration contract."
                ),
            ),
        ] = ()
        root_modules: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Additional shipped top-level modules; see the ProjectSpec "
                    "namesake for the declaration contract."
                ),
            ),
        ] = ()
        runtime_dependency_overlay: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Repository-declared runtime requirements rendered ahead of "
                    "the dependency profile's runtime set; see the ProjectSpec "
                    "namesake."
                ),
            ),
        ] = ()
        description: Annotated[
            t.NonEmptyStr, m.Field(description="Project description")
        ]
        version: Annotated[t.NonEmptyStr, m.Field(description="Project version")]
        license: Annotated[t.NonEmptyStr, m.Field(description="SPDX license id")]
        python_required_version: Annotated[
            t.NonEmptyStr, m.Field(description="PEP 440 project Python requirement")
        ]
        kubectl_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Exact kubectl toolchain version")
        ]
        helm_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Exact Helm toolchain version")
        ]
        kind_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Exact kind toolchain version")
        ]
        direnv_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Compatible direnv major.minor line")
        ]
        uv_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Compatible uv major.minor line")
        ]
        qlty_version: Annotated[
            t.NonEmptyStr,
            _tool_version_field("Moving qlty release selector, e.g. 'latest'"),
        ]
        node_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Compatible Node.js major.minor line")
        ]
        jscpd_version: Annotated[
            t.NonEmptyStr,
            _tool_version_field("Moving jscpd release selector, e.g. 'latest'"),
        ]
        waza_version: Annotated[
            t.NonEmptyStr,
            _tool_version_field("Moving Waza release selector, e.g. 'latest'"),
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
        scc_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Exact scc code-counter version")
        ]
        kubeconform_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Compatible kubeconform minor line")
        ]
        go_version: Annotated[
            t.NonEmptyStr, _tool_version_field("Exact Go runtime version")
        ]
        author_name: Annotated[
            t.NonEmptyStr, m.Field(description="Author display name")
        ]
        author_email: Annotated[t.NonEmptyStr, m.Field(description="Author email")]
        repository: Annotated[
            t.NonEmptyStr, m.Field(description="Project repository page URL")
        ]
        homepage: Annotated[t.NonEmptyStr, m.Field(description="Project homepage")]
        documentation: Annotated[
            t.NonEmptyStr, m.Field(description="Project documentation URL")
        ]
        flext_git_base_url: Annotated[
            t.NonEmptyStr, m.Field(description="FLEXT Git provider base URL")
        ]
        flext_git_branch: Annotated[
            t.NonEmptyStr, m.Field(description="FLEXT Git provider branch")
        ]
        repository_provider: Annotated[
            t.NonEmptyStr, m.Field(description="Repository provider catalog key")
        ]
        repository_git_url: Annotated[
            t.NonEmptyStr, m.Field(description="Canonical repository Git clone URL")
        ]
        repository_branch: Annotated[
            t.NonEmptyStr, m.Field(description="Canonical repository Git branch")
        ]
        year: Annotated[int, m.Field(description="Copyright year")]

    class WorkspaceBeadsServerSpec(_ConfigContract):
        """Optional Dolt connection declared by a versioned workspace manifest."""

        backend: Annotated[
            Literal["dolt"], m.Field(description="Workspace ledger storage engine")
        ]
        mode: Annotated[
            Literal["server"], m.Field(description="Workspace ledger connection mode")
        ]
        shared_server: Annotated[
            Literal[False],
            m.Field(description="Workspace ledger uses an external Dolt endpoint"),
        ] = False
        host: Annotated[t.NonEmptyStr, m.Field(description="Dolt server host")]
        port: Annotated[
            int, m.Field(ge=1, le=65535, description="Dolt server TCP port")
        ]
        user: Annotated[t.NonEmptyStr, m.Field(description="Dolt server user")]
        auto_commit: Annotated[
            Literal["off", "on", "batch"],
            m.Field(description="Dolt auto-commit policy"),
        ]

    class WorkspaceIntegrationSpec(_ConfigContract):
        """Workspace overlay for one provider integration branch."""

        provider: Annotated[
            t.NonEmptyStr, m.Field(description="Configured provider key")
        ]
        branch: Annotated[
            t.NonEmptyStr, m.Field(description="Workspace integration branch")
        ]
        organization: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Optional provider organization override"),
        ] = None
        base_url: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Optional provider base URL override"),
        ] = None

    class RepositoryPolicyOverlaySpec(_ConfigContract):
        """Bounded per-project policy declared by a workspace manifest."""

        project: Annotated[
            t.NonEmptyStr, m.Field(description="Canonical project distribution")
        ]
        beads_enabled: Annotated[
            bool, m.Field(description="Whether the repository participates in Beads")
        ] = False
        ci_enabled: Annotated[
            bool, m.Field(description="Whether conform owns the CI surface")
        ] = True
        ci_matrix_auto_run: Annotated[
            bool, m.Field(description="Whether the CI matrix runs automatically")
        ] = False
        gascity_enabled: Annotated[
            bool,
            m.Field(
                description=(
                    "Whether the repository consumes the Gas City runtime "
                    "contract (city-owned Dolt server, gc tool projection, "
                    "inherited endpoint keys). False renders the standalone "
                    "shape: repository-local Dolt server owned by Beads."
                )
            ),
        ] = True
        extra_ignored_patterns: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Repository-local generated ignore patterns"),
        ] = ()

    class WorkspaceExclusionSpec(_ConfigContract):
        """One explicitly excluded workspace-relative path."""

        path: Annotated[Path, m.Field(description="Workspace-relative path")]
        reason: Annotated[t.NonEmptyStr, m.Field(description="Exclusion rationale")]

    class WorkspaceManifestSpec(_ConfigContract):
        """Complete versioned input contract for ``config/workspace.yaml``."""

        version: Annotated[
            int,
            m.Field(
                ge=FlextInfraConstantsCodegenProject.WORKSPACE_MANIFEST_VERSION,
                le=FlextInfraConstantsCodegenProject.WORKSPACE_MANIFEST_VERSION,
                description="Workspace manifest schema version",
            ),
        ]
        name: Annotated[t.NonEmptyStr, m.Field(description="Workspace name")]
        ledger_id: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Optional workspace ledger database identity"),
        ] = None
        ledger_prefix: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Optional workspace issue-prefix identity"),
        ] = None
        beads_server: Annotated[
            FlextInfraConfigModels.WorkspaceBeadsServerSpec | None,
            m.Field(description="Optional workspace-local Dolt connection"),
        ] = None
        repository: Annotated[
            FlextInfraConfigModels.RepositoryRef,
            m.Field(description="Root repository declaration"),
        ]
        project: Annotated[
            FlextInfraConfigModels.ProjectSpec | None,
            m.Field(description="Optional project creation metadata"),
        ] = None
        members: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.RepositoryRef],
            m.Field(description="Declared member repository contracts"),
        ] = ()
        external_dependency_paths: Annotated[
            t.VariadicTuple[Path],
            m.Field(description="Declared external dependency paths"),
        ] = ()
        content_only: Annotated[
            t.VariadicTuple[Path], m.Field(description="Content-only Gitlink paths")
        ] = ()
        exclusions: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.WorkspaceExclusionSpec],
            m.Field(description="Explicit workspace exclusions"),
        ] = ()
        integration: Annotated[
            FlextInfraConfigModels.WorkspaceIntegrationSpec | None,
            m.Field(description="Optional integration provider overlay"),
        ] = None
        repository_policy_overlays: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.RepositoryPolicyOverlaySpec],
            m.Field(description="Repository-local policy overlays"),
        ] = ()

        @u.model_validator(mode="after")
        def _validate_references(self) -> Self:
            """Reject ambiguous paths and policy references in the full document."""
            external_paths = (*self.external_dependency_paths, *self.content_only)
            invalid_paths = tuple(
                path
                for path in external_paths
                if path.is_absolute() or not path.parts or ".." in path.parts
            )
            if invalid_paths:
                msg = "workspace dependency paths must be relative: " + ", ".join(
                    path.as_posix() for path in invalid_paths
                )
                raise ValueError(msg)
            member_paths = tuple(item.path for item in self.members)
            if len(set(member_paths)) != len(member_paths):
                msg = "composed project paths must be unique"
                raise ValueError(msg)
            if set(member_paths).intersection(external_paths):
                msg = "composed projects cannot also be external dependencies"
                raise ValueError(msg)
            projects = tuple(item.project for item in self.repository_policy_overlays)
            if len(set(projects)) != len(projects):
                msg = "repository policy overlays must be unique"
                raise ValueError(msg)
            repository_names = {
                item.distribution for item in (self.repository, *self.members)
            }
            unknown_projects = set(projects).difference(repository_names)
            if unknown_projects:
                msg = (
                    "repository policy overlays reference unknown projects: "
                    + ", ".join(sorted(unknown_projects))
                )
                raise ValueError(msg)
            return self

    class WorkspaceSpec(_ConfigContract):
        """Local identity plus topology read from this repository's Git inputs."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Workspace name")]
        beads: Annotated[
            FlextInfraConfigModels.BeadsProjectSpec,
            m.Field(description="Repository-local Beads identity"),
        ]
        gascity_enabled: Annotated[
            bool,
            m.Field(
                description=(
                    "Gas City runtime-contract participation resolved from the "
                    "matched repository policy overlay; True when the checkout "
                    "declares no manifest or no overlay."
                )
            ),
        ] = True
        repository: Annotated[
            FlextInfraConfigModels.RepositoryRef,
            m.Field(description="Local repository Git contract"),
        ]
        project: Annotated[
            FlextInfraConfigModels.ProjectSpec | None,
            m.Field(description="Metadata required only when materializing a new tree"),
        ] = None
        subprojects: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.RepositoryRef],
            m.Field(description="Direct governed repositories from local .gitmodules"),
        ] = ()
        external_dependency_paths: Annotated[
            t.VariadicTuple[Path],
            m.Field(description="Observed external or fork Git submodule paths"),
        ] = ()

        @u.model_validator(mode="after")
        def _validate_topology_paths(self) -> Self:
            """Reject duplicate, ambiguous, or escaping topology paths."""
            invalid_external_paths = tuple(
                path
                for path in self.external_dependency_paths
                if path.is_absolute() or not path.parts or ".." in path.parts
            )
            if invalid_external_paths:
                msg = (
                    "external dependency paths must be workspace-relative: "
                    f"{', '.join(path.as_posix() for path in invalid_external_paths)}"
                )
                raise ValueError(msg)
            if len(set(self.external_dependency_paths)) != len(
                self.external_dependency_paths
            ):
                msg = "external dependency paths must be unique"
                raise ValueError(msg)
            subproject_paths = {item.path for item in self.subprojects}
            if len(subproject_paths) != len(self.subprojects):
                msg = "subproject paths must be unique"
                raise ValueError(msg)
            overlap = subproject_paths.intersection(self.external_dependency_paths)
            if overlap:
                msg = (
                    "external dependencies cannot also be governed subprojects: "
                    f"{', '.join(sorted(path.as_posix() for path in overlap))}"
                )
                raise ValueError(msg)
            return self

    # The artifact list is the SINGLE SSOT for
    # ephemeral/generated resources; VS Code excludes and source_scan ignores
    # are derived projections, never re-declared in YAML.
    class CodegenArtifactSpec(_ConfigContract):
        """One ephemeral/generated resource every ignore/exclude derives from."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Basename of the resource")]
        is_dir: Annotated[bool, m.Field(description="Directory (vs file) resource")] = (
            True
        )
        vscode_exclude: Annotated[
            bool, m.Field(description="Feed VS Code files.exclude + search.exclude")
        ] = True
        watch_exclude: Annotated[
            bool, m.Field(description="Feed VS Code files.watcherExclude")
        ] = True
        gitignore: Annotated[
            bool, m.Field(description="Feed the Python/tool section of .gitignore")
        ] = True
        source_scan_ignore: Annotated[
            bool, m.Field(description="Feed source_scan.ignored_resources")
        ] = False

    class CodegenVscodeSpec(_ConfigContract):
        """Fully modeled content of the ``vscode`` section of ``config/codegen.yaml``."""

        scalar_settings: Annotated[
            Mapping[str, str | bool | int],
            m.Field(description="VS Code scalar keys enforced on every project"),
        ]
        list_settings: Annotated[
            Mapping[str, t.VariadicTuple[str]],
            m.Field(description="VS Code list keys enforced on every project"),
        ]
        map_union_settings: Annotated[
            Mapping[str, Mapping[str, str | bool | int]],
            m.Field(description="VS Code map keys union-merged over project settings"),
        ]

    class CodegenLocCapSpec(_ConfigContract):
        """Per-module logical-LOC ceiling policy (scc code lines)."""

        max_lines: Annotated[
            int,
            m.Field(
                ge=1,
                description=(
                    "Per-module code-LOC ceiling. Operator instruction "
                    "2026-09-07: the former 1000-LOC allowance stands."
                ),
            ),
        ] = 1000

    class ProjectGateBudgetSpec(_ConfigContract):
        """Resource ceiling for one registered gate's execution.

        Keys accept both spellings because the config SSOT and the emitted
        TOML table share the gate vocabulary (``time-seconds``), while the
        typed fields stay pythonic.
        """

        model_config = m.ConfigDict(populate_by_name=True)

        time_seconds: Annotated[
            int,
            m.Field(
                ge=1,
                alias="time-seconds",
                validation_alias=AliasChoices("time-seconds", "time_seconds"),
                description="Wall-clock ceiling in seconds",
            ),
        ]
        memory_mb: Annotated[
            int,
            m.Field(
                ge=1,
                alias="memory-mb",
                validation_alias=AliasChoices("memory-mb", "memory_mb"),
                description="Resident memory ceiling in MiB",
            ),
        ]
        tokens: Annotated[
            int, m.Field(ge=1, description="LLM token ceiling for the gate run")
        ]

    class CodegenConfigSpec(_ConfigContract):
        """Fully modeled content of ``config/codegen.yaml``."""

        version: Annotated[int, m.Field(ge=1, description="Config schema version")]
        loc_cap: Annotated[
            FlextInfraConfigModels.CodegenLocCapSpec,
            m.Field(description="Per-module code-LOC ceiling policy"),
        ]
        budget: Annotated[
            Mapping[str, FlextInfraConfigModels.ProjectGateBudgetSpec],
            m.Field(
                description=(
                    "Per-gate execution budgets projected as the managed "
                    "[tool.flext.project.budget] table; rows must cover "
                    "exactly the gate registry"
                )
            ),
        ]
        toolchain: Annotated[
            FlextInfraConfigModels.ToolchainSpec,
            m.Field(description="Exact generated toolchain"),
        ]
        github_actions: Annotated[
            Mapping[str, FlextInfraConfigModels.GithubActionPinSpec],
            m.Field(description="Immutable GitHub Action catalog"),
        ]
        checkout_submodules: Annotated[
            t.NonEmptyStr,
            m.Field(
                default="false",
                pattern=r"^(true|false|recursive)$",
                description=(
                    "Default actions/checkout submodules mode for every "
                    "generated workflow. 'false' keeps CI green on projects "
                    "whose submodules are private: the default GITHUB_TOKEN "
                    "cannot clone sibling private repositories and "
                    "'recursive' aborts the job at checkout"
                ),
            ),
        ]
        checkout_submodules_overrides: Annotated[
            Mapping[str, str],
            m.Field(
                default_factory=immutable_empty_mapping,
                description=(
                    "Per-distribution override of checkout_submodules, for "
                    "projects that really do exercise their subprojects in CI"
                ),
            ),
        ]
        ci_private_submodules: Annotated[
            Mapping[str, FlextInfraConfigModels.CiPrivateSubmodulesSpec],
            m.Field(
                default_factory=immutable_empty_mapping,
                description=(
                    "Per-distribution private submodule deploy-key contracts "
                    "rendered into generated CI before make setup"
                ),
            ),
        ]
        ci_private_dependency_auth: Annotated[
            Mapping[str, FlextInfraConfigModels.CiPrivateDependencyAuthSpec],
            m.Field(
                default_factory=immutable_empty_mapping,
                description=(
                    "Per-distribution GitHub App identity minting installation "
                    "tokens for private git dependencies in generated CI"
                ),
            ),
        ]
        ci_system_packages: Annotated[
            Mapping[str, t.VariadicTuple[t.NonEmptyStr]],
            m.Field(
                default_factory=immutable_empty_mapping,
                description=(
                    "Per-distribution runner packages (Ubuntu apt names) the "
                    "generated CI installs before the gates run"
                ),
            ),
        ]
        uv_exclude_dependencies: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.UvScopedDependencyExclusionSpec],
            m.Field(description="Project-scoped official uv dependency exclusions"),
        ] = ()
        infra_repository: Annotated[
            FlextInfraConfigModels.RepositorySourceSpec,
            m.Field(description="Canonical infrastructure repository identity"),
        ]
        providers: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.ProviderSpec],
            m.Field(min_length=1, description="Ordered FLEXT-owned Git providers"),
        ]
        branch_policy: Annotated[
            FlextInfraConfigModels.BranchPolicySpec,
            m.Field(description="Global governed branch ancestry policy"),
        ]
        profiles: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.ProfileSpec],
            m.Field(description="Ordered Make profiles"),
        ]
        make: Annotated[
            FlextInfraConfigModels.MakeSpec,
            m.Field(description="Canonical Make contract"),
        ]
        vscode: Annotated[
            FlextInfraConfigModels.CodegenVscodeSpec,
            m.Field(description="Canonical VS Code settings merge contract"),
        ]
        artifacts: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.CodegenArtifactSpec],
            m.Field(
                min_length=1,
                description=(
                    "Ephemeral/generated artifact SSOT; every ignore/exclude "
                    "projection derives from this list"
                ),
            ),
        ]
        layout: Annotated[
            FlextInfraModelsLayout.LayoutSpec,
            m.Field(
                description=(
                    "Declarative project-layout conformance contract consumed "
                    "by the layout engine and the layout quality gate"
                )
            ),
        ]

        @m.computed_field
        @property
        def vscode_files_exclude_map(self) -> Mapping[str, bool]:
            """Derived VS Code ``files.exclude`` entries from the artifact SSOT."""
            return {
                f"**/{artifact.name}": True
                for artifact in self.artifacts
                if artifact.vscode_exclude
            }

        @m.computed_field
        @property
        def vscode_watcher_exclude_map(self) -> Mapping[str, bool]:
            """Derived VS Code ``files.watcherExclude`` entries from the SSOT."""
            return {
                f"**/{artifact.name}/**": True
                for artifact in self.artifacts
                if artifact.watch_exclude
            }

        @m.computed_field
        @property
        def vscode_search_exclude_map(self) -> Mapping[str, bool]:
            """Derived VS Code ``search.exclude`` entries from the artifact SSOT."""
            return dict(self.vscode_files_exclude_map)

        @m.computed_field
        @property
        def source_scan_ignored(self) -> t.VariadicTuple[str]:
            """Derived ``source_scan.ignored_resources`` names from the SSOT."""
            return tuple(
                artifact.name
                for artifact in self.artifacts
                if artifact.source_scan_ignore
            )

        @m.computed_field
        @property
        def python_tool_distributions(self) -> t.VariadicTuple[str]:
            """Tool catalog for owned tools.

            One catalog projects every owned tool: the scaffold requirement
            owners (build and dev tables) plus the toolchain's declared
            additional tool identities. Runtime dependency profiles never
            enter it.
            """
            scaffold_owners: set[str] = set()
            for requirement in (
                *self.scaffold.build.requirements,
                *self.scaffold.project.dev,
            ):
                if (name := self._distribution_name(requirement)) is not None:
                    scaffold_owners.add(name)
            return tuple(
                sorted(
                    scaffold_owners
                    | set(self.toolchain.additional_python_tool_distributions)
                )
            )

        @staticmethod
        def _distribution_name(requirement: str) -> str | None:
            """Resolve the distribution name of one PEP 508 requirement line."""
            match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", requirement)
            return match.group(0) if match else None

        # The canonical .gitignore body is ONE computed
        # projection — the artifact SSOT feeds the Python/build section and the
        # static scaffold sections carry only what the SSOT cannot express
        # (file globs, secrets, editor/OS noise). Per-project exception fields
        # (extra_ignored / allowed dirs) land in their typed owner;
        # this projection is the seam they will extend.
        @m.computed_field
        @property
        def gitignore_sections(
            self,
        ) -> t.VariadicTuple[FlextInfraConfigModels.ScaffoldGitignoreSectionSpec]:
            """Derived canonical ``.gitignore`` sections (SSOT order, deduplicated).

            Ignore files are order-sensitive: a pattern placed before a
            catch-all such as ``/*`` is dead, and a directory ignored before
            its own ``!`` negation is never re-allowed. The declared sections
            are therefore emitted in their declared order, and derived artifact
            patterns are appended -- never prepended -- so a whitelist policy
            expressed in the SSOT survives the projection intact.
            """
            scaffold_sections = self.scaffold.gitignore_sections
            # A declared section may already govern a derived artifact, in
            # either direction: a whitelist re-allows `.agents/` with `!`, so
            # appending a bare `.agents/` ignore would contradict the declared
            # policy. Only artifacts the SSOT never mentions are appended.
            governed = {
                pattern.lstrip("!")
                for section in scaffold_sections
                for pattern in section.patterns
            }
            managed_allowed: t.MutableSequenceOf[str] = []
            declared_patterns = {
                pattern for section in scaffold_sections for pattern in section.patterns
            }
            for managed in self.managed_files:
                if (
                    managed.policy
                    == FlextInfraConstantsSharedInfra.MANAGED_FILE_POLICY_DELEGATED
                ):
                    continue
                parts = managed.path.parts
                candidates = [
                    *(f"!{'/'.join(parts[:depth])}/" for depth in range(1, len(parts))),
                    f"!{managed.path.as_posix()}",
                ]
                managed_allowed.extend(
                    candidate
                    for candidate in candidates
                    if candidate not in declared_patterns
                    and candidate not in managed_allowed
                )
            derived: t.MutableSequenceOf[str] = []
            for pattern in self.gitignore_artifact_patterns:
                if pattern not in governed and pattern not in derived:
                    derived.append(pattern)
            sections: t.MutableSequenceOf[
                FlextInfraConfigModels.ScaffoldGitignoreSectionSpec
            ] = []
            # Declared sections are emitted verbatim. Cross-section dedup is
            # unsound for ignore files: repeating `.beads/*` after an
            # intervening `!.beads/` is what keeps the directory scanned, so
            # dropping the repeat silently un-ignores its contents.
            sections.extend(scaffold_sections)
            # Derived artifacts are appended as their own trailing section: an
            # ignore file is evaluated in order, so injecting them into the
            # first section would place them before any `!` negation the policy
            # declares later and silently un-ignore governed paths.
            if derived:
                sections.append(
                    FlextInfraConfigModels.ScaffoldGitignoreSectionSpec(
                        name=FlextInfraConstantsSharedInfra.GITIGNORE_DERIVED_SECTION_NAME,
                        patterns=tuple(derived),
                    )
                )
            if managed_allowed:
                sections.append(
                    FlextInfraConfigModels.ScaffoldGitignoreSectionSpec(
                        name=FlextInfraConstantsSharedInfra.GITIGNORE_MANAGED_SECTION_NAME,
                        patterns=tuple(managed_allowed),
                    )
                )
            return tuple(sections)

        @m.computed_field
        @property
        def gitignore_artifact_patterns(self) -> t.VariadicTuple[str]:
            """Derived ``.gitignore`` artifact patterns from the SSOT (stable order)."""
            return tuple(
                f"{artifact.name}/" if artifact.is_dir else artifact.name
                for artifact in self.artifacts
                if artifact.gitignore
            )

        managed_files: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.ManagedFileSpec],
            m.Field(description="Files owned by conform"),
        ]
        scaffold: Annotated[
            FlextInfraConfigModels.ScaffoldSpec,
            m.Field(description="Typed new-project scaffold policy"),
        ]
        templates: Annotated[
            FlextInfraConfigModels.TemplatesSpec,
            m.Field(description="New-project-only scaffold template manifest"),
        ]
        # Operator law: flext-infra owns generic conform policy only. The set
        # of projects it serves is NOT its knowledge — each repository's own
        # .gitmodules is the read-only topology authority.

        @u.model_validator(mode="after")
        def _validate_github_artifact_ownership(self) -> Self:
            """Require one full-managed conform owner for every GitHub template."""
            github_templates = tuple(
                Path(entry.destination)
                for entry in self.templates.entries
                if Path(entry.destination).parts[:1] == (".github",)
            )
            github_managed = tuple(
                managed
                for managed in self.managed_files
                if managed.path.parts[:1] == (".github",)
            )
            template_paths = set(github_templates)
            managed_paths = {managed.path for managed in github_managed}
            duplicate_templates = len(github_templates) != len(template_paths)
            duplicate_managed = len(github_managed) != len(managed_paths)
            if duplicate_templates or duplicate_managed:
                msg = (
                    "GitHub artifacts must have exactly one template and managed owner"
                )
                raise ValueError(msg)
            if template_paths != managed_paths:
                missing_owners = sorted(
                    path.as_posix() for path in template_paths - managed_paths
                )
                missing_templates = sorted(
                    path.as_posix() for path in managed_paths - template_paths
                )
                msg = (
                    "GitHub template/managed ownership mismatch: "
                    f"missing owners={missing_owners}, "
                    f"missing templates={missing_templates}"
                )
                raise ValueError(msg)
            non_full = sorted(
                managed.path.as_posix()
                for managed in github_managed
                if managed.policy
                != FlextInfraConstantsSharedInfra.MANAGED_FILE_POLICY_FULL
            )
            if non_full:
                msg = f"GitHub artifacts must be full-managed: {non_full}"
                raise ValueError(msg)
            return self

    # Production source
    # selection is modeled once so iteration, Rope, and census share one SSOT.
    class SourceScanSpec(_ConfigContract):
        """Canonical production roots and recursively ignored directories."""

        roots: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Ordered production source directory names"),
        ]

    class StaticRule(_ConfigContract):
        """Shared immutable metadata for one Rope static-analysis rule."""

        kind: t.NonEmptyStr = m.Field(description="Violation kind")
        detail: t.NonEmptyStr = m.Field(description="Root-cause explanation")

    class StaticImportModuleRule(StaticRule):
        """Reject one imported module outside its configured owning project."""

        operator: Literal["import_module"] = m.Field(description="Operator")
        module: t.NonEmptyStr = m.Field(description="Rejected module root")
        owner_project: t.NonEmptyStr | None = m.Field(
            default=None, description="Permitted owning project"
        )

    class StaticImportMemberRule(StaticRule):
        """Reject one member imported from a configured module."""

        operator: Literal["import_member"] = m.Field(description="Operator")
        module: t.NonEmptyStr = m.Field(description="Import source module")
        member: t.NonEmptyStr = m.Field(description="Rejected imported member")

    class StaticAttributeRule(StaticRule):
        """Reject one member accessed through a semantically imported module alias."""

        operator: Literal["attribute"] = m.Field(description="Operator")
        module: t.NonEmptyStr = m.Field(description="Imported module")
        member: t.NonEmptyStr = m.Field(description="Rejected attribute")

    class StaticCallRule(StaticRule):
        """Reject calls to one bare callable name."""

        operator: Literal["call"] = m.Field(description="Operator")
        name: t.NonEmptyStr = m.Field(description="Rejected callable")

    class StaticCallKeywordRule(StaticRule):
        """Require one keyword in calls to a configured callable."""

        operator: Literal["call_keyword"] = m.Field(description="Operator")
        name: t.NonEmptyStr = m.Field(description="Callable")
        keyword: t.NonEmptyStr = m.Field(description="Required keyword")

    class StaticAnnotationRule(StaticRule):
        """Reject one identifier anywhere in an annotation."""

        operator: Literal["annotation"] = m.Field(description="Operator")
        name: t.NonEmptyStr = m.Field(description="Rejected annotation identifier")

    class StaticBareExceptRule(StaticRule):
        """Reject an exception handler without an exception contract."""

        operator: Literal["bare_except"] = m.Field(description="Operator")

    class StaticAnnotatedStringRule(StaticRule):
        """Reject an annotated target assigned directly to a string literal."""

        operator: Literal["annotated_string"] = m.Field(description="Operator")
        name: t.NonEmptyStr = m.Field(description="Rejected assignment target")

    class StaticCommentRule(StaticRule):
        """Reject one marker only when Rope classifies its region as a comment."""

        operator: Literal["comment"] = m.Field(description="Operator")
        marker: t.NonEmptyStr = m.Field(description="Rejected comment marker")

    type StaticRuleSpec = Annotated[
        StaticImportModuleRule
        | StaticImportMemberRule
        | StaticAttributeRule
        | StaticCallRule
        | StaticCallKeywordRule
        | StaticAnnotationRule
        | StaticBareExceptRule
        | StaticAnnotatedStringRule
        | StaticCommentRule,
        m.Field(discriminator="operator"),
    ]

    class StaticEnforcementSpec(_ConfigContract):
        """Complete validated static policy evaluated only through Rope facts."""

        rules: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.StaticRuleSpec],
            m.Field(min_length=1, description="Ordered static-analysis rules"),
        ]

    class ReleasePolicySpec(_ConfigContract):
        """The release protocol's declared data: who publishes, what bumps, where.

        Why (aihub-ioijy.9): `ReleaseOrchestrator._build_targets` hardcoded
        `project.name.startswith("flext-")`, so any consumer of this release
        engine whose distribution is not named `flext-*` resolved zero targets
        and died with "release build selected no publishable projects".
        Publishable membership is project policy, not a naming convention.

        `bump_types` maps a Conventional Commits type found in a merged
        pull-request title to the bump it earns; a type absent from the map
        releases nothing, and `!` in the title always earns a major bump. The
        Conventional Commits defaults are the typed default, so a consumer
        repository declares only what differs.
        """

        # The bump map is consumed as enum members by the strict release plan,
        # so the contract base's value coercion is switched off here.
        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            strict=False, frozen=True, extra="forbid", use_enum_values=False
        )

        publishable_prefixes: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Distribution-name prefixes eligible for build/publish. "
                    "Empty means every resolved project is eligible."
                ),
            ),
        ]
        bump_types: Annotated[
            Mapping[t.NonEmptyStr, FlextInfraConstantsRelease.VersionBump],
            m.Field(
                default_factory=lambda: {
                    "feat": FlextInfraConstantsRelease.VersionBump.MINOR,
                    "fix": FlextInfraConstantsRelease.VersionBump.PATCH,
                    "perf": FlextInfraConstantsRelease.VersionBump.PATCH,
                },
                description="Conventional Commits type -> semantic version bump",
            ),
        ]
        publish_url: Annotated[
            t.NonEmptyStr,
            m.Field(
                default=FlextInfraConstantsRelease.PYPI_UPLOAD_URL,
                description="Package index upload endpoint for verified artifacts",
            ),
        ]
        build_constraints: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.BuildConstraintSpec],
            m.Field(
                min_length=1,
                description=(
                    "Hash-pinned build-backend requirements every release artifact "
                    "is built with; projected to config/build-constraints.txt"
                ),
            ),
        ]

    class BuildConstraintSpec(_ConfigContract):
        """One hash-pinned build requirement (``uv build --require-hashes``)."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Distribution name")]
        version: Annotated[t.NonEmptyStr, m.Field(description="Exact version")]
        hashes: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Accepted sha256 digests"),
        ]

    class ReleasePolicyRenderSpec(_ConfigContract):
        """Typed input consumed by the generated release policy files."""

        build_constraints: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.BuildConstraintSpec],
            m.Field(min_length=1, description="Pins rendered into the constraints"),
        ]

    # This
    # field-only namespace is the sole validated owner exposed as config.Infra.
    class Infra(_ConfigContract):
        """Complete flext-infra configuration namespace."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Project distribution name")]
        initial_project_version: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Version seeded into a newly scaffolded project's pyproject; "
                    "from then on the release protocol is the only writer"
                )
            ),
        ]
        codegen: Annotated[
            FlextInfraConfigModels.CodegenConfigSpec,
            m.Field(description="Unified project and workspace codegen contract"),
        ]
        tooling: Annotated[
            FlextInfraModelsDepsToolSettings.ToolConfigDocument,
            m.Field(description="Validated lint, typecheck, and scaffold policy"),
        ]
        source_scan: Annotated[
            FlextInfraConfigModels.SourceScanSpec,
            m.Field(description="Production-only source discovery contract"),
        ]
        release: Annotated[
            FlextInfraConfigModels.ReleasePolicySpec,
            m.Field(description="Release protocol policy: eligibility, bumps, index"),
        ]
        # Static policy is validated data, never detector code.
        enforcement: Annotated[
            FlextInfraConfigModels.StaticEnforcementSpec,
            m.Field(description="Rope-only static enforcement policy"),
        ]

    class Root(_ConfigContract):
        """Root payload deep-merged from flext-infra config files."""

        Infra: Annotated[
            FlextInfraConfigModels.Infra,
            m.Field(description="Validated flext-infra namespace"),
        ]

    class ConfigLayerSpec(_ConfigContract):
        """One layer of the hierarchical config architecture."""

        path: Annotated[
            Path,
            m.Field(description="Config file path relative to flext-infra config root"),
        ]
        mutable: Annotated[
            bool,
            m.Field(
                description=(
                    "Whether this layer accepts project-specific overrides; "
                    "true for overrides, false for immutable business rules"
                )
            ),
        ]
        description: Annotated[
            t.NonEmptyStr,
            m.Field(description="Human-readable purpose of this config layer"),
        ]

    class ConfigLayersSpec(_ConfigContract):
        """Hierarchical config architecture: immutable config + project overrides."""

        primary: Annotated[
            FlextInfraConfigModels.ConfigLayerSpec,
            m.Field(description="Layer 1: immutable fleet-wide business rules"),
        ]
        overrides: Annotated[
            FlextInfraConfigModels.ConfigLayerSpec,
            m.Field(description="Layer 2: project-specific parameter overrides"),
        ]

    class ManagedFilePoliciesSpec(_ConfigContract):
        """Mandatory generation requirement: allowed/forbidden managed-file policies."""

        allowed: Annotated[
            t.VariadicTuple[str],
            m.Field(
                min_length=1,
                description=(
                    "Managed-file policies that permit generation; "
                    "create-only/delegated/manual are bypass policies"
                ),
            ),
        ]
        forbidden: Annotated[
            t.VariadicTuple[str],
            m.Field(
                min_length=1,
                description="Policies that bypass generation — always rejected by .gen enforcement",
            ),
        ]
        enforcement: Annotated[
            Literal["strict", "advisory"],
            m.Field(
                default="strict",
                description="strict rejects any forbidden policy; advisory reports without failing",
            ),
        ] = "strict"

        @u.model_validator(mode="after")
        def _validate_no_policy_overlap(self) -> Self:
            """Allowed and forbidden policies must not intersect."""
            allowed_set = set(self.allowed)
            forbidden_set = set(self.forbidden)
            overlap = allowed_set & forbidden_set
            if overlap:
                msg = f".gen policies overlap: {overlap}"
                raise ValueError(msg)
            return self

    class GenerationStepsSpec(_ConfigContract):
        """Mandatory generation requirement: all steps must run."""

        mandatory: Annotated[
            bool, m.Field(description="Whether every generation step must execute")
        ]
        skip_on_no_change: Annotated[
            bool,
            m.Field(description="Whether steps with no change are eligible to skip"),
        ]
        fail_on_drift: Annotated[
            bool, m.Field(description="Whether detected drift causes failure")
        ]

    class ConfigAuthoritySpec(_ConfigContract):
        """Mandatory generation requirement: config-driven authority."""

        requires_config: Annotated[
            bool,
            m.Field(description="Whether generation requires authoritative config"),
        ]
        requires_overrides: Annotated[
            bool, m.Field(description="Whether the overrides layer must be present")
        ]
        reject_manual_edits: Annotated[
            bool,
            m.Field(description="Whether manual edits to managed files are rejected"),
        ]

    class FixedPointSpec(_ConfigContract):
        """Mandatory generation requirement: post-generation fixed-point validation."""

        required: Annotated[
            bool,
            m.Field(
                description="Whether fixed-point re-conform validation is required"
            ),
        ]
        max_replans: Annotated[
            int,
            m.Field(ge=1, le=10, description="Maximum re-plan attempts before failure"),
        ]

    class GenRequirementsSpec(_ConfigContract):
        """Typed content of a ``.gen`` requirements contract file (codegen.gen.yaml).

        Declares mandatory generation requirements that the conform system must
        satisfy. The ``.j2`` templates remain the content generators; this file
        is the compliance contract that governs their execution.
        """

        version: Annotated[
            int, m.Field(ge=1, description="Generation requirements contract version")
        ]
        config_layers: Annotated[
            FlextInfraConfigModels.ConfigLayersSpec,
            m.Field(
                description="Hierarchical config architecture (immutable + overrides)"
            ),
        ]
        requirements: Annotated[
            FlextInfraConfigModels.GenRequirementEntries,
            m.Field(description="Mandatory generation requirements"),
        ]

    class GenRequirementEntries(_ConfigContract):
        """The mandatory requirement groups enforced by a .gen contract."""

        managed_file_policies: Annotated[
            FlextInfraConfigModels.ManagedFilePoliciesSpec,
            m.Field(description="Bypass policy enforcement for managed files"),
        ]
        generation_steps: Annotated[
            FlextInfraConfigModels.GenerationStepsSpec,
            m.Field(description="Step-level generation requirements"),
        ]
        config_authority: Annotated[
            FlextInfraConfigModels.ConfigAuthoritySpec,
            m.Field(description="Config-driven authority enforcement"),
        ]
        fixed_point: Annotated[
            FlextInfraConfigModels.FixedPointSpec,
            m.Field(description="Post-generation fixed-point validation"),
        ]
        externally_managed: Annotated[
            Mapping[str, FlextInfraConfigModels.ExternallyManagedSpec],
            m.Field(
                default_factory=immutable_empty_mapping,
                description=(
                    "Files owned by external systems (operator, workspace, make) "
                    "that are validated through .gen compliance but not generated "
                    "from .j2 templates. Replaces bypass policies with auditable "
                    "ownership declarations."
                ),
            ),
        ]

    class CodegenOverridesRoot(_ConfigContract):
        """Override root mirroring the Infra.codegen structure with override-only fields.

        Every field is optional and defaults to empty so an override file can
        declare only the deltas it needs. The conform system deep-merges this
        onto the immutable ``codegen.yaml`` before Pydantic validation.
        """

        codegen: Annotated[
            FlextInfraConfigModels._CodegenOverridesSection,
            m.Field(description="Override sections for the codegen namespace"),
        ]

    class _CodegenOverridesSection(_ConfigContract):
        """Override deltas that deep-merge onto CodegenConfigSpec fields."""

        checkout_submodules_overrides: Annotated[
            Mapping[str, str],
            m.Field(
                default_factory=immutable_empty_mapping,
                description="Per-distribution checkout submodules overrides",
            ),
        ]
        ci_private_submodules: Annotated[
            Mapping[str, t.JsonMapping],
            m.Field(
                default_factory=immutable_empty_mapping,
                description="Per-distribution private submodule deploy-key contracts",
            ),
        ]
        make: Annotated[
            FlextInfraConfigModels._MakeOverridesSection | None,
            m.Field(default=None, description="Make override deltas"),
        ] = None
        layout: Annotated[
            FlextInfraConfigModels._LayoutOverridesSection | None,
            m.Field(default=None, description="Layout override deltas"),
        ] = None

    class _MakeOverridesSection(_ConfigContract):
        """Override deltas for the generated Make contract."""

        custom_handler_profile_overrides: Annotated[
            Mapping[str, t.JsonMapping],
            m.Field(
                default_factory=immutable_empty_mapping,
                description="Per-profile custom handler policy relaxations",
            ),
        ]

    class _LayoutOverridesSection(_ConfigContract):
        """Override deltas for the layout conformance contract."""

        project_overrides: Annotated[
            Mapping[str, t.JsonMapping],
            m.Field(
                default_factory=immutable_empty_mapping,
                description="Per-project layout deltas",
            ),
        ]

    class CodegenOverridesSpec(_ConfigContract):
        """Typed content of the config overrides layer (config/codegen-overrides.yaml).

        Layer 2 of the hierarchical architecture: project-specific parameters
        that sit on top of the immutable codegen.yaml business rules. Every field
        here is a delta applied to the base config; the overrides file never
        duplicates immutable rules.
        """

        Infra: Annotated[
            FlextInfraConfigModels.CodegenOverridesRoot,
            m.Field(description="flext-infra override namespace"),
        ]

    class UvEnvironmentPlan(_ConfigContract):
        """One deterministic uv environment operation plan."""

        project_root: Annotated[Path, m.Field(description="Selected project root")]
        environment_root: Annotated[
            Path, m.Field(description="Project supplying the active .venv")
        ]
        lock_path: Annotated[Path, m.Field(description="Required versioned uv.lock")]
        python_version: Annotated[
            t.NonEmptyStr, m.Field(description="Mise/Python version selector")
        ]
        groups: Annotated[
            t.VariadicTuple[str],
            m.Field(description="Ordered dependency groups synchronized by setup"),
        ]
        editable_repositories: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.RepositoryRef],
            m.Field(description="Local repositories overlaid after locked sync"),
        ] = ()

    class BranchAncestryRef(_ConfigContract):
        """One exact branch or registered worktree ancestry observation."""

        reference: Annotated[
            t.NonEmptyStr, m.Field(description="Git ref or worktree identity")
        ]
        sha: Annotated[
            t.NonEmptyStr, m.Field(description="Observed commit object identifier")
        ]
        excluded: Annotated[
            bool, m.Field(description="Whether typed technical policy excludes the ref")
        ]
        ancestor: Annotated[
            bool | None,
            m.Field(description="Baseline ancestry verdict; None when excluded"),
        ]

    class BranchAncestryPlan(_ConfigContract):
        """Bounded ancestry inventory for one governed repository."""

        repository_root: Annotated[
            Path, m.Field(description="Governed repository root")
        ]
        baseline_reference: Annotated[
            t.NonEmptyStr, m.Field(description="Provider-owned remote baseline ref")
        ]
        baseline_sha: Annotated[
            t.NonEmptyStr, m.Field(description="Resolved baseline commit")
        ]
        references: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.BranchAncestryRef],
            m.Field(description="Local, remote, and worktree ancestry inventory"),
        ]

    class WorkspaceEnvironmentCliRequest(_ConfigContract):
        """CLI-safe request for one Python workspace environment sync."""

        repository_root: Annotated[
            Path, m.Field(description="Repository root receiving the sync")
        ]
        apply: Annotated[
            bool, m.Field(description="Write changes instead of reporting them")
        ] = True
        force: Annotated[
            bool, m.Field(description="Replace custom files with generated content")
        ] = False
        allow_direnv: Annotated[
            bool,
            m.Field(description="Authorize the rendered .envrc after an applied sync"),
        ] = True

    class WorkspaceEnvironmentSyncRequest(_ConfigContract):
        """Validated internal request for one workspace environment sync."""

        repository_root: Annotated[
            Path, m.Field(description="Repository root receiving the sync")
        ]
        apply: Annotated[
            bool, m.Field(description="Write changes instead of reporting them")
        ] = True
        force: Annotated[
            bool, m.Field(description="Replace custom files with generated content")
        ] = False
        beads: Annotated[
            FlextInfraConfigModels.BeadsWorkspaceEnvironmentSpec | None,
            m.Field(
                exclude=True,
                description=(
                    "Programmatic-only selection of generated beads-workspace "
                    ".envrc instead of the Python package environment"
                ),
            ),
        ] = None
        allow_direnv: Annotated[
            bool,
            m.Field(
                description=(
                    "Run `direnv allow` for the workspace after a successful "
                    "applied sync so managed roots never carry a stale allow"
                )
            ),
        ] = True

    class BeadsWorkspaceEnvironmentSpec(_ConfigContract):
        """Declarative contract for one generated beads-workspace .envrc.

        Defaults encode the canonical Gas City + Beads wiring: the sync owns
        the file end to end while every credential-free fact stays declarative
        here, and the single identity variable (``AGENTS_GAS_CITY_ROOT``) keeps
        failing loudly when the canonical checkout is not declared.
        """

        environment_sources: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Environment files sourced on activation"),
        ] = ("$HOME/.config/environment.d/projects/agent-tools.envrc",)
        identity_var: Annotated[
            t.NonEmptyStr,
            m.Field(description="Required variable naming the Gas City checkout"),
        ] = "AGENTS_GAS_CITY_ROOT"
        city_state_relpath: Annotated[
            t.NonEmptyStr,
            m.Field(description="Gas City Dolt state path relative to the checkout"),
        ] = ".gc/runtime/packs/dolt/dolt-state.json"
        beads_metadata_relpath: Annotated[
            t.NonEmptyStr,
            m.Field(description="Beads metadata path relative to the workspace"),
        ] = ".beads/metadata.json"
        unset_vars: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Inherited orchestration variables cleared on entry"),
        ] = (
            "GT_ROOT",
            "GT_TOWN_ROOT",
            "BEADS_DIR",
            "BEADS_DOLT_PORT",
            "BEADS_DOLT_DATA_DIR",
            "BEADS_DOLT_SHARED_SERVER",
        )

    class WorkspaceEnvironmentSyncResult(_ConfigContract):
        """Outcome of one workspace environment sync."""

        changed_files: Annotated[
            t.VariadicTuple[Path],
            m.Field(description="Environment files created, updated, or removed"),
        ] = ()

        @m.computed_field
        @property
        def changed(self) -> bool:
            """Whether the sync altered any environment file."""
            return bool(self.changed_files)

    class CodegenConformSurfaceContract(m.Value):
        """Typed ownership contract for one requested conformance surface."""

        # Why: leaf conform planning contract lives on m.Infra only (not nested in services).
        destinations: Annotated[
            frozenset[str] | None,
            m.Field(description="Output paths selected for conformance planning"),
        ] = None
        complete_governed: Annotated[
            bool, m.Field(description="Whether every governed output is represented")
        ] = False
        dependencies_only: Annotated[
            bool, m.Field(description="Whether planning is dependency-only")
        ] = False
        delegates: Annotated[
            bool, m.Field(description="Whether delegated templates are planned")
        ] = True
        pyproject: Annotated[
            bool, m.Field(description="Whether project metadata is planned")
        ] = True
        templates: Annotated[
            bool, m.Field(description="Whether managed templates are planned")
        ] = True
        custom: Annotated[
            bool, m.Field(description="Whether custom Make policy is planned")
        ] = True

    class CodegenConformRequest(_ConfigContract):
        """Validated public request for ``flext-infra codegen conform``."""

        root: Annotated[Path, m.Field(description="Repository or workspace root")]
        what: Annotated[
            FlextInfraConstantsCodegenProject.CodegenConformSurface,
            m.Field(description="Managed file selection"),
        ] = FlextInfraConstantsCodegenProject.CodegenConformSurface.ALL
        scope: Annotated[
            FlextInfraConstantsCodegenProject.CodegenConformScope,
            m.Field(description="Repository selection scope"),
        ] = FlextInfraConstantsCodegenProject.CodegenConformScope.SELF
        mode: Annotated[
            FlextInfraConstantsCodegenProject.CodegenConformMode,
            m.Field(description="Read-only check or atomic apply"),
        ] = FlextInfraConstantsCodegenProject.CodegenConformMode.CHECK

    class CodegenArtifactComposition(_ConfigContract):
        """Rendered artifact plus the exact source states used to compose it."""

        rendered: Annotated[
            str, m.Field(description="Fully composed managed-file content")
        ]
        source_states: Annotated[
            t.VariadicTuple[m.Cli.AtomicFileState],
            m.Field(description="Ordered immutable sources consumed by composition"),
        ] = ()

    class CodegenFilePlan(_ConfigContract):
        """Exact before state and desired state for one managed file."""

        project: Annotated[Path, m.Field(description="Physical owning project root")]
        path: Annotated[Path, m.Field(description="Absolute managed file path")]
        before: Annotated[
            m.Cli.AtomicFileState | m.Cli.AtomicDirectoryChainPlan,
            m.Field(
                description=(
                    "Descriptor-authenticated file state, or the exact absent "
                    "parent chain captured by read-only planning"
                )
            ),
        ]
        desired_content: Annotated[
            bytes | None,
            m.Field(
                strict=True,
                description="Exact desired bytes, or None for an absent destination",
            ),
        ]
        desired_mode: Annotated[
            int | None,
            m.Field(
                ge=0,
                le=0o7777,
                strict=True,
                description="Exact desired mode, or None for an absent destination",
            ),
        ]
        source_states: Annotated[
            t.VariadicTuple[m.Cli.AtomicFileState],
            m.Field(
                exclude=True,
                description="Exact source states that produced rendered content",
            ),
        ] = ()
        owner: Annotated[
            str,
            m.Field(description="Canonical artifact owner, empty for scaffold files"),
        ] = ""
        policy: Annotated[
            Literal["full", "merge", "create-only", "delegated", "manual"] | None,
            m.Field(description="Governed root artifact policy"),
        ] = None

        @u.model_validator(mode="after")
        def _validate_publication_identity(self) -> Self:
            """Bind one complete desired state to its exact project and target."""
            if not self.project.is_absolute() or not self.path.is_absolute():
                msg = "codegen project and path must be absolute"
                raise ValueError(msg)
            if isinstance(self.before, m.Cli.AtomicFileState):
                if self.before.path != self.path:
                    msg = "codegen before state belongs to another path"
                    raise ValueError(msg)
            elif (
                self.before.target != self.path.parent
                or not self.before.directories
                or self.desired_content is None
            ):
                msg = "codegen absent parent plan is inconsistent with its destination"
                raise ValueError(msg)
            try:
                self.path.relative_to(self.project)
            except ValueError as exc:
                msg = f"codegen path escapes owning project: {self.path}"
                raise ValueError(msg) from exc
            desired = (self.desired_content, self.desired_mode)
            if any(value is None for value in desired) != all(
                value is None for value in desired
            ):
                msg = (
                    "codegen desired bytes and mode must be present or absent together"
                )
                raise ValueError(msg)
            return self

    class CodegenPlan(_ConfigContract):
        """Fully validated plan produced before any managed-file write."""

        request: Annotated[
            FlextInfraConfigModels.CodegenConformRequest,
            m.Field(description="Validated public request"),
        ]
        repositories: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.RepositoryRef],
            m.Field(description="Selected repositories in deterministic order"),
        ]
        workspace: Annotated[
            FlextInfraConfigModels.WorkspaceSpec,
            m.Field(description="Workspace governing the selection"),
        ]
        make_spec: Annotated[
            FlextInfraConfigModels.MakeSpec,
            m.Field(description="Canonical Make contract"),
        ]
        uv_environments: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.UvEnvironmentPlan],
            m.Field(description="uv plans paired with selected repositories"),
        ]
        branch_ancestry: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.BranchAncestryPlan],
            m.Field(description="Governed branch ancestry observations"),
        ]
        files: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.CodegenFilePlan],
            m.Field(description="All render results validated before application"),
        ]

    class CodegenResult(_ConfigContract):
        """Public conformance outcome for check and apply modes."""

        plan: Annotated[
            FlextInfraConfigModels.CodegenPlan,
            m.Field(description="Plan that governed the operation"),
        ]
        written_files: Annotated[
            t.VariadicTuple[Path],
            m.Field(description="Files atomically replaced by apply"),
        ] = ()
        errors: Annotated[
            t.VariadicTuple[str],
            m.Field(description="Fail-closed validation or write errors"),
        ] = ()
