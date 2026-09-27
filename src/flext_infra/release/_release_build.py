"""Release build phase: attested artifacts built from committed sources."""

from __future__ import annotations

from pathlib import Path

from flext_core import r
from flext_infra import c, config, m, p, t, u

from ._release_project import FlextInfraReleaseProjectMixin


class FlextInfraReleaseBuildMixin(FlextInfraReleaseProjectMixin):
    """Build every selected project under one immutable policy; write the receipt."""

    @staticmethod
    def render_build_constraints(
        pins: t.SequenceOf[m.Infra.BuildConstraintSpec],
    ) -> str:
        """Render the ``uv build --require-hashes`` constraints from typed config.

        One ``name==version`` record per pin, continued by one ``--hash``
        line per digest; identical pins render identical bytes.
        """
        records = (
            " \\\n".join((
                f"{pin.name}=={pin.version}",
                *(f"    --hash=sha256:{digest}" for digest in pin.hashes),
            ))
            for pin in pins
        )
        return (
            "# Rendered by flext_infra release policy from "
            "config.Infra.release.build_constraints.\n"
            "# Release build policy: the isolated `uv build "
            "--build-constraints … --require-hashes`\n"
            "# of every release artifact resolves its build backend from "
            "exactly these pins.\n" + "\n".join(records) + "\n"
        )

    def phase_build(self, ctx: m.Infra.ReleasePhaseDispatchConfig) -> p.Result[bool]:
        """Build registry-safe member artifacts and write the receipt."""
        root = ctx.repository_root
        output_dir = self._release_dir(root, ctx.tag)
        selected = u.Infra.resolve_projects(root, ctx.project_names)
        if selected.failure:
            return r[bool].from_failure(selected)
        # Eligibility is declared data; no prefix means every project publishes.
        prefixes = tuple(config.Infra.release.publishable_prefixes)
        targets: t.MutableMappingKV[str, Path] = {}
        for project in selected.value:
            if project.path.exists() and project.name.startswith(prefixes or ("",)):
                targets.setdefault(project.name, project.path)
        if not targets:
            return r[bool].fail("release build selected no publishable projects")
        policy = self._snapshot_policy(root, output_dir / "policy")
        if policy.failure:
            return r[bool].from_failure(policy)
        # Each repository versions independently: a sibling is pinned to what
        # its own pyproject declares, never to a guessed version.
        every = u.Infra.resolve_projects(root, ())
        if every.failure:
            return r[bool].from_failure(every)
        versions: t.MutableStrMapping = {}
        for project in every.value:
            declared = u.Infra.current_workspace_version(project.path)
            if declared.failure:
                return r[bool].from_failure(declared)
            versions[project.name] = declared.value
        records: t.MutableSequenceOf[m.Infra.BuildRecord] = []
        for name, path in targets.items():
            record = self._build_project(ctx, policy.value, (name, path), versions)
            if record.failure:
                return r[bool].from_failure(record)
            records.append(record.value)
            self.logger.info(
                "release_phase_build_project",
                project=name,
                exit_code=record.value.exit_code,
            )
        failures = sum(record.exit_code != 0 for record in records)
        report = m.Infra.BuildReport(
            version=ctx.version,
            total=len(records),
            failures=failures,
            records=tuple(records),
            dry_run=ctx.dry_run,
            build_constraints_sha256=policy.value.build_constraints_sha256,
            gitleaks_policy_sha256=policy.value.gitleaks_policy_sha256,
        )
        written = u.Cli.json_write(
            output_dir / c.Infra.RELEASE_REPORT_FILENAME,
            report.model_dump(mode="json"),
            m.Cli.JsonWriteOptions(sort_keys=True),
        )
        if written.failure:
            return r[bool].from_failure(written)
        if failures:
            return r[bool].fail(f"build failed: {failures} project(s)")
        return r[bool].ok(True)

    @classmethod
    def _snapshot_policy(
        cls, root: Path, policy_dir: Path
    ) -> p.Result[m.Infra.BuildPolicy]:
        """Capture the immutable policy pair once, before the first project build.

        Build constraints render from the typed config SSOT; the Gitleaks
        policy is the repository's codegen projection.
        """
        constraints = policy_dir / "build-constraints.txt"
        gitleaks = policy_dir / "gitleaks-release.toml"
        try:
            snapshots = {
                constraints: cls.render_build_constraints(
                    config.Infra.release.build_constraints
                ).encode("utf-8"),
                gitleaks: (root / c.Infra.RELEASE_GITLEAKS_CONFIG_PATH).read_bytes(),
            }
            policy_dir.mkdir(parents=True, exist_ok=True)
            for destination, content in snapshots.items():
                if destination.exists() and destination.read_bytes() != content:
                    return r[m.Infra.BuildPolicy].fail(
                        f"immutable release policy collision: {destination}"
                    )
                destination.write_bytes(content)
        except OSError as exc:
            return r[m.Infra.BuildPolicy].fail_op(
                f"snapshot release policy into {policy_dir}", exc
            )
        return r[m.Infra.BuildPolicy].ok(
            m.Infra.BuildPolicy(
                build_constraints_path=str(constraints.resolve()),
                build_constraints_sha256=u.Cli.sha256_bytes(snapshots[constraints]),
                gitleaks_policy_path=str(gitleaks.resolve()),
                gitleaks_policy_sha256=u.Cli.sha256_bytes(snapshots[gitleaks]),
            )
        )


__all__: list[str] = ["FlextInfraReleaseBuildMixin"]
