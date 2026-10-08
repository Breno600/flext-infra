"""Public Git orchestration service for flext-infra consumers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, override

from flext_infra import m, r, u
from flext_infra.base import s

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraGitService(s[m.Infra.GitStatusReport]):
    """Thin public status, cleanliness, and lane admission use cases."""

    repository: Annotated[
        Path | None,
        m.Field(description="Repository path; defaults to repository_root"),
    ] = None

    def _repo(self) -> Path:
        """Resolve the single repository root for this invocation.

        Returns:
            The resulting ``Path``.

        """
        return (self.repository or self.repository_root).expanduser().resolve()

    @override
    def execute(self) -> p.Result[m.Infra.GitStatusReport]:
        """Capture porcelain status for the selected repository.

        Returns:
            The resulting ``p.Result[m.Infra.GitStatusReport]``.

        """
        return u.Infra.git_status(m.Infra.GitStatusRequest(repo_root=self._repo()))

    @classmethod
    def verify_clean(
        cls,
        request: m.Infra.GitStatusRequest,
    ) -> p.Result[m.Infra.GitStatusReport]:
        """Fail when the selected repository has staged, unstaged, or untracked work.

        Returns:
            The resulting ``p.Result[m.Infra.GitStatusReport]``.

        """
        report = cls(repository_root=request.repo_root).execute()
        if report.failure:
            return report
        if report.value.dirty:
            return r[m.Infra.GitStatusReport].fail(
                f"dirty repository: {report.value.repo_root}\n{report.value.porcelain}",
            )
        return report

    @staticmethod
    def verify_lane(
        request: m.Infra.GitLaneVerificationRequest,
    ) -> p.Result[m.Infra.GitOidReport]:
        """Run the shared, effect-free lane admission owner.

        Returns:
            Live integration identity or the original admission failure.

        """
        return u.Infra.git_verify_lane(request)

    @classmethod
    def verify_lanes(
        cls,
        request: m.Infra.GitStatusRequest,
    ) -> p.Result[m.Infra.GitLaneHygieneReport]:
        """Fail on stashes, merged-but-alive branches and orphan or merged worktrees.

        Returns:
            The resulting ``p.Result[m.Infra.GitLaneHygieneReport]``.

        """
        report = u.Infra.git_lane_hygiene(request)
        if report.failure or not report.value.violations:
            return report
        listing = "\n".join(
            f"{violation.kind}: {violation.ref}: {violation.detail}"
            for violation in report.value.violations
        )
        return r[m.Infra.GitLaneHygieneReport].fail(
            f"lane accumulation in {report.value.repo_root}"
            f" (integration base {report.value.integration_base}):\n{listing}",
        )


__all__: list[str] = ["FlextInfraGitService"]
