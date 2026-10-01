"""Testmon SQLite integrity and saveability contracts."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import FlextInfraTestmonDbInspector, config, m


class TestsFlextInfraTestmonDbInspector:
    """Prove WAL checkpoint, integrity, and saveability decisions."""

    @staticmethod
    def test_missing_db_fails_loud(tmp_path: Path) -> None:
        filename = config.Infra.codegen.make.testmon_cache.database_filename
        repository_root = tmp_path / "checkout"
        repository_root.mkdir()
        inspector = FlextInfraTestmonDbInspector(
            repository_root=repository_root,
            db_path=tmp_path / "cache" / filename,
            pre_run_digest=None,
        )

        with pytest.raises(FileNotFoundError):
            inspector.execute()

    @staticmethod
    def test_database_inside_checkout_is_rejected(tmp_path: Path) -> None:
        repository_root = tmp_path / "checkout"
        repository_root.mkdir()

        with pytest.raises(ValueError, match="outside the repository checkout"):
            FlextInfraTestmonDbInspector(
                repository_root=repository_root,
                db_path=repository_root
                / config.Infra.codegen.make.testmon_cache.database_filename,
                pre_run_digest=None,
            )

    @staticmethod
    def test_corrupt_db_preserves_sqlite_failure(tmp_path: Path) -> None:
        repository_root = tmp_path / "checkout"
        repository_root.mkdir()
        db = (
            tmp_path
            / "cache"
            / config.Infra.codegen.make.testmon_cache.database_filename
        )
        db.parent.mkdir()
        db.write_text("not a sqlite database", encoding="utf-8")

        with pytest.raises(sqlite3.DatabaseError):
            FlextInfraTestmonDbInspector(
                repository_root=repository_root,
                db_path=db,
                pre_run_digest=None,
            ).execute()

    @staticmethod
    def test_healthy_new_db_is_saveable_seed(tmp_path: Path) -> None:
        repository_root = tmp_path / "checkout"
        repository_root.mkdir()
        db = (
            tmp_path
            / "cache"
            / config.Infra.codegen.make.testmon_cache.database_filename
        )
        db.parent.mkdir()
        connection = sqlite3.connect(db)
        connection.execute("CREATE TABLE meta (k TEXT, v TEXT)")
        connection.execute("INSERT INTO meta VALUES ('schema', '1')")
        connection.commit()
        connection.close()
        state: m.Infra.TestmonCacheState = tm.ok(
            FlextInfraTestmonDbInspector(
                repository_root=repository_root,
                db_path=db,
                pre_run_digest=None,
            ).execute(),
        )
        tm.that(state.seed_needed, eq=True)
        tm.that(state.saveable, eq=True)
        tm.that(state.reason, eq="seed_ready")

    @staticmethod
    def test_unchanged_db_is_not_saveable(tmp_path: Path) -> None:
        repository_root = tmp_path / "checkout"
        repository_root.mkdir()
        db = (
            tmp_path
            / "cache"
            / config.Infra.codegen.make.testmon_cache.database_filename
        )
        db.parent.mkdir()
        connection = sqlite3.connect(db)
        connection.execute("CREATE TABLE meta (k TEXT)")
        connection.commit()
        connection.close()
        digest = FlextInfraTestmonDbInspector.digest_file(db)
        state: m.Infra.TestmonCacheState = tm.ok(
            FlextInfraTestmonDbInspector(
                repository_root=repository_root,
                db_path=db,
                pre_run_digest=digest,
            ).execute(),
        )
        tm.that(state.changed, eq=False)
        tm.that(state.saveable, eq=False)
        tm.that(state.reason, eq="unchanged")

    @staticmethod
    def test_in_checkout_database_is_rejected(tmp_path: Path) -> None:
        filename = config.Infra.codegen.make.testmon_cache.database_filename

        with pytest.raises(ValueError, match="outside the repository checkout"):
            FlextInfraTestmonDbInspector(
                repository_root=tmp_path,
                db_path=tmp_path / filename,
                pre_run_digest=None,
            )
