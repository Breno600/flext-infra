# Copyright 2026 FLEXT
"""Bootstrap Mise lock transaction: journaled, crash-recoverable publication.

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
import time
import tomllib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from flext_infra import c, t
from flext_infra._bootstrap_process import FlextInfraBootstrapProcessMixin


class FlextInfraBootstrapTransactionMixin(FlextInfraBootstrapProcessMixin):
    """Keep the old lock usable until every new sidecar is published."""

    @staticmethod
    @contextmanager
    def _serialized(project: Path) -> Iterator[None]:
        """Serialize all publisher versions on one declared physical mutex.

        Raises:
            ValueError: If Mise transaction mutex is a symlink; or if Mise transaction
                mutex is not physical; or if Mise transaction mutex is held elsewhere
                for over.
        """
        mutex = project / c.Infra.MISE_LOCK_MUTEX_FILENAME
        if mutex.is_symlink():
            msg = f"Mise transaction mutex is a symlink: {mutex}"
            raise ValueError(msg)
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(mutex, flags, 0o600)
        try:
            observed = os.fstat(descriptor)
            if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
                msg = f"Mise transaction mutex is not physical: {mutex}"
                raise ValueError(msg)
            if observed.st_size == 0:
                os.write(descriptor, b"\0")
                os.fsync(descriptor)
            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                deadline = time.monotonic() + c.Infra.MISE_LOCK_MUTEX_TIMEOUT_SECONDS
                while True:
                    try:
                        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            msg = (
                                "Mise transaction mutex is held elsewhere for over "
                                f"{c.Infra.MISE_LOCK_MUTEX_TIMEOUT_SECONDS:.0f}s: "
                                f"{mutex}"
                            )
                            raise ValueError(msg) from None
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
            msg = f"transaction directory is not physical: {path}"
            raise ValueError(msg)

    @staticmethod
    def _bytes(path: Path) -> bytes | None:
        try:
            observed = path.lstat()
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
            msg = f"transaction file is not physical: {path}"
            raise ValueError(msg)
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
            msg = f"unsafe mise.lock sidecar: {relative}"
            raise ValueError(msg)
        return selector

    @classmethod
    def _sidecars(cls, content: bytes | None, root: Path) -> t.StrDict:
        if content is None:
            return {}
        payload = tomllib.loads(content.decode("utf-8"))
        tools = payload.get("tools")
        if not isinstance(tools, dict):
            msg = "mise.lock has no tools table"
            raise ValueError(msg)
        result: t.StrDict = {}
        for entries in tools.values():
            for entry in entries if isinstance(entries, list) else (entries,):
                if not isinstance(entry, dict):
                    msg = "mise.lock tool entry is not a table"
                    raise ValueError(msg)
                for graph, filename in (("aube", "aube-lock.yaml"), ("uv", "uv.lock")):
                    annotation = entry.get(graph)
                    if annotation is None:
                        continue
                    if not isinstance(annotation, dict):
                        msg = f"mise.lock {graph} annotation is not a table"
                        raise ValueError(msg)
                    relative = annotation.get("path")
                    digest = annotation.get("digest")
                    if not isinstance(relative, str) or not isinstance(digest, str):
                        msg = f"mise.lock {graph} annotation is incomplete"
                        raise ValueError(msg)
                    selector = cls._sidecar_selector(relative)
                    if not digest.startswith("sha256:"):
                        msg = f"invalid mise.lock sidecar digest: {relative}"
                        raise ValueError(msg)
                    cls._reject_symlink_path(root, relative)
                    sidecar = root.joinpath(*selector.parts)
                    cls._physical_directory(sidecar)
                    source = cls._bytes(sidecar / filename)
                    if source is None:
                        msg = f"mise.lock sidecar is absent: {sidecar / filename}"
                        raise ValueError(msg)
                    actual = hashlib.sha256(source.replace(b"\r\n", b"\n")).hexdigest()
                    if actual != digest.removeprefix("sha256:"):
                        msg = f"mise.lock sidecar digest differs: {sidecar / filename}"
                        raise ValueError(msg)
                    result[relative] = cls._tree_digest(sidecar)
        return result

    @classmethod
    def _previous_sidecars(cls, content: bytes | None, project: Path) -> t.StrDict:
        """Read the owned graph from Git stage 2 during a lock merge conflict.

        Returns:
            The resulting ``t.StrDict``.

        Raises:
            ValueError: If git cannot read the unmerged index; or if conflicted
                mise.lock has no Git stage-2 source.
        """
        if content is None or b"<<<<<<< " not in content:
            return cls._sidecars(content, project)
        index = cls._git_output(project, "ls-files", "-u", "--", "mise.lock")
        if index is None:
            msg = f"git cannot read the unmerged index of {project}"
            raise ValueError(msg)
        if not any(
            line.split(b"\t", 1)[0].endswith(b" 2") for line in index.splitlines()
        ):
            msg = "conflicted mise.lock has no Git stage-2 source"
            raise ValueError(msg)
        prior = cls._git_output(project, "show", ":2:mise.lock")
        if prior is None:
            msg = f"git cannot read the stage-2 mise.lock of {project}"
            raise ValueError(msg)
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
                msg = f"nonphysical mise sidecar entry: {path}"
                raise ValueError(msg)
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
                msg = f"nonphysical Mise stage entry: {path}"
                raise ValueError(msg)
        cls._sync_directory(root)

    @classmethod
    def _write_journal(cls, stage: Path, journal: t.StrDict) -> None:
        candidate = stage / "transaction.json.new"
        with candidate.open("x", encoding="utf-8") as stream:
            json.dump(journal, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        Path(candidate).replace(stage / c.Infra.MISE_LOCK_JOURNAL_FILENAME)
        cls._sync_directory(stage)

    @classmethod
    def _read_journal(cls, stage: Path) -> t.StrDict | None:
        content = cls._bytes(stage / c.Infra.MISE_LOCK_JOURNAL_FILENAME)
        if content is None:
            return None
        payload = json.loads(content)
        if not isinstance(payload, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in payload.items()
        ):
            msg = f"invalid Mise lock transaction journal: {stage}"
            raise ValueError(msg)
        return payload

    @staticmethod
    def _journal_refs(journal: t.StrDict, name: str) -> t.StrDict:
        raw = journal.get(name)
        if raw is None:
            msg = f"Mise lock journal lacks {name}"
            raise ValueError(msg)
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in payload.items()
        ):
            msg = f"Mise lock journal has invalid {name}"
            raise ValueError(msg)
        for relative in payload:
            FlextInfraBootstrapTransactionMixin._sidecar_selector(relative)
        return payload

    @classmethod
    def _artifact_refs(cls, root: Path) -> t.StrDict:
        return {
            relative: cls._digest(cls._bytes(root / relative)) or ""
            for relative, _mode in c.Infra.MISE_LOCK_ARTIFACTS
        }

    @classmethod
    def _journal_artifacts(cls, journal: t.StrDict, name: str) -> t.StrDict:
        raw = journal.get(name)
        if raw is None:
            msg = f"Mise lock journal lacks {name}"
            raise ValueError(msg)
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in payload.items()
        ):
            msg = f"Mise lock journal has invalid {name}"
            raise ValueError(msg)
        return payload

    @classmethod
    def _recover_artifacts(
        cls,
        project: Path,
        stage: Path,
        journal: t.StrDict,
    ) -> None:
        old_refs = cls._journal_artifacts(journal, "old_artifacts")
        new_refs = cls._journal_artifacts(journal, "new_artifacts")
        declared = {relative for relative, _mode in c.Infra.MISE_LOCK_ARTIFACTS}
        if set(old_refs) != declared or set(new_refs) != declared:
            msg = "Mise transaction artifact manifest is incomplete"
            raise ValueError(msg)
        for relative, mode in c.Infra.MISE_LOCK_ARTIFACTS:
            source = stage / "new-artifacts" / relative
            expected = new_refs[relative]
            if cls._digest(cls._bytes(source)) != expected:
                msg = f"staged Mise artifact changed: {source}"
                raise ValueError(msg)
            target = project / relative
            current = cls._digest(cls._bytes(target))
            if current == expected:
                continue
            if current != (old_refs[relative] or None):
                msg = f"Mise artifact changed outside transaction: {target}"
                raise ValueError(msg)
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
            msg = "Mise lock stage must be a sibling of its destination"
            raise ValueError(msg)
        if stage.stat().st_dev != project.stat().st_dev:
            msg = "Mise lock stage is not on the destination filesystem"
            raise ValueError(msg)
        if not stage.name.startswith(f".{project.name}.mise-lock-stage."):
            msg = f"unexpected Mise lock transaction stage: {stage}"
            raise ValueError(msg)

    @staticmethod
    def _reject_symlink_path(project: Path, relative: str) -> None:
        cursor = project
        for part in PurePosixPath(relative).parts:
            cursor /= part
            if cursor.is_symlink():
                msg = f"Mise sidecar path contains a symlink: {cursor}"
                raise ValueError(msg)

    @classmethod
    def _ensure_parent(cls, root: Path, target: Path) -> None:
        """Materialize physical parents and durably record each directory entry.

        Raises:
            ValueError: If Mise sidecar escapes transaction root.
        """
        if not target.is_relative_to(root):
            msg = f"Mise sidecar escapes transaction root: {target}"
            raise ValueError(msg)
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
            msg = f"Mise cleanup target already exists: {retired}"
            raise ValueError(msg)
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
            # An unjournaled stage never reached its commit point: it is a
            # killed run's orphan, safe to retire without touching the project.
            cls._retire_stage(stage)
            return
        if journal.get("project") != str(project):
            msg = f"Mise lock journal belongs to another project: {stage}"
            raise ValueError(msg)
        old = cls._bytes(stage / c.Infra.MISE_LOCK_OLD_FILENAME)
        new = cls._bytes(stage / c.Infra.MISE_LOCK_NEW_FILENAME)
        if new is None:
            msg = f"Mise lock journal lost new lock: {stage}"
            raise ValueError(msg)
        if cls._digest(old) != (journal.get("old") or None) or cls._digest(
            new,
        ) != journal.get("new"):
            msg = f"Mise lock journal digest changed: {stage}"
            raise ValueError(msg)
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
                        msg = f"old Mise sidecar changed during recovery: {backup}"
                        raise ValueError(msg)
                    cls._ensure_parent(project, destination)
                    Path(backup).rename(destination)
                    cls._sync_directory(backup.parent)
                    cls._sync_directory(destination.parent)
                elif relative in old_refs:
                    if (
                        not destination.exists()
                        or cls._tree_digest(destination) != old_refs[relative]
                    ):
                        msg = f"old Mise sidecar missing during recovery: {destination}"
                        raise ValueError(msg)
                elif destination.exists():
                    msg = f"unowned Mise sidecar changed during recovery: {destination}"
                    raise ValueError(msg)
            cls._retire_stage(stage)
            return
        if live != new:
            msg = f"Mise lock changed outside transaction: {project / 'mise.lock'}"
            raise ValueError(msg)
        for relative, expected in new_refs.items():
            destination = project / relative
            if not destination.exists() or cls._tree_digest(destination) != expected:
                msg = f"committed Mise sidecar differs: {destination}"
                raise ValueError(msg)
        for relative, expected in old_refs.items():
            if relative in new_refs:
                continue
            destination = project / relative
            retired = stage / "retired-sidecars" / relative
            if destination.exists():
                if cls._tree_digest(destination) != expected:
                    msg = f"stale sidecar changed during recovery: {destination}"
                    raise ValueError(msg)
                cls._ensure_parent(stage, retired)
                Path(destination).rename(retired)
                cls._sync_directory(destination.parent)
                cls._sync_directory(retired.parent)
            elif not retired.exists():
                msg = f"stale sidecar disappeared during recovery: {destination}"
                raise ValueError(msg)
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
            project.parent.glob(f".{project.name}.mise-lock-cleanup.*"),
        ):
            cls._physical_directory(retired)
            journal = cls._read_journal(retired)
            if journal is None or journal.get("project") != str(project):
                msg = f"unowned Mise cleanup directory: {retired}"
                raise ValueError(msg)
            shutil.rmtree(retired)
        old = cls._bytes(project / "mise.lock")
        new = cls._bytes(stage / "mise.lock")
        if new is None:
            msg = f"staged mise.lock is absent: {stage}"
            raise ValueError(msg)
        old_refs = cls._previous_sidecars(old, project)
        new_refs = cls._sidecars(new, stage)
        artifact_stage = stage / "artifacts"
        new_artifacts: t.StrDict = {}
        old_artifacts: t.StrDict = {}
        if artifact_stage.exists() or artifact_stage.is_symlink():
            cls._physical_directory(artifact_stage)
            new_artifacts = cls._artifact_refs(artifact_stage)
            if any(not value for value in new_artifacts.values()):
                msg = "staged Mise launcher/pin set is incomplete"
                raise ValueError(msg)
            old_artifacts = cls._artifact_refs(project)
            for relative, _mode in c.Infra.MISE_LOCK_ARTIFACTS:
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
                    msg = f"unowned Mise sidecar occupies target: {destination}"
                    raise ValueError(msg)
                actual = cls._tree_digest(destination)
                if actual != expected and actual != old_refs[relative]:
                    msg = f"Mise sidecar changed outside transaction: {destination}"
                    raise ValueError(msg)
        if old is not None:
            with (stage / c.Infra.MISE_LOCK_OLD_FILENAME).open("xb") as stream:
                stream.write(old)
                stream.flush()
                os.fsync(stream.fileno())
        with (stage / c.Infra.MISE_LOCK_NEW_FILENAME).open("xb") as stream:
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


__all__: list[str] = ["FlextInfraBootstrapTransactionMixin"]
