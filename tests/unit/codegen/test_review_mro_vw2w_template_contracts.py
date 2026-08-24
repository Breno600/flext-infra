"""Template contracts for Bugbot/Security review fixes (mro-vw2w)."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

_TEMPLATES = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "flext_infra"
    / "templates"
    / "project"
    / "base"
)
_MAKEFILE = _TEMPLATES / "Makefile.j2"
_RELEASE = _TEMPLATES / ".github" / "workflows" / "release.yml.j2"
_CI = _TEMPLATES / ".github" / "workflows" / "ci.yml.j2"
_DOCS = _TEMPLATES / ".github" / "workflows" / "docs.yml.j2"


class TestsReviewTemplateContracts:
    """Lock the SSOT fixes for bootstrap pin, PROJECT selection, TestPyPI order."""

    def test_makefile_bootstrap_prefers_gitlink_oid(self) -> None:
        text = _MAKEFILE.read_text(encoding="utf-8")
        tm.that(text, has="FLEXT_INFRA_BOOTSTRAP_REF")
        tm.that(text, has='rev-parse "HEAD:{{ infra_repository.path }}"')
        tm.that(text, has="@$(FLEXT_INFRA_BOOTSTRAP_REF)")
        tm.that(text, lacks="@{{ infra_repository_branch }}")

    def test_makefile_deps_modernize_uses_selected_projects(self) -> None:
        text = _MAKEFILE.read_text(encoding="utf-8")
        tm.that(text, has='selected="$(strip $(SELECTED_PROJECTS))"')
        upgrade = text.split("_builtin_deps_upgrade:", 1)[1].split(
            "_builtin_build_artifacts:", 1
        )[0]
        tm.that(upgrade, lacks='selected="$(strip $(PROJECTS))"')
        tm.that(upgrade, has="$(if $(strip $(DEPENDENCY)),,--rewrite-constraints)")

    def test_makefile_defines_attached_member_for_status(self) -> None:
        text = _MAKEFILE.read_text(encoding="utf-8")
        tm.that(
            text,
            has=(
                "ATTACHED_MEMBER := $(if $(filter workspace-member,"
                "$(MAKE_PROFILE)),$(PROJECT_ROOT),)"
            ),
        )

    def test_release_verifies_core_gitlink_after_setup(self) -> None:
        text = _RELEASE.read_text(encoding="utf-8")
        job = text.split("testpypi:", 1)[1]
        boot = job.index("Boot workspace")
        verify = job.index("Verify immutable flext-core gitlink")
        root_verify = job.index("Verify immutable canary root")
        tm.that(root_verify < boot, eq=True)
        tm.that(boot < verify, eq=True)
        pre = job[:boot]
        tm.that(pre, lacks="git -C flext-core rev-parse HEAD")

    def test_ci_upload_excludes_raw_report_logs(self) -> None:
        text = _CI.read_text(encoding="utf-8")
        upload = text.split("Upload reports on failure", 1)[1].split(
            "# End SECTION: ci job", 1
        )[0]
        tm.that(upload, has=".reports/**/junit.xml")
        tm.that(upload, has=".reports/**/coverage.xml")
        tm.that(
            ".reports/**\n"
            not in upload
            .replace("junit.xml", "")
            .replace("coverage.xml", "")
            .replace("coverage.json", ""),
            eq=True,
        )

    def test_ci_dump_excludes_raw_pytest_logs(self) -> None:
        text = _CI.read_text(encoding="utf-8")
        dump = text.split("Dump reports on failure", 1)[1].split(
            "Upload reports on failure", 1
        )[0]
        tm.that(dump, lacks="pytest.log")
        tm.that(dump, has="junit.xml")
        tm.that(dump, has="coverage.xml")

    def test_docs_workflow_uses_public_cli_not_removed_make_verb(self) -> None:
        text = _DOCS.read_text(encoding="utf-8")
        tm.that(text, lacks="DOCS_PHASE=")
        tm.that(text, lacks="make docs")
        tm.that(text, has="python -m flext_infra docs audit")
        tm.that(text, has="python -m flext_infra docs generate")
        tm.that(text, has="python -m flext_infra docs validate")
        tm.that(text, has="python -m flext_infra docs build")

    def test_docs_pages_environment_avoids_static_schema_enum(self) -> None:
        text = _DOCS.read_text(encoding="utf-8")
        tm.that(text, has="name: {% raw %}${{ 'github-pages' }}{% endraw %}")
        tm.that(text, lacks="      name: github-pages")

    def test_docs_upload_excludes_raw_report_logs(self) -> None:
        text = _DOCS.read_text(encoding="utf-8")
        upload = text.split("Upload docs reports on failure", 1)[1].split("build:", 1)[
            0
        ]
        tm.that(upload, has="audit-summary.json")
        tm.that(upload, has="validate-summary.json")
        tm.that(upload, lacks="path: .reports/")
        tm.that(upload, lacks=".reports/workspace/docs/")
        tm.that(upload, lacks="pytest.log")
