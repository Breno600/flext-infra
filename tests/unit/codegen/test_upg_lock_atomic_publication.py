"""``make upg`` publishes uv.lock atomically: an interrupted run leaves it intact.

uv truncates and rewrites ``uv.lock`` in place, so a run killed while uv
wrote it left a partial lock behind (flext-idihq). The upgrade lifecycle
resolves in a scratch mirror and publishes by one rename, so the committed lock
survives any interruption byte-for-byte and a reader never observes a partial
file.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import errno
import os
import sys
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
        self,
        tmp_path: Path,
    ) -> None:
        """A run killed while uv resolves leaves the lock and checkout intact.

        Raises:
            BaseExceptionGroup: If upgrade observation and owned-session cleanup failed.

        """
        root, lock, committed = self._committed_project(tmp_path, python=">=3.13")
        # uv opens the find-links wheel to read its metadata. A FIFO without a
        # writer holds that open() in the kernel's ``wait_for_partner``, so the
        # interruption lands while uv is provably mid-run. Connecting a writer
        # would release it: uv seeks the zip, which a FIFO cannot serve.
        wheel = self._wheel_path(tmp_path)
        os.mkfifo(wheel)
        child = tm.ok(
            u.Cli.process_start(
                [c.Infra.MAKE, "_upg_lifecycle"],
                cwd=root,
                remove_env_keys=c.Tests.MAKE_ISOLATION_ENV_KEYS,
                start_new_session=True,
            ),
        )
        try:
            deadline = time.monotonic() + self.INTERRUPT_AFTER_SECONDS
            while time.monotonic() < deadline:
                tm.that(
                    child.poll(),
                    eq=None,
                    msg="upgrade exited before FIFO observation",
                )
                # uv opens the wheel on a tokio worker thread, whose thread
                # name is not "uv": identify the owned uv by its command line
                # and require that one of its threads waits on the FIFO.
                observed = tm.ok(
                    u.Cli.run(
                        ["ps", "--sid", str(child.pid), "-L", "-o", "wchan:64=,args="],
                        timeout=self.INTERRUPT_AFTER_SECONDS,
                    ),
                )
                # uv resolves on a tokio worker pool: the blocking wheel open
                # parks a thread whose comm is a runtime-internal name, never
                # the main ``uv`` thread. The owned uv process is identified by
                # its main-thread comm (execve names it), and the dependency
                # observation is any of its threads in wait_for_partner.
                if any(
                    len(fields) > 1
                    and fields[0] == "wait_for_partner"
                    and Path(fields[1]).name == c.Infra.UV
                    for fields in (row.split() for row in observed.stdout.splitlines())
                ):
                    break
                time.sleep(0.02)
            else:
                pytest.fail("owned uv never opened the dependency for resolution")
        finally:
            primary = sys.exception()
            try:
                tm.ok(child.terminate())
                status = tm.ok(child.wait(timeout=self.INTERRUPT_AFTER_SECONDS))
                self._release_fifo(wheel)
            except BaseException as cleanup_error:
                if primary is not None:
                    message = "upgrade observation and owned-session cleanup failed"
                    raise BaseExceptionGroup(
                        message,
                        [primary, cleanup_error],
                    ) from primary
                raise
        tm.that(status != 0, eq=True, msg=child.stderr)
        tm.that(lock.read_bytes(), eq=committed)
        tm.that(sorted(path.name for path in root.glob(".uv.lock.*")), eq=[])

    @pytest.mark.parametrize("conflicted", [False, True])
    def test_upg_replaces_lock_without_rewriting_the_committed_file(
        self,
        tmp_path: Path,
        *,
        conflicted: bool,
    ) -> None:
        """Publication swaps a complete lock in; a reader keeps the old one whole.

        Outside the setup bootstrap no Mise-resolved interpreter is handed
        over, so the lifecycle stops at the environment step right after
        publishing the lock.
        """
        root, lock, committed = self._committed_project(tmp_path, python=">=3.13")
        if conflicted:
            committed = (
                b"<<<<<<< HEAD\n"
                + committed
                + b"=======\n"
                + committed
                + b">>>>>>> integration\n"
            )
            lock.write_bytes(committed)
        self._write_wheel(self._wheel_path(tmp_path))
        with lock.open("rb") as reader:
            execution = tm.ok(
                u.Cli.run_raw(
                    [c.Infra.MAKE, "_upg_lifecycle"],
                    cwd=root,
                    env={"UV_PYTHON_DOWNLOADS": "never"},
                    timeout=self.INTERRUPT_AFTER_SECONDS,
                    remove_env_keys=(*c.Tests.MAKE_ISOLATION_ENV_KEYS, "SETUP_PYTHON"),
                ),
            )
            tm.that(reader.read(), eq=committed)
        tm.that(u.Cli.process_succeeded(execution.outcome), eq=False)
        tm.that(execution.stderr, has="missing Mise-resolved Python executable")
        tm.that(lock.read_text(encoding="utf-8"), has=f'name = "{self.DEPENDENCY}"')
        tm.ok(u.Cli.run_checked([c.Infra.UV, "lock", "--check", "--offline"], cwd=root))

    def _committed_project(
        self,
        tmp_path: Path,
        *,
        python: str,
    ) -> tuple[Path, Path, bytes]:
        """Render a real project whose committed lock predates one new dependency.

        Returns:
            The resulting ``tuple[Path, Path, bytes]``.

        """
        root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
            bootstrap=True,
        )
        links = self._wheel_path(tmp_path).parent
        links.mkdir()
        manifest = root / c.PYPROJECT_FILENAME
        for dependencies in ("", f'"{self.DEPENDENCY}"'):
            tm.ok(
                u.Cli.atomic_write_text_file(
                    manifest,
                    self.MANIFEST.format(
                        python=python,
                        dependencies=dependencies,
                        links=links.as_posix(),
                    ),
                ),
            )
            if not dependencies:
                tm.ok(u.Cli.run_checked([c.Infra.UV, "lock", "--offline"], cwd=root))
        lock = root / c.Infra.UV_LOCK_FILENAME
        return root, lock, lock.read_bytes()

    @staticmethod
    def _release_fifo(fifo: Path) -> None:
        """Give any reader still waiting on the FIFO its end of file.

        Raises:
            OSError: If ``error.errno != errno.ENXIO``.

        """
        try:
            writer = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
        except OSError as error:
            if error.errno != errno.ENXIO:
                raise
        else:
            os.close(writer)

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
