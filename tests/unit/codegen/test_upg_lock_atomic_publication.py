"""``make upg`` publishes uv.lock atomically: an interrupted run leaves it intact.

uv truncates and rewrites ``uv.lock`` in place, so a run killed while uv
wrote it left a partial lock behind (flext-idihq). The upgrade lifecycle
resolves in a scratch mirror and publishes by one rename, so the committed lock
survives any interruption byte-for-byte and a reader never observes a partial
file.
"""

from __future__ import annotations

import errno
import os
import threading
import time
import zipfile
from pathlib import Path
from typing import Final

import pytest
from flext_tests import tm

from tests import c, u

pytestmark = [pytest.mark.slow]


class TestsFlextInfraUpgLockAtomicPublication:
    """Run the real upgrade lifecycle around its lock publication."""

    DEPENDENCY: Final = "fixture-dependency"
    INTERRUPT_AFTER_SECONDS: Final = 8
    MANIFEST: Final = (
        "[project]\n"
        'name = "fixture-project"\n'
        'version = "0.1.0"\n'
        'requires-python = "{python}"\n'
        "dependencies = [{dependencies}]\n"
        "[tool.uv]\n"
        "no-index = true\n"
        'find-links = ["{links}"]\n'
    )

    def test_interrupted_upg_leaves_committed_lock_untouched(
        self, tmp_path: Path
    ) -> None:
        """A run killed while uv resolves leaves the lock and checkout intact."""
        root, lock, committed = self._committed_project(tmp_path, python=">=3.13")
        # uv opens the find-links wheel to read its metadata; a FIFO holds that
        # read, so the interruption lands while uv is provably mid-run.
        wheel = self._wheel_path(tmp_path)
        os.mkfifo(wheel)
        writers: list[int] = []
        stop = threading.Event()
        watcher = threading.Thread(target=self._hold_fifo, args=(wheel, writers, stop))
        watcher.start()
        try:
            execution = tm.ok(
                u.Cli.run_raw(
                    [c.Infra.MAKE, "_upg_lifecycle"],
                    cwd=root,
                    timeout=self.INTERRUPT_AFTER_SECONDS,
                    remove_env_keys=c.Tests.MAKE_ISOLATION_ENV_KEYS,
                )
            )
        finally:
            stop.set()
            watcher.join()
            for writer in writers:
                os.close(writer)
        tm.that(writers, len=1, msg="uv never opened the dependency for resolution")
        tm.that(execution.outcome.timed_out, eq=True, msg=execution.stderr)
        tm.that(lock.read_bytes(), eq=committed)
        tm.that(sorted(path.name for path in root.glob(".uv.lock.*")), eq=[])

    def test_upg_replaces_lock_without_rewriting_the_committed_file(
        self, tmp_path: Path
    ) -> None:
        """Publication swaps a complete lock in; a reader keeps the old one whole.

        No interpreter satisfies the manifest, so the lifecycle stops at the
        environment step right after publishing the lock.
        """
        root, lock, committed = self._committed_project(tmp_path, python=">=3.99")
        self._write_wheel(self._wheel_path(tmp_path))
        with lock.open("rb") as reader:
            execution = tm.ok(
                u.Cli.run_raw(
                    [c.Infra.MAKE, "_upg_lifecycle"],
                    cwd=root,
                    env={"UV_PYTHON_DOWNLOADS": "never"},
                    timeout=self.INTERRUPT_AFTER_SECONDS,
                    remove_env_keys=c.Tests.MAKE_ISOLATION_ENV_KEYS,
                )
            )
            tm.that(reader.read(), eq=committed)
        tm.that(u.Cli.process_succeeded(execution.outcome), eq=False)
        tm.that(lock.read_text(encoding="utf-8"), has=f'name = "{self.DEPENDENCY}"')
        tm.ok(u.Cli.run_checked([c.Infra.UV, "lock", "--check", "--offline"], cwd=root))

    def _committed_project(
        self, tmp_path: Path, *, python: str
    ) -> tuple[Path, Path, bytes]:
        """Render a real project whose committed lock predates one new dependency."""
        root, _ = u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.STANDALONE, bootstrap=True
        )
        links = self._wheel_path(tmp_path).parent
        links.mkdir()
        manifest = root / c.PYPROJECT_FILENAME
        for dependencies in ("", f'"{self.DEPENDENCY}"'):
            tm.ok(
                u.Cli.atomic_write_text_file(
                    manifest,
                    self.MANIFEST.format(
                        python=python, dependencies=dependencies, links=links.as_posix()
                    ),
                )
            )
            if not dependencies:
                tm.ok(u.Cli.run_checked([c.Infra.UV, "lock", "--offline"], cwd=root))
        lock = root / c.Infra.UV_LOCK_FILENAME
        return root, lock, lock.read_bytes()

    def _hold_fifo(
        self, wheel: Path, writers: list[int], stop: threading.Event
    ) -> None:
        """Open a FIFO writer once uv reads it, holding uv's read open."""
        while not stop.is_set():
            try:
                writers.append(os.open(wheel, os.O_WRONLY | os.O_NONBLOCK))
            except OSError as error:
                if error.errno != errno.ENXIO:
                    raise
                time.sleep(0.02)
            else:
                return

    def _wheel_path(self, tmp_path: Path) -> Path:
        name = self.DEPENDENCY.replace("-", "_")
        return tmp_path / "links" / f"{name}-1.0-py3-none-any.whl"

    def _write_wheel(self, wheel: Path) -> None:
        """Write the smallest valid pure wheel carrying the dependency metadata."""
        info = f"{self.DEPENDENCY.replace('-', '_')}-1.0.dist-info"
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr(
                f"{info}/METADATA",
                f"Metadata-Version: 2.1\nName: {self.DEPENDENCY}\nVersion: 1.0\n",
            )
            archive.writestr(
                f"{info}/WHEEL",
                "Wheel-Version: 1.0\nGenerator: fixture\n"
                "Root-Is-Purelib: true\nTag: py3-none-any\n",
            )
            archive.writestr(f"{info}/RECORD", "")
