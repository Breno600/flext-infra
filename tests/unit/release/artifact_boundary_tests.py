"""Public release archive-boundary behavior tests."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

from flext_tests import tm

from tests import u


class TestsFlextInfraReleaseArchiveBoundary:
    """Behavior contract for the public release archive materializer."""

    def _write_directory(self, archive: tarfile.TarFile, name: str) -> None:
        """Add one directory entry to a test tar archive."""
        info = tarfile.TarInfo(name)
        info.type = tarfile.DIRTYPE
        info.mode = 0o755
        archive.addfile(info)

    def _write_file(self, archive: tarfile.TarFile, name: str, content: bytes) -> None:
        """Add one file entry to a test tar archive."""
        info = tarfile.TarInfo(name)
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))

    def _write_symlink(self, archive: tarfile.TarFile, name: str, target: str) -> None:
        """Add one symbolic link entry to a test tar archive."""
        info = tarfile.TarInfo(name)
        info.type = tarfile.SYMTYPE
        info.linkname = target
        archive.addfile(info)

    @staticmethod
    def test_nested_relative_path_is_preserved() -> None:
        """Keep a normal relative tar member as a relative filesystem path."""
        result = u.Infra.archive_member_path("pkg-1.0/src/module.txt")

        tm.ok(result)
        tm.that(result.value, eq=Path("pkg-1.0/src/module.txt"))

    @staticmethod
    def test_path_traversal_and_absolute_paths_fail_loud() -> None:
        """Reject tar names that can escape the destination root."""
        traversal = u.Infra.archive_member_path("../escape.txt")
        absolute = u.Infra.archive_member_path("/escape.txt")
        backslash = u.Infra.archive_member_path("pkg\\escape.txt")

        tm.fail(traversal)
        tm.fail(absolute)
        tm.fail(backslash)
        tm.that(traversal.error or "", has="unsafe archive member path")
        tm.that(absolute.error or "", has="unsafe archive member path")
        tm.that(backslash.error or "", has="unsafe archive member path")

    def test_materialize_tar_tree_writes_safe_content(self, tmp_path: Path) -> None:
        """Materialize a simple archive tree without letting it escape."""
        archive_path = tmp_path / "release.tar"
        stage_path = tmp_path / "stage"
        with tarfile.open(archive_path, "w") as archive:
            self._write_directory(archive, "pkg-1.0")
            self._write_file(archive, "pkg-1.0/README.md", b"hello\n")
            self._write_file(archive, "pkg-1.0/src/module.txt", b"payload\n")

        with tarfile.open(archive_path, "r") as archive:
            result = u.Infra.materialize_tar_tree(archive, stage_path)

        tm.ok(result)
        tm.that((stage_path / "pkg-1.0").is_dir(), eq=True)
        tm.that(
            (stage_path / "pkg-1.0" / "README.md").read_text(encoding="utf-8"),
            eq="hello\n",
        )
        tm.that(
            (stage_path / "pkg-1.0" / "src" / "module.txt").read_text(encoding="utf-8"),
            eq="payload\n",
        )

    def test_materialize_tar_tree_rejects_symbolic_links(self, tmp_path: Path) -> None:
        """Reject tar members that would reintroduce link-based escapes."""
        archive_path = tmp_path / "release.tar"
        stage_path = tmp_path / "stage"
        with tarfile.open(archive_path, "w") as archive:
            self._write_directory(archive, "pkg-1.0")
            self._write_symlink(archive, "pkg-1.0/link", "target.txt")

        with tarfile.open(archive_path, "r") as archive:
            result = u.Infra.materialize_tar_tree(archive, stage_path)

        tm.fail(result)
        tm.that(result.error or "", has="symbolic or hard link")

    def test_materialize_tar_tree_rejects_path_traversal(self, tmp_path: Path) -> None:
        """Reject a tar tree that tries to write outside the stage path."""
        archive_path = tmp_path / "release.tar"
        stage_path = tmp_path / "stage"
        with tarfile.open(archive_path, "w") as archive:
            self._write_file(archive, "../escape.txt", b"escape\n")

        with tarfile.open(archive_path, "r") as archive:
            result = u.Infra.materialize_tar_tree(archive, stage_path)

        tm.fail(result)
        tm.that(result.error or "", has="unsafe archive member path")

    def test_materialize_tar_tree_leaves_no_partial_tree_on_rejection(
        self, tmp_path: Path
    ) -> None:
        """Reject a tar tree without leaving a half-written staging tree."""
        archive_path = tmp_path / "release.tar"
        stage_path = tmp_path / "stage"
        with tarfile.open(archive_path, "w") as archive:
            self._write_file(archive, "pkg-1.0/README.md", b"hello\n")
            self._write_symlink(archive, "pkg-1.0/link", "target.txt")

        with tarfile.open(archive_path, "r") as archive:
            result = u.Infra.materialize_tar_tree(archive, stage_path)

        tm.fail(result)
        tm.that(stage_path.exists(), eq=False)
