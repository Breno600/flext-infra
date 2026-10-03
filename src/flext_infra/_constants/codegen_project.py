"""Project-scaffold manifest (data) for ``flext-infra codegen new``.

Per ADR-005 this is the single source of truth describing *which* templates make
up a new project and *where* each lands. The engine (``u.Cli.template_render_dir``,
flext-cli) is policy-free; this manifest + the rope-derived context carry all the
FLEXT naming policy. Template-backed artifacts use ``.j2`` sources; typed
manifest artifacts serialize their Pydantic contract in the scaffold cycle.

Output paths use ``{token}`` placeholders (resolved by the service from rope) so
the engine never sees FLEXT naming. NOTE: the large-row form migrates to
``config/codegen/project_manifest.yaml`` in the ``conform`` slice (ADR-005 SSOT).

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from enum import StrEnum, unique
from typing import TYPE_CHECKING, ClassVar, Literal

from flext_infra._constants.validate import FlextInfraConstantsSharedInfra

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsCodegenProject:
    """Manifest + naming constants for project creation (flat in ``c.Infra.*``)."""

    CODEGEN_LOCAL_OVERRIDES_FILENAME: ClassVar[str] = "codegen-overrides.local.yaml"
    CODEGEN_ORG_OVERRIDES_FILENAME: ClassVar[str] = "codegen-org.yaml"
    CODEGEN_CLI_MODULE_FILENAME: ClassVar[str] = "cli.py"

    # These enums define the
    # one public conform contract shared by new and existing repositories. The
    # declarative values live in config/codegen.yaml; constants only type the
    # closed vocabulary used by models and CLI dispatch.

    @unique
    class TemplateDelegate(StrEnum):
        """Rendering owner for a scaffold catalog entry."""

        RENDER = "render"
        MANIFEST = "manifest"

    @unique
    class CodegenConformScope(StrEnum):
        """Repository selection accepted by ``codegen conform``."""

        SELF = "self"
        DECLARED = "declared_repositories"
        ALL = "all"

    @unique
    class CodegenConformSurface(StrEnum):
        """Managed file selection accepted by ``codegen conform``."""

        ALL = "all"
        DEPENDENCIES = "dependencies"
        DOCS_CONFIG = "docs-config"
        MAKEFILE = "makefile"
        MISE_TRIPLE = "mise-triple"
        PYPROJECT = "pyproject"

    @unique
    class CodegenConformMode(StrEnum):
        """Read-only or write mode accepted by ``codegen conform``."""

        CHECK = "check"
        APPLY = "apply"

    @unique
    class MiseResolutionMode(StrEnum):
        """How an apply-mode ``codegen conform`` resolves the Mise toolchain.

        ``AUTO`` probes the declared release endpoint once in preflight and
        becomes ``ONLINE`` (the newest Mise release and every moving tool
        selector are resolved and published) or ``OFFLINE`` (the published
        launchers and lock are kept byte-identical). The explicit values pin
        one path; none of them is a fallback taken after a failed effect.
        """

        AUTO = "auto"
        ONLINE = "online"
        OFFLINE = "offline"

    @unique
    class MakeProfile(StrEnum):
        """Generated Makefile profile for one repository.

        Topology is proven by the repository itself: a checkout that declares
        ``.gitmodules`` is a workspace, and one that does not is standalone.
        This mirrors ``MakeProfile``, which the detector returns, so the two
        vocabularies cannot drift.
        """

        WORKSPACE = "workspace"
        STANDALONE = "standalone"

    @unique
    class RepositoryState(StrEnum):
        """Lifecycle state used by repository selection."""

        ACTIVE = "active"
        EXCLUDED = "excluded"

    @unique
    class CheckoutKind(StrEnum):
        """Physical checkout topology for one repository."""

        ROOT = "root"
        SUBMODULE = "submodule"
        INDEPENDENT = "independent"

    @unique
    class CodegenKind(StrEnum):
        """Code-generation policy applied to one repository."""

        CONFORM = "conform"
        PYTHON = "python"
        NONE = "none"

    @unique
    class ProjectKind(StrEnum):
        """Governance kind of one repository; decides who may rewrite it.

        Generation applies to ``INTERNAL_FLEXT`` alone. An ``INTERNAL`` project
        is owned but not built on FLEXT, so FLEXT layout, facade chain, and
        typing policy do not apply to it. A ``THIRD_PARTY_FORK`` follows its
        upstream in everything, and standardizing it would destroy the contract
        the fork exists to track.
        """

        INTERNAL_FLEXT = "internal_flext"
        INTERNAL = "internal"
        THIRD_PARTY_FORK = "third_party_fork"

    BEADS_CONFIG_FILENAME: ClassVar[str] = "beads.yaml"
    BEADS_DIRNAME: ClassVar[str] = ".beads"
    BEADS_DIRECTORY_MODE: ClassVar[int] = 0o700
    BEADS_LOCAL_VERSION_FILENAME: ClassVar[str] = ".local_version"
    BEADS_LAST_TOUCHED_FILENAME: ClassVar[str] = "last-touched"
    BEADS_RUNTIME_ENTRY_NAMES: ClassVar[frozenset[str]] = frozenset({
        # Provenance: bd's own `.beads/.gitignore`. These are the live Dolt
        # server and daemon runtime entries bd writes beside the ledger: they
        # are projections of ledger truth, never composed output, so the
        # composed-project verify must tolerate them exactly as it tolerates
        # the passive `issues.jsonl`/`interactions.jsonl` exports.
        "dolt",
        "embeddeddolt",
        "proxieddb",
        "bd.sock",
        "bd.sock.startlock",
        "sync-state.json",
        "push-state.json",
        "daemon.lock",
        "daemon.log",
        "daemon.pid",
        "ephemeral.sqlite3",
        "ephemeral.sqlite3-journal",
        "ephemeral.sqlite3-shm",
        "ephemeral.sqlite3-wal",
        "dolt-server.activity",
        "dolt-server-config.yaml",
        "dolt-server.lock",
        "dolt-server.log",
        "dolt-server.pid",
        "dolt-server.port",
        "dolt-pprof",
        "proxied_server_client_info.json",
        ".env",
        ".exclusive-lock",
        ".sync.lock",
        # The bd client serializes every gate transaction through this marker
        # beside the ledger (measured: a members' gen failed composition on a
        # hours-stale zero-byte `dolt.gate.lock` whose holder had died). Same
        # class as `.exclusive-lock`/`.sync.lock`: a projection of ledger
        # operation, never composed output.
        "dolt.gate.lock",
    })
    "bd-owned Dolt/daemon runtime entries the composed-project verify tolerates."
    BEADS_CONFIG_VERSION: ClassVar[Literal[1]] = 1
    CONFORM_NAMESPACE_TABLE: ClassVar[t.VariadicTuple[str]] = (
        "tool",
        "flext",
        "namespace",
    )
    """Table the conform pipeline writes from the project SSOT.

    One owner for the path, consumed by the writer and by the managed-file
    declaration that must be able to recover it from a merge conflict. They
    drifted apart once, and the superproject merge then dead-ended on the
    owner's own output. The dotted spelling is derived through
    ``u.Cli.toml_dot_path``; it is never written a second time.
    """

    DOCS_SOURCE_STATE_RACE_MARKER: ClassVar[str] = (
        "docs source state changed during planning"
    )
    """Emitted by ``docs_verify_sources`` when one snapshotted docs source
    changes content or physical identity inside the planning window."""
    DOCS_SOURCE_TOPOLOGY_RACE_MARKER: ClassVar[str] = (
        "docs source topology changed during planning"
    )
    """Emitted by ``docs_verify_sources`` when the discovered docs source set
    gains or loses a file inside the planning window."""
    CONFIG_SNAPSHOT_ROOT_RACE_MARKER: ClassVar[str] = (
        "project root changed during config snapshot"
    )
    """Emitted by ``snapshot_config_sources`` when the project directory's
    physical state changes while its managed-artifact config is snapshotted."""
    CONFIG_SNAPSHOT_TOPOLOGY_RACE_MARKER: ClassVar[str] = (
        "project config source topology changed"
    )
    """Emitted by ``snapshot_config_sources`` when the ``config/*.yaml`` set
    changes while its managed-artifact config is snapshotted."""
    WORKSPACE_MANIFEST_FILENAME: ClassVar[str] = "workspace.yaml"
    WORKSPACE_MANIFEST_VERSION: ClassVar[int] = 3
    UV_LOCK_FILENAME: ClassVar[str] = "uv.lock"
    MISE_LOCK_FILENAME: ClassVar[str] = "mise.lock"
    MISE_LOCK_TRANSACTION_SCRIPT: ClassVar[str] = "bin/mise-lock-transaction.py"
    "Generated publisher the Makefile bootstrap runs to commit a staged mise.lock."
    MAKEFILE_BOOTSTRAP_DESTINATIONS: ClassVar[frozenset[str]] = frozenset({
        FlextInfraConstantsSharedInfra.MAKEFILE_FILENAME,
        MISE_LOCK_TRANSACTION_SCRIPT,
    })
    "The Makefile surface: the Makefile and the lock publisher its bootstrap runs."
    MISE_LOCK_ANNOTATION: ClassVar[str] = "~"
    "Lockfile cache-key fragment (``<version>~<hash>``); never a selector."
    MISE_MOVING_SELECTOR: ClassVar[str] = "latest"
    "Selector resolved only by ``make upg`` into the committed ``mise.lock``."
    GIT_URL_SUFFIX: ClassVar[str] = ".git"
    "Canonical clone-URL suffix every governed RepositoryRef URL carries."
    CUSTOM_MAKE_FILENAME: ClassVar[str] = "custom.mk"
    CUSTOM_CI_STEPS_FILENAME: ClassVar[str] = ".github/ci-custom-steps.yml"
    """Project-owned steps injected into generated CI, symmetric to custom.mk.

    It sits beside the workflows rather than inside them: GitHub parses every
    file under ``.github/workflows`` as a workflow, and a bare step list is not
    one, so a file placed there would surface as a permanent syntax error.
    """
    CUSTOM_HANDLER_PREFIX: ClassVar[str] = "_custom_"
    TEMPLATE_MODULE_SKELETON: ClassVar[str] = "module_skeleton.py.j2"
    "Scaffold module-skeleton template (replaces the legacy f-string)."
    TEMPLATE_TEST_MODULE_SKELETON: ClassVar[str] = "test_module_skeleton.py.j2"
    "Scaffold template for canonical test c/t/p/m/u facades."
    CODEGEN_CONFIG_FILENAME: ClassVar[str] = "codegen.yaml"
    CODEGEN_OVERRIDES_FILENAME: ClassVar[str] = "codegen-overrides.yaml"
    CODEGEN_GEN_FILENAME: ClassVar[str] = "codegen.gen.yaml"
    CODEGEN_GEN_SUFFIX: ClassVar[str] = ".gen.yaml"
    "File suffix for generation requirements contract files managed by conform."
    CODEGEN_CONFIG_DIR: ClassVar[str] = "config"
    "Directory name for flext-infra config files relative to package root."

    # One base catalog serves both profiles;
    # workspace topology is read only from each repository's own .gitmodules.


__all__: list[str] = ["FlextInfraConstantsCodegenProject"]
