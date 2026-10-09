"""Content-addressed Git worktree fingerprints for validation integrity.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import MutableMapping
from pathlib import Path

from flext_infra import c, m, p, r, t
from flext_infra._utilities import FlextInfraUtilitiesGit


class FlextInfraUtilitiesWorkspaceFingerprint:
    """Fingerprint HEAD, index entries, tracked content, and untracked content."""

    @staticmethod
    def _excluded(path: Path, exclusions: frozenset[Path]) -> bool:
        """Return whether a path is an explicit excluded artifact or descendant.

        Returns:
            Whether a path is an explicit excluded artifact or descendant.

        """
        return any(
            path == excluded or path.is_relative_to(excluded) for excluded in exclusions
        )

    @staticmethod
    def _read_content_digest(path: Path) -> bytes:
        """Hash one path without following symlinks.

        Returns:
            The resulting ``bytes``.

        """
        digest = hashlib.sha256()
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            digest.update(b"missing\0")
            return digest.digest()
        digest.update(str(stat.S_IMODE(metadata.st_mode)).encode())
        if stat.S_ISLNK(metadata.st_mode):
            digest.update(b"symlink\0")
            digest.update(os.fsencode(path.readlink()))
        elif stat.S_ISREG(metadata.st_mode):
            digest.update(b"file\0")
            with path.open("rb") as stream:
                while chunk := stream.read(
                    c.Infra.WORKSPACE_FINGERPRINT_READ_CHUNK_BYTES,
                ):
                    digest.update(chunk)
        elif stat.S_ISDIR(metadata.st_mode):
            digest.update(b"directory\0")
        else:
            digest.update(f"special:{stat.S_IFMT(metadata.st_mode)}".encode())
        return digest.digest()

    @classmethod
    def _file_content_digest(cls, path: Path) -> p.Result[bytes]:
        """Return a typed content digest or one precise read failure.

        Returns:
            A typed content digest or one precise read failure.

        """
        try:
            return r[bytes].ok(cls._read_content_digest(path))
        except OSError as exc:
            return r[bytes].fail(f"workspace fingerprint read failed for {path}: {exc}")

    @staticmethod
    def _index_entries(
        index_z: bytes,
    ) -> p.Result[t.MutableMappingKV[bytes, list[bytes]]]:
        """Parse the NUL-delimited git index into per-path stage metadata.

        Returns:
            The resulting ``p.Result[t.MutableMappingKV[bytes, list[bytes]]]``.

        """
        index_entries: MutableMapping[bytes, list[bytes]] = {}
        for record in index_z.split(b"\0"):
            if not record:
                continue
            try:
                metadata, raw_path = record.split(b"\t", maxsplit=1)
            except ValueError:
                return r[t.MutableMappingKV[bytes, list[bytes]]].fail(
                    "invalid NUL-delimited git index entry",
                )
            index_entries.setdefault(raw_path, []).append(metadata)
        return r[t.MutableMappingKV[bytes, list[bytes]]].ok(index_entries)

    @classmethod
    def _fingerprint_entries(
        cls,
        root: Path,
        paths_z: bytes,
        index_entries: t.MappingKV[bytes, list[bytes]],
        exclusions: frozenset[Path],
    ) -> p.Result[t.VariadicTuple[m.Infra.WorkspaceFingerprintEntry]]:
        """Digest every governed tracked path into one fingerprint entry.

        Returns:
            The resulting
            ``p.Result[t.VariadicTuple[m.Infra.WorkspaceFingerprintEntry]]``.

        """
        entries: list[m.Infra.WorkspaceFingerprintEntry] = []
        for raw_path in sorted(filter(None, paths_z.split(b"\0"))):
            relative = Path(os.fsdecode(raw_path))
            if relative.is_absolute() or ".." in relative.parts:
                return r[t.VariadicTuple[m.Infra.WorkspaceFingerprintEntry]].fail(
                    f"unsafe repository path in fingerprint: {relative}",
                )
            if cls._excluded(relative, exclusions):
                continue
            content_result = cls._file_content_digest(root / relative)
            if content_result.failure:
                return r[
                    t.VariadicTuple[m.Infra.WorkspaceFingerprintEntry]
                ].from_failure(content_result)
            entries.append(
                m.Infra.WorkspaceFingerprintEntry(
                    path=relative.as_posix(),
                    digest=cls._entry_digest(
                        raw_path,
                        index_entries.get(raw_path, ()),
                        content_result.value,
                    ),
                ),
            )
        return r[t.VariadicTuple[m.Infra.WorkspaceFingerprintEntry]].ok(tuple(entries))

    @staticmethod
    def _entry_digest(
        raw_path: bytes,
        index_metadata: t.SequenceOf[bytes],
        content_digest: bytes,
    ) -> str:
        """Hash one entry's path, index stage records, and content digest.

        Returns:
            The resulting ``str``.

        """
        entry_digest = hashlib.sha256()
        entry_digest.update(raw_path)
        entry_digest.update(b"\0")
        for metadata in sorted(index_metadata):
            entry_digest.update(metadata)
            entry_digest.update(b"\0")
        entry_digest.update(content_digest)
        return entry_digest.hexdigest()

    @staticmethod
    def _aggregate_digest(
        head: bytes,
        entries: list[m.Infra.WorkspaceFingerprintEntry],
    ) -> str:
        """Hash HEAD and every entry into the workspace aggregate digest.

        Returns:
            The resulting ``str``.

        """
        aggregate = hashlib.sha256(head)
        for entry in entries:
            aggregate.update(entry.path.encode())
            aggregate.update(b"\0")
            aggregate.update(entry.digest.encode())
            aggregate.update(b"\0")
        return aggregate.hexdigest()

    @classmethod
    def workspace_fingerprint(
        cls,
        checkout: Path,
        *,
        excluded_paths: t.SequenceOf[Path] = (),
    ) -> p.Result[m.Infra.WorkspaceFingerprint]:
        """Capture a content-addressed snapshot of one Git checkout.

        Returns:
            The resulting ``p.Result[m.Infra.WorkspaceFingerprint]``.

        """
        root = checkout.resolve()
        inputs = FlextInfraUtilitiesGit.git_fingerprint_inputs(
            m.Infra.GitRepoRequest(repo_root=root),
        )
        if inputs.failure:
            return r[m.Infra.WorkspaceFingerprint].from_failure(inputs)
        index_entries = cls._index_entries(inputs.value.index_z)
        if index_entries.failure:
            return r[m.Infra.WorkspaceFingerprint].from_failure(index_entries)
        entries = cls._fingerprint_entries(
            root,
            inputs.value.paths_z,
            index_entries.value,
            frozenset(excluded_paths),
        )
        if entries.failure:
            return r[m.Infra.WorkspaceFingerprint].from_failure(entries)
        return r[m.Infra.WorkspaceFingerprint].ok(
            m.Infra.WorkspaceFingerprint(
                digest=cls._aggregate_digest(inputs.value.head, list(entries.value)),
                entries=entries.value,
            ),
        )

    @staticmethod
    def workspace_fingerprint_changes(
        before: m.Infra.WorkspaceFingerprint,
        after: m.Infra.WorkspaceFingerprint,
    ) -> t.StrSequence:
        """Return repository paths whose content or index state changed.

        Returns:
            Repository paths whose content or index state changed.

        """
        before_entries = {entry.path: entry.digest for entry in before.entries}
        after_entries = {entry.path: entry.digest for entry in after.entries}
        return tuple(
            path
            for path in sorted(before_entries.keys() | after_entries.keys())
            if before_entries.get(path) != after_entries.get(path)
        )


__all__: list[str] = ["FlextInfraUtilitiesWorkspaceFingerprint"]
