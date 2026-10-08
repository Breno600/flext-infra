"""Release project build: one committed project to one attested artifact set.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from flext_infra import c, m, p, r, t, u
from flext_infra.release._release_metadata import FlextInfraReleaseMetadataMixin


class FlextInfraReleaseProjectMixin(FlextInfraReleaseMetadataMixin):
    """Build one project from its staged source under the snapshotted policy."""

    def _build_project(
        self,
        ctx: m.Infra.ReleasePhaseDispatchConfig,
        policy: m.Infra.BuildPolicy,
        target: t.Pair[str, Path],
        versions: t.StrMapping,
    ) -> p.Result[m.Infra.BuildRecord]:
        """Build one project; its fail-loud error becomes its failed, logged record.

        Returns:
            The resulting ``p.Result[m.Infra.BuildRecord]``.

        """
        name = target[0]
        log = self._release_dir(ctx.repository_root, ctx.tag) / f"build-{name}.log"
        try:
            with TemporaryDirectory(prefix=f"{name}-", dir=log.parent) as temporary:
                built = self._build_staged(
                    ctx,
                    policy,
                    target,
                    versions,
                    Path(temporary),
                )
        except OSError as exc:
            built = r[m.Infra.BuildRecord].fail_op(
                f"manage temporary release build for {name}",
                exc,
            )
        if built.success:
            return built
        written = self._write_release_text(
            log,
            (built.error or "release build failed") + "\n",
        )
        return written.map(lambda _: self._record(target, log, exit_code=1))

    @classmethod
    def mirror_release_inputs(
        cls,
        project_path: Path,
        stage_path: Path,
    ) -> p.Result[bool]:
        """Carry the project's prepared release inputs into the staged source.

        A project's own build hook can force-include inputs its lifecycle
        generates under ``dist/`` (a pylock, a vendored node lock, a source
        receipt). The stage is a Git archive: ignored build outputs never
        enter it, so the files prepared in the checkout are mirrored verbatim.
        The project's hook stays the sole owner of the input names and of
        failing when one is missing; a project without ``dist/`` stages
        unchanged.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        del cls
        source = project_path / "dist"
        if not source.is_dir():
            return r[bool].ok(value=True)
        staged = stage_path / "dist"
        try:
            staged.mkdir(parents=True, exist_ok=True)
            for entry in sorted(source.iterdir()):
                if not entry.is_file():
                    return r[bool].fail(
                        f"project dist must contain only regular files: {entry}",
                    )
                shutil.copy2(entry, staged / entry.name)
        except OSError as exc:
            return r[bool].fail_op(f"mirror release inputs {source}", exc)
        return r[bool].ok(value=True)

    def _build_staged(
        self,
        ctx: m.Infra.ReleasePhaseDispatchConfig,
        policy: m.Infra.BuildPolicy,
        target: t.Pair[str, Path],
        versions: t.StrMapping,
        temporary: Path,
    ) -> p.Result[m.Infra.BuildRecord]:
        """Stage, render, build, validate and persist one project in ``temporary``.

        Returns:
            The resulting ``p.Result[m.Infra.BuildRecord]``.

        """
        name, path = target
        output_dir = self._release_dir(ctx.repository_root, ctx.tag)
        log, stage = output_dir / f"build-{name}.log", temporary / "source"
        version = (
            ctx.version
            if path.resolve() == ctx.repository_root.resolve()
            else versions[name]
        )
        prepared = self._stage_release_source(path, stage, policy, version, versions)
        if prepared.failure:
            return r[m.Infra.BuildRecord].from_failure(prepared)
        staged, rendered, boundary = prepared.value
        written = self._write_release_metadata(name, stage, output_dir, rendered)
        if written.failure:
            return r[m.Infra.BuildRecord].from_failure(written)
        if ctx.dry_run:
            return self._write_release_text(
                log,
                f"release metadata staged and validated: {name}\n",
            ).map(lambda _: self._record(target, log, exit_code=0, source=staged))
        build = self._execute_staged_build(
            path,
            stage,
            dist=temporary / "dist",
            policy=policy,
            source_date_epoch=staged[0].source_date_epoch,
        )
        if build.failure:
            return r[m.Infra.BuildRecord].from_failure(build)
        failed = self._logged_build_verdict(build.value, log, target, staged)
        if failed is not None:
            return failed
        artifacts = self._persist_artifacts(
            temporary / "dist",
            output_dir / "artifacts" / name,
            m.Infra.ArtifactExpectation(
                project=name,
                version=version,
                license_sha256=staged[1],
                allowed_roots=tuple(boundary),
                versions=versions,
            ),
        )
        return artifacts.map(
            lambda built: self._record(
                target,
                log,
                exit_code=0,
                artifacts=built,
                source=staged,
            ),
        )

    def _stage_release_source(
        self,
        path: Path,
        stage: Path,
        policy: m.Infra.BuildPolicy,
        version: str,
        versions: t.StrMapping,
    ) -> p.Result[t.Triple[t.Pair[m.Infra.SourceSnapshot, str], str, t.StrSequence]]:
        """Stage, render, and boundary-check one project's release source.

        Returns:
            The resulting ``(staged, rendered, boundary_roots)`` triple.

        """
        result_type = r[
            t.Triple[t.Pair[m.Infra.SourceSnapshot, str], str, t.StrSequence]
        ]
        staged = self._stage_source(path, stage, Path(policy.gitleaks_policy_path))
        if staged.failure:
            return result_type.from_failure(staged)
        source = u.Cli.files_read_text(stage / c.PYPROJECT_FILENAME)
        if source.failure:
            return result_type.from_failure(source)
        rendered = self._release_pyproject(source.value, version, versions)
        if rendered.failure:
            return result_type.from_failure(rendered)
        document = u.Cli.toml_parse_text(rendered.value)
        tool = (
            u.Cli.toml_table_child(document, c.Infra.TOOL)
            if document is not None
            else None
        )
        hatch = u.Cli.toml_table_child(tool, "hatch") if tool is not None else None
        if hatch is None:
            return result_type.fail(
                "rendered release metadata lost Hatch build targets",
            )
        boundary = self._sdist_boundary(hatch)
        if boundary.failure:
            return result_type.from_failure(boundary)
        return result_type.ok((staged.value, rendered.value, boundary.value))

    def _write_release_metadata(
        self,
        name: str,
        stage: Path,
        output_dir: Path,
        rendered: str,
    ) -> p.Result[bool]:
        """Write the rendered release pyproject to the stage and the receipt.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for destination in (
            stage / c.PYPROJECT_FILENAME,
            output_dir / "metadata" / f"{name}-pyproject.toml",
        ):
            written = self._write_release_text(destination, rendered)
            if written.failure:
                return r[bool].from_failure(written)
        return r[bool].ok(value=True)

    def _execute_staged_build(
        self,
        path: Path,
        stage: Path,
        *,
        dist: Path,
        policy: m.Infra.BuildPolicy,
        source_date_epoch: int,
    ) -> p.Result[p.Cli.CommandOutput]:
        """Mirror the project's release inputs, then run the isolated build.

        Returns:
            The resulting ``p.Result[p.Cli.CommandOutput]``.

        """
        mirrored = self.mirror_release_inputs(path, stage)
        if mirrored.failure:
            return r[p.Cli.CommandOutput].from_failure(mirrored)
        return self._run_staged_build(
            stage,
            dist=dist,
            policy=policy,
            source_date_epoch=source_date_epoch,
        )

    def _logged_build_verdict(
        self,
        build: p.Cli.CommandOutput,
        log: Path,
        target: t.Pair[str, Path],
        staged: t.Pair[m.Infra.SourceSnapshot, str],
    ) -> p.Result[m.Infra.BuildRecord] | None:
        """Write the build log and return its failed record, or ``None`` on success.

        Returns:
            The failed build record, or ``None`` when the build succeeded.

        """
        output = (build.stdout + "\n" + build.stderr).strip()
        logged = self._write_release_text(log, output + "\n")
        if logged.failure:
            return r[m.Infra.BuildRecord].from_failure(logged)
        if not u.Cli.process_succeeded(build.outcome):
            return r[m.Infra.BuildRecord].ok(
                self._record(
                    target,
                    log,
                    exit_code=build.outcome.raw_return_code,
                    source=staged,
                ),
            )
        return None

    @staticmethod
    def _run_staged_build(
        stage: Path,
        *,
        dist: Path,
        policy: m.Infra.BuildPolicy,
        source_date_epoch: int,
    ) -> p.Result[p.Cli.CommandOutput]:
        """Run the isolated release build of one staged source tree.

        Returns:
            The resulting ``p.Result[p.Cli.CommandOutput]``.

        """
        return u.Cli.run_raw(
            [
                *c.Infra.RELEASE_UV_BUILD_ARGS,
                "--build-constraints",
                policy.build_constraints_path,
                "--out-dir",
                str(dist),
                str(stage),
            ],
            timeout=c.Infra.TIMEOUT_LONG,
            options=m.Cli.ProcessOptions(
                env={
                    c.Infra.SOURCE_DATE_EPOCH: str(source_date_epoch),
                    c.Infra.UV_HTTP_CONNECT_TIMEOUT: (
                        c.Infra.UV_RELEASE_HTTP_CONNECT_TIMEOUT
                    ),
                    c.Infra.UV_HTTP_TIMEOUT: c.Infra.UV_RELEASE_HTTP_TIMEOUT,
                    c.Infra.UV_HTTP_RETRIES: c.Infra.UV_RELEASE_HTTP_RETRIES,
                },
                remove_env_keys=c.Infra.UV_RELEASE_POLICY_ENV_KEYS,
            ),
        )

    @classmethod
    def _persist_artifacts(
        cls,
        dist: Path,
        destination: Path,
        expectation: m.Infra.ArtifactExpectation,
    ) -> p.Result[t.VariadicTuple[m.Infra.BuildArtifact]]:
        """Validate exactly one wheel and one sdist, then persist the set atomically.

        An existing set is immutable: it is accepted only byte for byte.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.BuildArtifact]]``.

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
                f"uv build emitted unexpected output: {', '.join(unexpected)}",
            )
        if len(wheels) != 1 or len(sdists) != 1:
            return result_type.fail(
                f"expected one wheel and one sdist, found "
                f"{len(wheels)} wheel(s) and {len(sdists)} sdist(s)",
            )
        built: t.MutableSequenceOf[m.Infra.BuildArtifact] = []
        for source in sources:
            validated = cls._validate_artifact(source, expectation)
            if validated.failure:
                return result_type.from_failure(validated)
            kind, digest = validated.value
            persisted = str((destination / source.name).resolve())
            built.append(
                m.Infra.BuildArtifact(path=persisted, kind=kind, sha256=digest),
            )
        committed = cls._commit_artifacts(destination, sources)
        if committed.failure:
            return result_type.from_failure(committed)
        return result_type.ok(tuple(built))

    @classmethod
    def _commit_artifacts(
        cls,
        destination: Path,
        sources: t.SequenceOf[Path],
    ) -> p.Result[bool]:
        """Commit the artifact set: byte-identical acceptance or atomic persist.

        An existing set is immutable: it is accepted only byte for byte.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if not destination.exists():
            return cls._persist_fresh_artifacts(destination, sources)
        return cls._existing_artifacts_match(destination, sources)

    @classmethod
    def _existing_artifacts_match(
        cls,
        destination: Path,
        sources: t.SequenceOf[Path],
    ) -> p.Result[bool]:
        """Prove an existing artifact set matches byte for byte.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        try:
            same = sorted(destination.iterdir()) == sorted(
                destination / source.name for source in sources
            ) and all(
                source.read_bytes() == (destination / source.name).read_bytes()
                for source in sources
            )
        except OSError as exc:
            return r[bool].fail_op(
                f"compare immutable artifacts {destination}",
                exc,
            )
        if not same:
            return r[bool].fail(
                f"immutable artifact collision at {destination}",
            )
        return r[bool].ok(value=True)

    @staticmethod
    def _persist_fresh_artifacts(
        destination: Path,
        sources: t.SequenceOf[Path],
    ) -> p.Result[bool]:
        """Persist a fresh artifact set atomically through a sibling staging dir.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(
                prefix=f".{destination.name}-",
                dir=destination.parent,
            ) as staging:
                for source in sources:
                    shutil.copy2(source, Path(staging) / source.name)
                Path(staging).replace(destination)
        except OSError as exc:
            return r[bool].fail_op(
                f"persist release artifact set {destination}",
                exc,
            )
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraReleaseProjectMixin"]
