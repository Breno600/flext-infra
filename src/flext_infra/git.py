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
    """Thin Git status and cleanliness use cases over ``u.Infra.git_status``."""

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


__all__: list[str] = ["FlextInfraGitService"]
