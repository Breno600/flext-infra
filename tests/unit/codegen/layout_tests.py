"""Tests for the declarative project-layout engine (mro-0wuz, epic mro-hzox)."""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, config, m
from flext_infra.codegen.conform import FlextInfraCodegenConform
from flext_infra.codegen.layout import FlextInfraCodegenLayout
from flext_infra.gates.layout import FlextInfraLayoutGate
from flext_tests import tm
from tests import t, u


def _build_loose_project(tmp_path: Path, name: str = "flext-demo") -> Path:
    """Create a minimal project carrying one violation of each layout kind."""
    project = tmp_path / name
    package_dir = project / "src" / name.replace("-", "_")
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        "[project]\nname='flext-demo'\nversion='0.1.0'\n", encoding="utf-8"
    )
    (project / "README.md").write_text("# demo\n", encoding="utf-8")
    guides = project / "guides"
    guides.mkdir()
    (guides / "intro.md").write_text("intro\n", encoding="utf-8")
    (project / "index.md").write_text("index\n", encoding="utf-8")
    (project / "output.log").write_text("log-line\n", encoding="utf-8")
    (project / "loose.txt").write_text("unknown\n", encoding="utf-8")
    return project


def _engine(
    workspace_root: Path, *, apply_changes: bool = False
) -> FlextInfraCodegenLayout:
    """Build the layout service over one fixture workspace root."""
    return FlextInfraCodegenLayout(
        workspace_root=workspace_root, apply_changes=apply_changes
    )


def test_check_reports_move_archive_review_and_gitignore(tmp_path: Path) -> None:
    """Check mode classifies every loose root entry without writing."""
    project = _build_loose_project(tmp_path)
    engine = _engine(tmp_path)

    report = engine.check_project(project)

    by_path = {finding.path: finding for finding in report.findings}
    tm.that(by_path["guides"].rule, eq="move")
    tm.that(by_path["guides"].target, eq="docs/guides")
    tm.that(by_path["index.md"].rule, eq="move")
    tm.that(by_path["output.log"].rule, eq="archive")
    tm.that(
        by_path["output.log"].target, eq=f"{_archive_root()}/{project.name}/output.log"
    )
    tm.that(by_path["loose.txt"].rule, eq="review")
    gitignore = [finding for finding in report.findings if finding.rule == "gitignore"]
    tm.that(bool(gitignore), eq=True)
    tm.that(gitignore[0].target, eq=f"{_archive_root()}/")


def test_check_execute_passes_while_severity_is_warning(tmp_path: Path) -> None:
    """CLI check posture is report-only while the SSOT severity is warning."""
    _build_loose_project(tmp_path)
    engine = _engine(tmp_path)

    result = engine.execute()

    tm.ok(result)
    tm.that(result.value, has="move guides -> docs/guides")


def test_apply_moves_archives_and_converges_idempotently(tmp_path: Path) -> None:
    """Apply reorganizes once; a second apply performs zero operations."""
    project = _build_loose_project(tmp_path)
    engine = _engine(tmp_path, apply_changes=True)

    first = engine.execute()

    tm.ok(first)
    tm.that((project / "docs" / "guides" / "intro.md").is_file(), eq=True)
    tm.that((project / "docs" / "index.md").is_file(), eq=True)
    archived = project / _archive_root() / project.name / "output.log"
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


def test_apply_adds_gitignore_entries_exactly_once(tmp_path: Path) -> None:
    """Gitignore additions from the SSOT are appended once across applies."""
    project = _build_loose_project(tmp_path, name="flext-cli")
    (project / "settings.json").write_text("{}\n", encoding="utf-8")
    engine = _engine(tmp_path, apply_changes=True)

    first = engine.execute()
    tm.ok(first)
    second = engine.execute()
    tm.ok(second)

    gitignore = (project / c.Infra.GITIGNORE).read_text(encoding="utf-8")
    # Why: count exact ENTRIES, never substrings. The SSOT also carries
    # negations such as !.vscode/settings.json, so a substring count reports
    # two occurrences for a file that was appended exactly once.
    entries = gitignore.splitlines()
    tm.that(entries.count("settings.json"), eq=1)
    tm.that(entries.count(f"{_archive_root()}/"), eq=1)
    tm.that(
        (project / _archive_root() / project.name / "settings.json").is_file(), eq=True
    )


def test_apply_uses_git_mv_for_tracked_files(tmp_path: Path) -> None:
    """Tracked sources move through git so history follows the rename."""
    project = _build_loose_project(tmp_path)
    u.Tests.initialize_git_repo(project)
    engine = _engine(tmp_path, apply_changes=True)

    result = engine.execute()

    tm.ok(result)
    tracked = u.Cli.capture([c.Infra.GIT, "ls-files"], cwd=project)
    tm.ok(tracked)
    tracked_names = set(tracked.value.split())
    tm.that("docs/guides/intro.md" in tracked_names, eq=True)
    tm.that("guides/intro.md" in tracked_names, eq=False)
    tm.that(f"{_archive_root()}/{project.name}/output.log" in tracked_names, eq=False)


def test_apply_docs_collision_keeps_target_and_archives_source(tmp_path: Path) -> None:
    """Different-content collisions preserve both sides (archive-not-delete)."""
    project = _build_loose_project(tmp_path)
    existing = project / "docs" / "guides"
    existing.mkdir(parents=True)
    (existing / "intro.md").write_text("canonical\n", encoding="utf-8")
    engine = _engine(tmp_path, apply_changes=True)

    result = engine.execute()

    tm.ok(result)
    tm.that((existing / "intro.md").read_text(encoding="utf-8"), eq="canonical\n")
    archived = project / _archive_root() / project.name / "guides" / "intro.md"
    tm.that(archived.is_file(), eq=True)
    tm.that(archived.read_text(encoding="utf-8"), eq="intro\n")
    tm.that((project / "guides").exists(), eq=False)


def test_apply_override_move_then_archives_emptied_dir(tmp_path: Path) -> None:
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
    engine = _engine(tmp_path, apply_changes=True)

    result = engine.execute()

    tm.ok(result)
    tm.that((project / "profiles.yml").is_file(), eq=True)
    tm.that((project / "profiles").exists(), eq=False)
    tm.that((project / _archive_root() / project.name / "profiles").is_dir(), eq=True)


def test_gate_reports_violations_but_passes_on_warning(tmp_path: Path) -> None:
    """Gate posture follows the SSOT severity: warning reports, never fails."""
    project = _build_loose_project(tmp_path)
    gate = FlextInfraLayoutGate(tmp_path)
    ctx = m.Infra.GateContext(workspace=tmp_path, reports_dir=tmp_path / ".reports")

    execution = gate.check(project, ctx)

    tm.that(execution.result.passed, eq=True)
    tm.that(bool(execution.issues), eq=True)
    tm.that(all(issue.severity == "WARNING" for issue in execution.issues), eq=True)


def test_managed_gitignore_render_includes_layout_additions() -> None:
    """The canonical gitignore render owns the layout SSOT additions."""
    rendered = FlextInfraCodegenConform.render_project_gitignore(
        config.Infra.codegen,
        profile=c.Infra.MakeProfile.STANDALONE,
        project_name="flext-cli",
    )

    tm.ok(rendered)
    tm.that(rendered.value, has="settings.json")
    tm.that(rendered.value, has=f"{_archive_root()}/")


def _archive_root() -> str:
    """Archive root from the same typed SSOT the engine consumes."""
    return config.Infra.codegen.layout.archive_root


__all__: t.StrSequence = []


def test_keep_root_files_override(tmp_path: Path) -> None:
    """Declared keep_root_files stay at root without review findings."""
    project = tmp_path / "ai-hub"
    package_dir = project / "src" / "ai_hub"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        "[project]\nname='ai-hub'\nversion='0.1.0'\n", encoding="utf-8"
    )
    (project / "README.md").write_text("# ai-hub\n", encoding="utf-8")
    (project / "UNIVERSAL_CORE.md").write_text("core\n", encoding="utf-8")
    (project / "ECOSYSTEM.md").write_text("eco\n", encoding="utf-8")
    engine = _engine(tmp_path)

    report = engine.check_project(project)

    paths = {finding.path for finding in report.findings}
    tm.that("UNIVERSAL_CORE.md" in paths, eq=False)
    tm.that("ECOSYSTEM.md" in paths, eq=False)


def test_special_and_reference_root_dirs_skipped(tmp_path: Path) -> None:
    """data/ is skipped; external-docs/ is allowed as reference corpus."""
    project = _build_loose_project(tmp_path)
    (project / "data").mkdir()
    (project / "data" / "proposal").mkdir()
    (project / "external-docs").mkdir()
    (project / "external-docs" / "note.md").write_text("ext\n", encoding="utf-8")
    engine = _engine(tmp_path)

    report = engine.check_project(project)

    paths = {finding.path for finding in report.findings}
    tm.that("data" in paths, eq=False)
    tm.that("external-docs" in paths, eq=False)


def test_duplicate_root_md_archives_when_docs_copy_exists(tmp_path: Path) -> None:
    """Root move_docs_files collide with docs/ -> archive root, keep docs."""
    project = _build_loose_project(tmp_path)
    docs = project / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "index.md").write_text("canonical-index\n", encoding="utf-8")
    engine = _engine(tmp_path, apply_changes=True)

    result = engine.execute()

    tm.ok(result)
    tm.that((docs / "index.md").read_text(encoding="utf-8"), eq="canonical-index\n")
    archived = project / _archive_root() / project.name / "index.md"
    tm.that(archived.is_file(), eq=True)
    tm.that(archived.read_text(encoding="utf-8"), eq="index\n")
    tm.that((project / "index.md").exists(), eq=False)
