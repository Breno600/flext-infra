"""Public release receipt validation using real builds and artifact bytes."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import TestsFlextInfraUtilities as u, c, m, t


class TestsFlextInfraReleasePublish:
    """Behavior contract for the public release publish phase."""

    def _built_workspace(self, tmp_path: Path) -> t.Pair[Path, m.Infra.BuildReport]:
        """Build one member and return the workspace with its verified receipt."""
        project_name = "flext-a"
        workspace = u.Tests.create_release_workspace(
            tmp_path,
            project_names=(project_name, *c.Tests.RELEASE_INTERNAL_DEPENDENCIES),
            initialize_project_git=True,
        )
        notes = workspace / "docs" / "releases"
        notes.mkdir(parents=True)
        (notes / "v0.1.0.md").write_text("# Release v0.1.0\n", encoding="utf-8")
        tm.that(
            u.Tests.run_release_main(
                workspace, "--phase", "build", "--projects", project_name, "--apply"
            ),
            eq=0,
        )
        report_path = (
            u.Tests.release_report_dir(workspace, c.Tests.RELEASE_VERSION_BASE)
            / c.Infra.RELEASE_REPORT_FILENAME
        )
        return workspace, m.Infra.BuildReport.model_validate_json(
            report_path.read_text(encoding="utf-8")
        )

    def test_dry_run_verifies_the_receipt_without_effects(self, tmp_path: Path) -> None:
        """Receipt validation preserves the artifacts produced by a real build."""
        workspace, report = self._built_workspace(tmp_path)
        artifacts = {
            Path(artifact.path): Path(artifact.path).read_bytes()
            for record in report.records
            for artifact in record.artifacts
        }

        tm.that(u.Tests.run_release_main(workspace, "--phase", "publish"), eq=0)
        for path, content in artifacts.items():
            tm.that(path.read_bytes(), eq=content)

    def test_tampered_artifact_is_refused(self, tmp_path: Path) -> None:
        """An artifact whose bytes no longer match the receipt never leaves."""
        workspace, report = self._built_workspace(tmp_path)
        artifact = Path(report.records[0].artifacts[0].path)
        artifact.write_bytes(artifact.read_bytes() + b"\n")

        tm.that(
            u.Tests.run_release_main(workspace, "--phase", "publish", "--apply"), ne=0
        )

    def test_missing_receipt_is_refused(self, tmp_path: Path) -> None:
        """Publishing without a build receipt has nothing attested to upload."""
        workspace = u.Tests.create_release_workspace(tmp_path)

        tm.that(
            u.Tests.run_release_main(workspace, "--phase", "publish", "--apply"), ne=0
        )
