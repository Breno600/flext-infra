"""Tests for flext_infra.constants — core namespace constants.

Tests cover Paths, Files, Gates, Status, and Excluded namespaces.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import tm

from flext_infra import config
from flext_infra.check.workspace_check_gates import FlextInfraGateRegistry
from tests import c


class TestsFlextInfraInfraConstantsCore:
    """Tests for Paths namespace constants."""

    def test_venv_bin_rel_constant(self) -> None:
        tm.that(c.Infra.VENV_BIN_REL, eq=".venv/bin")

    def test_default_src_dir_constant(self) -> None:
        tm.that(c.Infra.DEFAULT_SRC_DIR, eq="src")

    def test_paths_constants_are_strings(self) -> None:
        tm.that(c.Infra.VENV_BIN_REL, is_=str)
        tm.that(c.Infra.DEFAULT_SRC_DIR, is_=str)

    def test_pyproject_filename_constant(self) -> None:
        tm.that(c.PYPROJECT_FILENAME, eq="pyproject.toml")

    def test_makefile_filename_constant(self) -> None:
        tm.that(c.Infra.MAKEFILE_FILENAME, eq="Makefile")

    def test_files_constants_are_strings(self) -> None:
        tm.that(c.PYPROJECT_FILENAME, is_=str)
        tm.that(c.Infra.MAKEFILE_FILENAME, is_=str)

    def test_gate_constants_resolve_config_check_gates(self) -> None:
        """Every config-declared default check gate resolves to a live gate.

        The gate vocabulary is config-owned (P0): instead of pinning the
        constant strings to today's literals, the constants must keep
        resolving the exact gate ids the generated Make surface will run.
        """
        registry = FlextInfraGateRegistry()
        for gate_id in config.Infra.codegen.make.check_gates_default:
            tm.that(registry.get(gate_id), none=False)

    def test_pass_status_constant(self) -> None:
        tm.that(c.Infra.ResultStatus.PASSED, eq="PASS")

    def test_fail_status_constant(self) -> None:
        tm.that(c.Infra.ResultStatus.FAIL, eq="FAIL")

    def test_ok_status_constant(self) -> None:
        tm.that(c.Infra.ResultStatus.OK, eq="OK")

    def test_warn_status_constant(self) -> None:
        tm.that(c.Infra.ResultStatus.WARN, eq="WARN")

    def test_status_constants_are_result_status_members(self) -> None:
        tm.that(c.Infra.ResultStatus.PASSED, is_=c.Infra.ResultStatus)
        tm.that(c.Infra.ResultStatus.FAIL, is_=c.Infra.ResultStatus)
        tm.that(c.Infra.ResultStatus.OK, is_=c.Infra.ResultStatus)
        tm.that(c.Infra.ResultStatus.WARN, is_=c.Infra.ResultStatus)

    def test_common_excluded_dirs_is_string(self) -> None:
        excluded = c.Infra.COMMON_EXCLUDED_DIRS
        tm.that(excluded, is_=frozenset)

    def test_common_excluded_dirs_contains_standard_dirs(self) -> None:
        excluded = c.Infra.COMMON_EXCLUDED_DIRS
        tm.that(excluded, has=".git")
        tm.that(excluded, has=".venv")
        tm.that(excluded, has="__pycache__")
        tm.that(excluded, has="dist")
        tm.that(excluded, has="build")
        tm.that(excluded, has="venv")

    def test_doc_excluded_dirs_includes_common(self) -> None:
        doc_excluded = c.Infra.DOC_EXCLUDED_DIRS
        common = c.Infra.COMMON_EXCLUDED_DIRS
        tm.that(doc_excluded.issuperset(common), eq=True)

    def test_doc_excluded_dirs_includes_site(self) -> None:
        tm.that(c.Infra.DOC_EXCLUDED_DIRS, has="site")

    def test_pyproject_skip_dirs_includes_common(self) -> None:
        skip_dirs = c.Infra.PYPROJECT_SKIP_DIRS
        common = c.Infra.COMMON_EXCLUDED_DIRS
        tm.that(skip_dirs.issuperset(common), eq=True)

    def test_pyproject_skip_dirs_includes_flext_dirs(self) -> None:
        skip_dirs = c.Infra.PYPROJECT_SKIP_DIRS
        tm.that(skip_dirs, has=".claude.disabled")
        tm.that(skip_dirs, has="context_test")
        tm.that(skip_dirs, has="rope_ws")
        tm.that(skip_dirs, has="tmp_flow_test")

    def test_check_excluded_dirs_includes_common(self) -> None:
        check_excluded = c.Infra.CHECK_EXCLUDED_DIRS
        common = c.Infra.COMMON_EXCLUDED_DIRS
        tm.that(check_excluded.issuperset(common), eq=True)

    def test_check_excluded_dirs_omit_operational_storage(self) -> None:
        tm.that(c.Infra.CHECK_EXCLUDED_DIRS, has=".beads")

    def test_excluded_dirs_are_strings(self) -> None:
        tm.that(c.Infra.DOC_EXCLUDED_DIRS, is_=frozenset)
        tm.that(c.Infra.PYPROJECT_SKIP_DIRS, is_=frozenset)
        tm.that(c.Infra.CHECK_EXCLUDED_DIRS, is_=frozenset)
