# Copyright 2026 FLEXT
"""The projected Mise publisher restores a usable lock after interrupted work.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import hashlib
import sys
from typing import TYPE_CHECKING

from flext_tests import tm

from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsMiseLockTransaction:
    """Exercise the consumer script through its generated CLI boundary."""

    @staticmethod
    def _stage(root: Path, suffix: str, *, crlf: bool = False) -> Path:
        stage = root.parent / f".{root.name}.mise-lock-stage.{suffix}"
        stage.mkdir()
        annotations: list[str] = []
        for package in ("alpha", "beta"):
            relative = f".mise/locks/npm-{package}/1.0"
            sidecar = stage / relative / "aube-lock.yaml"
            sidecar.parent.mkdir(parents=True)
            content = f"name: {package}\n".encode()
            sidecar.write_bytes(content.replace(b"\n", b"\r\n") if crlf else content)
            digest = hashlib.sha256(content).hexdigest()
            annotations.append(
                f'[[tools."npm:{package}"]]\n'
                'version = "1.0"\n'
                f'aube = {{ path = "{relative}", digest = "sha256:{digest}" }}\n',
            )
        (stage / "mise.lock").write_text("\n".join(annotations), encoding="utf-8")
        return stage

    @staticmethod
    def _publish(root: Path, stage: Path) -> tuple[bool, str]:
        outcome = tm.ok(
            u.Cli.run_raw(
                [
                    sys.executable,
                    str(root / "bin/mise-lock-transaction.py"),
                    "publish",
                    str(root),
                    str(stage),
                ],
                cwd=root,
            ),
        )
        return u.Cli.process_succeeded(outcome.outcome), outcome.stderr

    def test_interrupted_sidecar_publication_recovers_then_commits(
        self,
        tmp_path: Path,
    ) -> None:
        """A real filesystem conflict after one rename leaves the old graph usable."""
        root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        old = b"[tools]\n"
        lock = root / "mise.lock"
        lock.write_bytes(old)
        first = self._stage(root, "first")
        conflict = root / ".mise/locks/npm-beta"
        conflict.parent.mkdir(parents=True, exist_ok=True)
        conflict.write_text("not a directory", encoding="utf-8")

        passed, error = self._publish(root, first)

        tm.that(passed, eq=False)
        tm.that(error, has="transaction directory is not physical")
        tm.that(lock.read_bytes(), eq=old)
        tm.that((first / "transaction.json").is_file(), eq=True)
        tm.that((root / ".mise/locks/npm-alpha/1.0/aube-lock.yaml").is_file(), eq=True)

        conflict.unlink()
        second = self._stage(root, "second")
        expected = (second / "mise.lock").read_bytes()
        passed, error = self._publish(root, second)

        tm.that(passed, eq=True, msg=error)
        tm.that(lock.read_bytes(), eq=expected)
        tm.that(first.exists(), eq=False)
        tm.that(second.exists(), eq=False)
        for package in ("alpha", "beta"):
            tm.that(
                (root / f".mise/locks/npm-{package}/1.0/aube-lock.yaml").is_file(),
                eq=True,
            )

    def test_native_sidecar_digest_accepts_crlf_checkout(self, tmp_path: Path) -> None:
        """Mise records a normalized graph digest across checkout line endings."""
        root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        stage = self._stage(root, "crlf", crlf=True)

        passed, error = self._publish(root, stage)

        tm.that(passed, eq=True, msg=error)
        for package in ("alpha", "beta"):
            tm.that(
                (root / f".mise/locks/npm-{package}/1.0/aube-lock.yaml").read_bytes(),
                eq=f"name: {package}\r\n".encode(),
            )
