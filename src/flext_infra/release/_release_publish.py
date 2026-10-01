"""Release publish phase: upload exactly what the build receipt attests."""

from __future__ import annotations

from pathlib import Path

from flext_core import r
from flext_infra import c, config, m, p, u

from ._release_build import FlextInfraReleaseBuildMixin


class FlextInfraReleasePublishMixin(FlextInfraReleaseBuildMixin):
    """Publish the receipt's artifacts, re-hashed, as a GitHub release and to the index.

    The package index receives them in dependency order, so a dependent
    never precedes its dependency.
    """

    def phase_publish(self, ctx: m.Infra.ReleasePhaseDispatchConfig) -> p.Result[bool]:
        """Publish the receipt's artifacts as a GitHub release and, on request, to the index."""
        receipt = self._verified_receipt(ctx)
        if receipt.failure:
            return r[bool].from_failure(receipt)
        if not ctx.dry_run:
            released = self._github_release(ctx, receipt.value)
            if released.failure:
                return released
            if ctx.index:
                uploaded = self._index_upload(ctx, receipt.value)
                if uploaded.failure:
                    return uploaded
        self.logger.info(
            "release_phase_publish", tag=ctx.tag, dry_run=ctx.dry_run, index=ctx.index
        )
        return r[bool].ok(True)

    def _verified_receipt(
        self, ctx: m.Infra.ReleasePhaseDispatchConfig
    ) -> p.Result[m.Infra.BuildReport]:
        """Load the receipt and prove every artifact still matches its digest."""
        path = (
            self._release_dir(ctx.repository_root, ctx.tag)
            / c.Infra.RELEASE_REPORT_FILENAME
        )
        content = u.Cli.files_read_text(path)
        if content.failure:
            return r[m.Infra.BuildReport].from_failure(content)
        report: p.Result[m.Infra.BuildReport] = u.validate_value(
            m.Infra.BuildReport, content.value, from_json=True
        )
        if report.failure:
            return r[m.Infra.BuildReport].fail_op(
                "validate release receipt", report.error
            )
        if (
            report.value.dry_run
            or report.value.failures
            or report.value.version != ctx.version
        ):
            return r[m.Infra.BuildReport].fail(
                f"release receipt is not publishable for {ctx.version}: {path}"
            )
        for artifact in (
            a for record in report.value.records for a in record.artifacts
        ):
            try:
                digest = u.Cli.sha256_file(Path(artifact.path))
            except OSError as exc:
                return r[m.Infra.BuildReport].fail_op(
                    f"read artifact {artifact.path}", exc
                )
            if digest != artifact.sha256:
                return r[m.Infra.BuildReport].fail(
                    f"artifact digest differs from receipt: {artifact.path}"
                )
        return report

    @staticmethod
    def _github_release(
        ctx: m.Infra.ReleasePhaseDispatchConfig, report: m.Infra.BuildReport
    ) -> p.Result[bool]:
        """Create or refresh the GitHub release with the receipt's artifacts."""
        root = ctx.repository_root
        assets = [a.path for record in report.records for a in record.artifacts]
        exists = u.Cli.capture(
            [c.Infra.GH, "release", "view", ctx.tag, "--json", "tagName"], cwd=root
        )
        if exists.success:
            return u.Cli.run_checked(
                [c.Infra.GH, "release", "upload", ctx.tag, *assets, "--clobber"],
                cwd=root,
            )
        notes = root / c.Infra.DIR_DOCS / "releases" / f"{ctx.tag}.md"
        return u.Cli.run_checked(
            [
                c.Infra.GH,
                "release",
                "create",
                ctx.tag,
                *assets,
                "--title",
                f"Release {ctx.tag}",
                "--notes-file",
                str(notes),
            ],
            cwd=root,
        )

    def _index_upload(
        self, ctx: m.Infra.ReleasePhaseDispatchConfig, report: m.Infra.BuildReport
    ) -> p.Result[bool]:
        """Upload verified artifacts wave by wave through trusted publishing.

        ``--check-url`` skips files already on the index, so a rerun after a
        partial failure resumes instead of failing on the first duplicate.
        """
        artifacts = {
            record.project: tuple(a.path for a in record.artifacts)
            for record in report.records
        }
        waves = u.Infra.release_publish_waves(
            tuple((record.project, Path(record.path)) for record in report.records)
        )
        if waves.failure:
            return r[bool].from_failure(waves)
        for wave in waves.value:
            uploaded = u.Cli.run_checked(
                [
                    c.Infra.UV,
                    "publish",
                    "--no-config",
                    "--publish-url",
                    config.Infra.release.publish_url,
                    "--check-url",
                    c.Infra.PYPI_SIMPLE_INDEX_URL,
                    "--trusted-publishing",
                    "always",
                    *(path for project in wave for path in artifacts[project]),
                ],
                cwd=ctx.repository_root,
            )
            if uploaded.failure:
                return uploaded
            self.logger.info("release_index_wave_published", projects=", ".join(wave))
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraReleasePublishMixin"]
