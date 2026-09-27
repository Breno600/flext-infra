"""Release boundary: what may ship, how internal pins read, where receipts live."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from packaging.version import InvalidVersion, Version

from flext_core import r
from flext_infra import c, config, m, p, t, u
from flext_infra.base_selection import FlextInfraProjectSelectionServiceBase


class FlextInfraReleaseBoundaryMixin(FlextInfraProjectSelectionServiceBase[bool]):
    """Shared release policy every phase applies to one repository."""

    @staticmethod
    def _release_dir(root: Path, tag: str = "") -> Path:
        """Return the release report directory, or one version's receipt directory."""
        return u.Cli.resolve_report_dir(root, c.Infra.PROJECT, c.Infra.RK_RELEASE) / tag

    @staticmethod
    def _write_release_text(path: Path, content: str) -> p.Result[bool]:
        """Write release text, creating its directory."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return r[bool].fail_op(
                f"create release output directory {path.parent}", exc
            )
        return u.Cli.files_write_text(path, content)

    @staticmethod
    def _path_error(name: str, kind: str, *, root_index: int | None = None) -> str:
        """Return why ``name`` may not ship, or an empty string.

        Repository-operational trees are rejected only at an archive's content
        root (``root_index``): a package may ship a ``.github`` tree as data.
        A file codegen renders or manages is a projection, never a secret,
        whatever its name; other sensitive material is rejected at every depth.
        """
        path = PurePosixPath(name)
        if not name or "\\" in name or path.is_absolute() or ".." in path.parts:
            return f"unsafe {kind} path: {name}"
        if (
            root_index is not None
            and len(path.parts) > root_index
            and path.parts[root_index].casefold() in c.Infra.RELEASE_OPERATIONAL_ROOTS
        ):
            return f"operational {kind} path: {name}"
        codegen = config.Infra.codegen
        if name in {entry.destination for entry in codegen.templates.entries} or any(
            name == item.path.as_posix() for item in codegen.managed_files
        ):
            return ""
        for part in (part.casefold() for part in path.parts):
            if (
                part in c.Infra.RELEASE_SENSITIVE_PARTS
                or part.startswith(c.Infra.RELEASE_SENSITIVE_PREFIXES)
                or part.endswith(c.Infra.RELEASE_SENSITIVE_SUFFIXES)
            ):
                return f"sensitive {kind} path: {name}"
        return ""

    @staticmethod
    def _sdist_member_allowed(parts: t.StrSequence) -> bool:
        """Return whether one regular sdist member is inside the public boundary."""
        relative = tuple(part.casefold() for part in parts[1:])
        if relative and relative[0] in c.Infra.RELEASE_SDIST_ROOT_DIRS:
            return True
        return len(relative) == 1 and (
            relative[0] in c.Infra.RELEASE_LICENSE_NAMES
            or relative[0] in c.Infra.RELEASE_SDIST_ROOT_FILES
            or relative[0].startswith("readme")
        )

    @staticmethod
    def _release_specifier(version: str) -> p.Result[str]:
        """Return the compatible-release range a sibling's declared version earns.

        The same minor line before 1.0, the same major line after: exactly
        what semantic versioning promises is compatible.
        """
        try:
            parsed = Version(version)
        except InvalidVersion as exc:
            return r[str].fail_op("parse internal dependency version", exc)
        if parsed.major == 0:
            return r[str].ok(f"~={version}")
        return r[str].ok(f">={version},<{parsed.major + 1}")

    @staticmethod
    def _record(
        name: str,
        path: Path,
        log: Path,
        *,
        exit_code: int,
        artifacts: t.SequenceOf[m.Infra.BuildArtifact] = (),
        snapshot: m.Infra.SourceSnapshot | None = None,
        source_license_sha256: str | None = None,
    ) -> m.Infra.BuildRecord:
        """Model one strict build record with absolute paths."""
        return m.Infra.BuildRecord(
            project=name,
            path=str(path.resolve()),
            exit_code=exit_code,
            log=str(log.resolve()),
            artifacts=tuple(artifacts),
            commit_oid=snapshot.commit_oid if snapshot is not None else None,
            source_date_epoch=snapshot.source_date_epoch
            if snapshot is not None
            else None,
            source_license_sha256=source_license_sha256,
        )


__all__: list[str] = ["FlextInfraReleaseBoundaryMixin"]
