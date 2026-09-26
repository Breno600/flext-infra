"""Release project build: one committed project to one attested artifact set."""

from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from flext_core import r
from flext_infra import c, m, p, t, u

from ._release_metadata import FlextInfraReleaseMetadataMixin


class FlextInfraReleaseProjectMixin(FlextInfraReleaseMetadataMixin):
    """Build one project from its staged source under the snapshotted policy."""

    def _build_project(
        self,
        ctx: m.Infra.ReleasePhaseDispatchConfig,
        policy: m.Infra.BuildPolicy,
        target: t.Pair[str, Path],
        versions: t.StrMapping,
    ) -> p.Result[m.Infra.BuildRecord]:
        """Build one project; its fail-loud error becomes its failed, logged record."""
        name, path = target
        log = self._release_dir(ctx.repository_root, ctx.tag) / f"build-{name}.log"
        try:
            with TemporaryDirectory(prefix=f"{name}-", dir=log.parent) as temporary:
                built = self._build_staged(
                    ctx, policy, target, versions, Path(temporary)
                )
        except OSError as exc:
            built = r[m.Infra.BuildRecord].fail_op(
                f"manage temporary release build for {name}", exc
            )
        if built.success:
            return built
        written = self._write_release_text(
            log, (built.error or "release build failed") + "\n"
        )
        return written.map(lambda _: self._record(name, path, log, exit_code=1))

    def _build_staged(
        self,
        ctx: m.Infra.ReleasePhaseDispatchConfig,
        policy: m.Infra.BuildPolicy,
        target: t.Pair[str, Path],
        versions: t.StrMapping,
        temporary: Path,
    ) -> p.Result[m.Infra.BuildRecord]:
        """Stage, render, build, validate and persist one project in ``temporary``."""
        name, path = target
        output_dir = self._release_dir(ctx.repository_root, ctx.tag)
        log, stage = output_dir / f"build-{name}.log", temporary / "source"
        root_project = path.resolve() == ctx.repository_root.resolve()
        version = ctx.version if root_project else versions[name]
        staged = self._stage_source(path, stage, Path(policy.gitleaks_policy_path))
        if staged.failure:
            return r[m.Infra.BuildRecord].from_failure(staged)
        snapshot, license_sha256 = staged.value
        source = u.Cli.files_read_text(stage / c.PYPROJECT_FILENAME)
        if source.failure:
            return r[m.Infra.BuildRecord].from_failure(source)
        rendered = self._release_pyproject(source.value, version, versions)
        if rendered.failure:
            return r[m.Infra.BuildRecord].from_failure(rendered)
        for destination in (
            stage / c.PYPROJECT_FILENAME,
            output_dir / "metadata" / f"{name}-pyproject.toml",
        ):
            written = self._write_release_text(destination, rendered.value)
            if written.failure:
                return r[m.Infra.BuildRecord].from_failure(written)
        if ctx.dry_run:
            return self._write_release_text(
                log, f"release metadata staged and validated: {name}\n"
            ).map(
                lambda _: self._record(
                    name,
                    path,
                    log,
                    exit_code=0,
                    snapshot=snapshot,
                    source_license_sha256=license_sha256,
                )
            )
        dist = temporary / "dist"
        build = u.Cli.run_raw(
            [
                *c.Infra.RELEASE_UV_BUILD_ARGS,
                "--build-constraints",
                policy.build_constraints_path,
                "--out-dir",
                str(dist),
                str(stage),
            ],
            timeout=c.Infra.TIMEOUT_LONG,
            env={
                c.Infra.SOURCE_DATE_EPOCH: str(snapshot.source_date_epoch),
                c.Infra.UV_HTTP_CONNECT_TIMEOUT: c.Infra.UV_RELEASE_HTTP_CONNECT_TIMEOUT,
                c.Infra.UV_HTTP_TIMEOUT: c.Infra.UV_RELEASE_HTTP_TIMEOUT,
                c.Infra.UV_HTTP_RETRIES: c.Infra.UV_RELEASE_HTTP_RETRIES,
            },
            remove_env_keys=c.Infra.UV_RELEASE_POLICY_ENV_KEYS,
        )
        if build.failure:
            return r[m.Infra.BuildRecord].from_failure(build)
        output = (build.value.stdout + "\n" + build.value.stderr).strip()
        written = self._write_release_text(log, output + "\n")
        if written.failure:
            return r[m.Infra.BuildRecord].from_failure(written)
        if not u.Cli.process_succeeded(build.value.outcome):
            return r[m.Infra.BuildRecord].ok(
                self._record(
                    name,
                    path,
                    log,
                    exit_code=build.value.outcome.raw_return_code,
                    snapshot=snapshot,
                    source_license_sha256=license_sha256,
                )
            )
        artifacts = self._persist_artifacts(
            dist,
            output_dir / "artifacts" / name,
            (name, version),
            license_sha256,
            versions,
        )
        return artifacts.map(
            lambda built: self._record(
                name,
                path,
                log,
                exit_code=0,
                artifacts=built,
                snapshot=snapshot,
                source_license_sha256=license_sha256,
            )
        )

    @classmethod
    def _persist_artifacts(
        cls,
        dist: Path,
        destination: Path,
        identity: t.Pair[str, str],
        license_sha256: str,
        versions: t.StrMapping,
    ) -> p.Result[t.VariadicTuple[m.Infra.BuildArtifact]]:
        """Validate exactly one wheel and one sdist, then persist the set atomically.

        An existing set is immutable: it is accepted only byte for byte.
        """
        result_type = r[t.VariadicTuple[m.Infra.BuildArtifact]]
        try:
            entries = tuple(sorted(dist.iterdir()))
        except OSError as exc:
            return result_type.fail_op(f"list uv build output {dist}", exc)
        wheels = tuple(entry for entry in entries if entry.suffix == ".whl")
        sdists = tuple(entry for entry in entries if entry.name.endswith(".tar.gz"))
        sources = (*wheels, *sdists)
        unexpected = [entry.name for entry in entries if entry not in sources]
        if unexpected:
            return result_type.fail(
                f"uv build emitted unexpected output: {', '.join(unexpected)}"
            )
        if len(wheels) != 1 or len(sdists) != 1:
            return result_type.fail(
                f"expected one wheel and one sdist, found "
                f"{len(wheels)} wheel(s) and {len(sdists)} sdist(s)"
            )
        built: t.MutableSequenceOf[m.Infra.BuildArtifact] = []
        for source in sources:
            validated = cls._validate_artifact(
                source, identity, license_sha256, versions
            )
            if validated.failure:
                return result_type.from_failure(validated)
            kind, digest = validated.value
            persisted = str((destination / source.name).resolve())
            built.append(
                m.Infra.BuildArtifact(path=persisted, kind=kind, sha256=digest)
            )
        if destination.exists():
            try:
                same = sorted(destination.iterdir()) == sorted(
                    destination / source.name for source in sources
                ) and all(
                    source.read_bytes() == (destination / source.name).read_bytes()
                    for source in sources
                )
            except OSError as exc:
                return result_type.fail_op(
                    f"compare immutable artifacts {destination}", exc
                )
            if not same:
                return result_type.fail(
                    f"immutable artifact collision at {destination}"
                )
            return result_type.ok(tuple(built))
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(
                prefix=f".{destination.name}-", dir=destination.parent
            ) as staging:
                for source in sources:
                    shutil.copy2(source, Path(staging) / source.name)
                Path(staging).replace(destination)
        except OSError as exc:
            return result_type.fail_op(
                f"persist release artifact set {destination}", exc
            )
        return result_type.ok(tuple(built))


__all__: list[str] = ["FlextInfraReleaseProjectMixin"]
