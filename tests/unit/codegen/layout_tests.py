"""Tests for the declarative project-layout engine (flext-0wuz, epic flext-hzox)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import FlextInfraConfig, c, m
from flext_infra.gates.layout import FlextInfraLayoutGate
from tests import u
from tests.unit.codegen.layout_fixture import (
    archive_root,
    build_loose_project,
    layout_engine,
)


class TestsFlextInfraCodegenLayout:
    """Test suite for the declarative project-layout engine."""

    @staticmethod
    def _fresh_layout_report(project: Path) -> m.Infra.LayoutProjectReport:
        """Load consumer-owned configuration in a new public-service process."""
        process = tm.ok(
            u.Cli.run_raw(
                [
                    sys.executable,
                    "-c",
                    (
                        "from pathlib import Path\n"
                        "from flext_infra import FlextInfraCodegenLayout\n"
                        "root = Path.cwd()\n"
                        "report = FlextInfraCodegenLayout(repository_root=root)"
                        ".check_project(root)\n"
                        "print(report.model_dump_json(exclude_computed_fields=True))\n"
                    ),
                ],
                cwd=project,
                env={"FLEXT_INFRA_CONFIG_DIR": str(FlextInfraConfig.ssot_config_dir())},
            )
        )
        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )
        return m.Infra.LayoutProjectReport.model_validate_json(process.stdout)

    @classmethod
    def _assert_keep_override(
        cls, tmp_path: Path, *, distribution: str, checkout_name: str, keep_count: int
    ) -> None:
        """Prove declared files change classification without changing defaults."""
        project = build_loose_project(tmp_path, name=distribution)
        if project.name != checkout_name:
            project = project.rename(tmp_path / checkout_name)
        candidates = tuple(f"consumer-note-{index}.fixture" for index in range(3))
        for filename in candidates:
            (project / filename).write_text(f"{filename}\n", encoding="utf-8")
        baseline = cls._fresh_layout_report(project)
        baseline_paths = {finding.path for finding in baseline.findings}
        tm.that(set(candidates) <= baseline_paths, eq=True)
        override = m.Infra.LayoutProjectOverrideSpec(
            keep_root_files=candidates[:keep_count]
        )
        declaration = m.Infra.CodegenOverridesSpec.model_validate({
            "Infra": {
                "codegen": {
                    "layout": {
                        "project_overrides": {
                            distribution: override.model_dump(mode="json")
                        }
                    }
                }
            }
        })
        org_overlay = (
            project
            / c.Infra.CODEGEN_CONFIG_DIR
            / c.Infra.CODEGEN_ORG_OVERRIDES_FILENAME
        )
        tm.that(org_overlay.is_relative_to(tmp_path), eq=True)
        org_overlay.parent.mkdir(exist_ok=True)
        tm.ok(
            u.Cli.yaml_dump(
                org_overlay, declaration.model_dump(mode="json", exclude_none=True)
            )
        )

        report = cls._fresh_layout_report(project)

        tm.that(report.project, eq=distribution)
        paths = {finding.path for finding in report.findings}
        tm.that(
            paths & set(candidates), eq=set(candidates) - set(override.keep_root_files)
        )
        for filename in candidates:
            tm.that(
                (project / filename).read_text(encoding="utf-8"), eq=f"{filename}\n"
            )

    def test_check_reports_move_archive_review_and_gitignore(
        self, tmp_path: Path
    ) -> None:
        """Check mode classifies every loose root entry without writing."""
        project = build_loose_project(tmp_path)
        engine = layout_engine(tmp_path)

        report = engine.check_project(project)

        by_path = {finding.path: finding for finding in report.findings}
        tm.that(by_path["guides"].rule, eq="move")
        tm.that(by_path["guides"].target, eq="docs/guides")
        tm.that(by_path["index.md"].rule, eq="move")
        tm.that(by_path["output.log"].rule, eq="archive")
        tm.that(
            by_path["output.log"].target,
            eq=f"{archive_root()}/{project.name}/output.log",
        )
        tm.that(by_path["loose.txt"].rule, eq="review")
        gitignore = [
            finding for finding in report.findings if finding.rule == "gitignore"
        ]
        tm.that(bool(gitignore), eq=True)
        tm.that(gitignore[0].target, eq=f"{archive_root()}/")

    def test_check_execute_passes_while_severity_is_warning(
        self, tmp_path: Path
    ) -> None:
        """CLI check posture is report-only while the SSOT severity is warning."""
        build_loose_project(tmp_path)
        engine = layout_engine(tmp_path)

        result = engine.execute()

        tm.ok(result)
        tm.that(result.value, has="move guides -> docs/guides")

    def test_apply_moves_archives_and_converges_idempotently(
        self, tmp_path: Path
    ) -> None:
        """Apply reorganizes once; a second apply performs zero operations."""
        project = build_loose_project(tmp_path)
        engine = layout_engine(tmp_path, apply_changes=True)

        first = engine.execute()

        tm.ok(first)
        tm.that((project / "docs" / "guides" / "intro.md").is_file(), eq=True)
        tm.that((project / "docs" / "index.md").is_file(), eq=True)
        archived = project / archive_root() / project.name / "output.log"
        tm.that(archived.is_file(), eq=True)
        tm.that(archived.read_text(encoding="utf-8"), eq="log-line\n")
        tm.that((project / "guides").exists(), eq=False)
        tm.that((project / "output.log").exists(), eq=False)
        tm.that((project / "loose.txt").is_file(), eq=True)
        second = engine.execute()
        tm.ok(second)
        tm.that(second.value, has="0 applied")
        residual = engine.check_project(project)
        tm.that(len(residual.actionable), eq=0)
        tm.that([finding.rule for finding in residual.findings], eq=["review"])

    def test_apply_docs_collision_keeps_target_and_archives_source(
        self, tmp_path: Path
    ) -> None:
        """Different-content collisions preserve both sides (archive-not-delete)."""
        project = build_loose_project(tmp_path)
        existing = project / "docs" / "guides"
        existing.mkdir(parents=True)
        (existing / "intro.md").write_text("canonical\n", encoding="utf-8")
        engine = layout_engine(tmp_path, apply_changes=True)

        result = engine.execute()

        tm.ok(result)
        tm.that((existing / "intro.md").read_text(encoding="utf-8"), eq="canonical\n")
        archived = project / archive_root() / project.name / "guides" / "intro.md"
        tm.that(archived.is_file(), eq=True)
        tm.that(archived.read_text(encoding="utf-8"), eq="intro\n")
        tm.that((project / "guides").exists(), eq=False)

    def test_apply_override_move_then_archives_emptied_dir(
        self, tmp_path: Path
    ) -> None:
        """Override moves run before the emptied directory is archived."""
        project = tmp_path / "flext-dbt-ldif"
        profiles = project / "profiles"
        package_dir = project / "src" / "flext_dbt_ldif"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        profiles.mkdir(parents=True)
        (project / "pyproject.toml").write_text(
            "[project]\nname='flext-dbt-ldif'\nversion='0.1.0'\n", encoding="utf-8"
        )
        (profiles / "profiles.yml").write_text("profile: 1\n", encoding="utf-8")
        u.Tests.declare_workspace_projects(tmp_path, (project.name,))
        engine = layout_engine(tmp_path, apply_changes=True)

        result = engine.execute()

        tm.ok(result)
        tm.that((project / "profiles.yml").is_file(), eq=True)
        tm.that((project / "profiles").exists(), eq=False)
        tm.that(
            (project / archive_root() / project.name / "profiles").is_dir(), eq=True
        )

    def test_gate_reports_violations_and_fails_on_warning(self, tmp_path: Path) -> None:
        """The shared gate contract rejects warnings without hiding their severity."""
        project = build_loose_project(tmp_path)
        gate = FlextInfraLayoutGate(tmp_path)
        ctx = m.Infra.GateContext(
            repository_root=tmp_path, reports_dir=tmp_path / ".reports"
        )

        execution = gate.check(project, ctx)

        tm.that(execution.result.passed, eq=False)
        tm.that(bool(execution.issues), eq=True)
        tm.that(all(issue.severity == "WARNING" for issue in execution.issues), eq=True)

    @pytest.mark.parametrize("keep_count", [0, 1, 3])
    def test_keep_root_files_override(self, tmp_path: Path, keep_count: int) -> None:
        """Arbitrary consumer keep-lists preserve only their declared root files."""
        self._assert_keep_override(
            tmp_path,
            distribution="fixture-layout-consumer",
            checkout_name="fixture-layout-consumer",
            keep_count=keep_count,
        )

    @pytest.mark.parametrize("keep_count", [0, 1, 3])
    def test_override_resolves_by_declared_name_not_checkout_directory(
        self, tmp_path: Path, keep_count: int
    ) -> None:
        """Renamed checkouts still consume the PEP 621 distribution's keep-list."""
        self._assert_keep_override(
            tmp_path,
            distribution="fixture-declared-layout",
            checkout_name="independent-checkout-name",
            keep_count=keep_count,
        )

    def test_special_and_reference_root_dirs_skipped(self, tmp_path: Path) -> None:
        """data/ is skipped; external-docs/ is allowed as reference corpus."""
        project = build_loose_project(tmp_path)
        (project / "data").mkdir()
        (project / "data" / "proposal").mkdir()
        (project / "external-docs").mkdir()
        (project / "external-docs" / "note.md").write_text("ext\n", encoding="utf-8")
        engine = layout_engine(tmp_path)

        report = engine.check_project(project)

        paths = {finding.path for finding in report.findings}
        tm.that("data" in paths, eq=False)
        tm.that("external-docs" in paths, eq=False)

    def test_declared_repositories_are_canonical_root_entries(
        self, tmp_path: Path
    ) -> None:
        """A workspace root accepts only repository directories declared by topology."""
        declared_name = "flext-declared"
        undeclared_name = "flext-undeclared"
        (tmp_path / declared_name).mkdir()
        (tmp_path / undeclared_name).mkdir()
        # Why: an empty directory carries no git-trackable content — git status
        # never reports it, so the layout engine's git-tracked-entries scope (the
        # current contract) would silently skip it rather than flag it. A real
        # file makes the untracked directory visible to `git status`, matching
        # how an actual undeclared repository shows up on disk.
        (tmp_path / undeclared_name / "marker.txt").write_text("x", encoding="utf-8")
        u.Tests.declare_workspace_projects(tmp_path, (declared_name,))
        engine = layout_engine(tmp_path)

        report = engine.check_project(tmp_path)

        findings = {finding.path: finding for finding in report.findings}
        tm.that(declared_name in findings, eq=False)
        tm.that(findings[undeclared_name].rule, eq="review")

    def test_duplicate_root_md_archives_when_docs_copy_exists(
        self, tmp_path: Path
    ) -> None:
        """Root move_docs_files collide with docs/ -> archive root, keep docs."""
        project = build_loose_project(tmp_path)
        docs = project / "docs"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "index.md").write_text("canonical-index\n", encoding="utf-8")
        engine = layout_engine(tmp_path, apply_changes=True)

        result = engine.execute()

        tm.ok(result)
        tm.that((docs / "index.md").read_text(encoding="utf-8"), eq="canonical-index\n")
        archived = project / archive_root() / project.name / "index.md"
        tm.that(archived.is_file(), eq=True)
        tm.that(archived.read_text(encoding="utf-8"), eq="index\n")
        tm.that((project / "index.md").exists(), eq=False)
