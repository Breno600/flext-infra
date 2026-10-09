"""Release build phase: attested artifacts built from committed sources.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, config, m, p, r, t, u
from flext_infra.release._release_project import FlextInfraReleaseProjectMixin


class FlextInfraReleaseBuildMixin(FlextInfraReleaseProjectMixin):
    """Build every selected project under one immutable policy; write the receipt."""

    @staticmethod
    def render_build_constraints(
        pins: t.SequenceOf[m.Infra.BuildConstraintSpec],
    ) -> str:
        """Render the ``uv build --require-hashes`` constraints from typed config.

        One ``name==version`` record per pin, continued by one ``--hash``
        line per digest; identical pins render identical bytes.

        Returns:
            The resulting ``str``.

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
        """Build registry-safe member artifacts and write the receipt.

        Returns:
            The resulting ``p.Result[bool]``.

        """
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
        # A consumer requirement can name an internal distribution the release
        # tree does not carry as a workspace project (e.g. ``flext-api``);
        # the root uv.lock is the resolved-version authority `make upg` wrote,
        # so its internal git entries seed the map and workspace projects keep
        # precedence.
        locked = self.internal_locked_versions(root)
        if locked.failure:
            return r[bool].from_failure(locked)
        for name, version in locked.value.items():
            versions.setdefault(name, version)
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
        return r[bool].ok(value=True)

    @staticmethod
    def internal_locked_versions(
        repository_root: Path,
    ) -> p.Result[t.MutableStrMapping]:
        """Map internal git dependencies to the version the root lock resolved.

        ``make upg`` owns the lock and every resolved revision it records, so
        for an internal distribution that a consumer requires as a git
        dependency — one the release tree carries in its lock but not as a
        workspace project — the lock's declared version is the only honest
        pin. Workspace projects keep precedence in the caller; a name absent
        from both remains unknown to the render and fails loud there.

        Returns:
            The resulting ``p.Result[t.MutableStrMapping]``.

        """
        lock_path = repository_root / c.Infra.UV_LOCK_FILENAME
        text = u.Cli.files_read_text(lock_path)
        if text.failure:
            # A consumer without a lock (fixture workspaces, first-release
            # trees) has no internal git entries to seed; the render's
            # fail-loud still covers every name the map lacks.
            return r[t.MutableStrMapping].ok({})
        document = u.Cli.toml_parse_text(text.value)
        if document is None:
            return r[t.MutableStrMapping].fail(
                f"release build cannot parse {lock_path}: invalid TOML",
            )
        versions: t.MutableStrMapping = {}
        for package in document.get("package") or []:
            name = package.get("name") or ""
            version = package.get("version") or ""
            source = package.get("source") or {}
            if (
                name.startswith(c.Infra.PKG_PREFIX_HYPHEN)
                and version
                and isinstance(source, dict)
                and source.get("git")
            ):
                versions.setdefault(name, version)
        return r[bool].ok(versions)

    @classmethod
    def _snapshot_policy(
        cls,
        root: Path,
        policy_dir: Path,
    ) -> p.Result[m.Infra.BuildPolicy]:
        """Capture the immutable policy pair once, before the first project build.

        Build constraints render from the typed config SSOT; the Gitleaks
        policy is the repository's codegen projection.

        Returns:
            The resulting ``p.Result[m.Infra.BuildPolicy]``.

        """
        constraints = policy_dir / "build-constraints.txt"
        gitleaks = policy_dir / "gitleaks-release.toml"
        try:
            snapshots = {
                constraints: cls.render_build_constraints(
                    config.Infra.release.build_constraints,
                ).encode("utf-8"),
                gitleaks: (root / c.Infra.RELEASE_GITLEAKS_CONFIG_PATH).read_bytes(),
            }
            policy_dir.mkdir(parents=True, exist_ok=True)
            for destination, content in snapshots.items():
                if destination.exists() and destination.read_bytes() != content:
                    return r[m.Infra.BuildPolicy].fail(
                        f"immutable release policy collision: {destination}",
                    )
                destination.write_bytes(content)
        except OSError as exc:
            return r[m.Infra.BuildPolicy].fail_op(
                f"snapshot release policy into {policy_dir}",
                exc,
            )
        return r[m.Infra.BuildPolicy].ok(
            m.Infra.BuildPolicy(
                build_constraints_path=str(constraints.resolve()),
                build_constraints_sha256=u.Cli.sha256_bytes(snapshots[constraints]),
                gitleaks_policy_path=str(gitleaks.resolve()),
                gitleaks_policy_sha256=u.Cli.sha256_bytes(snapshots[gitleaks]),
            ),
        )


__all__: list[str] = ["FlextInfraReleaseBuildMixin"]
