"""Work-in-progress merge law: a WIP head never merges into integration.

The runtime surface is the generated CI ``merge-guard`` job, owned by
config/codegen.yaml (``Infra.codegen.make.work_in_progress``). A GitHub Draft
selects no job at all; a non-draft PR whose head commit subject matches a WIP
pattern fails the guard when it targets a protected integration branch.

These tests execute the committed CI projection's guard script against real Git
heads and read every expectation from the typed config values
(generator/consumer round-trip), never from hardcoded config copies.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import re
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from flext_tests import tm

from flext_infra import config, p
from tests import u

_TEMPLATES = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "flext_infra"
    / "templates"
    / "project"
    / "base"
)
_CI_TEMPLATE = _TEMPLATES / ".github" / "workflows" / "ci.yml.j2"
_RENDERED_CI = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"
_WIP = config.Infra.codegen.make.work_in_progress


class TestsWorkInProgressGates:
    """Prove the WIP merge predicate end to end on the rendered artifact."""

    @staticmethod
    @contextmanager
    def _base_ref(value: str) -> Generator[None]:
        """Export the pull request base the guard reads, restoring the caller's."""
        saved = os.environ.get("BASE_REF")
        os.environ["BASE_REF"] = value
        try:
            yield
        finally:
            u.Tests.restore_env("BASE_REF", saved)

    @staticmethod
    def _merge_guard_script() -> str:
        """Extract the rendered merge-guard run script from the repo projection.

        Returns:
            The resulting ``str``.

        """
        section = _RENDERED_CI.read_text(encoding="utf-8").split("merge-guard:", 1)[1]
        body = section.split("run: |", 1)[1].split("# End SECTION: merge-guard job")[0]
        return "".join(line[10:] + "\n" for line in body.splitlines() if line.strip())

    @classmethod
    def _guard(cls, root: Path, subject: str, base: str) -> p.Result[str]:
        """Run the committed guard against one real head commit subject.

        Returns:
            The resulting ``p.Result[str]``.

        """
        u.Tests.git_bootstrap(root, ("commit", "--allow-empty", "-m", subject))
        with cls._base_ref(base):
            return u.Cli.capture(
                ["bash", "-c", cls._merge_guard_script()],
                cwd=root,
                timeout=120,
            )

    @staticmethod
    def test_template_binds_the_config_owned_predicate() -> None:
        """The CI template reads make.work_in_progress, never a literal copy."""
        ci = _CI_TEMPLATE.read_text(encoding="utf-8")
        tm.that(
            ci,
            has=[
                "merge-guard:",
                "make.work_in_progress.merge_lock_target_branches",
                "make.work_in_progress.head_subject_patterns",
                "github.event.pull_request.draft == false",
            ],
        )
        tm.that(ci, lacks="|".join(_WIP.merge_lock_target_branches))

    def test_rendered_merge_guard_round_trips_config(self) -> None:
        """The committed CI projection mirrors the typed branch and subject sets."""
        script = self._merge_guard_script()
        tm.that(
            script,
            has=[
                "|".join(_WIP.merge_lock_target_branches) + ")",
                "|".join(_WIP.head_subject_patterns),
            ],
        )

    def test_rendered_merge_guard_decision_matrix(self, tmp_path: Path) -> None:
        """WIP heads are blocked on protected bases; clean or unprotected pass."""
        u.Tests.initialize_git_repo(tmp_path)
        protected = _WIP.merge_lock_target_branches[0]
        wip_subject = "[WIP] preserve lane"
        tm.that(
            any(
                re.search(pattern, wip_subject, re.IGNORECASE)
                for pattern in _WIP.head_subject_patterns
            ),
            eq=True,
        )
        tm.fail(self._guard(tmp_path, wip_subject, protected))
        tm.ok(self._guard(tmp_path, wip_subject, "feature/unprotected"))
        tm.ok(self._guard(tmp_path, "fix(check): land the lane", protected))
