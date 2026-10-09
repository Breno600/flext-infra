"""Release source staging: committed snapshot, sensitive paths, secret scan.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import tarfile
from pathlib import Path

from flext_infra import c, m, p, r, t, u
from flext_infra.release._release_artifact import FlextInfraReleaseArtifactMixin


class FlextInfraReleaseSourceMixin(FlextInfraReleaseArtifactMixin):
    """Stage one project's committed HEAD, never its working tree."""

    @classmethod
    def _stage_source(
        cls,
        project_path: Path,
        stage_path: Path,
        gitleaks_config: Path,
    ) -> p.Result[t.Pair[m.Infra.SourceSnapshot, str]]:
        """Extract HEAD of a clean project; scan, return identity + license digest.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.SourceSnapshot, str]]``.

        """
        result_type = r[t.Pair[m.Infra.SourceSnapshot, str]]
        snapshot = cls._committed_snapshot(project_path)
        if snapshot.failure:
            return result_type.from_failure(snapshot)
        extracted = cls._extract_commit(
            project_path,
            stage_path,
            snapshot.value.commit_oid,
        )
        if extracted.failure:
            return result_type.from_failure(extracted)
        license_digest = cls._audited_license_digest(stage_path, gitleaks_config)
        if license_digest.failure:
            return result_type.from_failure(license_digest)
        return result_type.ok((snapshot.value, license_digest.value))

    @staticmethod
    def _committed_snapshot(project_path: Path) -> p.Result[m.Infra.SourceSnapshot]:
        """Read the HEAD commit identity of a project with a clean working tree.

        Returns:
            The committed source identity and its reproducible epoch.

        """
        result_type = r[m.Infra.SourceSnapshot]
        status = u.Cli.capture(
            [c.Infra.GIT, "status", "--porcelain"],
            cwd=project_path,
            timeout=c.Infra.TIMEOUT_MEDIUM,
        )
        if status.failure:
            return result_type.from_failure(status)
        if status.value.strip():
            return result_type.fail(f"release project is dirty: {project_path}")
        identity = u.Cli.capture(
            [
                c.Infra.GIT,
                "show",
                "-s",
                "--format=%H %ct",
                f"{c.Infra.GIT_HEAD}^{{commit}}",
            ],
            cwd=project_path,
            timeout=c.Infra.TIMEOUT_MEDIUM,
        )
        if identity.failure:
            return result_type.from_failure(identity)
        oid, _, epoch = identity.value.strip().partition(" ")
        if not epoch.isdigit():
            return result_type.fail(
                f"commit epoch is not an integer for {project_path}: {epoch}",
            )
        snapshot: p.Result[m.Infra.SourceSnapshot] = u.validate_value(
            m.Infra.SourceSnapshot,
            {"commit_oid": oid, "source_date_epoch": int(epoch)},
        )
        if snapshot.failure:
            return result_type.fail_op(
                "validate committed release source identity",
                snapshot.error,
            )
        return snapshot

    @staticmethod
    def _extract_commit(
        project_path: Path,
        stage_path: Path,
        oid: str,
    ) -> p.Result[bool]:
        """Materialize the committed tree of one commit into the stage.

        Returns:
            Success once the archive of the commit is extracted.

        """
        archive_path = stage_path.parent / f"{stage_path.name}.tar"
        archived = u.Cli.run_checked(
            [c.Infra.GIT, "archive", "--format=tar", f"--output={archive_path}", oid],
            cwd=project_path,
            timeout=c.Infra.TIMEOUT_MEDIUM,
        )
        if archived.failure:
            return r[bool].from_failure(archived)
        try:
            with tarfile.open(archive_path, "r") as archive:
                extracted = u.Infra.materialize_tar_tree(archive, stage_path)
        except (OSError, tarfile.TarError) as exc:
            return r[bool].fail(
                f"extract committed release source failed: {exc}",
                exception=exc,
            )
        return extracted

    @classmethod
    def _staged_licenses(cls, stage_path: Path) -> p.Result[t.VariadicTuple[Path]]:
        """Reject unsafe staged paths and return the top-level license files.

        Returns:
            The license files found at the root of the staged source.

        """
        result_type = r[t.VariadicTuple[Path]]
        try:
            members = tuple(sorted(stage_path.rglob("*")))
            licenses = tuple(
                path
                for path in stage_path.iterdir()
                if path.is_file()
                and path.name.casefold() in c.Infra.RELEASE_LICENSE_NAMES
            )
        except OSError as exc:
            return result_type.fail_op(f"list staged release source {stage_path}", exc)
        for member in members:
            relative = member.relative_to(stage_path).as_posix()
            error = cls._path_error(relative, "staged source")
            if error:
                return result_type.fail(error)
            if member.is_symlink():
                return result_type.fail(
                    f"staged source contains symbolic link: {relative}",
                )
        return result_type.ok(licenses)

    @classmethod
    def _audited_license_digest(
        cls,
        stage_path: Path,
        gitleaks_config: Path,
    ) -> p.Result[str]:
        """Audit the staged source and hash its single license file.

        Returns:
            The SHA-256 digest of the one staged license.

        """
        licenses = cls._staged_licenses(stage_path)
        if licenses.failure:
            return r[str].from_failure(licenses)
        scanned = cls._scan_source(stage_path, gitleaks_config)
        if scanned.failure:
            return r[str].from_failure(scanned)
        if len(licenses.value) != 1:
            return r[str].fail(
                f"release source must contain exactly one LICENSE: {stage_path}",
            )
        try:
            return r[str].ok(u.Cli.sha256_file(licenses.value[0]))
        except OSError as exc:
            return r[str].fail_op(f"hash source license {licenses.value[0]}", exc)

    @staticmethod
    def _scan_source(stage_path: Path, gitleaks_config: Path) -> p.Result[bool]:
        """Scan the staged source with the trusted policy, never an ambient one.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        policy = u.Cli.files_read_text(gitleaks_config)
        if policy.failure or not policy.value.strip():
            return r[bool].fail(
                policy.error or f"release Gitleaks policy is empty: {gitleaks_config}",
            )
        scan = u.Cli.run_raw(
            [
                c.Infra.GITLEAKS,
                "dir",
                "--config",
                str(gitleaks_config),
                "--gitleaks-ignore-path",
                str(gitleaks_config.parent),
                "--no-banner",
                "--no-color",
                "--redact=100",
                "--exit-code",
                str(c.Infra.GITLEAKS_LEAK_EXIT_CODE),
                "--ignore-gitleaks-allow",
                str(stage_path),
            ],
            cwd=gitleaks_config.parent,
            timeout=c.Infra.TIMEOUT_LONG,
            remove_env_keys=c.Infra.GITLEAKS_POLICY_ENV_KEYS,
        )
        if scan.failure:
            return r[bool].from_failure(scan)
        code = scan.value.outcome.raw_return_code
        if code == c.Infra.GITLEAKS_LEAK_EXIT_CODE:
            return r[bool].fail("gitleaks detected a secret in staged release source")
        if not u.Cli.process_succeeded(scan.value.outcome):
            return r[bool].fail(f"gitleaks failed with exit code {code}")
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraReleaseSourceMixin"]
