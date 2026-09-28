"""Canonical Git responsibility mixin for ``u.Infra``."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from git import (
    BaseIndexEntry,
    GitCommandError,
    InvalidGitRepositoryError,
    NoSuchPathError,
    Repo,
)

from flext_core import r
from flext_infra import c, m, t

from .semantic_paths import FlextInfraUtilitiesGitSemanticPathsMixin

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraUtilitiesGitSemanticIndexMixin(
    FlextInfraUtilitiesGitSemanticPathsMixin
):
    """Own semantic index operations."""

    _GITLINK_MODE: ClassVar[str] = "160000"
    _STAGED_GITLINK_FIELDS: ClassVar[int] = 2
    _STAGE_ENTRY_FIELDS: ClassVar[int] = 4

    @classmethod
    def git_committed_directory_blobs(
        cls, repo_root: Path, relative_dir: str
    ) -> p.Result[t.MappingKV[str, bytes]]:
        """Read every blob directly under ``relative_dir`` in HEAD.

        Git objects are immutable, so the content is returned by name without
        a physical source state. A directory absent from HEAD is the typed
        empty mapping; an unreadable repository or object fails loud.
        """
        try:
            repo = Repo(repo_root, search_parent_directories=True)
            tree = repo.head.commit.tree / relative_dir
        except KeyError:
            return r[t.MappingKV[str, bytes]].ok({})
        except (
            GitCommandError,
            InvalidGitRepositoryError,
            NoSuchPathError,
            OSError,
            ValueError,
        ) as exc:
            return r[t.MappingKV[str, bytes]].fail(
                f"cannot open committed directory {relative_dir} at {repo_root}: {exc}",
                exception=exc,
            )
        try:
            return r[t.MappingKV[str, bytes]].ok({
                blob.name: blob.data_stream.read() for blob in tree.blobs
            })
        except (OSError, ValueError) as exc:
            return r[t.MappingKV[str, bytes]].fail_op(
                f"read committed blobs {relative_dir} at {repo_root}", exc
            )

    @classmethod
    def git_head_numstat(
        cls, request: m.Infra.GitRepoRequest
    ) -> p.Result[m.Infra.GitNumstatReport]:
        """Capture HEAD subject and ``HEAD~1..HEAD`` numstat."""
        try:
            repo = cls._repo(request.repo_root)
            subject = repo.git.log("-1", "--format=%s")
            numstat = repo.git.diff("--numstat", "HEAD~1", c.Infra.GIT_HEAD)
        except GitCommandError as exc:
            return r[m.Infra.GitNumstatReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitNumstatReport].fail(
                f"git numstat read failed: {exc}", exception=exc
            )
        return r[m.Infra.GitNumstatReport].ok(
            m.Infra.GitNumstatReport(subject=subject.strip(), numstat=numstat)
        )

    @classmethod
    def git_fingerprint_inputs(
        cls, request: m.Infra.GitRepoRequest
    ) -> p.Result[m.Infra.GitFingerprintInputsReport]:
        """Capture byte-exact fingerprint inputs for one worktree."""
        try:
            repo = cls._repo(request.repo_root)
            paths_z, index_z, head = cls._git_capture_fingerprint(repo)
        except GitCommandError as exc:
            return r[m.Infra.GitFingerprintInputsReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitFingerprintInputsReport].fail(
                f"failed to capture fingerprint inputs: {exc}", exception=exc
            )
        return r[m.Infra.GitFingerprintInputsReport].ok(
            m.Infra.GitFingerprintInputsReport(
                paths_z=paths_z, index_z=index_z, head=head
            )
        )

    @staticmethod
    def _git_capture_fingerprint(repo: Repo) -> t.Triple[bytes, bytes, bytes]:
        """Capture (paths_z, index_z, head) bytes for fingerprinting."""
        paths_z = repo.git.ls_files(
            "-z", "--cached", "--others", "--exclude-standard"
        ).encode(c.Cli.ENCODING_DEFAULT)
        index_z = repo.git.ls_files("--stage", "-z").encode(c.Cli.ENCODING_DEFAULT)
        try:
            head = repo.head.commit.hexsha.encode(c.Cli.ENCODING_DEFAULT)
        except ValueError:
            # Unborn HEAD: git itself reports no commit, so the fingerprint
            # input is the literal "UNBORN" marker, matching `git rev-parse HEAD`.
            head = b"UNBORN"
        return paths_z, index_z, head

    @classmethod
    def git_update_index_gitlink(
        cls, request: m.Infra.GitUpdateIndexGitlinkRequest
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Stage one gitlink (mode 160000) into the index."""
        try:
            repo = cls._repo(request.repo_root)
            entry = BaseIndexEntry((
                c.Infra.GIT_MODE_GITLINK,
                bytes.fromhex(request.oid),
                c.Infra.GIT_STAGE_NORMAL,
                request.relative_path,
            ))
            repo.index.add([entry])
        except GitCommandError as exc:
            return r[m.Infra.GitBoolReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"failed to update-index gitlink: {exc}", exception=exc
            )
        return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=True))

    @classmethod
    def git_gitlink_spec(
        cls, request: m.Infra.GitRefRequest
    ) -> p.Result[m.Infra.GitOidReport]:
        """Resolve the indexed gitlink oid for one submodule path.

        The ``ls-files --stage`` entry is validated structurally: mode
        ``160000``, stage ``0``, and an exact path match.
        """
        try:
            repo = cls._repo(request.repo_root)
            output = repo.git.ls_files("--stage", "--", request.reference)
        except GitCommandError as exc:
            return r[m.Infra.GitOidReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitOidReport].fail(
                f"failed to read gitlink spec: {exc}", exception=exc
            )
        if not output.strip():
            return r[m.Infra.GitOidReport].fail(
                f"Git gitlink is missing from the index: {request.reference}"
            )
        match output.split():
            case [mode, oid, stage, indexed_path] if (
                mode == cls._GITLINK_MODE
                and stage == str(c.Infra.GIT_STAGE_NORMAL)
                and indexed_path == request.reference
            ):
                return r[m.Infra.GitOidReport].ok(m.Infra.GitOidReport(oid=oid))
            case _:
                return r[m.Infra.GitOidReport].fail(
                    f"Git gitlink entry is malformed: {request.reference}"
                )

    @classmethod
    def git_staged_gitlink_oid(
        cls, request: m.Infra.GitRefRequest
    ) -> p.Result[m.Infra.GitOidReport]:
        """Return the gitlink OID the index records for one submodule path."""
        try:
            repo = cls._repo(request.repo_root)
            staged = repo.git.ls_files("--stage", "--", request.reference)
        except (GitCommandError, OSError, ValueError) as exc:
            return r[m.Infra.GitOidReport].fail(
                f"failed to read the staged gitlink for {request.reference}: {exc}",
                exception=exc,
            )
        for line in staged.splitlines():
            fields = line.split()
            if (
                len(fields) >= cls._STAGED_GITLINK_FIELDS
                and fields[0] == cls._GITLINK_MODE
            ):
                return r[m.Infra.GitOidReport].ok(m.Infra.GitOidReport(oid=fields[1]))
        return r[m.Infra.GitOidReport].fail(
            f"governed gitlink is absent from the index: {request.reference}"
        )

    @classmethod
    def git_index_gitlink_paths(cls, repository_root: Path) -> p.Result[t.StrSequence]:
        """Return every path the index records as a gitlink (mode ``160000``).

        Git records a directory that contains its own ``.git`` as a gitlink the
        moment it is staged, with no warning and no ``.gitmodules`` entry. The
        index is therefore the only place that knows the complete set; reading
        it is how a caller compares what is recorded against what the
        repository declares.
        """
        try:
            repo = cls._repo(repository_root)
            staged = repo.git.ls_files("--stage")
        except (GitCommandError, InvalidGitRepositoryError, NoSuchPathError) as exc:
            return r[t.StrSequence].fail(
                f"failed to read the Git index: {exc}", exception=exc
            )
        except (OSError, ValueError) as exc:
            return r[t.StrSequence].fail(
                f"failed to read the Git index: {exc}", exception=exc
            )
        paths = tuple(
            line.split(maxsplit=3)[3]
            for line in staged.splitlines()
            if line.startswith(cls._GITLINK_MODE)
            and len(line.split(maxsplit=3)) == cls._STAGE_ENTRY_FIELDS
        )
        return r[t.StrSequence].ok(paths)


__all__: list[str] = ["FlextInfraUtilitiesGitSemanticIndexMixin"]
