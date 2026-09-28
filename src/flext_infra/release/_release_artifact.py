"""Release artifact boundary: archive content, core metadata, and internal pins."""

from __future__ import annotations

import stat
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path, PurePosixPath

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from flext_core import r
from flext_infra import c, p, t, u

from ._release_boundary import FlextInfraReleaseBoundaryMixin


class FlextInfraReleaseArtifactMixin(FlextInfraReleaseBoundaryMixin):
    """Prove a built wheel or sdist ships exactly the committed public boundary.

    An archive is read once into its members ``(name, is_link, is_file)`` and
    the bytes of the files the proof needs: licenses and core metadata.
    """

    @staticmethod
    def _is_license(name: str) -> bool:
        """Whether an archive member is a license file."""
        return PurePosixPath(name).name.casefold() in c.Infra.RELEASE_LICENSE_NAMES

    @classmethod
    def _carried(cls, name: str) -> bool:
        """Whether an archive file's bytes take part in the proof."""
        return cls._is_license(name) or name.endswith(("/METADATA", "/PKG-INFO"))

    @classmethod
    def _archive_contents(
        cls, path: Path
    ) -> p.Result[
        t.Pair[t.SequenceOf[t.Triple[str, bool, bool]], t.MappingKV[str, bytes]]
    ]:
        """Read one wheel or sdist's members and the bytes the proof needs."""
        result_type = r[
            t.Pair[t.SequenceOf[t.Triple[str, bool, bool]], t.MappingKV[str, bytes]]
        ]
        if path.suffix == ".whl":
            try:
                with zipfile.ZipFile(path) as wheel:
                    infos = tuple(i for i in wheel.infolist() if not i.is_dir())
                    payload = {
                        i.filename: wheel.read(i)
                        for i in infos
                        if cls._carried(i.filename)
                    }
            except (OSError, zipfile.BadZipFile) as exc:
                return result_type.fail(
                    f"validate wheel archive {path} failed: {exc}", exception=exc
                )
            members = tuple(
                (i.filename, stat.S_ISLNK(i.external_attr >> 16), True) for i in infos
            )
            return result_type.ok((members, payload))
        try:
            with tarfile.open(path, "r:gz") as sdist:
                items = tuple(sdist.getmembers())
                payload = {
                    item.name: extracted.read()
                    for item in items
                    if item.isfile()
                    and cls._carried(item.name)
                    and (extracted := sdist.extractfile(item)) is not None
                }
        except (OSError, tarfile.TarError) as exc:
            return result_type.fail(
                f"validate sdist archive {path} failed: {exc}", exception=exc
            )
        members = tuple((i.name, i.issym() or i.islnk(), i.isfile()) for i in items)
        return result_type.ok((members, payload))

    @classmethod
    def _archive_error(
        cls, path: Path, project: str, members: t.SequenceOf[t.Triple[str, bool, bool]]
    ) -> str:
        """Return why an archive's members leave the public boundary, or ''."""
        wheel = path.suffix == ".whl"
        package = project.replace("-", "_").casefold()
        roots: t.Infra.StrSet = set()
        for name, link, regular in members:
            # A wheel's content root is its package; an sdist's sits under
            # its single `<name>-<version>/` directory.
            error = cls._path_error(name, "archive member", root_index=int(not wheel))
            if error:
                return error
            root = PurePosixPath(name).parts[0].casefold()
            roots.add(root)
            if link:
                return f"{path.name} contains symbolic or hard link: {name}"
            if (
                wheel
                and root != package
                and not (
                    root.startswith(f"{package}-")
                    and root.endswith((".data", ".dist-info"))
                )
            ):
                return f"wheel contains unexpected top-level path: {name}"
            if (
                not wheel
                and regular
                and not cls._sdist_member_allowed(PurePosixPath(name).parts)
            ):
                return f"sdist contains unexpected public content: {name}"
        if wheel:
            return ""
        root = next(iter(roots), "")
        if len(roots) != 1:
            return f"sdist must contain exactly one top-level directory: {path}"
        if not root.startswith((f"{project.casefold()}-", f"{package}-")):
            return f"sdist root does not match project {project}: {root}"
        return ""

    @classmethod
    def _validate_artifact(
        cls,
        path: Path,
        identity: t.Pair[str, str],
        license_sha256: str,
        versions: t.StrMapping,
    ) -> p.Result[t.Pair[t.Infra.ReleaseArtifactKind, t.Infra.ReleaseArtifactSha256]]:
        """Validate one artifact's boundary, identity and pins; return kind and digest."""
        result_type = r[
            t.Pair[t.Infra.ReleaseArtifactKind, t.Infra.ReleaseArtifactSha256]
        ]
        project, version = identity
        kind: t.Infra.ReleaseArtifactKind = (
            "wheel" if path.suffix == ".whl" else "sdist"
        )
        contents = cls._archive_contents(path)
        if contents.failure:
            return result_type.from_failure(contents)
        members, payload = contents.value
        error = cls._archive_error(path, project, members)
        licenses = [data for name, data in payload.items() if cls._is_license(name)]
        metadata = [data for name, data in payload.items() if not cls._is_license(name)]
        if not error and len(licenses) != 1:
            error = f"{kind} must contain exactly one LICENSE: {path}"
        if not error and u.Cli.sha256_bytes(licenses[0]) != license_sha256:
            error = f"{kind} LICENSE differs from committed source: {path}"
        if not error and len(metadata) != 1:
            error = f"{kind} must contain one core metadata file: {path}"
        if error:
            return result_type.fail(error)
        try:
            message = Parser().parsestr(metadata[0].decode("utf-8"))
        except UnicodeDecodeError as exc:
            return result_type.fail_op(f"read core metadata of {path}", exc)
        name = message.get("Name")
        if name is None or canonicalize_name(name) != canonicalize_name(project):
            return result_type.fail(
                f"artifact Name mismatch: expected {project}, found {name}"
            )
        try:
            expected, actual = Version(version), Version(message.get("Version") or "")
        except InvalidVersion as exc:
            return result_type.fail_op("validate artifact Version", exc)
        if actual != expected:
            return result_type.fail(
                f"artifact Version mismatch: expected {expected}, found {actual}"
            )
        for text in message.get_all("Requires-Dist", []):
            try:
                requirement = Requirement(text)
            except InvalidRequirement as exc:
                return result_type.fail_op("parse artifact requirement", exc)
            dependency = canonicalize_name(requirement.name)
            # A direct reference is source-declared; only fleet pins derive.
            if requirement.url is not None or not dependency.startswith(
                c.Infra.PKG_PREFIX_HYPHEN
            ):
                continue
            pin = (
                cls._release_specifier(versions[dependency])
                if dependency in versions
                else r[str].fail(f"internal dependency version unknown: {dependency}")
            )
            if pin.failure or str(requirement.specifier) != pin.value:
                return result_type.fail(
                    f"artifact contains unpinned FLEXT dependency: {text}"
                )
        try:
            digest = u.Cli.sha256_file(path)
        except OSError as exc:
            return result_type.fail_op(f"hash release artifact {path}", exc)
        return result_type.ok((kind, digest))


__all__: list[str] = ["FlextInfraReleaseArtifactMixin"]
