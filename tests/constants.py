"""Constants for FLEXT infra tests.

Provides TestsFlextInfraConstants, extending FlextTestsConstants with
infra-specific constants for infrastructure testing, project names, and test
markers.

Copyright (FlextTestsConstants) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar

from flext_tests import FlextTestsConstants

from flext_infra import FlextInfraConstants, FlextInfraModels
from tests.constants_scan import TestsFlextInfraConstantsScanMixin

if TYPE_CHECKING:
    from flext_infra import t


class TestsFlextInfraConstants(FlextTestsConstants, FlextInfraConstants):
    """Constants for FLEXT infra tests - extends FlextTestsConstants.

    Architecture layer: Layer 0 foundation constants with infra test extensions.
    Architecture: Extends FlextTestsConstants with infra-specific constants.
    All base constants from FlextTestsConstants are available through inheritance.
    """

    class Tests(TestsFlextInfraConstantsScanMixin, FlextTestsConstants.Tests):
        """Flat constants optimized for data-driven infra tests."""

        GIT_LOCAL_ENV_KEYS: ClassVar[t.StrSequence] = (
            "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_CONFIG",
            "GIT_CONFIG_PARAMETERS",
            "GIT_CONFIG_COUNT",
            "GIT_OBJECT_DIRECTORY",
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GIT_IMPLICIT_WORK_TREE",
            "GIT_GRAFT_FILE",
            "GIT_INDEX_FILE",
            "GIT_NO_REPLACE_OBJECTS",
            "GIT_REPLACE_REF_BASE",
            "GIT_PREFIX",
            "GIT_SHALLOW_FILE",
            "GIT_COMMON_DIR",
        )
        """Repository-local variables Git exports to hooks and aliases."""

        MAKE_TEMPLATE_HOSTILE_VENV: ClassVar[str] = "hostile/.venv"
        """Foreign environment beside a run-scoped ``make upg`` template."""

        COLD_MISE_STORAGE: ClassVar[str] = "cold-mise-storage"
        """Mise storage that starts empty, so every tool and lookup is fetched."""

        MAKE_TEMPLATE_CI_CHECKOUT: ClassVar[str] = "ci"
        """Home of the template checkout set up once in cold CI storage."""

        MAKE_TEMPLATE_UPG_RECEIPT: ClassVar[str] = "upg-receipt.json"
        """Recorded ``make upg`` outcome of one run-scoped template."""

        MAKE_TEMPLATE_CI_RECEIPT: ClassVar[str] = "ci-setup-receipt.json"
        """Recorded cold-storage CI ``make setup`` outcome of one template."""

        DIRENV_STATE_ENV_KEYS: ClassVar[t.StrSequence] = (
            "DIRENV_DIFF",
            "DIRENV_DIR",
            "DIRENV_FILE",
            "DIRENV_WATCHES",
        )
        """direnv's loaded-activation protocol; ``direnv exec`` first reverts it.

        An outer activation (the operator's shell) would otherwise undo the
        variables a test hands to the activation under test.
        """

        MAKE_ISOLATION_ENV_KEYS: ClassVar[t.StrSequence] = (
            *DIRENV_STATE_ENV_KEYS,
            "BASH_ENV",
            "CHANGED_ONLY",
            "CHECK_GATES",
            "CHECK_ONLY",
            "FILE",
            "FILES",
            "FIX",
            "FLEXT_INFRA_PYTHON",
            "FLEXT_ROOT",
            "FLEXT_STANDALONE",
            "FLEXT_REPOSITORY_ROOT",
            "MATCH",
            "PROJECT",
            "PROJECTS",
            "PYRIGHT_ARGS",
            "PYTEST_ARGS",
            "RUFF_ARGS",
            "UV",
            "VALIDATE_GATES",
            "WHAT",
            "REPOSITORY_ROOT",
            *FlextInfraConstants.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS,
            # The host's Gas City identity selects the generated .envrc beads
            # branch; a fixture project declares no city, so the owner-declared
            # identity variable never crosses into an isolated run.
            FlextInfraModels.Infra.BeadsWorkspaceEnvironmentSpec.model_fields[
                "identity_var"
            ].default,
        )
        """Environment inherited from an outer Make invocation to discard in tests."""

        # ClassVar, not Final: these rebindings live on a Pydantic model
        # class, and Pydantic 2.11 deprecates final-annotated defaults
        # (filterwarnings=error turns that into a collection failure).
        RELEASE_PHASE_PLAN: ClassVar[str] = FlextInfraConstants.Infra.ReleasePhase.PLAN
        RELEASE_PHASE_VERSION: ClassVar[str] = (
            FlextInfraConstants.Infra.ReleasePhase.VERSION
        )
        RELEASE_PHASE_TAG: ClassVar[str] = FlextInfraConstants.Infra.ReleasePhase.TAG
        RELEASE_PHASE_BUILD: ClassVar[str] = (
            FlextInfraConstants.Infra.ReleasePhase.BUILD
        )
        RELEASE_PHASE_PUBLISH: ClassVar[str] = (
            FlextInfraConstants.Infra.ReleasePhase.PUBLISH
        )

        WORKSPACE_PROJECT_NAME: ClassVar[str] = "workspace"
        DEMO_PROJECT_NAME: ClassVar[str] = "demo-project"
        PROJECT_A_NAME: ClassVar[str] = "proj-a"
        PROJECT_B_NAME: ClassVar[str] = "proj-b"
        PROJECT_NO_SRC_NAME: ClassVar[str] = "no-src"
        PROJECT_MEMBERS_BY_SCENARIO: ClassVar[t.MappingKV[str, t.StrSequence]] = (
            MappingProxyType({
                "single": (DEMO_PROJECT_NAME,),
                "filtered": (PROJECT_A_NAME, PROJECT_B_NAME),
                "missing_src": (PROJECT_NO_SRC_NAME,),
            })
        )

        CODEGEN_NAMESPACE_FILES: ClassVar[frozenset[str]] = frozenset({
            "__init__.py",
            "__version__.py",
            "py.typed",
        })
        CODEGEN_SKIPPED_DIRS: ClassVar[frozenset[str]] = frozenset({
            ".hidden",
            "vendor",
            "node_modules",
            ".venv",
        })

        REFACTOR_SCAN_FILE_COUNT: ClassVar[int] = 1000
        REFACTOR_SCAN_MAX_SECONDS: ClassVar[float] = 30.0
        REFACTOR_MEMORY_FILE_COUNT: ClassVar[int] = 500
        REFACTOR_MEMORY_MAX_MB: ClassVar[float] = 500.0
        REFACTOR_RULE_ITERATIONS: ClassVar[int] = 100
        REFACTOR_RULE_MAX_SECONDS: ClassVar[float] = 0.1

        # flext-perf.4: gen pipeline performance thresholds (lazy-init stage).
        GEN_PIPELINE_PROJECT_COUNT: ClassVar[int] = 20
        GEN_PIPELINE_MODULES_PER_PROJECT: ClassVar[int] = 5
        GEN_PIPELINE_MAX_SECONDS: ClassVar[float] = 30.0
        GEN_PIPELINE_MEMORY_MAX_MB: ClassVar[float] = 500.0

        RELEASE_VERSION_BASE: ClassVar[str] = "0.1.0"
        RELEASE_VERSION_PATCH: ClassVar[str] = "0.1.1"
        RELEASE_VERSION_PRERELEASE: ClassVar[str] = "0.1.0rc0"
        RELEASE_PROJECTS: ClassVar[t.Pair[str, str]] = ("flext-a", "flext-b")
        # Fixture members depend on these siblings, so a release build must see
        # them to pin their declared versions.
        RELEASE_INTERNAL_DEPENDENCIES: ClassVar[t.Pair[str, str]] = (
            "flext-core",
            "flext-tests",
        )
        RELEASE_TAG_TARGET: ClassVar[str] = "v1.0.0"
        RELEASE_VERSION_TARGET: ClassVar[str] = "1.0.0"
        RELEASE_NOTES_HEADING: ClassVar[str] = "# Release v1.0.0"
        RELEASE_NOTES_CHANGE_LINE: ClassVar[str] = "- fix: release flow"
        RELEASE_INITIAL_CHANGE_LINE: ClassVar[str] = "- Initial tagged release"
        RELEASE_CHANGELOG_HEADER: ClassVar[str] = "# Changelog\n\n"


c = TestsFlextInfraConstants
__all__: list[str] = ["TestsFlextInfraConstants", "c"]
