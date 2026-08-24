"""Public github service tests using real workspaces."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from flext_infra import c, config
from flext_tests import tm
from tests import m, u


class TestsInfraGithub:
    """Verify GitHub automation through the public infrastructure facade."""

    def test_sync_reports_create_operations(self, tmp_path: Path) -> None:
        """Report one create operation for every discovered project."""
        workspace = u.Tests.create_github_workspace(
            tmp_path, project_names=("flext-a", "flext-b")
        )

        result = u.Infra.sync_github_workflows(
            m.Infra.GithubWorkflowSyncRequest(workspace=str(workspace))
        )

        tm.ok(result)
        report = result.unwrap()
        tm.that(report.mode, eq="dry-run")
        tm.that(report.summary, eq={"create": 2})
        tm.that(
            [operation.project for operation in report.operations],
            eq=["flext-a", "flext-b"],
        )

    def test_sync_apply_writes_ci_files_and_report(self, tmp_path: Path) -> None:
        """Write the adapted workflow and the requested structured report."""
        workspace = u.Tests.create_github_workspace(
            tmp_path,
            project_names=("flext-a", "flext-b"),
            source_workflow=(
                "name: CI\n"
                "jobs:\n"
                "  ci:\n"
                "    steps:\n"
                "      - name: Boot (blocking)\n"
                "        run: make boot\n"
                "      - name: Val (advisory)\n"
                "        run: make val\n"
            ),
        )
        report_path = tmp_path / "sync-report.json"

        result = u.Infra.sync_github_workflows(
            m.Infra.GithubWorkflowSyncRequest(
                workspace=str(workspace), apply=True, report=str(report_path)
            )
        )

        tm.ok(result)
        tm.that(report_path.is_file(), eq=True)
        for project_name in ("flext-a", "flext-b"):
            destination = workspace / project_name / ".github/workflows/ci.yml"
            content = destination.read_text(encoding="utf-8")
            tm.that(destination.is_file(), eq=True)
            tm.that(content, has="name: CI")
            tm.that(content, has="- name: Setup (blocking)")
            tm.that(content, has="run: make setup")
            tm.that(content, has="run: make val")
            tm.that(content, lacks="run: make boot")

    def test_sync_prunes_noncanonical_files(self, tmp_path: Path) -> None:
        """Remove noncanonical workflow files only when pruning is requested."""
        workspace = u.Tests.create_github_workspace(
            tmp_path, project_names=("flext-a",)
        )
        extra_workflow = workspace / "flext-a/.github/workflows/extra.yml"
        extra_workflow.parent.mkdir(parents=True, exist_ok=True)
        extra_workflow.write_text("name: Extra\n", encoding="utf-8")

        result = u.Infra.sync_github_workflows(
            m.Infra.GithubWorkflowSyncRequest(
                workspace=str(workspace), apply=True, prune=True
            )
        )

        tm.ok(result)
        report = result.unwrap()
        tm.that(report.summary, eq={"create": 1, "prune": 1})
        tm.that(extra_workflow.exists(), eq=False)

    def test_lint_writes_report(self, tmp_path: Path) -> None:
        """Write a lint report and expose the real actionlint availability."""
        workspace = u.Tests.create_github_workspace(
            tmp_path, project_names=("flext-a",)
        )
        report_path = tmp_path / "lint-report.json"

        result = u.Infra.lint_github_workflows(
            m.Infra.GithubWorkflowLintRequest(
                workspace=str(workspace), report=str(report_path), strict=True
            )
        )

        tm.ok(result)
        outcome = result.unwrap()
        tm.that(report_path.is_file(), eq=True)
        if shutil.which("actionlint") is None:
            tm.that(outcome.status, eq="skipped")
        else:
            tm.that(outcome.status, eq="ok")

    def test_pull_request_fails_for_minimal_repo(self, tmp_path: Path) -> None:
        """Run native gh and return a typed failure for a non-repository."""
        workspace = u.Tests.create_github_workspace(
            tmp_path, project_names=("flext-a",)
        )

        result = u.Infra.run_github_pull_request(
            m.Infra.GithubPullRequestRequest(
                repo_root=str(workspace / "flext-a"),
                action=c.Infra.PullRequestAction.STATUS,
            )
        )

        tm.fail(result)
        tm.that((result.error or ""), has="PR operation exited with code")
        log_path = workspace / "flext-a/.reports/workspace/pr/flext-a.log"
        tm.that(log_path.is_file(), eq=True)
        tm.that(log_path.read_text(encoding="utf-8"), lacks="No module named")

    def test_pull_request_create_requires_noninteractive_content(
        self, tmp_path: Path
    ) -> None:
        """Reject create before transport when title or body is absent."""
        workspace = u.Tests.create_github_workspace(
            tmp_path, project_names=("flext-a",)
        )

        result = u.Infra.run_github_pull_request(
            m.Infra.GithubPullRequestRequest(
                repo_root=str(workspace / "flext-a"),
                action=c.Infra.PullRequestAction.CREATE,
                head="feature/arbitrary",
            )
        )

        tm.fail(result)
        tm.that((result.error or ""), has="title is required")

    def test_every_workflow_make_verb_exists_in_the_codegen_ssot(self) -> None:
        """Reject any CI workflow verb absent from the canonical verb SSOT.

        ``config/codegen.yaml`` declares the only public Make verbs a generated
        Makefile exposes. A workflow that invokes anything else can never run:
        the workspace CI historically called ``make boot`` and ``make val``,
        neither of which the SSOT declares, so the first blocking step failed
        with "No rule to make target". Comparing against the SSOT (instead of
        hardcoding verb names) keeps this test correct when the SSOT changes.
        """
        declared = {verb.name for verb in config.Infra.codegen.make.verbs}
        repository_root = Path(__file__).resolve().parents[3]
        workflows = sorted((repository_root / ".github/workflows").glob("*.yml"))
        invoked: dict[str, set[str]] = {}
        for workflow in workflows:
            if not workflow.is_file():
                continue
            verbs = {
                match.group(1)
                for match in re.finditer(
                    r"run:\s*make\s+([a-z][a-z0-9-]*)", workflow.read_text("utf-8")
                )
            }
            undeclared = verbs - declared
            if undeclared:
                invoked[str(workflow.relative_to(repository_root))] = undeclared

        tm.that(invoked, eq={})
