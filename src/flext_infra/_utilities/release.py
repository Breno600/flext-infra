"""Release protocol utilities for the u.Infra FLEXT chain."""

from __future__ import annotations

import tarfile
from collections.abc import Mapping, MutableMapping, Sequence
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from flext_cli import r, u

from flext_infra import c, m, p, t

from .dependencies import FlextInfraUtilitiesDependencies


class FlextInfraUtilitiesRelease:
    """Bump derivation, release notes, changelog, and publish-order utilities."""

    @staticmethod
    def archive_member_path(name: str) -> p.Result[Path]:
        """Return one safe relative archive member path."""
        relative = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or relative.is_absolute()
            or any(part in {".", ".."} for part in relative.parts)
        ):
            return r[Path].fail(f"unsafe archive member path: {name}")
        if not relative.parts:
            return r[Path].fail(f"unsafe archive member path: {name}")
        return r[Path].ok(Path(*relative.parts))

    @staticmethod
    def materialize_tar_tree(
        archive: tarfile.TarFile, destination: Path
    ) -> p.Result[bool]:
        """Materialize one trusted tar tree without path traversal."""
        try:
            members = tuple(archive.getmembers())
        except tarfile.TarError as exc:
            return r[bool].fail_op("read release archive members", exc)
        validated_members: list[t.Pair[tarfile.TarInfo, Path]] = []
        for member in members:
            path_result = FlextInfraUtilitiesRelease.archive_member_path(member.name)
            if path_result.failure:
                return r[bool].from_failure(path_result)
            if member.issym() or member.islnk():
                return r[bool].fail(
                    f"release archive contains symbolic or hard link: {member.name}"
                )
            if not member.isdir() and not member.isfile():
                return r[bool].fail(
                    f"release archive contains unsupported member: {member.name}"
                )
            validated_members.append((member, path_result.value))
        if destination.exists():
            return r[bool].fail(
                f"release stage directory already exists: {destination}"
            )
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return r[bool].fail_op(
                f"create release stage parent {destination.parent}", exc
            )
        try:
            with TemporaryDirectory(
                dir=destination.parent, prefix=f".{destination.name}."
            ) as staging_dir:
                staging = Path(staging_dir)
                written = FlextInfraUtilitiesRelease._write_validated_tar_tree(
                    archive, staging, validated_members
                )
                if written.failure:
                    return written
                staging.rename(destination)
        except OSError as exc:
            return r[bool].fail_op(
                f"materialize release archive into {destination}", exc
            )
        return r[bool].ok(True)

    @staticmethod
    def _write_validated_tar_tree(
        archive: tarfile.TarFile,
        staging: Path,
        validated_members: Sequence[t.Pair[tarfile.TarInfo, Path]],
    ) -> p.Result[bool]:
        """Write prevalidated tar members into a staging directory."""
        for member, relative_path in validated_members:
            member_path = staging / relative_path
            if member.isdir():
                try:
                    member_path.mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    return r[bool].fail_op(
                        f"create release archive directory {member_path}", exc
                    )
                continue
            try:
                member_path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                return r[bool].fail_op(
                    f"create release archive parent {member_path.parent}", exc
                )
            extracted = archive.extractfile(member)
            if extracted is None:
                return r[bool].fail(
                    f"release archive could not open member: {member.name}"
                )
            try:
                member_path.write_bytes(extracted.read())
            except OSError as exc:
                return r[bool].fail_op(
                    f"write release archive member {member_path}", exc
                )
            finally:
                extracted.close()
        return r[bool].ok(True)

    @staticmethod
    def plan_bump(
        subjects: t.StrSequence, bump_types: Mapping[str, c.Infra.VersionBump]
    ) -> p.Result[c.Infra.VersionBump]:
        """Derive the release bump from the merged pull-request subjects.

        Every subject is the merge commit of one pull request, so it carries the
        pull-request title. A Conventional Commits title maps through
        ``bump_types``; ``!`` marks a breaking change. A GitHub default merge
        subject carries no release information and therefore fails loudly: the
        protocol requires the title, never a guess. Any other merge subject (a
        lane absorbing its integration base) contributes nothing.
        """
        order = tuple(c.Infra.VersionBump)
        bump = c.Infra.VersionBump.NONE
        for subject in subjects:
            if c.Infra.PULL_REQUEST_MERGE_SUBJECT_RE.match(subject):
                return r[c.Infra.VersionBump].fail(
                    "merged pull request without a Conventional Commits title: "
                    f"{subject!r}"
                )
            match = c.Infra.CONVENTIONAL_SUBJECT_RE.match(subject)
            if match is None:
                continue
            candidate = (
                c.Infra.VersionBump.MAJOR
                if match.group("breaking")
                else bump_types.get(match.group("type"), c.Infra.VersionBump.NONE)
            )
            if order.index(candidate) > order.index(bump):
                bump = candidate
        return r[c.Infra.VersionBump].ok(bump)

    @staticmethod
    def is_release_subject(subject: str, version: str) -> bool:
        """Whether ``subject`` is the protocol's release commit for ``version``.

        Matches the commit as the lane wrote it and as GitHub merged it, which
        appends the pull-request number to the subject.
        """
        match = c.Infra.RELEASE_COMMIT_SUBJECT_RE.match(subject)
        return match is not None and match.group("version") == version

    @staticmethod
    def generate_notes(
        version: str,
        tag: str,
        project_list: t.SequenceOf[m.Infra.ProjectInfo],
        changes: str,
        output_path: Path,
    ) -> p.Result[bool]:
        """Generate release notes markdown from release context."""
        lines: t.MutableSequenceOf[str] = [
            f"# Release {tag}",
            "",
            "## Scope",
            "",
            f"- Release version: {version}",
            f"- Projects packaged: {len(project_list) + 1}",
            "",
            "## Projects impacted",
            "",
            "- root",
        ]
        lines.extend(f"- {proj.name}" for proj in project_list)
        lines.extend([
            "",
            "## Pull requests since last release",
            "",
            changes or "- Initial tagged release",
        ])
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            u.write_file(
                output_path,
                "\n".join(lines).rstrip() + "\n",
                encoding=c.Cli.ENCODING_DEFAULT,
            )
            u.fetch_logger(__name__).info(
                "release_notes_written", path=str(output_path)
            )
            return r[bool].ok(True)
        except OSError as exc:
            return r[bool].fail(f"failed to write release notes: {exc}", exception=exc)

    @staticmethod
    def update_changelog(
        repository_root: Path, version: str, tag: str, notes_path: Path
    ) -> p.Result[bool]:
        """Update docs/changelog and docs/releases entries."""
        docs = repository_root / c.Infra.DIR_DOCS
        changelog_path = docs / "CHANGELOG.md"
        latest_path = docs / "releases" / "latest.md"
        tagged_path = docs / "releases" / f"{tag}.md"
        try:
            FlextInfraUtilitiesRelease._write_changelog_files(
                changelog_path=changelog_path,
                latest_path=latest_path,
                tagged_path=tagged_path,
                version=version,
                tag=tag,
                notes_path=notes_path,
            )
        except OSError as exc:
            return r[bool].fail_op("changelog update", exc)
        return r[bool].ok(True)

    @staticmethod
    def _write_changelog_files(
        *,
        changelog_path: Path,
        latest_path: Path,
        tagged_path: Path,
        version: str,
        tag: str,
        notes_path: Path,
    ) -> None:
        """Write changelog and release note files."""
        notes_text = notes_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
        existing = (
            changelog_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
            if changelog_path.exists()
            else "# Changelog\n\n"
        )
        updated = FlextInfraUtilitiesRelease._updated_changelog(
            existing=existing, version=version, tag=tag
        )
        changelog_path.parent.mkdir(parents=True, exist_ok=True)
        u.write_file(changelog_path, updated, encoding=c.Cli.ENCODING_DEFAULT)
        latest_path.parent.mkdir(parents=True, exist_ok=True)
        u.write_file(latest_path, notes_text, encoding=c.Cli.ENCODING_DEFAULT)
        u.write_file(tagged_path, notes_text, encoding=c.Cli.ENCODING_DEFAULT)
        u.fetch_logger(__name__).info(
            "release_changelog_written", path=str(changelog_path)
        )
        u.fetch_logger(__name__).info(
            "release_tagged_notes_written", path=str(tagged_path)
        )

    @staticmethod
    def _updated_changelog(*, existing: str, version: str, tag: str) -> str:
        """Return changelog text with a release section for the version."""
        date = u.now().date().isoformat()
        heading = f"## {version} - "
        section = (
            f"{heading}{date}\n\n- Release tag: `{tag}`\n\n"
            f"Full notes: `docs/releases/{tag}.md`\n\n"
        )
        marker = "# Changelog\n\n"
        if heading in existing:
            updated = existing
        elif marker in existing:
            updated = existing.replace(marker, marker + section, 1)
        else:
            updated = marker + section + existing
        # Why: a changelog ending with the section's blank line failed the
        # markdown gate (MD012); the normalization applies on every stamp, so a
        # rerun on an open release lane repairs a changelog written before it.
        return updated.rstrip("\n") + "\n"

    @classmethod
    def release_publish_waves(
        cls, targets: t.SequenceOf[t.Pair[str, Path]]
    ) -> p.Result[t.SequenceOf[t.StrSequence]]:
        """Group selected release projects into dependency-respecting waves.

        Publishing to an index is immutable: a dependent uploaded before its
        dependency leaves a state no rollback repairs. The order is derived
        from each project's own ``pyproject.toml`` -- the manifests are the
        SSOT, and a hand-written order would be a second source that diverges
        in silence. Every project in a wave depends only on earlier waves, so a
        wave may upload in parallel while the sequence between waves is strict.
        """
        selected = {name for name, _ in targets}
        edges: MutableMapping[str, t.StrSequence] = {}
        for name, path in targets:
            declared = cls._release_runtime_dependencies(path)
            if declared.failure:
                return r[t.SequenceOf[t.StrSequence]].from_failure(declared)
            # A dependency outside the selection is not an edge: it is already
            # on the index or out of scope, and treating it as an edge would
            # deadlock the graph on a package this release never publishes.
            edges[name] = tuple(
                sorted(
                    dependency
                    for dependency in declared.value
                    if dependency in selected and dependency != name
                )
            )
        return FlextInfraUtilitiesDependencies.dependency_waves(edges)

    @staticmethod
    def _release_runtime_dependencies(path: Path) -> p.Result[t.StrSequence]:
        """Return the runtime dependency names declared by one project.

        Only ``[project].dependencies`` counts. Dev groups are not part of the
        published distribution, so an index never resolves them -- and because
        the platform packages test against each other, counting them would
        report the whole workspace as one cycle.
        """
        pyproject = path / c.PYPROJECT_FILENAME
        if not pyproject.is_file():
            return r[t.StrSequence].fail(
                f"release project has no {c.PYPROJECT_FILENAME}: {path}"
            )
        document = u.Cli.toml_read_document(pyproject)
        if document.failure:
            return r[t.StrSequence].from_failure(document)
        payload = u.Cli.toml_as_mapping(document.value)
        project = payload.get(c.Infra.PROJECT) if payload else None
        if not isinstance(project, Mapping):
            return r[t.StrSequence].ok(())
        requirements = project.get(c.Infra.DEPENDENCIES)
        if not isinstance(requirements, Sequence) or isinstance(requirements, str):
            return r[t.StrSequence].ok(())
        return r[t.StrSequence].ok(
            tuple(
                sorted({
                    name
                    for requirement in requirements
                    if isinstance(requirement, str)
                    and (name := FlextInfraUtilitiesDependencies.dep_name(requirement))
                    is not None
                })
            )
        )


__all__: list[str] = ["FlextInfraUtilitiesRelease"]
