"""Publication lane behavior: what a step produces reaches one pull request.

The lane is the canonical owner release and member propagation share: from a
clean integration checkout, ``u.Infra.git_publish_lane`` enters the lane,
runs the producing step, commits exactly the paths it produced, pushes the
lane and opens or refreshes its pull request.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING

from flext_tests import tm

from flext_core import r
from tests import TestsFlextInfraUtilities as u, c, m, p, t

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path


class TestsFlextInfraReleasePublicationLane:
    """Behavior contract for the shared publication lane."""

    LANE = "lane/propagation"
    SUBJECT = "chore(deps): propagate the integrated infrastructure"

    @contextmanager
    def _lane(
        self, tmp_path: Path
    ) -> Generator[t.Triple[Path, m.Infra.GitLaneRequest, Path]]:
        """Yield a clean integration checkout, its lane request and the ``gh`` log."""
        repo = u.Tests.git_repository(tmp_path)
        base = u.Tests.checkout_integration(repo)
        u.Tests.configure_local_origin(repo, tmp_path / "remote")
        body = tmp_path / "body.md"
        body.write_text("# Propagation\n", encoding="utf-8")
        gh_log = u.Tests.cli_shim(tmp_path / "bin", c.Infra.GH)
        shim_path = f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}"
        request = m.Infra.GitLaneRequest(
            repo_root=repo,
            branch=self.LANE,
            base=base,
            subject=self.SUBJECT,
            body_file=body,
        )
        with u.Tests.env_vars_context(env_vars={"PATH": shim_path}):
            yield repo, request, gh_log

    @staticmethod
    def _produce(
        repo: Path, content: str = "produced\n"
    ) -> Callable[[], p.Result[bool]]:
        """Return a producing step that writes one file."""
        return lambda: u.Cli.files_write_text(repo / "produced.txt", content)

    def _published(self, tmp_path: Path) -> str:
        """Return the lane branch the bare origin carries, or an empty string."""
        return u.Tests.git_capture(
            tmp_path / "remote" / "origin.git", "branch", "--list", self.LANE
        ).strip()

    def test_produced_paths_reach_the_pull_request(self, tmp_path: Path) -> None:
        """Exactly the produced path is committed, pushed and proposed."""
        with self._lane(tmp_path) as (repo, request, gh_log):
            tm.ok(u.Infra.git_publish_lane(request, self._produce(repo)))

            tm.that(
                u.Tests.git_capture(repo, "branch", "--show-current").strip(),
                eq=self.LANE,
            )
            tm.that(
                u.Tests.git_capture(repo, "log", "-1", "--format=%s").strip(),
                eq=self.SUBJECT,
            )
            tm.that(
                u.Tests.git_capture(
                    repo, "show", "--name-only", "--format=", "HEAD"
                ).split(),
                eq=["produced.txt"],
            )
            tm.that(self._published(tmp_path), eq=self.LANE)
            recorded = gh_log.read_text(encoding="utf-8")
            tm.that(recorded, has=f"pr create --base {request.base} --head {self.LANE}")
            tm.that(recorded, has=f"--title {self.SUBJECT}")
            tm.that(recorded, has=f"--body-file {request.body_file}")

    def test_rerun_continues_the_lane_without_a_second_commit(
        self, tmp_path: Path
    ) -> None:
        """Reproducing identical bytes on the open lane commits nothing."""
        with self._lane(tmp_path) as (repo, request, _):
            tm.ok(u.Infra.git_publish_lane(request, self._produce(repo)))
            tm.that(u.Tests.git_run(repo, "switch", request.base), eq=True)

            tm.ok(u.Infra.git_publish_lane(request, self._produce(repo)))

            count = u.Tests.git_capture(
                repo, "rev-list", "--count", f"{request.base}..{self.LANE}"
            )
            tm.that(count.strip(), eq="1")

    def test_dirty_checkout_is_refused(self, tmp_path: Path) -> None:
        """A lane never absorbs changes it did not produce."""
        with self._lane(tmp_path) as (repo, request, gh_log):
            (repo / "stray.txt").write_text("wip\n", encoding="utf-8")

            tm.fail(u.Infra.git_publish_lane(request, self._produce(repo)))
            tm.that(u.Tests.git_ref_exists(repo, f"refs/heads/{self.LANE}"), eq=False)
            tm.that(gh_log.exists(), eq=False)

    def test_checkout_off_its_base_is_refused(self, tmp_path: Path) -> None:
        """A lane starts only from the branch its pull request targets."""
        with self._lane(tmp_path) as (repo, request, _):
            tm.that(u.Tests.git_run(repo, "switch", "--create", "elsewhere"), eq=True)

            result = u.Infra.git_publish_lane(request, self._produce(repo))

            tm.fail(result)
            tm.that(result.error or "", has=f"starts from {request.base}")

    def test_failed_production_publishes_nothing(self, tmp_path: Path) -> None:
        """The first failure of the producing step ends the lane unpushed."""
        with self._lane(tmp_path) as (_repo, request, gh_log):
            result = u.Infra.git_publish_lane(
                request, lambda: r[bool].fail("production failed")
            )

            tm.fail(result)
            tm.that(self._published(tmp_path), eq="")
            tm.that(gh_log.exists(), eq=False)
