"""Typed post-run integrity and saveability for pytest-testmon SQLite DBs."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Self, override

from flext_core import r
from flext_infra import m, u

from ..base import s

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraTestmonDbInspector(s[m.Infra.TestmonCacheState]):
    """Checkpoint WAL, verify integrity, and compute saveability."""

    db_path: Annotated[Path, m.Field(description="Absolute .testmondata path.")]
    pre_run_digest: Annotated[
        str | None,
        m.Field(default=None, description="Hex digest of DB bytes before pytest."),
    ] = None

    @u.model_validator(mode="after")
    def _validate_absolute_db(self) -> Self:
        """Reject relative or empty DB paths."""
        if not self.db_path.is_absolute():
            msg = "testmon db_path must be absolute"
            raise ValueError(msg)
        return self

    @staticmethod
    def digest_file(path: Path) -> str | None:
        """Return a stable digest; absence alone denotes an unseeded cache."""
        if path.is_symlink():
            msg = f"testmon db must not be a symlink: {path}"
            raise ValueError(msg)
        if not path.exists():
            return None
        if not path.is_file():
            msg = f"testmon db must be a regular file: {path}"
            raise ValueError(msg)
        if path.stat().st_size == 0:
            msg = f"testmon db must not be empty: {path}"
            raise ValueError(msg)
        return u.Cli.sha256_file(path)

    @staticmethod
    def _validate_open_db(connection: sqlite3.Connection) -> None:
        """Raise on the first invalid SQLite cache property."""
        checkpoint = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if checkpoint is None or int(checkpoint[0]) != 0:
            msg = f"testmon wal_checkpoint busy={checkpoint!r}"
            raise RuntimeError(msg)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            msg = f"testmon integrity_check={integrity!r}"
            raise RuntimeError(msg)
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if not tables:
            msg = "testmon schema empty"
            raise RuntimeError(msg)

    def _inspect_existing(self) -> p.Result[m.Infra.TestmonCacheState]:
        """Validate one on-disk DB after pytest has closed it."""
        path = self.db_path
        if path.is_symlink():
            msg = f"testmon db must not be a symlink: {path}"
            raise ValueError(msg)
        if not path.exists():
            raise FileNotFoundError(path)
        if not path.is_file():
            msg = f"testmon db must be a regular file: {path}"
            raise ValueError(msg)
        if path.stat().st_size == 0:
            msg = f"testmon db must not be empty: {path}"
            raise ValueError(msg)
        with closing(sqlite3.connect(f"file:{path}?mode=rw", uri=True)) as connection:
            self._validate_open_db(connection)
        post_digest = self.digest_file(path)
        changed = post_digest is not None and post_digest != self.pre_run_digest
        seed_needed = self.pre_run_digest is None
        saveable = seed_needed or changed
        if seed_needed:
            reason = "seed_ready"
        elif changed:
            reason = "changed_saveable"
        else:
            reason = "unchanged"
        return r[m.Infra.TestmonCacheState].ok(
            m.Infra.TestmonCacheState(
                seed_needed=seed_needed,
                restored_accepted=self.pre_run_digest is not None,
                changed=changed,
                saveable=saveable,
                reason=reason,
            )
        )

    @override
    def execute(self) -> p.Result[m.Infra.TestmonCacheState]:
        """Return typed cache state after a successful testmon-backed pytest run."""
        return self._inspect_existing()


__all__: list[str] = ["FlextInfraTestmonDbInspector"]
