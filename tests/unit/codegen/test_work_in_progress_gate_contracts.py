"""P0 work-in-progress law (mro-g3zl2): WIP/draft skips pre-push gates and blocks merges.

The law has two runtime surfaces, both owned by config/codegen.yaml
(``Infra.codegen.make.work_in_progress``):

* the generated pre-commit pre-push entries skip every gate when the branch
  matches a WIP pattern or the PR is a GitHub draft;
* the generated CI ``merge-guard`` job fails any PR merging a WIP/draft source
  into a protected integration branch.

These tests render the SSOT templates through the public owner and execute the
rendered shell decisions against the typed config values (generator/consumer
round-trip), never against hardcoded config copies.

Two-type standard (operator ruling 2026-08-16, restored): workspace vs
standalone, where the ONLY differentiator is .gitmodules existence. Hook
contexts are self-scope: a workspace (has .gitmodules) never propagates hook
gates to subprojects — member hooks and push CI own member gates; a
standalone runs the full local gate suite.
"""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from flext_infra import config, m, u
from flext_tests import tm

if TYPE_CHECKING:
    from flext_infra import p

_TEMPLATES = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "flext_infra"
    / "templates"
    / "project"
    / "base"
)
_PRECOMMIT = _TEMPLATES / ".pre-commit-config.yaml.j2"
_CI_TEMPLATE = _TEMPLATES / ".github" / "workflows" / "ci.yml.j2"
_RENDERED_CI = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"
_WIP = config.Infra.codegen.make.work_in_progress


@contextmanager
def _env(**overrides: str) -> Generator[None]:
    """Temporarily export environment values for one command decision."""
    saved = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _render_precommit() -> str:
    """Render the hook artifact through the public owner with the typed SSOT."""
    return tm.ok(
        u.Cli.template_render(
            _PRECOMMIT,
            m.Infra.MakeWorkflowRenderSpec(
                dist="flext-demo", make=config.Infra.codegen.make
            ),
        )
    )


def _hook_shell(rendered: str, stage: str) -> str:
    """Return the inner shell of the first hook entry for one stage."""
    for block in rendered.split("  - id:"):
        if f"stages: [{stage}]" not in block:
            continue
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith("bash -eu -o pipefail -c '") and stripped.endswith(
                "'"
            ):
                return stripped.removeprefix("bash -eu -o pipefail -c '").removesuffix(
                    "'"
                )
    err = f"no {stage} shell entry in rendered hook config"
    raise AssertionError(err)


def _pre_commit_shell(rendered: str) -> str:
    """Return the inner shell of the first pre-commit hook entry."""
    return _hook_shell(rendered, "pre-commit")


def _pre_push_shell(rendered: str) -> str:
    """Return the inner shell of the first pre-push hook entry."""
    return _hook_shell(rendered, "pre-push")


def _git_repo(root: Path, branch: str, *, workspace: bool = False) -> None:
    """Create a throwaway repository checked out on one branch."""
    tm.ok(u.Cli.capture(["git", "init", "-q"], cwd=root, timeout=60))
    tm.ok(u.Cli.capture(["git", "checkout", "-q", "-b", branch], cwd=root, timeout=60))
    if workspace:
        (root / ".gitmodules").write_text(
            '[submodule "member"]\n\tpath = member\n\turl = https://example.com/member.git\n',
            encoding="utf-8",
        )


def _gh_stub(bin_dir: Path, *, broken: bool = False) -> None:
    """Provide a deterministic gh answer so PR draft state is input, not network."""
    stub = bin_dir / "gh"
    body = (
        "#!/bin/sh\nexit 1\n"
        if broken
        else ('#!/bin/sh\necho "${FLEXT_TEST_GH_DRAFT:-false}"\n')
    )
    stub.write_text(body, encoding="utf-8")
    stub.chmod(0o755)


def _bare_path(bin_dir: Path) -> None:
    """Expose only bash/git/gh stubs so gh can be genuinely unresolvable."""
    for tool in ("bash", "git"):
        target = shutil.which(tool)
        if target is not None:
            (bin_dir / tool).symlink_to(target)


def _merge_guard_script() -> str:
    """Extract the rendered merge-guard run script from the repo projection."""
    section = _RENDERED_CI.read_text(encoding="utf-8").split("merge-guard:", 1)[1]
    body = section.split("run: |", 1)[1].split("# End SECTION: merge-guard job", 1)[0]
    return "".join(line[10:] + "\n" for line in body.splitlines() if line.strip())


def _run(script: str, cwd: Path) -> p.Result[str]:
    return u.Cli.capture(["bash", "-c", script], cwd=cwd, timeout=120)


class TestsWorkInProgressGates:
    """Prove the P0 predicate end to end on the rendered artifacts."""

    def test_templates_bind_the_config_owned_predicate(self) -> None:
        """Both SSOT templates read make.work_in_progress, never hardcode it."""
        ci = _CI_TEMPLATE.read_text(encoding="utf-8")
        tm.that(ci, has="merge-guard:")
        tm.that(ci, has="make.work_in_progress.merge_lock_target_branches")
        tm.that(ci, has="make.work_in_progress.branch_patterns")
        tm.that(ci, lacks="dev|develop")
        precommit = _PRECOMMIT.read_text(encoding="utf-8")
        tm.that(precommit, has="make.work_in_progress.branch_patterns")
        tm.that(precommit, has="make.work_in_progress.draft_pr")

    def test_pre_push_skips_gates_on_wip_branch(self, tmp_path: Path) -> None:
        """A WIP-pattern branch exits before any make verb can run."""
        repo = tmp_path / "wip-repo"
        repo.mkdir()
        _git_repo(repo, "wip/demo-lane")
        tm.that(
            any(re.search(pat, "wip/demo-lane") for pat in _WIP.branch_patterns),
            eq=True,
        )
        result = _run(_pre_push_shell(_render_precommit()), repo)
        tm.ok(result)
        tm.that(result.value, has="skipping pre-push gate")

    @pytest.mark.skipif(
        not _WIP.draft_pr, reason="draft_pr disabled in config; nothing to assert"
    )
    def test_pre_push_skips_gates_on_draft_pr(self, tmp_path: Path) -> None:
        """A draft PR answer skips the gates before any make verb can run."""
        repo = tmp_path / "draft-repo"
        repo.mkdir()
        _git_repo(repo, "feature/demo-lane")
        tm.that(
            any(re.search(pat, "feature/demo-lane") for pat in _WIP.branch_patterns),
            eq=False,
        )
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        _gh_stub(bin_dir)
        with _env(
            PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            FLEXT_TEST_GH_DRAFT="true",
        ):
            result = _run(_pre_push_shell(_render_precommit()), repo)
        tm.ok(result)
        tm.that(result.value, has="skipping pre-push gate")

    def test_pre_push_runs_gates_on_clean_branch(self, tmp_path: Path) -> None:
        """A clean branch reaches the make verb; with no Makefile it must fail."""
        repo = tmp_path / "clean-repo"
        repo.mkdir()
        _git_repo(repo, "feature/clean-lane")
        tm.that(
            any(re.search(pat, "feature/clean-lane") for pat in _WIP.branch_patterns),
            eq=False,
        )
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        _gh_stub(bin_dir)
        with _env(
            PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            FLEXT_TEST_GH_DRAFT="false",
        ):
            result = _run(_pre_push_shell(_render_precommit()), repo)
        tm.fail(result)

    def test_pre_push_skips_gates_when_pr_state_unresolvable(
        self, tmp_path: Path
    ) -> None:
        """A gh failure must fail open: the push is never the blocked state."""
        repo = tmp_path / "unresolvable-repo"
        repo.mkdir()
        _git_repo(repo, "feature/demo-lane")
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        _gh_stub(bin_dir, broken=True)
        with _env(PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}"):
            result = _run(_pre_push_shell(_render_precommit()), repo)
        tm.ok(result)
        tm.that(result.value, has="fail-open")

    def test_pre_push_skips_gates_when_gh_absent(self, tmp_path: Path) -> None:
        """Without gh the PR state cannot resolve; the gate must fail open."""
        repo = tmp_path / "no-gh-repo"
        repo.mkdir()
        _git_repo(repo, "feature/demo-lane")
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        _bare_path(bin_dir)
        with _env(PATH=str(bin_dir)):
            result = _run(_pre_push_shell(_render_precommit()), repo)
        tm.ok(result)
        tm.that(result.value, has="fail-open")

    def test_workspace_type_hooks_stay_self_scoped(self, tmp_path: Path) -> None:
        """A repo with .gitmodules never fans hook gates out to members."""
        repo = tmp_path / "workspace-repo"
        repo.mkdir()
        _git_repo(repo, "feature/demo-lane", workspace=True)
        rendered = _render_precommit()
        result = _run(_pre_commit_shell(rendered), repo)
        tm.ok(result)
        tm.that(result.value, has="self-scope only")
        push = _run(_pre_push_shell(rendered), repo)
        tm.ok(push)
        tm.that(push.value, has="self-scope only")

    def test_standalone_type_hooks_run_local_gates(self, tmp_path: Path) -> None:
        """Without .gitmodules the pre-commit verb runs; no Makefile means failure."""
        repo = tmp_path / "standalone-repo"
        repo.mkdir()
        _git_repo(repo, "feature/demo-lane")
        result = _run(_pre_commit_shell(_render_precommit()), repo)
        # The verb genuinely executed (no Makefile -> make fails), proving the
        # standalone repo did not take the workspace self-scope exit.
        tm.fail(result)

    def test_rendered_merge_guard_round_trips_config(self) -> None:
        """The committed CI projection mirrors the typed branch/pattern sets."""
        script = _merge_guard_script()
        tm.that(script, has="|".join(_WIP.merge_lock_target_branches) + ")")
        for pattern in _WIP.branch_patterns:
            tm.that(script, has=f"'{pattern}'")

    def test_rendered_merge_guard_decision_matrix(self, tmp_path: Path) -> None:
        """Draft/WIP sources are blocked; clean and unprotected paths pass."""
        cwd = tmp_path
        script = _merge_guard_script()
        target = _WIP.merge_lock_target_branches[0]
        wip_head = next(
            head
            for head in ("wip/lane", "feature/WIP-lane")
            if any(re.search(pat, head) for pat in _WIP.branch_patterns)
        )
        clean_head = "feature/clean-lane"
        tm.that(
            any(re.search(pat, clean_head) for pat in _WIP.branch_patterns), eq=False
        )
        if _WIP.draft_pr:
            with _env(BASE_REF=target, HEAD_REF=clean_head, IS_DRAFT="true"):
                tm.fail(_run(script, cwd))
        with _env(BASE_REF=target, HEAD_REF=wip_head, IS_DRAFT="false"):
            tm.fail(_run(script, cwd))
        with _env(BASE_REF=target, HEAD_REF=clean_head, IS_DRAFT="false"):
            tm.ok(_run(script, cwd))
        with _env(BASE_REF="feature/unprotected", HEAD_REF=wip_head, IS_DRAFT="true"):
            tm.ok(_run(script, cwd))
