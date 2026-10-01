"""Release source staging: committed snapshot, sensitive paths, secret scan."""

from __future__ import annotations

import tarfile
from pathlib import Path

from flext_core import r
from flext_infra import c, m, p, t, u

from ._release_artifact import FlextInfraReleaseArtifactMixin


class FlextInfraReleaseSourceMixin(FlextInfraReleaseArtifactMixin):
    """Stage one project's committed HEAD, never its working tree."""

    @classmethod
    def _stage_source(
        cls, project_path: Path, stage_path: Path, gitleaks_config: Path
    ) -> p.Result[t.Pair[m.Infra.SourceSnapshot, str]]:
        """Extract HEAD of a clean project, scan it, and return identity and license digest."""
        result_type = r[t.Pair[m.Infra.SourceSnapshot, str]]
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
                f"commit epoch is not an integer for {project_path}: {epoch}"
            )
        snapshot: p.Result[m.Infra.SourceSnapshot] = u.validate_value(
            m.Infra.SourceSnapshot, {"commit_oid": oid, "source_date_epoch": int(epoch)}
        )
        if snapshot.failure:
            return result_type.fail_op(
                "validate committed release source identity", snapshot.error
            )
        archive_path = stage_path.parent / f"{stage_path.name}.tar"
        archived = u.Cli.run_checked(
            [c.Infra.GIT, "archive", "--format=tar", f"--output={archive_path}", oid],
            cwd=project_path,
            timeout=c.Infra.TIMEOUT_MEDIUM,
        )
        if archived.failure:
            return result_type.from_failure(archived)
        try:
            with tarfile.open(archive_path, "r") as archive:
                extracted = u.Infra.materialize_tar_tree(archive, stage_path)
        except (OSError, tarfile.TarError) as exc:
            return result_type.fail(
                f"extract committed release source failed: {exc}", exception=exc
            )
        if extracted.failure:
            return result_type.from_failure(extracted)
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
                    f"staged source contains symbolic link: {relative}"
                )
        scanned = cls._scan_source(stage_path, gitleaks_config)
        if scanned.failure:
            return result_type.from_failure(scanned)
        if len(licenses) != 1:
            return result_type.fail(
                f"release source must contain exactly one LICENSE: {stage_path}"
            )
        try:
            return result_type.ok((snapshot.value, u.Cli.sha256_file(licenses[0])))
        except OSError as exc:
            return result_type.fail_op(f"hash source license {licenses[0]}", exc)

    @staticmethod
    def _scan_source(stage_path: Path, gitleaks_config: Path) -> p.Result[bool]:
        """Scan the staged source with the trusted policy, never an ambient one."""
        policy = u.Cli.files_read_text(gitleaks_config)
        if policy.failure or not policy.value.strip():
            return r[bool].fail(
                policy.error or f"release Gitleaks policy is empty: {gitleaks_config}"
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
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraReleaseSourceMixin"]
