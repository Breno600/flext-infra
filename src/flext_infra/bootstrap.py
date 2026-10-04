# Copyright 2026 FLEXT
"""Bootstrap owner: Mise lock reconcile, transactional publish and uv relock.

This module is the SINGLE owner of the dirty-tree recovery (operator
2026-10-02). It runs inside an interpreter that has ``flext_infra`` installed,
by module or by file path (``python .../flext_infra/bootstrap.py <verb> ...``);
every child process goes through the canonical ``u.Cli`` runner. The projected
``bin/mise-lock-transaction.py`` and ``bin/mise-lock-converge.py`` copies stay
stdlib-only for the generated Makefiles.

Verbs:
    publish   PROJECT STAGE          publish a staged mise.lock atomically
    recover   PROJECT STAGE          finish or undo an interrupted publication
    reconcile PROJECT RELEASE        rebuild a lock the pinned Mise satisfies
    relock    PROJECT                rebuild uv.lock and publish it by one rename
    converge  PROJECT STAGE RELEASE  hold failing tools in an upg lock stage

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

from flext_infra._bootstrap_mise import FlextInfraBootstrapMiseMixin


class FlextInfraBootstrap(FlextInfraBootstrapMiseMixin):
    """Command-line entry over the Mise transaction, reconcile and uv relock."""

    @staticmethod
    def _uv_binary() -> str:
        """Prefer the Mise-resolved uv shim, exactly as the lifecycle does.

        Returns:
            The resulting ``str``.

        Raises:
            ValueError: If uv executable is absent from PATH.
        """
        shim = (
            FlextInfraBootstrap._mise_storage_root()
            / "shims"
            / ("uv.exe" if os.name == "nt" else "uv")
        )
        if shim.is_file() and os.access(shim, os.X_OK):
            return str(shim)
        resolved = shutil.which("uv")
        if resolved is None:
            msg = "uv executable is absent from PATH"
            raise ValueError(msg)
        return resolved

    @classmethod
    def _uv_run(cls, arguments: list[str]) -> str:
        """Run one uv command; failures escape loudly with their output.

        Returns:
            The resulting ``str``.
        """
        return cls._checked("uv", [cls._uv_binary(), *arguments]).stdout

    @classmethod
    def relock(cls, project: Path) -> None:
        """Rebuild uv.lock in a scratch mirror and publish it by one rename.

        A merge that mixes dependency generations can leave the committed
        uv.lock behind the manifests; ``uv sync --locked`` then refuses and
        every verb that needs the environment deadlocks. This is the uv half
        of the reconcile: resolve in a scratch mirror of the manifests uv
        itself reports (seeded with the committed lock, so pinned versions are
        retained), prove it with ``uv lock --check``, and replace the committed
        lock by one rename inside its directory. An interrupted run never
        touches the committed lock.

        Raises:
            ValueError: If lock staging path already exists.
        """
        cls._physical_directory(project)
        workspace = Path(
            cls._uv_run(["workspace", "dir", "--project", str(project)]).strip(),
        )
        stage = Path(tempfile.mkdtemp(prefix=".uv-relock."))
        candidate = workspace / f".uv.lock.{os.getpid()}"
        try:
            members = cls._uv_run(
                ["workspace", "list", "--paths", "--project", str(workspace)],
            ).splitlines()
            for member in members:
                member = member.strip()
                if not member:
                    continue
                mirror = stage / "mirror" / member[len(str(workspace)) + 1 :]
                mirror.mkdir(parents=True, exist_ok=True)
                manifest = Path(member) / "pyproject.toml"
                if manifest.is_file():
                    shutil.copyfile(manifest, mirror / "pyproject.toml")
            lock = workspace / "uv.lock"
            if lock.is_file():
                shutil.copyfile(lock, stage / "mirror" / "uv.lock")
            cls._uv_run(["lock", "--project", str(stage / "mirror")])
            cls._uv_run(["lock", "--check", "--project", str(stage / "mirror")])
            if candidate.exists():
                msg = f"lock staging path already exists: {candidate}"
                raise ValueError(msg)
            shutil.copyfile(stage / "mirror" / "uv.lock", candidate)
            Path(candidate).replace(lock)
            print("relock: published uv.lock")
        finally:
            shutil.rmtree(stage, ignore_errors=True)
            if candidate.exists():
                candidate.unlink()

    @classmethod
    def main(cls, arguments: list[str]) -> int:
        """Provide ``main``.

        Returns:
            The resulting ``int``.

        Raises:
            ValueError: If usage.
        """
        if len(arguments) == 2 and arguments[0] == "relock":
            with cls._serialized(Path(arguments[1]).absolute()):
                cls.relock(Path(arguments[1]).absolute())
            return 0
        if len(arguments) == 4 and arguments[0] == "converge":
            project = Path(arguments[1]).absolute()
            with cls._serialized(project):
                cls.converge(project, Path(arguments[2]).absolute(), arguments[3])
            return 0
        if len(arguments) != 3 or arguments[0] not in {
            "publish",
            "recover",
            "reconcile",
        }:
            msg = (
                "usage: bootstrap.py (publish|recover) PROJECT STAGE"
                " | reconcile PROJECT RELEASE | relock PROJECT"
                " | converge PROJECT STAGE RELEASE"
            )
            raise ValueError(msg)
        project = Path(arguments[1]).absolute()
        if arguments[0] == "reconcile":
            with cls._serialized(project):
                cls.reconcile(project, arguments[2])
            return 0
        stage = Path(arguments[2]).absolute()
        with cls._serialized(project):
            if arguments[0] == "publish":
                cls.publish(project, stage)
            elif stage.exists() or stage.is_symlink():
                cls.recover(project, stage)
        return 0


if __name__ == "__main__":
    raise SystemExit(FlextInfraBootstrap.main(sys.argv[1:]))
