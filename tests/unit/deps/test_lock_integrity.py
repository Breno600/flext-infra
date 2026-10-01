"""Committed generated TOML lock integrity verification tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import c
from flext_infra.deps.lock_integrity import FlextInfraLockIntegrityVerifier

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDepsLockIntegrity:
    """Validate committed generated lock verification through its public model."""

    @staticmethod
    def _verifier(repository_root: Path) -> FlextInfraLockIntegrityVerifier:
        """Build the public verifier command for one repository root."""
        return FlextInfraLockIntegrityVerifier(repository_root=repository_root)

    def test_healthy_locks_verify_green(self, tmp_path: Path) -> None:
        """Parseable locks without repeated sections verify successfully."""
        (tmp_path / c.Infra.MISE_LOCK_FILENAME).write_text(
            '[tools."github:kucherenko/jscpd"]\nversion = "5.3.3"\n', encoding="utf-8"
        )
        (tmp_path / c.Infra.UV_LOCK_FILENAME).write_text(
            'version = 1\n[[package]]\nname = "filelock"\nversion = "4.0.6"\n',
            encoding="utf-8",
        )
        result = self._verifier(tmp_path).execute()
        tm.ok(result)
        tm.that(result.value, eq=True)

    def test_duplicated_sections_fail_with_file_and_keys(self, tmp_path: Path) -> None:
        """A merge-concatenated lock fails naming the file and duplicated keys."""
        (tmp_path / c.Infra.MISE_LOCK_FILENAME).write_text(
            '[tools."github:kucherenko/jscpd".options]\n'
            'asset_pattern = "jscpd-linux-x64-gnu.tar.gz"\n'
            "\n"
            '[tools."github:kucherenko/jscpd".options]\n'
            'asset_pattern = "jscpd-darwin-x64.tar.gz"\n',
            encoding="utf-8",
        )
        (tmp_path / c.Infra.UV_LOCK_FILENAME).write_text(
            "version = 1\n", encoding="utf-8"
        )
        error = tm.fail(self._verifier(tmp_path).execute())
        tm.that(error, has=c.Infra.MISE_LOCK_FILENAME)
        tm.that(error, has="duplicated sections")
        tm.that(error, has='tools."github:kucherenko/jscpd".options')

    def test_unparseable_lock_fails_with_parser_cause(self, tmp_path: Path) -> None:
        """A lock that is not TOML fails with the strict parser cause."""
        (tmp_path / c.Infra.MISE_LOCK_FILENAME).write_text(
            "not toml at all\n", encoding="utf-8"
        )
        (tmp_path / c.Infra.UV_LOCK_FILENAME).write_text(
            "version = 1\n", encoding="utf-8"
        )
        error = tm.fail(self._verifier(tmp_path).execute())
        tm.that(error, has=c.Infra.MISE_LOCK_FILENAME)

    def test_missing_locks_fail_loud(self, tmp_path: Path) -> None:
        """A repository root without any committed generated lock fails loud."""
        error = tm.fail(self._verifier(tmp_path).execute())
        tm.that(error, has="missing committed generated lock")
