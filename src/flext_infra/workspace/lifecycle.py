"""Serial lifecycle validation through each governed repository's public Make verbs.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra import c, m, p, r, u
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector


class FlextInfraWorkspaceLifecycle:
    """Validate declared topology without Git publication or private Make handlers."""

    @staticmethod
    def execute_request(
        request: p.Infra.WorkspaceEnvironmentRequest,
    ) -> p.Result[m.Infra.LifecycleReport]:
        """Run the fixed lifecycle serially, retaining first-failure evidence.

        Returns:
            The typed receipt on success, otherwise the first causal failure.
        """
        root = request.repository_root.expanduser().resolve()
        loaded = FlextInfraWorkspaceDetector.load_workspace_spec(root)
        if loaded.failure:
            return r[m.Infra.LifecycleReport].from_failure(loaded)
        workspace = loaded.value
        if workspace.repository.role != c.Infra.MakeProfile.WORKSPACE:
            return r[m.Infra.LifecycleReport].fail(
                f"validate-lifecycle requires a workspace root: {root}",
            )
        scope = (root, *(root / member.path for member in workspace.subprojects))
        commands = tuple(
            (cwd, (c.Infra.MAKE, verb))
            for cwd in scope
            for verb in c.Infra.LIFECYCLE_VERBS
        )
        output_dir = root / c.Infra.LIFECYCLE_REPORT_RELATIVE_PATH.with_suffix("")
        receipts = [
            m.Infra.LifecycleReceipt(
                command=command,
                cwd=cwd,
                output_file=output_dir / f"{index:04d}-{command[-1]}.log",
            )
            for index, (cwd, command) in enumerate(commands)
        ]
        report = m.Infra.LifecycleReport(
            workspace_root=root,
            scope=scope,
            receipts=tuple(receipts),
        )
        published = u.Infra.publish_refactor_report_evidence(
            root,
            report,
            relative_path=c.Infra.LIFECYCLE_REPORT_RELATIVE_PATH,
        )
        if published.failure:
            return r[m.Infra.LifecycleReport].from_failure(published)
        for index, receipt in enumerate(receipts):
            u.Cli.info(
                f"[validate-lifecycle] {receipt.cwd}: {' '.join(receipt.command)}",
            )
            run = u.Cli.run_to_file(
                receipt.command,
                receipt.output_file,
                cwd=receipt.cwd,
                options=m.Cli.ProcessOptions(
                    remove_env_keys=c.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS,
                    live=True,
                ),
            )
            exit_code = None if run.failure else run.value.raw_return_code
            error = run.error if run.failure else None
            if not run.failure and not u.Cli.process_succeeded(run.value):
                error = (
                    f"failed ({exit_code}): {' '.join(receipt.command)} "
                    f"in {receipt.cwd}; timed_out={run.value.timed_out}, "
                    f"forwarded_signal={run.value.forwarded_signal}; "
                    f"output={receipt.output_file}"
                )
            receipts[index] = m.Infra.LifecycleReceipt(
                command=receipt.command,
                cwd=receipt.cwd,
                output_file=receipt.output_file,
                exit_code=exit_code,
                error=error,
            )
            report = m.Infra.LifecycleReport(
                workspace_root=root,
                scope=scope,
                receipts=tuple(receipts),
            )
            published = u.Infra.publish_refactor_report_evidence(
                root,
                report,
                relative_path=c.Infra.LIFECYCLE_REPORT_RELATIVE_PATH,
            )
            if published.failure:
                return r[m.Infra.LifecycleReport].fail(
                    f"{error + '; ' if error else ''}receipt publication failed: "
                    f"{published.error}",
                )
            if error is not None:
                return (
                    r[m.Infra.LifecycleReport].from_failure(run)
                    if run.failure
                    else r[m.Infra.LifecycleReport].fail(error)
                )
        return r[m.Infra.LifecycleReport].ok(report)


__all__: list[str] = ["FlextInfraWorkspaceLifecycle"]
