"""Tests for flext_infra.constants — Check, Github, Encoding, alias, and consistency.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import tm

from tests import c


class TestsFlextInfraInfraConstantsExtra:
    """Tests for Check namespace constants."""

    @staticmethod
    def test_github_constants_are_strings() -> None:
        """Test github constants are strings."""
        tm.that(c.Infra.GITHUB_REPO_URL, is_=str)
        tm.that(c.Infra.GITHUB_REPO_NAME, is_=str)

    @staticmethod
    def test_encoding_constant_is_string() -> None:
        """Test encoding constant is string."""
        tm.that(c.Infra.ENCODING_DEFAULT, is_=str)

    @staticmethod
    def test_c_alias_is_string() -> None:
        """Test c alias is string."""
        tm.that(c, is_=type)

    @staticmethod
    def test_excluded_dirs_are_immutable() -> None:
        """Test excluded dirs are immutable."""
        excluded = c.Infra.COMMON_EXCLUDED_DIRS
        tm.that(excluded, is_=frozenset)

    @staticmethod
    def test_all_status_values_are_uppercase() -> None:
        """Test all status values are uppercase."""
        tm.that(c.Infra.ResultStatus.PASSED.isupper(), eq=True)
        tm.that(c.Infra.ResultStatus.FAIL.isupper(), eq=True)
        tm.that(c.Infra.ResultStatus.OK.isupper(), eq=True)
        tm.that(c.Infra.ResultStatus.WARN.isupper(), eq=True)

    @staticmethod
    def test_all_gate_values_are_lowercase() -> None:
        """Test all gate values are lowercase."""
        gates = [
            c.Infra.LINT,
            c.Infra.FORMAT,
            c.Infra.PYREFLY,
            c.Infra.MYPY,
            c.Infra.PYRIGHT,
            c.Infra.SECURITY,
            c.Infra.MARKDOWN,
        ]
        for gate in gates:
            tm.that(gate.islower(), eq=True, msg=f"Gate {gate} should be lowercase")

    @staticmethod
    def test_excluded_dirs_no_duplicates() -> None:
        """Test excluded dirs no duplicates."""
        common = c.Infra.COMMON_EXCLUDED_DIRS
        doc = c.Infra.DOC_EXCLUDED_DIRS
        tm.that(len(common), eq=len(set(common)))
        tm.that(len(doc), eq=len(set(doc)))
