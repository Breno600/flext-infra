# Copyright 2026 FLEXT
"""Stdlib-only bootstrap owner: Mise lock reconcile and transactional publish.

This module is the SINGLE owner of the dirty-tree recovery the generated
Makefiles invoke (operator 2026-10-02). It must stay importable and executable
with a bare CPython interpreter and no third-party dependencies, even when the
workspace virtual environment, ``uv.lock``, or ``mise.lock`` are broken: run it
by file path (``python .../flext_infra/bootstrap.py <verb> ...``) so importing
the ``flext_infra`` package is never required. Projected copies
(``bin/mise-lock-transaction.py``) are thin shims that delegate here.

Verbs:
    publish   PROJECT STAGE      publish a staged mise.lock atomically
    recover   PROJECT STAGE      finish or undo an interrupted publication
    reconcile PROJECT RELEASE    rebuild a lock the pinned Mise satisfies

Its journal and project-scoped mutex recover process interruption on every
platform. Directory fsync is POSIX-only; Windows power-loss durability is not
promised by this transaction.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

STORAGE_DIRECTORIES = ("cache", "state", "installs", "shims", "uv-cache", "bootstrap")
"""Persistent Mise storage layout (mirrors the bootstrap recipe contract)."""


class FlextInfraBootstrap:
    """Keep the old lock usable until every new sidecar is published."""

    JOURNAL = "transaction.json"
    NEW_LOCK = "new.lock"
    OLD_LOCK = "old.lock"
    # Artifact set declared by flext-infra/config/codegen.yaml toolchain rows:
    # Unix launcher, Windows launcher, and the resolved-release pin with modes.
    ARTIFACTS = (
        ("bin/mise", 0o755),
        ("bin/mise.cmd", 0o644),
        ("mise.version", 0o644),
    )
    MUTEX = ".mise-lock-transaction.lock"
    MUTEX_TIMEOUT_SECONDS = 600.0

    @staticmethod
    @contextmanager
    def _serialized(project: Path) -> Iterator[None]:
        """Serialize all publisher versions on one declared physical mutex.

        Raises:
            ValueError: If Mise transaction mutex is a symlink; or if Mise transaction
                mutex is not physical; or if Mise transaction mutex is held elsewhere
                for over.
        """
        mutex = project / FlextInfraBootstrap.MUTEX
        if mutex.is_symlink():
            raise ValueError(f"Mise transaction mutex is a symlink: {mutex}")
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(mutex, flags, 0o600)
        try:
            observed = os.fstat(descriptor)
            if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
                raise ValueError(f"Mise transaction mutex is not physical: {mutex}")
            if observed.st_size == 0:
                os.write(descriptor, b"\0")
                os.fsync(descriptor)
            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                deadline = time.monotonic() + FlextInfraBootstrap.MUTEX_TIMEOUT_SECONDS
                while True:
                    try:
                        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise ValueError(
                                "Mise transaction mutex is held elsewhere for over "
                                f"{FlextInfraBootstrap.MUTEX_TIMEOUT_SECONDS:.0f}s: {mutex}",
                            ) from None
                        time.sleep(0.2)
            try:
                yield
            finally:
                if os.name == "nt":
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)

    @staticmethod
    def _physical_directory(path: Path) -> None:
        observed = path.lstat()
        if not stat.S_ISDIR(observed.st_mode):
            raise ValueError(f"transaction directory is not physical: {path}")

    @staticmethod
    def _bytes(path: Path) -> bytes | None:
        try:
            observed = path.lstat()
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
            raise ValueError(f"transaction file is not physical: {path}")
        return path.read_bytes()

    @staticmethod
    def _digest(content: bytes | None) -> str | None:
        return None if content is None else hashlib.sha256(content).hexdigest()

    @staticmethod
    def _sidecar_selector(relative: str) -> PurePosixPath:
        selector = PurePosixPath(relative)
        if (
            selector.is_absolute()
            or selector.as_posix() != relative
            or len(selector.parts) < 4
            or selector.parts[:2] != (".mise", "locks")
            or ".." in selector.parts
        ):
            raise ValueError(f"unsafe mise.lock sidecar: {relative}")
        return selector

    @classmethod
    def _sidecars(cls, content: bytes | None, root: Path) -> dict[str, str]:
        if content is None:
            return {}
        payload = tomllib.loads(content.decode("utf-8"))
        tools = payload.get("tools")
        if not isinstance(tools, dict):
            raise ValueError("mise.lock has no tools table")
        result: dict[str, str] = {}
        for entries in tools.values():
            for entry in entries if isinstance(entries, list) else (entries,):
                if not isinstance(entry, dict):
                    raise ValueError("mise.lock tool entry is not a table")
                for graph, filename in (("aube", "aube-lock.yaml"), ("uv", "uv.lock")):
                    annotation = entry.get(graph)
                    if annotation is None:
                        continue
                    if not isinstance(annotation, dict):
                        raise ValueError(f"mise.lock {graph} annotation is not a table")
                    relative = annotation.get("path")
                    digest = annotation.get("digest")
                    if not isinstance(relative, str) or not isinstance(digest, str):
                        raise ValueError(f"mise.lock {graph} annotation is incomplete")
                    selector = cls._sidecar_selector(relative)
                    if not digest.startswith("sha256:"):
                        raise ValueError(
                            f"invalid mise.lock sidecar digest: {relative}"
                        )
                    cls._reject_symlink_path(root, relative)
                    sidecar = root.joinpath(*selector.parts)
                    cls._physical_directory(sidecar)
                    source = cls._bytes(sidecar / filename)
                    if source is None:
                        raise ValueError(
                            f"mise.lock sidecar is absent: {sidecar / filename}"
                        )
                    actual = hashlib.sha256(source.replace(b"\r\n", b"\n")).hexdigest()
                    if actual != digest.removeprefix("sha256:"):
                        raise ValueError(
                            f"mise.lock sidecar digest differs: {sidecar / filename}"
                        )
                    result[relative] = cls._tree_digest(sidecar)
        return result

    @classmethod
    def _previous_sidecars(cls, content: bytes | None, project: Path) -> dict[str, str]:
        """Read the owned graph from Git stage 2 during a lock merge conflict.

        Returns:
            The resulting ``dict[str, str]``.

        Raises:
            ValueError: If conflicted mise.lock has no Git stage-2 source.
        """
        if content is None or b"<<<<<<< " not in content:
            return cls._sidecars(content, project)
        index = subprocess.run(
            ["git", "-C", str(project), "ls-files", "-u", "--", "mise.lock"],
            check=True,
            capture_output=True,
        ).stdout
        if not any(
            line.split(b"\t", 1)[0].endswith(b" 2") for line in index.splitlines()
        ):
            raise ValueError("conflicted mise.lock has no Git stage-2 source")
        prior = subprocess.run(
            ["git", "-C", str(project), "show", ":2:mise.lock"],
            check=True,
            capture_output=True,
        ).stdout
        return cls._sidecars(prior, project)

    @classmethod
    def _tree_digest(cls, root: Path) -> str:
        cls._physical_directory(root)
        checksum = hashlib.sha256()
        for path in sorted(root.rglob("*")):
            observed = path.lstat()
            relative = path.relative_to(root).as_posix().encode()
            if stat.S_ISDIR(observed.st_mode):
                checksum.update(b"D\0" + relative + b"\0")
            elif stat.S_ISREG(observed.st_mode) and observed.st_nlink == 1:
                checksum.update(b"F\0" + relative + b"\0" + path.read_bytes())
            else:
                raise ValueError(f"nonphysical mise sidecar entry: {path}")
        return checksum.hexdigest()

    @staticmethod
    def _sync_directory(path: Path) -> None:
        """Sync POSIX directory metadata; Windows relies on journal recovery."""
        if os.name == "nt":
            return
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @classmethod
    def _sync_tree(cls, root: Path) -> None:
        """Persist staged payload bytes before publishing the journal.

        Raises:
            ValueError: If nonphysical Mise stage entry.
        """
        cls._physical_directory(root)
        for path in sorted(root.rglob("*"), reverse=True):
            observed = path.lstat()
            if stat.S_ISDIR(observed.st_mode):
                cls._sync_directory(path)
            elif stat.S_ISREG(observed.st_mode) and observed.st_nlink == 1:
                descriptor = os.open(path, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            else:
                raise ValueError(f"nonphysical Mise stage entry: {path}")
        cls._sync_directory(root)

    @classmethod
    def _write_journal(cls, stage: Path, journal: dict[str, str]) -> None:
        candidate = stage / "transaction.json.new"
        with candidate.open("x", encoding="utf-8") as stream:
            json.dump(journal, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        Path(candidate).replace(stage / cls.JOURNAL)
        cls._sync_directory(stage)

    @classmethod
    def _read_journal(cls, stage: Path) -> dict[str, str] | None:
        content = cls._bytes(stage / cls.JOURNAL)
        if content is None:
            return None
        payload = json.loads(content)
        if not isinstance(payload, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in payload.items()
        ):
            raise ValueError(f"invalid Mise lock transaction journal: {stage}")
        return payload

    @staticmethod
    def _journal_refs(journal: dict[str, str], name: str) -> dict[str, str]:
        raw = journal.get(name)
        if raw is None:
            raise ValueError(f"Mise lock journal lacks {name}")
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in payload.items()
        ):
            raise ValueError(f"Mise lock journal has invalid {name}")
        for relative in payload:
            FlextInfraBootstrap._sidecar_selector(relative)
        return payload

    @classmethod
    def _artifact_refs(cls, root: Path) -> dict[str, str]:
        return {
            relative: cls._digest(cls._bytes(root / relative)) or ""
            for relative, _mode in cls.ARTIFACTS
        }

    @classmethod
    def _journal_artifacts(cls, journal: dict[str, str], name: str) -> dict[str, str]:
        raw = journal.get(name)
        if raw is None:
            raise ValueError(f"Mise lock journal lacks {name}")
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in payload.items()
        ):
            raise ValueError(f"Mise lock journal has invalid {name}")
        return payload

    @classmethod
    def _recover_artifacts(
        cls, project: Path, stage: Path, journal: dict[str, str]
    ) -> None:
        old_refs = cls._journal_artifacts(journal, "old_artifacts")
        new_refs = cls._journal_artifacts(journal, "new_artifacts")
        declared = {relative for relative, _mode in cls.ARTIFACTS}
        if set(old_refs) != declared or set(new_refs) != declared:
            raise ValueError("Mise transaction artifact manifest is incomplete")
        for relative, mode in cls.ARTIFACTS:
            source = stage / "new-artifacts" / relative
            expected = new_refs[relative]
            if cls._digest(cls._bytes(source)) != expected:
                raise ValueError(f"staged Mise artifact changed: {source}")
            target = project / relative
            current = cls._digest(cls._bytes(target))
            if current == expected:
                continue
            if current != (old_refs[relative] or None):
                raise ValueError(f"Mise artifact changed outside transaction: {target}")
            pending = stage / "pending-artifacts" / relative
            cls._ensure_parent(stage, pending)
            shutil.copyfile(source, pending)
            Path(pending).chmod(mode)
            descriptor = os.open(pending, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            cls._ensure_parent(project, target)
            Path(pending).replace(target)
            cls._sync_directory(target.parent)

    @classmethod
    def _require_roots(cls, project: Path, stage: Path) -> None:
        cls._physical_directory(project)
        cls._physical_directory(stage)
        if stage.parent != project.parent or stage == project:
            raise ValueError("Mise lock stage must be a sibling of its destination")
        if stage.stat().st_dev != project.stat().st_dev:
            raise ValueError("Mise lock stage is not on the destination filesystem")
        if not stage.name.startswith(f".{project.name}.mise-lock-stage."):
            raise ValueError(f"unexpected Mise lock transaction stage: {stage}")

    @staticmethod
    def _reject_symlink_path(project: Path, relative: str) -> None:
        cursor = project
        for part in PurePosixPath(relative).parts:
            cursor /= part
            if cursor.is_symlink():
                raise ValueError(f"Mise sidecar path contains a symlink: {cursor}")

    @classmethod
    def _ensure_parent(cls, root: Path, target: Path) -> None:
        """Materialize physical parents and durably record each directory entry.

        Raises:
            ValueError: If Mise sidecar escapes transaction root.
        """
        if not target.is_relative_to(root):
            raise ValueError(f"Mise sidecar escapes transaction root: {target}")
        missing: list[Path] = []
        cursor = target.parent
        while cursor != root:
            missing.append(cursor)
            cursor = cursor.parent
        for directory in reversed(missing):
            if directory.exists():
                cls._physical_directory(directory)
            else:
                directory.mkdir()
                cls._sync_directory(directory.parent)

    @classmethod
    def _retire_stage(cls, stage: Path) -> None:
        """Move a completed journal out of the recovery scan before deleting it.

        Raises:
            ValueError: If Mise cleanup target already exists.
        """
        retired = stage.with_name(
            stage.name.replace(".mise-lock-stage.", ".mise-lock-cleanup.", 1),
        )
        if retired.exists() or retired.is_symlink():
            raise ValueError(f"Mise cleanup target already exists: {retired}")
        Path(stage).rename(retired)
        cls._sync_directory(stage.parent)
        shutil.rmtree(retired)

    @classmethod
    def recover(cls, project: Path, stage: Path) -> None:
        """Finish or undo a prior interrupted publication by its lock commit point.

        Raises:
            ValueError: If uncommitted Mise stage has no recovery journal; or if Mise
                lock journal belongs to another project; or if Mise lock journal lost
                new lock; or if Mise lock journal digest changed; or if Mise lock
                changed outside transaction; or if committed Mise sidecar differs; or if
                stale sidecar changed during recovery; or if stale sidecar disappeared
                during recovery; or if old Mise sidecar changed during recovery; or if
                old Mise sidecar missing during recovery; or if unowned Mise sidecar
                changed during recovery.
        """
        cls._require_roots(project, stage)
        journal = cls._read_journal(stage)
        if journal is None:
            raise ValueError(f"uncommitted Mise stage has no recovery journal: {stage}")
        if journal.get("project") != str(project):
            raise ValueError(f"Mise lock journal belongs to another project: {stage}")
        old = cls._bytes(stage / cls.OLD_LOCK)
        new = cls._bytes(stage / cls.NEW_LOCK)
        if new is None:
            raise ValueError(f"Mise lock journal lost new lock: {stage}")
        if cls._digest(old) != (journal.get("old") or None) or cls._digest(
            new
        ) != journal.get("new"):
            raise ValueError(f"Mise lock journal digest changed: {stage}")
        old_refs = cls._journal_refs(journal, "old_refs")
        new_refs = cls._journal_refs(journal, "new_refs")
        for relative in old_refs | new_refs:
            cls._reject_symlink_path(project, relative)
        live = cls._bytes(project / "mise.lock")
        if live == old:
            for relative, expected in new_refs.items():
                destination = project / relative
                backup = stage / "old-sidecars" / relative
                abandoned = stage / "abandoned-sidecars" / relative
                if (
                    destination.exists()
                    and cls._tree_digest(destination) == expected
                    and expected != old_refs.get(relative)
                ):
                    cls._ensure_parent(stage, abandoned)
                    Path(destination).rename(abandoned)
                    cls._sync_directory(destination.parent)
                    cls._sync_directory(abandoned.parent)
                if backup.exists():
                    if (
                        destination.exists()
                        or cls._tree_digest(backup) != old_refs[relative]
                    ):
                        raise ValueError(
                            f"old Mise sidecar changed during recovery: {backup}"
                        )
                    cls._ensure_parent(project, destination)
                    Path(backup).rename(destination)
                    cls._sync_directory(backup.parent)
                    cls._sync_directory(destination.parent)
                elif relative in old_refs:
                    if (
                        not destination.exists()
                        or cls._tree_digest(destination) != old_refs[relative]
                    ):
                        raise ValueError(
                            f"old Mise sidecar missing during recovery: {destination}"
                        )
                elif destination.exists():
                    raise ValueError(
                        f"unowned Mise sidecar changed during recovery: {destination}"
                    )
            cls._retire_stage(stage)
            return
        if live != new:
            raise ValueError(
                f"Mise lock changed outside transaction: {project / 'mise.lock'}"
            )
        for relative, expected in new_refs.items():
            destination = project / relative
            if not destination.exists() or cls._tree_digest(destination) != expected:
                raise ValueError(f"committed Mise sidecar differs: {destination}")
        for relative, expected in old_refs.items():
            if relative in new_refs:
                continue
            destination = project / relative
            retired = stage / "retired-sidecars" / relative
            if destination.exists():
                if cls._tree_digest(destination) != expected:
                    raise ValueError(
                        f"stale sidecar changed during recovery: {destination}"
                    )
                cls._ensure_parent(stage, retired)
                Path(destination).rename(retired)
                cls._sync_directory(destination.parent)
                cls._sync_directory(retired.parent)
            elif not retired.exists():
                raise ValueError(
                    f"stale sidecar disappeared during recovery: {destination}"
                )
        if "new_artifacts" in journal:
            cls._recover_artifacts(project, stage, journal)
        cls._retire_stage(stage)

    @classmethod
    def publish(cls, project: Path, stage: Path) -> None:
        """Publish sidecars first and make the lock rename the commit point.

        Raises:
            ValueError: If staged mise.lock is absent; or if unowned Mise cleanup
                directory; or if staged Mise launcher/pin set is incomplete; or if
                unowned Mise sidecar occupies target; or if Mise sidecar changed outside
                transaction.
        """
        cls._require_roots(project, stage)
        for prior in sorted(project.parent.glob(f".{project.name}.mise-lock-stage.*")):
            if prior != stage:
                cls.recover(project, prior)
        for retired in sorted(
            project.parent.glob(f".{project.name}.mise-lock-cleanup.*")
        ):
            cls._physical_directory(retired)
            journal = cls._read_journal(retired)
            if journal is None or journal.get("project") != str(project):
                raise ValueError(f"unowned Mise cleanup directory: {retired}")
            shutil.rmtree(retired)
        old = cls._bytes(project / "mise.lock")
        new = cls._bytes(stage / "mise.lock")
        if new is None:
            raise ValueError(f"staged mise.lock is absent: {stage}")
        old_refs = cls._previous_sidecars(old, project)
        new_refs = cls._sidecars(new, stage)
        artifact_stage = stage / "artifacts"
        new_artifacts: dict[str, str] = {}
        old_artifacts: dict[str, str] = {}
        if artifact_stage.exists() or artifact_stage.is_symlink():
            cls._physical_directory(artifact_stage)
            new_artifacts = cls._artifact_refs(artifact_stage)
            if any(not value for value in new_artifacts.values()):
                raise ValueError("staged Mise launcher/pin set is incomplete")
            old_artifacts = cls._artifact_refs(project)
            for relative, _mode in cls.ARTIFACTS:
                destination = stage / "new-artifacts" / relative
                cls._ensure_parent(stage, destination)
                shutil.copyfile(artifact_stage / relative, destination)
        cls._sync_tree(stage)
        for relative in old_refs | new_refs:
            cls._reject_symlink_path(project, relative)
        for relative, expected in new_refs.items():
            destination = project / relative
            if destination.exists():
                if relative not in old_refs:
                    raise ValueError(
                        f"unowned Mise sidecar occupies target: {destination}"
                    )
                actual = cls._tree_digest(destination)
                if actual != expected and actual != old_refs[relative]:
                    raise ValueError(
                        f"Mise sidecar changed outside transaction: {destination}"
                    )
        if old is not None:
            with (stage / cls.OLD_LOCK).open("xb") as stream:
                stream.write(old)
                stream.flush()
                os.fsync(stream.fileno())
        with (stage / cls.NEW_LOCK).open("xb") as stream:
            stream.write(new)
            stream.flush()
            os.fsync(stream.fileno())
        cls._sync_directory(stage)
        journal = {
            "project": str(project),
            "old": cls._digest(old) or "",
            "new": cls._digest(new),
            "old_refs": json.dumps(old_refs, sort_keys=True),
            "new_refs": json.dumps(new_refs, sort_keys=True),
        }
        if new_artifacts:
            journal["old_artifacts"] = json.dumps(old_artifacts, sort_keys=True)
            journal["new_artifacts"] = json.dumps(new_artifacts, sort_keys=True)
        cls._write_journal(stage, journal)
        for relative, expected in new_refs.items():
            destination = project / relative
            if destination.exists():
                if cls._tree_digest(destination) == expected:
                    continue
                backup = stage / "old-sidecars" / relative
                cls._ensure_parent(stage, backup)
                Path(destination).rename(backup)
                cls._sync_directory(destination.parent)
                cls._sync_directory(backup.parent)
            cls._ensure_parent(project, destination)
            Path(stage / relative).rename(destination)
            cls._sync_directory(destination.parent)
            cls._sync_directory((stage / relative).parent)
        Path(stage / "mise.lock").replace(project / "mise.lock")
        cls._sync_directory(project)
        cls.recover(project, stage)

    @staticmethod
    def _mise_storage_root() -> Path:
        """Resolve the persistent Mise storage the bootstrap recipe declared.

        Returns:
            The resulting ``Path``.

        Raises:
            ValueError: If MISE_DATA_DIR, XDG_DATA_HOME, or HOME must identify Mise
                storage.
        """
        override = os.environ.get("MISE_DATA_DIR")
        if override:
            return Path(override)
        data_home = os.environ.get("XDG_DATA_HOME")
        if data_home:
            return Path(data_home) / "mise"
        home = os.environ.get("HOME")
        if home:
            return Path(home) / ".local/share/mise"
        raise ValueError(
            "MISE_DATA_DIR, XDG_DATA_HOME, or HOME must identify Mise storage"
        )

    @classmethod
    def _pinned_runtime(cls, storage: Path, release: str) -> Path:
        """Locate the installed Mise runtime the pin names (layout from config).

        Returns:
            The resulting ``Path``.

        Raises:
            ValueError: If missing pinned Mise runtime.
        """
        base = storage / "bootstrap"
        suffix = ".exe" if os.name == "nt" else ""
        exact = base / f"mise-{release.lstrip('v')}{suffix}"
        if exact.is_file() and os.access(exact, os.X_OK):
            return exact
        candidates = sorted(base.glob(f"mise-{release.lstrip('v')}*"))
        for candidate in candidates:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate
        raise ValueError(f"missing pinned Mise runtime {exact}; run make setup")

    @staticmethod
    def _manifest_settings(manifest: Path) -> tuple[str, str]:
        """Read the cooldown and lockfile platforms the manifest projects.

        Returns:
            The resulting ``tuple[str, str]``.

        Raises:
            ValueError: If Mise manifest has no settings table; or if Mise manifest
                lacks cooldown or lockfile platforms.
        """
        payload = tomllib.loads(manifest.read_text(encoding="utf-8"))
        settings = payload.get("settings")
        if not isinstance(settings, dict):
            raise ValueError(f"Mise manifest has no settings table: {manifest}")
        cooldown = settings.get("minimum_release_age")
        platforms = settings.get("lockfile_platforms")
        if not isinstance(cooldown, str) or not isinstance(platforms, list):
            raise ValueError(
                f"Mise manifest lacks cooldown or lockfile platforms: {manifest}"
            )
        return cooldown, ",".join(str(platform) for platform in platforms)

    @staticmethod
    def _mise_environment(
        storage: Path,
        stage: Path,
        scratch: Path,
        cooldown: str,
        platforms: str,
    ) -> dict[str, str]:
        """Build the isolated Mise environment the bootstrap recipe runs in.

        Returns:
            The resulting ``dict[str, str]``.
        """
        for name in (
            "home",
            "appdata",
            "config",
            "tmp",
            "xdg-config",
            "xdg-data",
            "xdg-cache",
            "xdg-state",
            "system-config",
        ):
            (scratch / name).mkdir(parents=True, exist_ok=True)
        (scratch / "global-config.toml").write_bytes(b"")
        (scratch / "system-config" / "config.toml").write_bytes(b"")
        environment = {
            "HOME": str(scratch / "home"),
            "USERPROFILE": str(scratch / "home"),
            "APPDATA": str(scratch / "appdata"),
            "LOCALAPPDATA": str(scratch / "appdata"),
            "XDG_CONFIG_HOME": str(scratch / "xdg-config"),
            "XDG_DATA_HOME": str(scratch / "xdg-data"),
            "XDG_CACHE_HOME": str(scratch / "xdg-cache"),
            "XDG_STATE_HOME": str(scratch / "xdg-state"),
            "MISE_CONFIG_DIR": str(scratch / "config"),
            "MISE_SYSTEM_CONFIG_DIR": str(scratch / "system-config"),
            "MISE_SYSTEM_CONFIG_FILE": str(scratch / "system-config" / "config.toml"),
            "MISE_TMP_DIR": str(scratch / "tmp"),
            "TMPDIR": str(scratch / "tmp"),
            "TMP": str(scratch / "tmp"),
            "TEMP": str(scratch / "tmp"),
            "MISE_DATA_DIR": str(storage),
            "MISE_CACHE_DIR": str(storage / "cache"),
            "MISE_STATE_DIR": str(storage / "state"),
            "MISE_INSTALLS_DIR": str(storage / "installs"),
            "MISE_SHIMS_DIR": str(storage / "shims"),
            "UV_CACHE_DIR": str(storage / "uv-cache"),
            "MISE_TRUSTED_CONFIG_PATHS": str(stage),
            "MISE_LOCKFILE": "true",
            "MISE_LOCKED": "true",
            "MISE_QUIET": "1",
            "MISE_NETRC": "false",
            "MISE_HTTP_RETRIES": "0",
            "MISE_MINIMUM_RELEASE_AGE": cooldown,
            "MISE_LOCKFILE_PLATFORMS": platforms,
            "GIT_TERMINAL_PROMPT": "0",
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
        }
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            environment["GITHUB_TOKEN"] = token
        return environment

    @staticmethod
    def _run(runtime: Path, arguments: list[str], environment: dict[str, str]) -> str:
        """Run one isolated Mise command; warnings and failures escape loudly.

        Returns:
            The resulting ``str``.

        Raises:
            ValueError: If Mise exited; or if Mise warned during.
        """
        completed = subprocess.run(
            [str(runtime), *arguments],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        output = completed.stdout.strip()
        if completed.returncode != 0:
            sys.stderr.write(completed.stdout)
            sys.stderr.write(completed.stderr)
            diagnostics = (completed.stdout + completed.stderr).strip()
            raise ValueError(
                f"Mise exited {completed.returncode}: {' '.join(arguments)}\n{diagnostics}",
            )
        if "mise WARN" in completed.stdout or "mise WARN" in completed.stderr:
            sys.stderr.write(completed.stderr)
            raise ValueError(
                f"Mise warned during {' '.join(arguments)}; reconcile stopped"
            )
        if completed.stderr:
            sys.stderr.write(completed.stderr)
        return output

    @staticmethod
    def _git_head_lock(project: Path) -> bytes | None:
        """Read the committed mise.lock, the retention set of the prior state.

        Returns:
            The resulting ``bytes | None``.
        """
        try:
            completed = subprocess.run(
                ["git", "-C", str(project), "show", "HEAD:mise.lock"],
                capture_output=True,
                check=False,
            )
        except OSError:
            return None
        if completed.returncode != 0:
            return None
        return completed.stdout

    @staticmethod
    def _staged_lock_satisfies(
        runtime: Path, stage: Path, environment: dict[str, str]
    ) -> bool:
        """Prove the staged lock satisfies the manifest without mutating tools.

        Returns:
            The resulting ``bool``.
        """
        completed = subprocess.run(
            [str(runtime), "-C", str(stage), "install", "--dry-run"],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode == 0

    @classmethod
    def reconcile(cls, project: Path, release: str) -> None:
        """Rebuild a mise.lock the pinned Mise release satisfies, and publish it.

        A dirty tree — a mixed-generation merge, an interrupted ``upg``, or a
        lock written by a different Mise release — recovers here. Seeds are
        tried in order, each proven by a staged dry-run install before
        publication: the working lock, the committed Git lock (its retained
        pins survive the cooldown), and finally a fresh resolution. Publication
        is atomic and parks an unreadable prior state inside the stage. This is
        the reconcile phase ``make setup`` invokes; it never bumps a tool
        beyond the declared cooldown.

        Raises:
            ValueError: Always; or if missing Mise manifest.
        """
        cls._physical_directory(project)
        manifest = project / ".mise.toml"
        if not manifest.is_file():
            raise ValueError(f"missing Mise manifest: {manifest}")
        storage = cls._mise_storage_root()
        for relative in STORAGE_DIRECTORIES:
            (storage / relative).mkdir(parents=True, exist_ok=True)
        runtime = cls._pinned_runtime(storage, release)
        cooldown, platforms = cls._manifest_settings(manifest)
        seeds: list[tuple[str, bytes | None]] = [
            ("working", cls._bytes(project / "mise.lock")),
        ]
        head_lock = cls._git_head_lock(project)
        if head_lock is not None:
            seeds.append(("git-head", head_lock))
        seeds.append(("fresh", None))
        failures: list[str] = []
        for name, payload in seeds:
            stage = Path(
                tempfile.mkdtemp(
                    prefix=f".{project.name}.mise-lock-stage.", dir=project.parent
                ),
            )
            scratch = Path(tempfile.mkdtemp(prefix="mise-reconcile."))
            try:
                shutil.copyfile(manifest, stage / ".mise.toml")
                if payload is not None:
                    (stage / "mise.lock").write_bytes(payload)
                environment = cls._mise_environment(
                    storage, stage, scratch, cooldown, platforms
                )
                try:
                    cls._run(runtime, ["-C", str(stage), "lock"], environment)
                except ValueError as error:
                    if "refusing to replace locked version" not in str(error):
                        failures.append(f"{name}: lock failed: {error}")
                        continue
                    # Mise refused a cooldown-admissible version whose release
                    # lacks platform coverage and kept the locked version; the
                    # staged dry-run below remains the publication gate (the
                    # same tolerance the upg lock stage ships).
                if not cls._staged_lock_satisfies(runtime, stage, environment):
                    failures.append(
                        f"{name}: staged lock does not satisfy the manifest"
                    )
                    continue
                staged_python = cls._run(
                    runtime,
                    ["-C", str(stage), "which", "python"],
                    environment,
                )
                if not staged_python or not os.access(staged_python, os.X_OK):
                    failures.append(f"{name}: staged Mise Python is not executable")
                    continue
                try:
                    cls.publish(project, stage)
                except ValueError:
                    parked = stage / "reconcile-parked"
                    parked.mkdir()
                    if (project / "mise.lock").exists():
                        Path(project / "mise.lock").replace(parked / "mise.lock")
                    locks = project / ".mise" / "locks"
                    if locks.exists():
                        Path(locks).replace(parked / "locks")
                    cls.publish(project, stage)
                print(
                    f"reconcile: published the {name} mise.lock Mise {release} satisfies"
                )
                return
            finally:
                shutil.rmtree(scratch, ignore_errors=True)
                if stage.exists() and not (stage / cls.JOURNAL).exists():
                    shutil.rmtree(stage, ignore_errors=True)
        raise ValueError(
            "reconcile: no seed produced a lock the pinned Mise satisfies ("
            + "; ".join(failures)
            + "); run make upg at the runtime root",
        )

    @staticmethod
    def _uv_binary() -> str:
        """Prefer the Mise-resolved uv shim, exactly as the lifecycle does.

        Returns:
            The resulting ``str``.
        """
        shim = (
            FlextInfraBootstrap._mise_storage_root()
            / "shims"
            / ("uv.exe" if os.name == "nt" else "uv")
        )
        if shim.is_file() and os.access(shim, os.X_OK):
            return str(shim)
        return "uv"

    @classmethod
    def _uv_run(cls, arguments: list[str]) -> str:
        """Run one uv command; failures escape loudly with their output.

        Returns:
            The resulting ``str``.

        Raises:
            ValueError: If ``completed.returncode != 0``.
        """
        completed = subprocess.run(
            [cls._uv_binary(), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            sys.stderr.write(completed.stdout)
            sys.stderr.write(completed.stderr)
            raise ValueError(
                f"uv exited {completed.returncode}: {' '.join(arguments)}\n"
                + (completed.stdout + completed.stderr).strip(),
            )
        if completed.stderr:
            sys.stderr.write(completed.stderr)
        return completed.stdout

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
            cls._uv_run(["workspace", "dir", "--project", str(project)]).strip()
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
                raise ValueError(f"lock staging path already exists: {candidate}")
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
        if len(arguments) != 3 or arguments[0] not in {
            "publish",
            "recover",
            "reconcile",
        }:
            raise ValueError(
                "usage: bootstrap.py (publish|recover) PROJECT STAGE"
                " | reconcile PROJECT RELEASE | relock PROJECT",
            )
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
