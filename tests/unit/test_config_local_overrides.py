"""Contract for the gitignored per-clone local config override file.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from flext_tests import tm

from flext_core import e
from flext_infra import FlextInfraConfig, c


class TestsFlextInfraConfigLocalOverrides:
    """Prove the local override file merges last through the public surface."""

    @staticmethod
    def _copy_tracked_configs(target: Path) -> None:
        """Seed one config directory with the real tracked fleet config."""
        for tracked in FlextInfraConfig.ssot_config_dir().glob("*.yaml"):
            shutil.copy(tracked, target / tracked.name)

    def test_tracked_configs_keep_fleet_defaults(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without a local file the tracked scalar survives untouched.

        The expectation is the tracked SSOT read itself (P0): any legitimate
        config change keeps both loads equal, and only a broken merge diverges.
        """
        self._copy_tracked_configs(tmp_path)
        baseline = FlextInfraConfig.fetch_global()
        monkeypatch.setenv("FLEXT_INFRA_CONFIG_DIR", str(tmp_path))
        FlextInfraConfig.reset_for_testing()
        try:
            fresh = FlextInfraConfig.fetch_global()
            tm.that(
                fresh.Infra.codegen.loc_cap.max_lines,
                eq=baseline.Infra.codegen.loc_cap.max_lines,
            )
        finally:
            FlextInfraConfig.reset_for_testing()

    def test_local_file_scalar_wins_despite_sorted_glob_position(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The local override wins scalars although its name sorts first.

        ``codegen-overrides.local.yaml`` sorts before the tracked files, so a
        plain glob would let the tracked config clobber it; the loader must
        anchor it last regardless of lexicographic position.
        """
        self._copy_tracked_configs(tmp_path)
        (tmp_path / c.Infra.CODEGEN_LOCAL_OVERRIDES_FILENAME).write_text(
            "Infra:\n  codegen:\n    loc_cap:\n      max_lines: 500\n", encoding="utf-8"
        )
        monkeypatch.setenv("FLEXT_INFRA_CONFIG_DIR", str(tmp_path))
        FlextInfraConfig.reset_for_testing()
        try:
            fresh = FlextInfraConfig.fetch_global()
            tm.that(fresh.Infra.codegen.loc_cap.max_lines, eq=500)
        finally:
            FlextInfraConfig.reset_for_testing()

    def test_local_file_dict_entries_add_beside_tracked_ones(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A dict-typed registry gains the local entry and keeps tracked ones."""
        self._copy_tracked_configs(tmp_path)
        (tmp_path / c.Infra.CODEGEN_LOCAL_OVERRIDES_FILENAME).write_text(
            "Infra:\n"
            "  codegen:\n"
            "    layout:\n"
            "      project_overrides:\n"
            "        example-project:\n"
            "          ignore_globs:\n"
            "            - example\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("FLEXT_INFRA_CONFIG_DIR", str(tmp_path))
        FlextInfraConfig.reset_for_testing()
        try:
            fresh = FlextInfraConfig.fetch_global()
            overrides = fresh.Infra.codegen.layout.project_overrides
            tm.that("example-project" in overrides, eq=True)
            tm.that("flext-cli" in overrides, eq=True)
        finally:
            FlextInfraConfig.reset_for_testing()

    def test_org_layer_from_governed_repository_resolves(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The governed repository's tracked org layer merges last in its cwd.

        CI runs the generator from the governed repository root, where no
        operator-local file exists: the org layer is what lets a private
        organization declare its own doc checkouts on a runner. A provider
        registry is not part of that surface — provider identity is detected
        from each repository's own workspace manifest, and a org-layer
        ``providers`` block now fails validation loudly.
        """
        self._copy_tracked_configs(tmp_path)
        org_root = tmp_path / "org-repo"
        (org_root / c.Infra.CODEGEN_CONFIG_DIR).mkdir(parents=True)
        (
            org_root
            / c.Infra.CODEGEN_CONFIG_DIR
            / c.Infra.CODEGEN_ORG_OVERRIDES_FILENAME
        ).write_text(
            "Infra:\n"
            "  codegen:\n"
            "    make:\n"
            "      docs:\n"
            "        github_repos:\n"
            "          - organization: example-org\n"
            "            repository: example-docs\n"
            "            branch: main\n"
            "            local_checkout: ~/example-docs\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("FLEXT_INFRA_CONFIG_DIR", str(tmp_path))
        monkeypatch.chdir(org_root)
        FlextInfraConfig.reset_for_testing()
        try:
            fresh = FlextInfraConfig.fetch_global()
            orgs = [
                entry.organization
                for entry in fresh.Infra.codegen.make.docs.github_repos
            ]
            tm.that("example-org" in orgs, eq=True)
            tm.that("flext-sh" in orgs, eq=True)
        finally:
            FlextInfraConfig.reset_for_testing()

    def test_provider_registry_declaration_fails_validation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The exterminated provider registry cannot come back through a merge."""
        self._copy_tracked_configs(tmp_path)
        (tmp_path / c.Infra.CODEGEN_LOCAL_OVERRIDES_FILENAME).write_text(
            "Infra:\n"
            "  codegen:\n"
            "    providers:\n"
            "      - name: example-org\n"
            "        organization: example-org\n"
            "        base_url: https://github.com/example-org\n"
            "        branch: main\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("FLEXT_INFRA_CONFIG_DIR", str(tmp_path))
        FlextInfraConfig.reset_for_testing()
        try:
            # The settings boundary surfaces pydantic's own ValidationError
            # (public alias e.PydanticValidationError); the exterminated
            # providers registry is rejected as a forbidden extra field.
            with pytest.raises(e.PydanticValidationError, match="providers"):
                FlextInfraConfig.fetch_global()
        finally:
            FlextInfraConfig.reset_for_testing()
