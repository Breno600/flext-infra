"""Testmon SQLite integrity and saveability contracts."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import FlextInfraTestmonDbInspector, config, m


class TestsFlextInfraTestmonDbInspector:
    """Prove WAL checkpoint, integrity, and saveability decisions."""

    def test_missing_db_fails_loud(self, tmp_path: Path) -> None:
        filename = config.Infra.codegen.make.testmon_cache.database_filename
        inspector = FlextInfraTestmonDbInspector(
            repository_root=tmp_path, db_path=tmp_path / filename, pre_run_digest=None
        )

        with pytest.raises(FileNotFoundError):
            inspector.execute()

    def test_corrupt_db_preserves_sqlite_failure(self, tmp_path: Path) -> None:
        db = tmp_path / config.Infra.codegen.make.testmon_cache.database_filename
        db.write_text("not a sqlite database", encoding="utf-8")

        with pytest.raises(sqlite3.DatabaseError):
            FlextInfraTestmonDbInspector(
                repository_root=tmp_path, db_path=db, pre_run_digest=None
            ).execute()

    def test_healthy_new_db_is_saveable_seed(self, tmp_path: Path) -> None:
        db = tmp_path / config.Infra.codegen.make.testmon_cache.database_filename
        connection = sqlite3.connect(db)
        connection.execute("CREATE TABLE meta (k TEXT, v TEXT)")
        connection.execute("INSERT INTO meta VALUES ('schema', '1')")
        connection.commit()
        connection.close()
        state: m.Infra.TestmonCacheState = tm.ok(
            FlextInfraTestmonDbInspector(
                repository_root=tmp_path, db_path=db, pre_run_digest=None
            ).execute()
        )
        tm.that(state.seed_needed, eq=True)
        tm.that(state.saveable, eq=True)
        tm.that(state.reason, eq="seed_ready")

    def test_unchanged_db_is_not_saveable(self, tmp_path: Path) -> None:
        db = tmp_path / config.Infra.codegen.make.testmon_cache.database_filename
        connection = sqlite3.connect(db)
        connection.execute("CREATE TABLE meta (k TEXT)")
        connection.commit()
        connection.close()
        digest = FlextInfraTestmonDbInspector.digest_file(db)
        state: m.Infra.TestmonCacheState = tm.ok(
            FlextInfraTestmonDbInspector(
                repository_root=tmp_path, db_path=db, pre_run_digest=digest
            ).execute()
        )
        tm.that(state.changed, eq=False)
        tm.that(state.saveable, eq=False)
        tm.that(state.reason, eq="unchanged")
