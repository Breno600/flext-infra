"""Public release build-policy tests using real workspaces."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from flext_tests import tm

from flext_infra import config
from tests import c, u


class TestsFlextInfraReleaseDag:
    """Behavior contract for fail-closed release build policy."""

    class TestsDryRun:
        """Metadata-only build behavior."""

        @staticmethod
        def test_release_succeeds_in_dry_run_mode(tmp_path: Path) -> None:
            """Create strict reports without persisting package artifacts."""
            project_name = "flext-a"
            workspace = u.Tests.release_internal_workspace(tmp_path, project_name)

            result = u.Tests.run_release_build(workspace, project_name, dry_run=True)

            report = u.Tests.release_build_report(workspace)
            tm.that(result, eq=0)
            tm.that(report.total, eq=1)
            tm.that(report.records[0].project, eq=project_name)
            tm.that(report.records[0].artifacts, eq=())

    class TestsBuildConstraints:
        """Hashed build-toolchain policy behavior."""

        @staticmethod
        def policy_snapshot(workspace: Path, name: str) -> bytes:
            """Read one immutable policy file a build phase snapshotted."""
            return (
                u.Tests.release_report_dir(workspace, c.Tests.RELEASE_VERSION_BASE)
                / "policy"
                / name
            ).read_bytes()

        @staticmethod
        def test_complete_hashed_constraints_build_and_are_attested(
            tmp_path: Path,
        ) -> None:
            """Build only with the complete hashed toolchain and attest its digests."""
            project_name = "flext-a"
            workspace = u.Tests.release_internal_workspace(tmp_path, project_name)

            result = u.Tests.run_release_build(workspace, project_name)

            report = u.Tests.release_build_report(workspace)
            snapshot = TestsFlextInfraReleaseDag.TestsBuildConstraints.policy_snapshot
            gitleaks_path = workspace / c.Infra.RELEASE_GITLEAKS_CONFIG_PATH
            tm.that(result, eq=0)
            tm.that(
                report.build_constraints_sha256,
                eq=hashlib.sha256(
                    snapshot(workspace, "build-constraints.txt")
                ).hexdigest(),
            )
            tm.that(
                report.gitleaks_policy_sha256,
                eq=hashlib.sha256(gitleaks_path.read_bytes()).hexdigest(),
            )
            tm.that(report.records[0].exit_code, eq=0)

        @staticmethod
        def test_policy_snapshot_pins_every_configured_backend(tmp_path: Path) -> None:
            """The snapshot carries each configured pin with exactly its digests.

            ``uv build --require-hashes`` then accepts precisely the declared
            backend; the typed config is the only owner of those bytes, and a
            second build renders them identically.
            """
            project_name = "flext-a"
            workspace = u.Tests.release_internal_workspace(tmp_path, project_name)
            snapshot = TestsFlextInfraReleaseDag.TestsBuildConstraints.policy_snapshot

            first = u.Tests.run_release_build(workspace, project_name, dry_run=True)
            rendered = snapshot(workspace, "build-constraints.txt").decode("utf-8")
            second = u.Tests.run_release_build(workspace, project_name, dry_run=True)

            pins = config.Infra.release.build_constraints
            tm.that((first, second), eq=(0, 0))
            for pin in pins:
                tm.that(rendered, has=f"{pin.name}=={pin.version} \\")
                for digest in pin.hashes:
                    tm.that(rendered, has=f"--hash=sha256:{digest}")
            tm.that(
                rendered.count("--hash=sha256:"),
                eq=sum(len(pin.hashes) for pin in pins),
            )
            tm.that(rendered, lacks="\\\n\n")
            tm.that(
                snapshot(workspace, "build-constraints.txt").decode("utf-8"),
                eq=rendered,
            )

        @staticmethod
        def test_only_the_gitleaks_policy_is_projected_into_repositories() -> None:
            """Codegen owns the Gitleaks policy everywhere and no constraints file.

            Build constraints render from the typed config at release time; a
            repository ``config/build-constraints.txt`` would be a second owner.
            """
            entries = {
                entry.destination: entry
                for entry in config.Infra.codegen.templates.entries
            }
            gitleaks = entries[c.Infra.RELEASE_GITLEAKS_CONFIG_PATH]
            tm.that("config/build-constraints.txt" in entries, eq=False)
            tm.that(set(gitleaks.profiles), eq=set(c.Infra.MakeProfile))
            tm.that(gitleaks.overwrite, eq=True)

    class TestsArchiveBoundary:
        """Publishable archive content policy."""

        @staticmethod
        def test_package_data_may_carry_an_operational_looking_tree(
            tmp_path: Path,
        ) -> None:
            """A `.github` tree inside the package is data, not repository operations.

            flext-infra ships the fleet's `.github` workflow templates as package
            data; only the archive root is an operational boundary.
            """
            project_name = "flext-a"
            workspace = u.Tests.release_internal_workspace(tmp_path, project_name)
            project = workspace / project_name
            templates = project / "src" / "flext_a" / "templates" / ".github"
            templates.mkdir(parents=True)
            (templates / "ci.yml.j2").write_text("name: CI\n", encoding="utf-8")
            u.Tests.commit_git_changes(project, "package the workflow templates")

            result = u.Tests.run_release_build(workspace, project_name)

            build_log = u.Tests.release_build_log_text(workspace, project_name)
            tm.that(result, eq=0, msg=build_log)
            wheel = next(
                u.Tests.release_artifact_dir(
                    workspace, c.Tests.RELEASE_VERSION_BASE, project_name
                ).glob("*.whl")
            )
            with zipfile.ZipFile(wheel) as archive:
                tm.that(archive.namelist(), has="flext_a/templates/.github/ci.yml.j2")

    class TestsMetadata:
        """Publishable metadata policy behavior."""

        @staticmethod
        def test_unavailable_sibling_manifest_fails_release(tmp_path: Path) -> None:
            """Never substitute installed versions for an unavailable release source."""
            project_name = "flext-a"
            workspace = u.Tests.create_release_workspace(
                tmp_path, project_names=(project_name,), initialize_project_git=True
            )
            result = u.Tests.run_release_build(workspace, project_name)
            tm.that(result, ne=0)
            tm.that(
                u.Tests.release_build_log_text(workspace, project_name),
                has="internal dependency version unknown",
            )

        @staticmethod
        def test_missing_hatch_config_fails_before_artifact_build(
            tmp_path: Path,
        ) -> None:
            """Reject committed metadata without the required Hatch boundary."""
            project_name = "flext-a"
            workspace = u.Tests.release_internal_workspace(tmp_path, project_name)
            project = workspace / project_name
            pyproject = project / "pyproject.toml"
            content = pyproject.read_text(encoding="utf-8")
            pyproject.write_text(
                content.split("[tool.hatch.build.targets.sdist]", maxsplit=1)[0],
                encoding="utf-8",
            )
            u.Tests.commit_git_changes(project, "remove Hatch release metadata")

            result = u.Tests.run_release_build(workspace, project_name)

            build_log = u.Tests.release_build_log_text(workspace, project_name)
            tm.that(result, eq=1)
            tm.that(build_log, has="release pyproject must define [tool.hatch]")
            tm.that(
                u.Tests.release_artifact_dir(
                    workspace, c.Tests.RELEASE_VERSION_BASE, project_name
                ).exists(),
                eq=False,
            )

    class TestsGitleaksPolicy:
        """Trusted secret-scanning policy behavior."""

        @staticmethod
        def test_ambient_gitleaks_override_cannot_replace_trusted_policy(
            tmp_path: Path,
        ) -> None:
            """Detect committed secret material despite permissive ambient config."""
            project_name = "flext-a"
            workspace = u.Tests.release_internal_workspace(tmp_path, project_name)
            project = workspace / project_name
            synthetic_token = hashlib.sha256(project_name.encode()).hexdigest()
            (project / "credential.txt").write_text(
                # Split literal: fixture writes a synthetic secret for the
                # gitleaks detection path and must not self-match scans.
                "api_" + f'key = "{synthetic_token}"\n',
                encoding="utf-8",
            )
            u.Tests.commit_git_changes(project, "add synthetic secret fixture")
            ambient_policy = tmp_path / "ambient-gitleaks.toml"
            ambient_policy.write_text(
                'title = "permissive ambient policy"\n', encoding="utf-8"
            )

            with tm.scope(env={"GITLEAKS_CONFIG": str(ambient_policy)}):
                result = u.Tests.run_release_build(workspace, project_name)

            build_log = u.Tests.release_build_log_text(workspace, project_name)
            tm.that(result, eq=1)
            tm.that(build_log, has="gitleaks detected a secret")

        @staticmethod
        def test_committed_gitleaks_policy_file_is_rejected(tmp_path: Path) -> None:
            """Reject project-owned scanner policy from the committed source set."""
            project_name = "flext-a"
            workspace = u.Tests.release_internal_workspace(tmp_path, project_name)
            project = workspace / project_name
            (project / ".gitleaks.toml").write_text(
                'title = "project override"\n', encoding="utf-8"
            )
            u.Tests.commit_git_changes(project, "add forbidden scanner policy")

            result = u.Tests.run_release_build(workspace, project_name)

            build_log = u.Tests.release_build_log_text(workspace, project_name)
            tm.that(result, eq=1)
            tm.that(build_log, has="sensitive staged source path: .gitleaks.toml")

        @staticmethod
        def test_codegen_owned_env_example_is_accepted(tmp_path: Path) -> None:
            """A file codegen owns is a projection, never a secret, whatever its name.

            Every generated repository carries `.env.example`; rejecting it by
            its `.env.` prefix blocked the build phase fleet-wide.
            """
            project_name = "flext-a"
            workspace = u.Tests.release_internal_workspace(tmp_path, project_name)
            project = workspace / project_name
            (project / ".env.example").write_text(
                "FLEXT_A_LOG_LEVEL=INFO\n", encoding="utf-8"
            )
            u.Tests.commit_git_changes(project, "add the generated environment example")

            _ = u.Tests.run_release_build(workspace, project_name)

            build_log = u.Tests.release_build_log_text(workspace, project_name)
            tm.that(build_log, lacks="sensitive staged source path")

    class TestsCommittedSource:
        """Immutable committed-source behavior."""

        @staticmethod
        def test_dirty_committed_member_is_rejected(tmp_path: Path) -> None:
            """Reject a project whose committed source has working-tree changes."""
            project_name = "flext-a"
            workspace = u.Tests.release_internal_workspace(tmp_path, project_name)
            package_file = workspace / project_name / "src" / "flext_a" / "__init__.py"
            package_file.write_text("# uncommitted release change\n", encoding="utf-8")

            result = u.Tests.run_release_build(workspace, project_name)

            build_log = u.Tests.release_build_log_text(workspace, project_name)
            tm.that(result, eq=1)
            tm.that(build_log, has="release project is dirty")
            tm.that(
                u.Tests.release_artifact_dir(
                    workspace, c.Tests.RELEASE_VERSION_BASE, project_name
                ).exists(),
                eq=False,
            )
