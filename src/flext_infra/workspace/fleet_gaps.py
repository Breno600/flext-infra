"""Fleet gaps: one typed hygiene row per declared repository.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import override

from flext_infra import c, config, m, p, r, t, u
from flext_infra.base import s
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector


class FlextInfraWorkspaceFleetGaps(s[m.Infra.FleetGapsReport]):
    """Report every declared repository's hygiene gaps from that repo's own facts.

    Each row observes only what the checkout itself publishes: its porcelain
    status, its open pull requests (an unreachable provider degrades to an
    empty list), its unmerged-vs-integration branch count, the violation
    counts explicitly selected check invocations carry, and the presence of the fleet's
    standards files. The command is read-only over every probed repository
    and writes exactly one receipt under the invoking workspace root.
    """

    quality_receipts: str | None = m.Field(
        default=None,
        description=(
            "Comma-separated explicit check SARIF paths; relative to repository-root. "
            "Omitted gates are unknown; duplicate repo/gate selections fail."
        ),
    )

    @override
    def execute(self) -> p.Result[m.Infra.FleetGapsReport]:
        """Probe every declared member and external consumer, then publish.

        Returns:
            The resulting ``p.Result[m.Infra.FleetGapsReport]``.

        """
        root = self.repository_root
        loaded = FlextInfraWorkspaceDetector.load_workspace_spec(root)
        if loaded.failure:
            return r[m.Infra.FleetGapsReport].from_failure(loaded)
        workspace = loaded.value
        quality = self._quality_findings(root, workspace)
        if quality.failure:
            return r[m.Infra.FleetGapsReport].from_failure(quality)
        rows: list[m.Infra.FleetRepoGaps] = [
            self._member_row(root, workspace, member, quality.value)
            for member in workspace.subprojects
        ]
        rows.extend(
            self._external_consumer_row(consumer, quality.value)
            for consumer in workspace.external_consumers
        )
        report = m.Infra.FleetGapsReport(
            schema_version=c.Infra.FLEET_GAPS_REPORT_SCHEMA_VERSION,
            workspace_root=root.resolve(),
            workspace_name=workspace.name,
            repos=tuple(rows),
        )
        published = u.Infra.publish_refactor_report_evidence(
            root,
            report,
            relative_path=c.Infra.FLEET_GAPS_REPORT_RELATIVE_PATH,
        )
        if published.failure:
            return r[m.Infra.FleetGapsReport].from_failure(published)
        return r[m.Infra.FleetGapsReport].ok(report)

    def _member_row(
        self,
        root: Path,
        workspace: m.Infra.WorkspaceSpec,
        member: m.Infra.RepositoryRef,
        quality: t.MappingKV[tuple[Path, str], int],
    ) -> m.Infra.FleetRepoGaps:
        """Probe one declared member at its composed path.

        Returns:
            The resulting ``m.Infra.FleetRepoGaps``.

        """
        member_root = root / member.path
        return self._repo_row(
            member_root,
            name=member.name,
            quality=quality,
            declared=workspace.integration.branch
            if workspace.integration is not None
            else None,
        )

    def _external_consumer_row(
        self,
        consumer: m.Infra.ExternalConsumerSpec,
        quality: t.MappingKV[tuple[Path, str], int],
    ) -> m.Infra.FleetRepoGaps:
        """Probe one declared external consumer at its absolute root.

        Returns:
            The resulting ``m.Infra.FleetRepoGaps``.

        """
        return self._repo_row(
            consumer.root,
            name=consumer.name,
            quality=quality,
            declared=consumer.integration_branch,
        )

    def _repo_row(
        self,
        repo_root: Path,
        *,
        name: str,
        declared: str | None,
        quality: t.MappingKV[tuple[Path, str], int],
    ) -> m.Infra.FleetRepoGaps:
        """Assemble one row from the checkout's own Git, provider, and report facts.

        A missing checkout retains its presence fact. Unselected or unexecuted
        quality gates remain unknown, independently of the other hygiene probes.

        Returns:
            The resulting ``m.Infra.FleetRepoGaps``.

        """
        present = repo_root.is_dir()
        stamp = self._skills_stamp_payload(repo_root)
        return m.Infra.FleetRepoGaps(
            name=name,
            root=repo_root,
            present=present,
            dirty_paths=self._dirty_paths(repo_root) if present else (),
            open_pull_requests=self._open_pull_requests(repo_root) if present else (),
            unmerged_branches=(
                self._unmerged_branches(repo_root, declared=declared) if present else 0
            ),
            lint_findings=quality.get((repo_root.resolve(), c.Infra.LINT)),
            pyrefly_findings=quality.get((repo_root.resolve(), c.Infra.PYREFLY)),
            codemod_findings=self._codemod_findings(repo_root),
            agents_doc_present=(repo_root / c.Infra.AGENTS_DOC_FILENAME).is_file(),
            skills_stamp_present=stamp is not None,
            skills_stamp_distribution_version=(self._stamp_distribution_version(stamp)),
            beads_config_present=(
                (repo_root / c.Infra.BEADS_RUNTIME_CONFIG_RELPATH).is_file()
            ),
        )

    @staticmethod
    def _dirty_paths(repo_root: Path) -> t.StrSequence:
        """Return the checkout's porcelain status paths.

        Returns:
            The resulting ``t.StrSequence``.

        """
        status = u.Infra.git_status(m.Infra.GitStatusRequest(repo_root=repo_root))
        if status.failure:
            return ()
        return tuple(
            line[c.Infra.GIT_PORCELAIN_PATH_OFFSET :].split("-> ", 1)[-1].strip()
            for line in status.value.porcelain.splitlines()
            if line.strip()
        )

    @staticmethod
    def _open_pull_requests(
        repo_root: Path,
    ) -> t.VariadicTuple[m.Infra.FleetPullRequest]:
        """List the checkout's open pull requests; a provider failure is empty.

        Returns:
            The resulting ``t.VariadicTuple[m.Infra.FleetPullRequest]``.

        """
        run = u.Cli.run_raw(
            (
                c.Infra.GH,
                "pr",
                "list",
                "--state",
                "open",
                "--json",
                "number,headRefName,title,url",
            ),
            cwd=repo_root,
            timeout=c.Infra.TIMEOUT_SHORT,
        )
        if run.failure or run.value.outcome.raw_return_code != 0:
            return ()
        parsed = u.Cli.json_parse(run.value.stdout)
        if parsed.failure or not isinstance(parsed.value, list):
            return ()
        pull_requests: list[m.Infra.FleetPullRequest] = []
        for item in parsed.value:
            validated = u.validate_value(m.Infra.FleetPullRequest, item)
            if validated.failure:
                return ()
            pull_requests.append(validated.value)
        return tuple(pull_requests)

    @classmethod
    def _unmerged_branches(
        cls,
        repo_root: Path,
        *,
        declared: str | None,
    ) -> int:
        """Count local branches the integration line does not contain.

        Returns:
            The resulting ``int``.

        """
        base = u.Infra.resolve_integration_branch(
            repo_root,
            preference=(
                config.Infra.codegen.branch_policy.integration_branch_preference
            ),
            declared=declared,
        )
        if base.failure:
            return 0
        listed = u.Cli.run_raw(
            (c.Infra.GIT, "branch", "--no-merged", base.value),
            cwd=repo_root,
            timeout=c.Infra.TIMEOUT_SHORT,
        )
        if listed.failure or listed.value.outcome.raw_return_code != 0:
            return 0
        return sum(1 for line in listed.value.stdout.splitlines() if line.strip())

    @staticmethod
    def _stamp_distribution_version(stamp: t.JsonMapping | None) -> str:
        """Read the skills stamp's declared distribution version.

        Returns:
            The resulting ``str``.

        """
        if stamp is None:
            return ""
        version = stamp.get(c.Infra.SKILLS_STAMP_DISTRIBUTION_VERSION_KEY)
        return version if isinstance(version, str) else ""

    @staticmethod
    def _skills_stamp_payload(repo_root: Path) -> t.JsonMapping | None:
        """Parse the checkout's skills stamp when it exists.

        Returns:
            The resulting ``t.JsonMapping | None``.

        """
        stamp_path = repo_root / c.Infra.SKILLS_STAMP_RELPATH
        if not stamp_path.is_file():
            return None
        parsed = u.Cli.json_parse(
            stamp_path.read_text(encoding=c.Cli.ENCODING_DEFAULT),
        )
        if parsed.failure or not isinstance(parsed.value, dict):
            return None
        return t.Cli.JSON_MAPPING_ADAPTER.validate_python(parsed.value)

    def _quality_findings(
        self,
        root: Path,
        workspace: m.Infra.WorkspaceSpec,
    ) -> p.Result[t.MappingKV[tuple[Path, str], int]]:
        """Read only explicit native SARIF receipts, before unrelated probes.

        A full-project completed lint/Pyrefly execution owns its count. Missing
        gates and file-scoped invocations are unknown. Invalid selected evidence,
        unrelated projects, tool errors and duplicate repo/gate selections fail.

        Returns:
            Counts keyed by canonical checkout root and executed quality gate.
        """
        result = r[t.MappingKV[tuple[Path, str], int]]
        counts: dict[tuple[Path, str], int] = {}
        if self.quality_receipts is None:
            return result.ok(counts)
        roots = frozenset(
            {(root / member.path).resolve() for member in workspace.subprojects}
            | {consumer.root.resolve() for consumer in workspace.external_consumers},
        )
        for selected in self.quality_receipts.split(","):
            if not selected.strip():
                return result.fail(
                    "quality-receipts requires nonempty explicit SARIF paths"
                )
            path = (root / selected.strip()).resolve()
            summary = self._quality_receipt(path, roots)
            if summary.failure:
                return result.from_failure(summary)
            counted = self._receipt_counts(path, summary.value, roots, counts)
            if counted.failure:
                return result.from_failure(counted)
        return result.ok(counts)

    @staticmethod
    def _quality_receipt(
        path: Path,
        roots: frozenset[Path],
    ) -> p.Result[m.Infra.CheckReportSummary]:
        """Load one selected native receipt and prove its invocation facts.

        Returns:
            The typed invocation summary, or the first violated receipt fact.
        """
        result = r[m.Infra.CheckReportSummary]
        try:
            report = m.Infra.SarifReport.model_validate_json(path.read_bytes())
        except (OSError, ValueError) as exc:
            return result.fail(f"Invalid quality receipt {path}: {exc}", exception=exc)
        summary = report.properties
        if (
            summary is None
            or len(report.runs) != 1
            or (report.runs[0].tool_name != "flext-infra-check")
        ):
            return result.fail(f"Quality receipt lacks native invocation facts: {path}")
        if len(report.runs[0].results) != sum(
            project.total_findings for project in summary.results
        ):
            return result.fail(
                f"Quality receipt findings disagree with executions: {path}"
            )
        targets = {target.name: target.path for target in summary.targets}
        if (
            not targets
            or len(targets) != len(summary.targets)
            or any(
                not target.is_absolute() or target.resolve() not in roots
                for target in targets.values()
            )
        ):
            return result.fail(
                f"Unbound or duplicate project targets in quality receipt: {path}"
            )
        return result.ok(summary)

    @classmethod
    def _receipt_counts(
        cls,
        path: Path,
        summary: m.Infra.CheckReportSummary,
        roots: frozenset[Path],
        counts: dict[tuple[Path, str], int],
    ) -> p.Result[bool]:
        """Add one receipt's full-project lint/Pyrefly counts, refusing ambiguity.

        Returns:
            True once every executed quality gate of the receipt is counted.
        """
        result = r[bool]
        targets = {target.name: target.path for target in summary.targets}
        seen: set[str] = set()
        for project in summary.results:
            project_root = targets.get(project.project)
            if (
                project_root is None
                or project_root.resolve() not in roots
                or project.project in seen
            ):
                return result.fail(
                    f"Unbound or duplicate quality project {project.project}: {path}"
                )
            seen.add(project.project)
            for gate in (c.Infra.LINT, c.Infra.PYREFLY):
                execution = project.gates.get(gate)
                if execution is None:
                    continue
                if not cls._execution_proven(gate, project.project, execution, path):
                    return result.fail(
                        f"Invalid quality execution {project.project}/{gate}: {path}"
                    )
                if summary.selected_files:
                    continue
                key = (project_root.resolve(), gate)
                if key in counts:
                    return result.fail(
                        f"Ambiguous quality receipts for {project_root}/{gate}"
                    )
                counts[key] = execution.finding_count
        return result.ok(value=True)

    @staticmethod
    def _execution_proven(
        gate: str,
        project: str,
        execution: m.Infra.GateExecution,
        path: Path,
    ) -> bool:
        """Whether one gate execution is a completed native run of this receipt.

        Returns:
            True only when verdict, outcome, issues and raw receipt agree.
        """
        outcome = execution.outcome
        receipt = execution.raw_receipt
        facts = (
            execution.result.gate == gate,
            outcome != c.Infra.ToolOutcome.ERROR,
            execution.result.project == project,
            execution.result.passed or bool(execution.issues),
            outcome != c.Infra.ToolOutcome.CLEAN
            or (not execution.issues and execution.result.passed),
            outcome != c.Infra.ToolOutcome.FINDINGS or bool(execution.issues),
            receipt is not None
            and receipt.is_file()
            and receipt.resolve().is_relative_to(path.parent),
        )
        return all(facts)

    @staticmethod
    def _codemod_findings(repo_root: Path) -> int:
        """Read the checkout's mod evidence findings total; absent is zero.

        Returns:
            The resulting ``int``.

        """
        report_path = repo_root / c.Infra.MOD_SCAN_REPORT_RELATIVE_PATH
        if not report_path.is_file():
            return 0
        parsed = u.Cli.json_parse(
            report_path.read_text(encoding=c.Cli.ENCODING_DEFAULT),
        )
        if parsed.failure or not isinstance(parsed.value, dict):
            return 0
        findings = parsed.value.get("findings")
        return findings if isinstance(findings, int) else 0


__all__: list[str] = ["FlextInfraWorkspaceFleetGaps"]
