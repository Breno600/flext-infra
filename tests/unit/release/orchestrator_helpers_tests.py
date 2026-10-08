"""Public release utilities and artifact-boundary behavior tests.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra.gates.markdown_format import FlextInfraMarkdownFormatGate
from flext_infra.release import FlextInfraReleaseBuildMixin
from tests import c, m, p, u


class TestsFlextInfraReleaseHelpers:
    """Behavior contract for public release helpers and strict boundaries."""

    class TestsReleaseNotes:
        """Release-note behavior."""

        @staticmethod
        def test_generate_notes_writes_release_document(tmp_path: Path) -> None:
            """Generate notes containing projects and verification lines."""
            notes_path = tmp_path / "release" / c.Infra.RELEASE_NOTES_FILENAME
            project = u.Tests.create_project_info(tmp_path / "flext-a", name="flext-a")

            result = u.Infra.generate_notes(
                c.Tests.RELEASE_VERSION_TARGET,
                c.Tests.RELEASE_TAG_TARGET,
                [project],
                c.Tests.RELEASE_NOTES_CHANGE_LINE,
                notes_path,
            )

            notes = notes_path.read_text(encoding="utf-8")
            tm.ok(result)
            tm.that(notes, has=c.Tests.RELEASE_NOTES_HEADING)
            tm.that(notes, has="- root")
            tm.that(notes, has="- flext-a")
            tm.that(notes, has=c.Tests.RELEASE_NOTES_CHANGE_LINE)

        @staticmethod
        def test_generate_notes_is_formatter_stable(tmp_path: Path) -> None:
            """The canonical formatter leaves generated notes byte-identical."""
            notes_path = tmp_path / "release" / c.Infra.RELEASE_NOTES_FILENAME
            first_subject = (
                "fix(release): *.aihub-prior-* marker and a subject long enough to "
                "cross the print budget and wrap onto a continuation line"
            )
            second_subject = "feat(x): add [link](x) and `code` and _em_ and ~tilde~"
            changes = f"{first_subject}\n{second_subject}"

            first = u.Infra.generate_notes(
                c.Tests.RELEASE_VERSION_TARGET,
                c.Tests.RELEASE_TAG_TARGET,
                [],
                changes,
                notes_path,
            )
            second = u.Infra.generate_notes(
                c.Tests.RELEASE_VERSION_TARGET,
                c.Tests.RELEASE_TAG_TARGET,
                [],
                changes,
                notes_path,
            )
            tm.ok(first)
            tm.ok(second)
            config_dir = Path(__file__).resolve().parents[3]
            release_dir = notes_path.parent
            (release_dir / c.Infra.MARKDOWNLINT_CONFIG_FILENAME).write_text(
                (config_dir / c.Infra.MARKDOWNLINT_CONFIG_FILENAME).read_text(
                    encoding="utf-8",
                ),
                encoding="utf-8",
            )
            checked = u.Tests.run_gate_check(
                FlextInfraMarkdownFormatGate,
                tmp_path,
                release_dir,
            )
            tm.that(checked.result.passed, eq=True)
            tm.that(len(checked.issues), eq=0)

        @staticmethod
        def test_generate_notes_failure_returns_result_error(tmp_path: Path) -> None:
            """Return a typed failure when the note path is a directory."""
            notes_path = tmp_path / "release" / c.Infra.RELEASE_NOTES_FILENAME
            notes_path.mkdir(parents=True, exist_ok=True)
            result = u.Infra.generate_notes(
                c.Tests.RELEASE_VERSION_TARGET,
                c.Tests.RELEASE_TAG_TARGET,
                [],
                "",
                notes_path,
            )

            tm.fail(result)
            tm.that(result.error or "", has="failed to write release notes")

        @staticmethod
        def test_generate_notes_escapes_subject_markdown(tmp_path: Path) -> None:
            """Escape inline punctuation so an untrusted subject stays literal."""
            notes_path = tmp_path / "release" / c.Infra.RELEASE_NOTES_FILENAME

            result = u.Infra.generate_notes(
                c.Tests.RELEASE_VERSION_TARGET,
                c.Tests.RELEASE_TAG_TARGET,
                [],
                "- chore(deps): bump *.aihub-prior-* and _underscore_",
                notes_path,
            )

            notes = notes_path.read_text(encoding="utf-8")
            tm.ok(result)
            tm.that(notes, has=r"\*.aihub-prior-\*")
            tm.that(notes, has=r"\_underscore\_")

        @staticmethod
        def test_generate_notes_wraps_within_the_markdown_ceiling(
            tmp_path: Path,
        ) -> None:
            """Wrap an overlong subject so no line overruns the markdown ceiling."""
            notes_path = tmp_path / "release" / c.Infra.RELEASE_NOTES_FILENAME
            subject = "feat(x): " + " and ".join("segment" for _ in range(30))

            result = u.Infra.generate_notes(
                c.Tests.RELEASE_VERSION_TARGET,
                c.Tests.RELEASE_TAG_TARGET,
                [],
                f"- {subject}",
                notes_path,
            )

            notes = notes_path.read_text(encoding="utf-8")
            tm.ok(result)
            widest = max(len(line) for line in notes.splitlines())
            tm.that(widest <= c.Infra.RELEASE_NOTES_LINE_LENGTH, eq=True)

        @staticmethod
        def test_generate_notes_is_deterministic(tmp_path: Path) -> None:
            """Re-stamping an unchanged subject set produces byte-identical notes."""
            first = tmp_path / "first" / c.Infra.RELEASE_NOTES_FILENAME
            second = tmp_path / "second" / c.Infra.RELEASE_NOTES_FILENAME
            changes = "- fix: *.aihub-prior-* and a long trailing subject that wraps"

            first_result = u.Infra.generate_notes(
                c.Tests.RELEASE_VERSION_TARGET,
                c.Tests.RELEASE_TAG_TARGET,
                [],
                changes,
                first,
            )
            second_result = u.Infra.generate_notes(
                c.Tests.RELEASE_VERSION_TARGET,
                c.Tests.RELEASE_TAG_TARGET,
                [],
                changes,
                second,
            )

            tm.ok(first_result)
            tm.ok(second_result)
            tm.that(
                first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8"),
                eq=True,
            )

    class TestsChangelog:
        """Changelog behavior."""

        @staticmethod
        def write_notes(workspace: Path) -> Path:
            """Write the release-notes fixture the changelog updates consume.

            Returns:
                The resulting ``Path``.

            """
            notes_path = workspace / "notes.md"
            notes_path.parent.mkdir(parents=True, exist_ok=True)
            notes_path.write_text(
                c.Tests.RELEASE_NOTES_HEADING + "\n",
                encoding="utf-8",
            )
            return notes_path

        @staticmethod
        def update_changelog_at(workspace: Path, notes_path: Path) -> p.Result[bool]:
            """Run the public changelog update at the canonical release targets.

            Returns:
                The resulting ``p.Result[bool]``.

            """
            return u.Infra.update_changelog(
                workspace,
                c.Tests.RELEASE_VERSION_TARGET,
                c.Tests.RELEASE_TAG_TARGET,
                notes_path,
            )

        @staticmethod
        def update_changelog_from_seed(workspace: Path, changelog_text: str) -> str:
            """Seed one existing changelog, update it, and return the rewritten text.

            Returns:
                The resulting ``str``.

            """
            docs_dir = workspace / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "CHANGELOG.md").write_text(changelog_text, encoding="utf-8")
            notes_path = TestsFlextInfraReleaseHelpers.TestsChangelog.write_notes(
                workspace,
            )
            result = TestsFlextInfraReleaseHelpers.TestsChangelog.update_changelog_at(
                workspace,
                notes_path,
            )
            tm.ok(result)
            return (docs_dir / "CHANGELOG.md").read_text(encoding="utf-8")

        @staticmethod
        def test_update_changelog_creates_expected_files(tmp_path: Path) -> None:
            """Create changelog, latest and versioned release documents."""
            workspace = tmp_path / "workspace"
            notes_path = TestsFlextInfraReleaseHelpers.TestsChangelog.write_notes(
                workspace,
            )

            result = TestsFlextInfraReleaseHelpers.TestsChangelog.update_changelog_at(
                workspace,
                notes_path,
            )

            tm.ok(result)
            tm.that((workspace / "docs" / "CHANGELOG.md").is_file(), eq=True)
            # The markdown gate (MD012) rejects a trailing blank line, so a
            # first changelog ends with exactly one newline.
            changelog = (workspace / "docs" / "CHANGELOG.md").read_text(
                encoding="utf-8",
            )
            tm.that(changelog.endswith("\n"), eq=True)
            tm.that(changelog.endswith("\n\n"), eq=False)
            tm.that((workspace / "docs" / "releases" / "latest.md").is_file(), eq=True)
            tm.that(
                (
                    workspace / "docs" / "releases" / f"{c.Tests.RELEASE_TAG_TARGET}.md"
                ).is_file(),
                eq=True,
            )

        @staticmethod
        def test_update_changelog_is_idempotent(tmp_path: Path) -> None:
            """Keep one release heading across repeated public updates."""
            workspace = tmp_path / "workspace"
            notes_path = TestsFlextInfraReleaseHelpers.TestsChangelog.write_notes(
                workspace,
            )

            update = TestsFlextInfraReleaseHelpers.TestsChangelog.update_changelog_at
            first_result = update(workspace, notes_path)
            second_result = update(workspace, notes_path)

            changelog = (workspace / "docs" / "CHANGELOG.md").read_text(
                encoding="utf-8",
            )
            tm.ok(first_result)
            tm.ok(second_result)
            tm.that(changelog.count(f"## {c.Tests.RELEASE_VERSION_TARGET} - "), eq=1)

        @staticmethod
        def test_update_changelog_normalizes_an_existing_trailing_blank_line(
            tmp_path: Path,
        ) -> None:
            """A rerun repairs a changelog written before the newline normalization.

            The release lane keeps the changelog a previous stamp wrote; the
            markdown gate (MD012) rejects its trailing blank line, so the rerun
            must rewrite it even though the release section already exists.
            """
            workspace = tmp_path / "workspace"
            changelog = (
                TestsFlextInfraReleaseHelpers.TestsChangelog.update_changelog_from_seed(
                    workspace,
                    f"# Changelog\n\n## {c.Tests.RELEASE_VERSION_TARGET} - "
                    f"2026-01-01\n\n"
                    f"- Release tag: `{c.Tests.RELEASE_TAG_TARGET}`\n\n"
                    f"Full notes: `docs/releases/{c.Tests.RELEASE_TAG_TARGET}.md`"
                    "\n\n\n",
                )
            )
            tm.that(changelog.count(f"## {c.Tests.RELEASE_VERSION_TARGET} - "), eq=1)
            tm.that(changelog.endswith("\n"), eq=True)
            tm.that(changelog.endswith("\n\n"), eq=False)

        @staticmethod
        def test_update_changelog_adds_default_header(tmp_path: Path) -> None:
            """Add the canonical header when an existing file lacks it."""
            workspace = tmp_path / "workspace"
            changelog = (
                TestsFlextInfraReleaseHelpers.TestsChangelog.update_changelog_from_seed(
                    workspace,
                    "Existing notes only\n",
                )
            )
            tm.that(changelog, starts=c.Tests.RELEASE_CHANGELOG_HEADER)

        @staticmethod
        def test_update_changelog_missing_notes_returns_failure(tmp_path: Path) -> None:
            """Return a typed failure when source release notes are absent."""
            workspace = tmp_path / "workspace"

            result = u.Infra.update_changelog(
                workspace,
                c.Tests.RELEASE_VERSION_TARGET,
                c.Tests.RELEASE_TAG_TARGET,
                workspace / "missing-notes.md",
            )

            tm.fail(result)
            tm.that(result.error or "", has="changelog update failed")

    class TestsBuildArtifacts:
        """Successful artifact behavior."""

        @staticmethod
        def test_duplicate_project_selectors_build_once(tmp_path: Path) -> None:
            """Build each selected project once with strict modeled artifacts."""
            project_name = "flext-a"
            workspace = u.Tests.release_internal_workspace(tmp_path, project_name)

            result = u.Tests.run_release_main(
                workspace,
                "--phase",
                c.Tests.RELEASE_PHASE_BUILD,
                "--projects",
                project_name,
                "--projects",
                project_name,
                "--apply",
            )

            report = u.Tests.release_build_report(workspace)
            tm.that(result, eq=0)
            tm.that(report.total, eq=1)
            tm.that([record.project for record in report.records], eq=[project_name])
            record = report.records[0]
            tm.that(
                sorted(artifact.kind for artifact in record.artifacts),
                eq=["sdist", "wheel"],
            )
            for artifact in record.artifacts:
                artifact_path = Path(artifact.path)
                tm.that(artifact_path.is_file(), eq=True)
                tm.that(len(artifact.sha256), eq=64)
                tm.that(
                    hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                    eq=artifact.sha256,
                )
            staged_metadata = (
                u.Tests.release_report_dir(workspace, c.Tests.RELEASE_VERSION_BASE)
                / "metadata"
                / f"{project_name}-pyproject.toml"
            ).read_text(encoding="utf-8")
            # Siblings are pinned to the compatible range of the version their
            # own pyproject declares, never to this project's release version.
            tm.that(staged_metadata, has=f"flext-core~={c.Tests.RELEASE_VERSION_BASE}")
            tm.that(staged_metadata, has=f"flext-tests~={c.Tests.RELEASE_VERSION_BASE}")
            tm.that(staged_metadata, lacks="git+")
            tm.that(staged_metadata, lacks="[tool.uv")

    class TestsStrictModels:
        """Release report model boundary behavior."""

        @staticmethod
        def test_artifact_rejects_relative_path() -> None:
            """Reject a relative artifact path at the public model boundary."""
            with pytest.raises(c.ValidationError) as exc_info:
                m.Infra.BuildArtifact(
                    path="dist/flext_a-1.0.0-py3-none-any.whl",
                    kind="wheel",
                    sha256="a" * 64,
                )
            tm.that(exc_info.value.errors()[0]["type"], eq="string_pattern_mismatch")
            tm.that(exc_info.value.errors()[0]["loc"], eq=("path",))

        @staticmethod
        def test_build_record_accepts_negative_exit_and_rejects_string(
            tmp_path: Path,
        ) -> None:
            """Retain signal exits as strict integers without coercing strings."""
            record = m.Infra.BuildRecord(
                project="flext-a",
                path=str(tmp_path.resolve()),
                exit_code=-9,
                log=str((tmp_path / "build.log").resolve()),
                artifacts=(),
            )

            tm.that(record.exit_code, eq=-9)
            with pytest.raises(c.ValidationError):
                m.Infra.BuildRecord.model_validate({
                    "project": "flext-a",
                    "path": str(tmp_path.resolve()),
                    "exit_code": "-9",
                    "log": str((tmp_path / "build.log").resolve()),
                })

    class TestsArtifactPersistence:
        """Atomic immutable artifact-set behavior."""

        # Why (flext-oftik class): builds a real artifact twice (uv build); the
        # SSOT slow budget (flext_slow_timeout_seconds) owns its ceiling.
        @pytest.mark.slow
        @staticmethod
        def test_collision_preserves_complete_existing_set(tmp_path: Path) -> None:
            """Fail on immutable collision without partial or temporary output."""
            project_name = "flext-a"
            workspace = u.Tests.release_internal_workspace(tmp_path, project_name)
            artifact_dir = u.Tests.release_artifact_dir(
                workspace,
                c.Tests.RELEASE_VERSION_BASE,
                project_name,
            )
            first_result = u.Tests.run_release_build(workspace, project_name)
            original_artifacts = {
                path.name: path.read_bytes() for path in artifact_dir.iterdir()
            }
            collided_artifact = min(artifact_dir.iterdir())
            collision_bytes = b"immutable collision\n"
            collided_artifact.write_bytes(collision_bytes)
            expected_artifacts = original_artifacts | {
                collided_artifact.name: collision_bytes,
            }

            second_result = u.Tests.run_release_build(workspace, project_name)

            current_artifacts = {
                path.name: path.read_bytes() for path in artifact_dir.iterdir()
            }
            build_log = u.Tests.release_build_log_text(workspace, project_name)
            tm.that(first_result, eq=0)
            tm.that(second_result, eq=1)
            tm.that(current_artifacts, eq=expected_artifacts)
            tm.that(build_log, has="immutable artifact collision")

        @staticmethod
        def test_unexpected_uv_output_is_rejected_without_artifacts(
            tmp_path: Path,
        ) -> None:
            """Reject a real Hatch build that emits a third output entry."""
            project_name = "flext-a"
            workspace = u.Tests.release_internal_workspace(tmp_path, project_name)
            project = workspace / project_name
            pyproject = project / "pyproject.toml"
            wheel_target = "[tool.hatch.build.targets.sdist]"
            pyproject.write_text(
                pyproject.read_text(encoding="utf-8").replace(
                    wheel_target,
                    "[tool.hatch.build.hooks.custom]\n"
                    'path = "src/flext_a/build_hook.py"\n\n'
                    f"{wheel_target}",
                ),
                encoding="utf-8",
            )
            (project / "src" / "flext_a" / "build_hook.py").write_text(
                "from pathlib import Path\n"
                "from hatchling.builders.hooks.plugin.interface import "
                "BuildHookInterface\n\n"
                "class CustomBuildHook(BuildHookInterface):\n"
                '    PLUGIN_NAME = "custom"\n\n'
                "    def finalize(self, version, build_data, artifact_path):\n"
                "        Path(self.directory, 'unexpected.txt').write_text("
                "'unexpected\\n', encoding='utf-8')\n",
                encoding="utf-8",
            )
            u.Tests.commit_git_changes(project, "emit unexpected build output")

            result = u.Tests.run_release_build(workspace, project_name)

            build_log = u.Tests.release_build_log_text(workspace, project_name)
            tm.that(result, eq=1)
            tm.that(build_log, has="uv build emitted unexpected output")
            tm.that(build_log, has="unexpected.txt")
            tm.that(
                u.Tests.release_artifact_dir(
                    workspace,
                    c.Tests.RELEASE_VERSION_BASE,
                    project_name,
                ).exists(),
                eq=False,
            )

    class TestsInternalLockedVersions:
        """The internal-versions map reads git dependencies from the root lock."""

        @staticmethod
        def write_lock(workspace: Path, body: str) -> Path:
            """Write one uv.lock body into the workspace root.

            Returns:
                The resulting ``Path``.

            """
            lock = workspace / c.Infra.UV_LOCK_FILENAME
            lock.write_text(body, encoding="utf-8")
            return lock

        @staticmethod
        def test_reads_internal_git_versions_and_skips_the_rest(tmp_path: Path) -> None:
            """Internal git entries seed the map; other names and sources do not."""
            lock_body = """
[[package]]
name = "flext-api"
version = "0.12.0"
source = { git = "https://example/flext-api.git?rev=0.12.0-dev#df73a089" }

[[package]]
name = "flext-core"
version = "0.12.0"
source = { editable = "vendor/flext-core" }

[[package]]
name = "pyyaml"
version = "6.0.0"
source = { registry = "https://pypi.org/simple" }
"""
            TestsFlextInfraReleaseHelpers.TestsInternalLockedVersions.write_lock(
                tmp_path,
                lock_body,
            )

            result = FlextInfraReleaseBuildMixin.internal_locked_versions(tmp_path)

            tm.ok(result)
            tm.that(result.value, eq={"flext-api": "0.12.0"})

        @staticmethod
        def test_missing_lock_yields_an_empty_map(tmp_path: Path) -> None:
            """No lock means no git entries to seed; the render stays the authority."""
            result = FlextInfraReleaseBuildMixin.internal_locked_versions(tmp_path)

            tm.ok(result)
            tm.that(result.value, eq={})

        @staticmethod
        def test_invalid_lock_fails_loud(tmp_path: Path) -> None:
            """A corrupt lock is a typed failure, never a silently empty map."""
            TestsFlextInfraReleaseHelpers.TestsInternalLockedVersions.write_lock(
                tmp_path,
                "not [ valid toml",
            )

            result = FlextInfraReleaseBuildMixin.internal_locked_versions(tmp_path)

            tm.fail(result)
            tm.that(result.error or "", has="invalid TOML")
